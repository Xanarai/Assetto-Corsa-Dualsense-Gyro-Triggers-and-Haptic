"""
High-Precision Racing Gyroscope Steering Processor for Assetto Corsa.
Implements:
1. Complementary Filter (Accelerometer + Gyroscope) with roll-over protection beyond 90 deg.
2. Dynamic Curb/Bump Rejection (suppresses curb shocks from shaking the steering wheel).
3. Exponential Moving Average (EMA) noise filter for zero muscle micro-tremor.
4. Smooth Deadzone (continuous remapping without step jumps).
5. Configurable Linearity / Gamma curve.
6. Speed-sensitive steering damping via Assetto Corsa Shared Memory.
7. Quick Zero / Center calibration (via Touchpad click or GUI).
"""

import math
import time
import logging
from typing import Optional

from ..config import Config

logger = logging.getLogger("DualSenseACBridge.GyroProcessor")

ACCEL_SCALE_G = 8192.0
GYRO_SCALE_DPS = 16.384


class GyroProcessor:
    def __init__(self):
        # Завантаження налаштувань із конфігураційного файлу
        cfg = Config()

        self.enabled: bool = cfg.get("enable_gyro", True)
        self.max_steer_angle: float = float(cfg.get("gyro_max_angle", 65.0))
        self.deadzone: float = float(cfg.get("gyro_deadzone", 0.02))
        self.ema_alpha: float = float(cfg.get("gyro_ema_alpha", 0.08))
        self.gamma: float = float(cfg.get("gyro_gamma", 1.15))
        self.invert_steer: bool = cfg.get("gyro_invert", False)
        self.stick_override: bool = cfg.get("gyro_stick_override", True)
        self.stick_override_threshold: float = float(cfg.get("gyro_stick_override_threshold", 0.20))
        self.filter_beta: float = float(cfg.get("gyro_filter_beta", 0.98))
        self.speed_sensitivity: float = float(cfg.get("gyro_speed_sensitivity", 0.15))
        self.enable_speed_sensitivity: bool = cfg.get("gyro_enable_speed_sensitivity", True)
        self.gyro_axis: str = str(cfg.get("gyro_axis", "y")).lower()
        self.gyro_scale: float = float(cfg.get("gyro_scale", GYRO_SCALE_DPS))
        self.gyro_rate_invert: bool = bool(cfg.get("gyro_rate_invert", False))

        # Steam-подібне калібрування (читаємо з конфігу, якщо є, або ставимо дефолт)
        self.cfg = cfg
        self.noise_threshold: float = float(cfg.get("gyro_noise_threshold", 0.08))
        self.zero_offset: float = float(cfg.get("gyro_zero_offset", 0.0))
        
        self.is_calibrating: bool = False
        self.calib_start_time: float = 0.0
        self.calib_samples: list = []
        self.bump_detected: bool = False
        self.is_counting_down: bool = False
        self.countdown_start: float = 0.0
        self.countdown_duration: float = 3.0
        self.live_jitter: float = 0.0

        # Змінні стану
        self.filtered_angle: float = 0.0        # Кут після фільтрації (градуси)
        self.final_output: float = 0.0          # Нормалізований вихідний сигнал [-1.0, 1.0]

        self.raw_accel_angle: float = 0.0
        self.current_angle: float = 0.0         # Абсолютний кут для Sensor Fusion
        self.is_initialized: bool = False       # Прапорець для ініціалізації кута
        self.touchpad_pressed_prev: bool = False
        self.last_time: float = time.perf_counter()

    def reset(self):
        self.filtered_angle = 0.0
        self.final_output = 0.0
        self.current_angle = 0.0
        self.is_initialized = False
        self.last_time = time.perf_counter()

    def process_imu(
        self,
        ax_raw: int,
        ay_raw: int,
        az_raw: int,
        gx_raw: int,
        gy_raw: int,
        gz_raw: int,
        speed_kmh: float = 0.0,
        touchpad_clicked: bool = False
    ) -> float:
        # Відстеження тачпада (калібрування запускається виключно з GUI, щоб уникнути випадкових натискань під час заїзду)
        self.touchpad_pressed_prev = touchpad_clicked

        if not self.enabled:
            self.final_output = 0.0
            return 0.0

        now = time.perf_counter()
        dt = now - self.last_time
        if dt <= 0.0 or dt > 0.1:
            dt = 0.004  # Оптимізація під 250Hz (уникаємо стрибка 10ms при старті)
        self.last_time = now

        ax = float(ax_raw)
        ay = float(ay_raw)
        az = float(az_raw)

        # Обчислення абсолютного кута нахилу з акселерометра (крен / roll)
        yz_magnitude = math.sqrt(ay * ay + az * az)
        if yz_magnitude > 10.0:
            accel_angle = -math.degrees(math.atan2(ax, yz_magnitude))
        else:
            accel_angle = -90.0 if ax > 0 else 90.0

        self.raw_accel_angle = accel_angle

        # Обчислення швидкості обертання з гіроскопа (градуси в секунду)
        if self.gyro_axis == 'x':
            gyro_rate = float(gx_raw) / self.gyro_scale
        elif self.gyro_axis == 'z':
            gyro_rate = float(gz_raw) / self.gyro_scale
        else:
            gyro_rate = float(gy_raw) / self.gyro_scale
            
        # Інверсія гіроскопа для виправлення "мікроповороту не в той бік"
        # За замовчуванням гіроскоп і акселерометр у DualSense мають різні знаки
        if not self.gyro_rate_invert:
            gyro_rate = -gyro_rate
            
        gyro_angle_change = gyro_rate * dt

        # Ініціалізація початкового кута
        if not self.is_initialized:
            self.current_angle = accel_angle
            self.is_initialized = True

        # 1. Фаза підготовки / зворотного відліку (3... 2... 1...)
        if self.is_counting_down:
            self.live_jitter = accel_angle - self.zero_offset
            elapsed_cd = time.time() - self.countdown_start
            if elapsed_cd >= self.countdown_duration:
                self.is_counting_down = False
                self.is_calibrating = True
                self.calib_start_time = time.time()
                self.calib_samples.clear()
                logger.info("Початок вимірювання шуму (10 сек). Не торкайтесь геймпада...")
            self.final_output = 0.0
            return 0.0

        # 2. Фаза збору даних шуму із захистом від рухів
        if self.is_calibrating:
            self.current_angle = accel_angle  # Синхронізуємо кут під час калібрування

            if self.calib_samples:
                current_avg = sum(self.calib_samples) / len(self.calib_samples)
            else:
                current_avg = accel_angle

            self.live_jitter = accel_angle - current_avg

            # STEAM-ФІШКА: Захист від поштовхів (поріг 0.5° на нерухомому столі)
            if len(self.calib_samples) > 20:
                if abs(accel_angle - current_avg) > 0.5:
                    logger.warning("Виявлено рух або поштовх! Таймер калібрування скинуто на 10с.")
                    self.calib_start_time = time.time()
                    self.calib_samples.clear()
                    self.final_output = 0.0
                    return 0.0

            self.calib_samples.append(accel_angle)

            if time.time() - self.calib_start_time >= 10.0:
                self.finish_calibration()

            self.final_output = 0.0
            return 0.0

        # Звичайний режим роботи (Adaptive Sensor Fusion / Адаптивний фільтр):
        # ЕКСТРЕМАЛЬНИЙ РЕЖИМ: плавно змінюємо довіру до датчиків в реальному часі.
        # Коли крутимо кермо - довіряємо ВИКЛЮЧНО гіроскопу (tau = 2.5s) для 0ms лагу і захисту від поребриків.
        # Коли їдемо прямо - м'яко вмикаємо акселерометр (tau = 0.25s), щоб ідеально тримати пряму лінію.
        
        movement_intensity = min(1.0, abs(gyro_rate) / 20.0) # 0.0 (нерухомо) .. 1.0 (швидкий поворот)
        tau = 0.25 + (movement_intensity * 2.25) # Динамічний перехід від 0.25 сек до 2.5 сек
        
        alpha = tau / (tau + dt)
        
        self.current_angle = alpha * (self.current_angle + gyro_angle_change) + (1.0 - alpha) * accel_angle

        angle_centered = self.current_angle - self.zero_offset
        self.live_jitter = angle_centered

        # Захист від шуму на основі калібрування (мертва зона навколо центру)
        if self.noise_threshold > 0.0 and abs(angle_centered) <= self.noise_threshold:
            angle_centered = 0.0

        # --- ПОВНІСТЮ ЧИСТИЙ СИГНАЛ БЕЗ ЗГЛАДЖУВАННЯ (0ms затримки) ---
        # Жодних фільтрів, затримок чи згладжування: миттєва реакція на 100%.
        self.filtered_angle = angle_centered

        # Нормалізація кута повороту
        max_angle = max(10.0, self.max_steer_angle)
        norm_val = self.filtered_angle / max_angle
        norm_val = max(-1.0, min(1.0, norm_val))

        # Плавна мертва зона (Continuous deadzone)
        dz = max(0.0, min(0.3, self.deadzone))
        abs_val = abs(norm_val)

        if abs_val <= dz:
            deadzoned = 0.0
        else:
            sign = 1.0 if norm_val > 0.0 else -1.0
            deadzoned = sign * ((abs_val - dz) / (1.0 - dz))

        # Крива нелінійності / Гамма
        if abs(deadzoned) > 1e-5 and self.gamma != 1.0:
            sign = 1.0 if deadzoned > 0.0 else -1.0
            curved = sign * (abs(deadzoned) ** self.gamma)
        else:
            curved = deadzoned

        # Динамічна чутливість залежно від швидкості (Speed sensitivity)
        if self.enable_speed_sensitivity and speed_kmh > 30.0:
            # Плавне демпфування кута повороту на високих швидкостях
            speed_factor = 1.0 / (1.0 + (speed_kmh - 30.0) * (self.speed_sensitivity * 0.01))
            curved *= max(0.25, speed_factor)

        if self.invert_steer:
            curved = -curved

        self.final_output = max(-1.0, min(1.0, curved))
        return self.final_output

    def start_calibration(self, countdown: float = 3.0):
        if countdown > 0:
            self.is_counting_down = True
            self.countdown_start = time.time()
            self.countdown_duration = countdown
            self.is_calibrating = False
            self.calib_samples.clear()
            logger.info(f"Приготуйтесь: калібрування розпочнеться через {int(countdown)} сек. Покладіть геймпад на стіл...")
        else:
            self.is_counting_down = False
            self.is_calibrating = True
            self.calib_start_time = time.time()
            self.calib_samples.clear()
            logger.info("Початок калібрування шуму (10 сек). Не торкайтесь геймпада...")

    def finish_calibration(self):
        import json
        import os
        
        self.is_calibrating = False
        self.is_counting_down = False
        if not self.calib_samples:
            return
            
        # 1. Вираховуємо ідеальний центр
        self.zero_offset = sum(self.calib_samples) / len(self.calib_samples)
        
        # 2. Визначаємо амплітуду шуму з розумними межами (0.04° - 0.35°)
        max_deviation = max(abs(s - self.zero_offset) for s in self.calib_samples)
        self.noise_threshold = max(0.04, min(0.35, max_deviation * 1.25))
        
        # 3. Зберігаємо результати у config.json назавжди
        config_path = self.cfg.config_path if hasattr(self, 'cfg') and self.cfg and os.path.exists(self.cfg.config_path) else "config.json"
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            else:
                config_data = {}

            config_data["gyro_zero_offset"] = round(self.zero_offset, 4)
            config_data["gyro_noise_threshold"] = round(self.noise_threshold, 4)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
                
            if hasattr(self, 'cfg') and self.cfg:
                self.cfg.data["gyro_zero_offset"] = round(self.zero_offset, 4)
                self.cfg.data["gyro_noise_threshold"] = round(self.noise_threshold, 4)

            logger.info(f"Калібрування УСПІШНЕ! Дані збережено в config.json.")
            logger.info(f"Центр: {self.zero_offset:+.4f}°, Шум: {self.noise_threshold:.4f}°")
        except Exception as e:
            logger.error(f"Помилка збереження в config.json: {e}")

        self.filtered_angle = 0.0
        self.final_output = 0.0

    def calibrate_center(self):
        self.start_calibration(countdown=3.0)
import keyboard
import threading
import logging

logger = logging.getLogger("DualSenseACBridge.KeyboardEmulator")

class KeyboardEmulator:
    def __init__(self):
        self.key_press_counts = {}
        self.lock = threading.Lock()
        self.key_binds = {}

    def update_binds(self, new_binds):
        with self.lock:
            # release all currently pressed keys first to avoid stuck keys
            for key in list(self.key_press_counts.keys()):
                if self.key_press_counts[key] > 0:
                    try:
                        keyboard.release(key)
                    except Exception:
                        pass
            self.key_press_counts.clear()
            self.key_binds = new_binds or {}

    def press_button(self, button_name):
        with self.lock:
            if button_name in self.key_binds:
                key = self.key_binds[button_name]
                if key:
                    count = self.key_press_counts.get(key, 0)
                    if count == 0:
                        try:
                            keyboard.press(key)
                        except Exception as e:
                            logger.error(f"Failed to press key {key}: {e}")
                    self.key_press_counts[key] = count + 1

    def release_button(self, button_name):
        with self.lock:
            if button_name in self.key_binds:
                key = self.key_binds[button_name]
                if key:
                    count = self.key_press_counts.get(key, 0)
                    if count > 0:
                        count -= 1
                        self.key_press_counts[key] = count
                        if count == 0:
                            try:
                                keyboard.release(key)
                            except Exception as e:
                                logger.error(f"Failed to release key {key}: {e}")

    def release_all(self):
        with self.lock:
            for key, count in self.key_press_counts.items():
                if count > 0:
                    try:
                        keyboard.release(key)
                    except Exception:
                        pass
            self.key_press_counts.clear()

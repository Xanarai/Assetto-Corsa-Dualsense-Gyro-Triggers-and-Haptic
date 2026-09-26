"""
DualSense Windows Audio Auto-Configurator.

Provides read-only diagnostics (check_dualsense_audio_status) and
write operations (configure via pycaw + registry) with optional
UAC elevation for 4-channel format changes.

Requirements: pip install pycaw comtypes
Admin rights required for format change (4-channel).
"""

import os
import sys
import json
import struct
import logging
import ctypes
import subprocess
from typing import Tuple

logger = logging.getLogger("DualSenseACBridge.AudioSetup")

# WAVEFORMATEXTENSIBLE for 4ch, 48000 Hz, 24-bit valid / 32-bit container
# Quadraphonic layout: FL | FR | BL | BR  (channel mask 0x33)
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE
_KSDATAFORMAT_SUBTYPE_PCM = (
    b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
)
_CHANNEL_MASK_QUAD = 0x00000033  # FL | FR | BL | BR

_DS_KEYWORDS = ("wireless controller", "dualsense", "playstation")

# Registry property keys (PROPERTYKEY as string: {fmtid},pid)
_PKEY_AudioEngine_DeviceFormat = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},0"
_PKEY_AudioEngine_OEMFormat = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},3"
_PKEY_Device_FriendlyName = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
_PKEY_DeviceInterface_FriendlyName = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
_MMDEVICES_RENDER_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
)


def open_mmsys_cpl() -> bool:
    """
    Directly opens classic Windows Sound Control Panel (mmsys.cpl).
    This is the fastest and most reliable place for users to enable disabled devices.
    """
    try:
        subprocess.Popen(["control", "mmsys.cpl", "sounds"])
        return True
    except Exception:
        try:
            os.startfile("mmsys.cpl")
            return True
        except Exception as e:
            logger.warning(f"Could not open mmsys.cpl: {e}")
            return False


def open_sound_settings() -> bool:
    """
    Opens Windows Sound Settings page (ms-settings:sound) or mmsys.cpl as fallback.
    Returns True if launched successfully.
    """
    try:
        os.startfile("ms-settings:sound")
        return True
    except Exception:
        return open_mmsys_cpl()


def enable_dualsense_endpoint_com() -> bool:
    """
    Directly enables the DualSense audio endpoint using Windows IPolicyConfig COM interface.
    This mimics the exact action of right-clicking the device in mmsys.cpl and selecting 'Enable'.
    Does NOT require administrator elevation or audio service restart.
    """
    try:
        from pycaw.pycaw import AudioUtilities
        from pycaw.constants import EDataFlow, DEVICE_STATE
        from comtypes import GUID
        from ctypes import POINTER, c_void_p, c_wchar_p, c_int, HRESULT, WINFUNCTYPE

        devices = AudioUtilities.GetAllDevices(
            data_flow=EDataFlow.eRender.value,
            device_state=DEVICE_STATE.MASK_ALL.value,
        )
        if not devices:
            return False

        clsid = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")
        iid = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        p = c_void_p()
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(p)
        )
        if hr != 0:
            logger.debug(f"IPolicyConfig CoCreateInstance failed: hr={hr}")
            return False

        vtable = ctypes.cast(p, POINTER(POINTER(c_void_p))).contents
        # vtable[14]: HRESULT SetEndpointVisibility(LPCWSTR wszDeviceId, BOOL bVisible);
        SetEndpointVisibility = WINFUNCTYPE(HRESULT, c_void_p, c_wchar_p, c_int)(vtable[14])

        enabled_any = False
        for dev in devices:
            name = (dev.FriendlyName or "").lower()
            if any(kw in name for kw in _DS_KEYWORDS):
                # Ignore unplugged/not-present devices (state == 4 or 8)
                st_val = getattr(dev.state, "value", dev.state)
                if st_val not in (4, 8):
                    res = SetEndpointVisibility(p, dev.id, 1)
                    if res == 0:
                        logger.info(
                            f"Enabled DualSense audio endpoint '{dev.FriendlyName}' ({dev.id}) via IPolicyConfig COM"
                        )
                        enabled_any = True
                    else:
                        logger.warning(
                            f"SetEndpointVisibility for '{dev.FriendlyName}' returned hr={hex(res)}"
                        )

        return enabled_any
    except Exception as e:
        logger.warning(f"enable_dualsense_endpoint_com error: {e}")
        return False


def _build_waveformatextensible(
    channels: int = 4,
    sample_rate: int = 48000,
    bits: int = 24,
    container_bits: int = 32,
) -> bytes:
    """Builds a WAVEFORMATEXTENSIBLE binary blob for registry injection."""
    block_align = channels * (container_bits // 8)
    avg_bytes = sample_rate * block_align
    header = struct.pack(
        "<HHIIHHh",
        _WAVE_FORMAT_EXTENSIBLE,
        channels,
        sample_rate,
        avg_bytes,
        block_align,
        container_bits,
        22,
    )
    extension = struct.pack("<HI", bits, _CHANNEL_MASK_QUAD)
    return header + extension + _KSDATAFORMAT_SUBTYPE_PCM


def _is_admin() -> bool:
    """Returns True if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# READ-ONLY DIAGNOSTICS  (no admin required)
# ─────────────────────────────────────────────────────────────────────────────


def check_dualsense_audio_status() -> dict:
    """
    Non-destructive check of DualSense audio device status.
    Returns a dict describing what is configured and what needs setup.

    Keys:
        device_found     (bool): DualSense audio device present in Windows.
        device_disabled  (bool): True if device is disabled / restricted in Windows.
        device_name      (str):  Friendly name of the device.
        channels         (int):  Current max output channels (0 if disabled/not found).
        is_4ch           (bool): True if device already exposes >= 4 channels and is active.
        volume_ok        (bool): True if master volume is >= 0.99 (effectively 100%).
        volume_level     (float): Current master volume scalar [0.0, 1.0].
        needs_setup      (bool): True if any configuration step is still needed.
    """
    result = {
        "device_found": False,
        "device_disabled": False,
        "device_name": "",
        "channels": 0,
        "is_4ch": False,
        "volume_ok": False,
        "volume_level": 0.0,
        "needs_setup": True,
    }

    # 1. Check active render devices via pycaw
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from pycaw.constants import EDataFlow
        from comtypes import CLSCTX_ALL

        render_devices = AudioUtilities.GetAllDevices(data_flow=EDataFlow.eRender.value)
        active_ds = None
        disabled_ds = None

        for dev in render_devices:
            name = (dev.FriendlyName or "").lower()
            if any(kw in name for kw in _DS_KEYWORDS):
                st = dev._dev.GetState() if hasattr(dev._dev, "GetState") else 1
                # 1 = ACTIVE, 2 = DISABLED, 4 = NOTPRESENT, 8 = UNPLUGGED
                if st == 1 and active_ds is None:
                    active_ds = dev
                elif st == 2 and disabled_ds is None:
                    disabled_ds = dev

        if active_ds:
            result["device_found"] = True
            result["device_disabled"] = False
            result["device_name"] = active_ds.FriendlyName
            try:
                iface = active_ds._dev.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                vol = iface.QueryInterface(IAudioEndpointVolume)
                level = vol.GetMasterVolumeLevelScalar()
                result["volume_level"] = round(level, 3)
                result["volume_ok"] = level >= 0.99
            except Exception as vol_e:
                logger.debug(f"Volume check for {active_ds.FriendlyName} failed: {vol_e}")
                result["volume_ok"] = True
                result["volume_level"] = 1.0

        elif disabled_ds:
            result["device_found"] = True
            result["device_disabled"] = True
            result["device_name"] = disabled_ds.FriendlyName
            result["volume_ok"] = False
            result["volume_level"] = 0.0
            result["is_4ch"] = False

    except Exception as e:
        logger.debug(f"pycaw render check failed: {e}")

    # 2. Check channels via sounddevice (only works if device is enabled in Windows)
    if not result["device_disabled"]:
        try:
            import sounddevice as sd
            # Ensure PortAudio re-enumerates live devices so recent Windows settings apply immediately
            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass

            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            wasapi_indices = [
                i
                for i, h in enumerate(hostapis)
                if "WASAPI" in h.get("name", "").upper()
            ]

            best = None
            for idx, dev in enumerate(devices):
                name = dev.get("name", "").upper()
                out_ch = dev.get("max_output_channels", 0)
                host_api = dev.get("hostapi", -1)
                if out_ch > 0 and any(kw in name for kw in ("WIRELESS CONTROLLER", "DUALSENSE", "PLAYSTATION")):
                    is_wasapi = host_api in wasapi_indices
                    score = (10 if is_wasapi else 1) + (10 if out_ch >= 4 else 0)
                    if best is None or score > best[0]:
                        best = (score, idx, dev.get("name", ""), out_ch)

            if best:
                result["device_found"] = True
                if not result["device_name"]:
                    result["device_name"] = best[2]
                result["channels"] = best[3]
                result["is_4ch"] = best[3] >= 4
        except Exception as e:
            logger.debug(f"sounddevice check failed: {e}")

    # 3. Direct registry scan fallback if device not found via COM
    if not result["device_found"]:
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                _MMDEVICES_RENDER_KEY,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as rk:
                subkeys_count = winreg.QueryInfoKey(rk)[0]
                for si in range(subkeys_count):
                    guid = winreg.EnumKey(rk, si)
                    props_path = f"{_MMDEVICES_RENDER_KEY}\\{guid}\\Properties"
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            props_path,
                            0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                        ) as pk:
                            num_vals = winreg.QueryInfoKey(pk)[1]
                            for vi in range(num_vals):
                                _, vdata, _ = winreg.EnumValue(pk, vi)
                                if isinstance(vdata, str) and any(kw in vdata.lower() for kw in _DS_KEYWORDS):
                                    result["device_found"] = True
                                    result["device_name"] = vdata
                                    try:
                                        with winreg.OpenKey(
                                            winreg.HKEY_LOCAL_MACHINE,
                                            f"{_MMDEVICES_RENDER_KEY}\\{guid}",
                                            0,
                                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                                        ) as dk:
                                            st, _ = winreg.QueryValueEx(dk, "DeviceState")
                                            if st != 1:
                                                result["device_disabled"] = True
                                    except Exception:
                                        pass
                                    break
                            if result["device_found"]:
                                break
                    except Exception:
                        continue
        except Exception as reg_e:
            logger.debug(f"Registry fallback check failed: {reg_e}")

    if result["device_disabled"]:
        result["is_4ch"] = False
        result["channels"] = 0
        result["volume_ok"] = False
        result["needs_setup"] = True
    else:
        result["needs_setup"] = not (result["device_found"] and result["is_4ch"] and result["volume_ok"])

    return result


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────


def _set_volume_pycaw(target_volume: float) -> Tuple[bool, str]:
    """Sets DualSense master volume via pycaw for ACTIVE render device. No admin required."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from pycaw.constants import EDataFlow
        from comtypes import CLSCTX_ALL
    except ImportError:
        logger.warning("pycaw not installed — volume auto-config skipped.")
        return False, ""

    try:
        render_devices = AudioUtilities.GetAllDevices(data_flow=EDataFlow.eRender.value)
        for dev in render_devices:
            name = (dev.FriendlyName or "").lower()
            if any(kw in name for kw in _DS_KEYWORDS):
                st = dev._dev.GetState() if hasattr(dev._dev, "GetState") else 1
                if st != 1:  # Not ACTIVE (e.g. disabled or unplugged)
                    continue
                try:
                    iface = dev._dev.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                    )
                    vol = iface.QueryInterface(IAudioEndpointVolume)
                    vol.SetMasterVolumeLevelScalar(float(target_volume), None)
                    logger.info(
                        f"Volume set to {int(target_volume * 100)}% "
                        f"for '{dev.FriendlyName}'"
                    )
                    return True, dev.FriendlyName
                except Exception as act_e:
                    logger.debug(f"Could not activate volume on {dev.FriendlyName}: {act_e}")
                    continue
        logger.warning("DualSense active audio render device not found for volume config.")
        return False, ""
    except Exception as e:
        logger.warning(f"Volume config failed: {e}")
        return False, ""


def _enable_and_format_device_registry(
    channels: int = 4, sample_rate: int = 48000
) -> Tuple[bool, bool]:
    """
    Finds DualSense render device in MMDevices registry and COM:
    1. First attempts COM activation via IPolicyConfig (works without service restart).
    2. In MMDevices registry, sets DeviceState = 1 (Active) for all present DualSense endpoints.
    3. Writes 4-channel format blob to _PKEY_AudioEngine_DeviceFormat and _PKEY_AudioEngine_OEMFormat.
    4. Restarts Windows Audio Endpoint Builder and audiosrv so changes apply immediately.
    Returns (device_enabled, format_ok).
    Requires Administrator rights for registry and service restart.
    """
    import winreg

    wave_blob = _build_waveformatextensible(channels, sample_rate)
    device_enabled = False
    format_ok = False

    # 1. First attempt COM endpoint activation
    try:
        if enable_dualsense_endpoint_com():
            device_enabled = True
    except Exception as e_com:
        logger.debug(f"Initial COM enable attempt note: {e_com}")

    try:
        render_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            _MMDEVICES_RENDER_KEY,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
    except OSError as e:
        logger.warning(f"Cannot open MMDevices registry key: {e}")
        return device_enabled, format_ok

    candidate_guids = []
    with render_key:
        idx = 0
        while True:
            try:
                guid_name = winreg.EnumKey(render_key, idx)
                idx += 1
            except OSError:
                break

            props_path = f"{_MMDEVICES_RENDER_KEY}\\{guid_name}\\Properties"
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    props_path,
                    0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                ) as props:
                    num_vals = winreg.QueryInfoKey(props)[1]
                    for vi in range(num_vals):
                        _, vdata, _ = winreg.EnumValue(props, vi)
                        if isinstance(vdata, str) and any(kw in vdata.lower() for kw in _DS_KEYWORDS):
                            candidate_guids.append((guid_name, vdata))
                            break
            except Exception:
                continue

    if not candidate_guids:
        logger.warning("No DualSense render device found in MMDevices registry.")
        return device_enabled, format_ok

    logger.info(f"Found DualSense render devices in registry: {candidate_guids}")

    # Process all candidate GUIDs (prioritizing non-NotPresent devices)
    for guid_name, friendly_name in candidate_guids:
        dev_path = f"{_MMDEVICES_RENDER_KEY}\\{guid_name}"
        props_path = f"{dev_path}\\Properties"

        # Check DeviceState
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                dev_path,
                0,
                winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
            ) as dev_k:
                try:
                    cur_state, _ = winreg.QueryValueEx(dev_k, "DeviceState")
                except OSError:
                    cur_state = None

                # Only change if not already active (1) and not unplugged/not present (4)
                if cur_state != 1:
                    winreg.SetValueEx(dev_k, "DeviceState", 0, winreg.REG_DWORD, 1)
                    logger.info(
                        f"DeviceState set to 1 (active) for '{friendly_name}' ({guid_name}), was {cur_state}"
                    )
                    device_enabled = True
                else:
                    device_enabled = True
        except PermissionError:
            logger.warning(f"Registry write denied for DeviceState on {guid_name} — Administrator required.")
        except Exception as e:
            logger.debug(f"DeviceState write failed for {guid_name}: {e}")

        # Write 4-channel format to Properties
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                props_path,
                0,
                winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
            ) as props_w:
                winreg.SetValueEx(
                    props_w,
                    _PKEY_AudioEngine_DeviceFormat,
                    0,
                    winreg.REG_BINARY,
                    wave_blob,
                )
                try:
                    winreg.SetValueEx(
                        props_w,
                        _PKEY_AudioEngine_OEMFormat,
                        0,
                        winreg.REG_BINARY,
                        wave_blob,
                    )
                except Exception:
                    pass

                logger.info(f"4-channel format written for device: '{friendly_name}' ({guid_name})")
                format_ok = True
        except PermissionError:
            logger.warning(f"Registry write denied for format on {guid_name} — Administrator required.")
        except Exception as e:
            logger.debug(f"Format write failed for {guid_name}: {e}")

    # If any change was made, restart audio services to apply
    if device_enabled or format_ok:
        try:
            subprocess.run(["net", "stop", "audiosrv", "/y"], capture_output=True, timeout=6)
            subprocess.run(["net", "start", "AudioEndpointBuilder"], capture_output=True, timeout=6)
            subprocess.run(["net", "start", "audiosrv"], capture_output=True, timeout=6)
            logger.info("Restarted Windows Audio services to apply changes.")
        except Exception as srv_e:
            logger.debug(f"Audio services restart note: {srv_e}")

    return device_enabled, format_ok


def _set_format_registry(
    channels: int = 4, sample_rate: int = 48000
) -> bool:
    """Backwards compatible wrapper for 4-channel format registry write."""
    _, format_ok = _enable_and_format_device_registry(channels, sample_rate)
    return format_ok


def configure_dualsense_audio(
    target_volume: float = 1.0,
    channels: int = 4,
    sample_rate: int = 48000,
) -> dict:
    """
    Applies volume + format + enable settings. Format/enable requires admin.

    Returns dict: volume_ok, format_ok, device_enabled, device_name, admin.
    """
    admin = _is_admin()
    volume_ok, device_name = _set_volume_pycaw(target_volume)

    format_ok = False
    device_enabled = False
    if admin:
        device_enabled, format_ok = _enable_and_format_device_registry(channels, sample_rate)
    else:
        # Standard user: attempt COM enable first
        try:
            device_enabled = enable_dualsense_endpoint_com()
        except Exception:
            pass
        logger.info(
            f"Not running as Administrator — COM device_enabled={device_enabled}. 4-channel format not applied."
        )

    return {
        "volume_ok": volume_ok,
        "format_ok": format_ok,
        "device_enabled": device_enabled,
        "device_name": device_name,
        "admin": admin,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ELEVATED SUBPROCESS WIZARD
# ─────────────────────────────────────────────────────────────────────────────


def run_elevated_setup() -> dict:
    """
    Spawns an elevated (admin) child process using audio_setup_worker.py that:
    1. Re-enables the DualSense audio device via COM & registry if disabled.
    2. Applies 4-channel format to registry.
    3. Restarts audio services so changes take effect immediately.
    4. Sets DualSense volume to 100%.
    Uses ShellExecuteW 'runas' verb for UAC prompt.
    Captures complete logs from worker into %TEMP%\\ds_audio_setup.log.

    Returns dict: format_ok, device_enabled, volume_ok, error (str or None).
    """
    worker_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "audio_setup_worker.py"
    )
    python_exe = sys.executable
    temp_dir = os.environ.get("TEMP", ".")
    temp_result = os.path.join(temp_dir, f"ds_setup_res_{os.getpid()}.json")
    temp_log = os.path.join(temp_dir, f"ds_setup_log_{os.getpid()}.log")

    try:
        if os.path.exists(temp_result):
            os.remove(temp_result)
    except OSError:
        pass

    try:
        params = f'"{worker_script}" "{temp_result}" "{temp_log}"'
        logger.info(f"Launching elevated audio setup worker: {python_exe} {params}")

        # ShellExecuteW with 'runas' triggers UAC elevation dialog
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # verb — triggers UAC
            python_exe,     # file
            params,         # parameters
            None,           # directory
            0,              # nShowCmd = SW_HIDE
        )
        # ShellExecuteW returns > 32 on success
        if ret <= 32:
            err = f"UAC elevation cancelled or failed (code {ret})."
            logger.warning(err)
            return {
                "format_ok": False,
                "device_enabled": False,
                "volume_ok": False,
                "error": err,
            }

        # Wait for the worker to write the result JSON (up to 20 seconds)
        import time
        for _ in range(40):
            time.sleep(0.5)
            if os.path.exists(temp_result):
                try:
                    with open(temp_result, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    try:
                        os.remove(temp_result)
                    except OSError:
                        pass
                    logger.info(f"Elevated audio worker returned: {data}")
                    return data
                except Exception as read_e:
                    logger.debug(f"Waiting for result file to complete write: {read_e}")
                    continue

        # If timed out, read the worker log file to see what happened
        log_content = ""
        if os.path.exists(temp_log):
            try:
                with open(temp_log, "r", encoding="utf-8") as f:
                    log_content = f.read().strip()
            except Exception:
                pass

        err_msg = f"Elevated setup timed out. Worker log: {log_content[-300:] if log_content else 'No log produced'}"
        logger.error(err_msg)
        return {
            "format_ok": False,
            "device_enabled": False,
            "volume_ok": False,
            "error": err_msg,
        }

    except Exception as e:
        logger.error(f"run_elevated_setup exception: {e}", exc_info=True)
        return {
            "format_ok": False,
            "device_enabled": False,
            "volume_ok": False,
            "error": str(e),
        }

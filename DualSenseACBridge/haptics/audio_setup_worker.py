"""
DualSense Elevated Audio Setup Worker.

Launched as an elevated process (via UAC ShellExecuteW 'runas') to:
1. Re-enable DualSense render endpoint via IPolicyConfig / Registry.
2. Write 4-channel format to MMDevices registry.
3. Restart Windows Audio services (audiosrv / AudioEndpointBuilder).
4. Set volume to 100% via pycaw.

Outputs result JSON to the path passed as sys.argv[1].
Logs full trace to sys.argv[2] (or %TEMP%\\ds_audio_setup.log).
"""

import sys
import os
import json
import logging
import traceback
import time

def setup_worker_logger(log_path: str):
    logging.basicConfig(
        filename=log_path,
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("DualSenseAudioWorker")

def main():
    result_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "ds_audio_setup_result.json")
    log_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "."), "ds_audio_setup.log")

    logger = setup_worker_logger(log_path)
    logger.info("Elevated audio worker started.")
    logger.info(f"Python: {sys.executable}, argv: {sys.argv}")

    # Ensure parent project directory is in sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    logger.info(f"Project root added to sys.path: {project_root}")

    result = {
        "format_ok": False,
        "device_enabled": False,
        "volume_ok": False,
        "error": None,
        "traceback": None,
    }

    try:
        from DualSenseACBridge.haptics.audio_setup import (
            enable_dualsense_endpoint_com,
            _enable_and_format_device_registry,
            _set_volume_pycaw,
        )

        # 1. Attempt COM endpoint activation
        logger.info("Attempting COM endpoint activation via IPolicyConfig...")
        com_enabled = False
        try:
            com_enabled = enable_dualsense_endpoint_com()
            logger.info(f"COM enable result: {com_enabled}")
        except Exception as e_com:
            logger.warning(f"COM enable failed: {e_com}")

        # 2. Registry format and enable
        logger.info("Applying 4-channel format and registry settings...")
        dev_en, fmt_ok = _enable_and_format_device_registry(channels=4, sample_rate=48000)
        logger.info(f"Registry result -> dev_en: {dev_en}, fmt_ok: {fmt_ok}")

        result["device_enabled"] = bool(com_enabled or dev_en)
        result["format_ok"] = bool(fmt_ok)

        # Brief pause to allow Windows Audio services to settle
        time.sleep(1.0)

        # 3. Set volume to 100%
        logger.info("Setting volume to 100% via pycaw...")
        vol_ok, dev_name = _set_volume_pycaw(1.0)
        logger.info(f"Volume result -> vol_ok: {vol_ok}, device_name: {dev_name}")
        result["volume_ok"] = bool(vol_ok)

    except Exception as e:
        err_msg = str(e)
        tb_str = traceback.format_exc()
        logger.error(f"Worker exception: {err_msg}\n{tb_str}")
        result["error"] = err_msg
        result["traceback"] = tb_str

    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote result JSON to {result_path}: {result}")
    except Exception as e_write:
        logger.error(f"Failed to write result JSON: {e_write}")

    logger.info("Elevated audio worker exiting.")

if __name__ == "__main__":
    main()

"""
clap_launcher.py
─────────────────
Listens for a double clap via the microphone.
When detected, launches main.py automatically.
 
Usage:
    python clap_launcher.py
"""
 
import os
import sys
import time
import subprocess
import threading
from pathlib import Path
 
import numpy as np
import sounddevice as sd
 
 
# ─── Config ───────────────────────────────────────────────────────────────────
SAMPLE_RATE       = 16000      # Hz
CHUNK_DURATION    = 0.03       # seconds per chunk (30 ms)
CHUNK_SIZE        = int(SAMPLE_RATE * CHUNK_DURATION)
 
# Clap detection thresholds
CLAP_THRESHOLD    = 2000       # RMS amplitude to count as a clap
CLAP_MIN_GAP      = 0.08       # seconds — min gap between two claps (avoids echo double-count)
CLAP_MAX_GAP      = 0.6        # seconds — max gap between two claps in a double-clap
CLAP_COOLDOWN     = 1.5        # seconds — ignore claps after a double is detected
 
# What to launch
BASE_DIR   = Path(__file__).resolve().parent
LAUNCH_CMD = [sys.executable, str(BASE_DIR / "main.py")]
 
 
# ─── State ────────────────────────────────────────────────────────────────────
_last_clap_time   = 0.0
_prev_clap_time   = 0.0
_cooldown_until   = 0.0
_launched         = False
_lock             = threading.Lock()
 
 
def _rms(data: np.ndarray) -> float:
    return float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
 
 
def _on_chunk(indata: np.ndarray, frames: int, time_info, status):
    global _last_clap_time, _prev_clap_time, _cooldown_until, _launched
 
    now = time.time()
 
    with _lock:
        if now < _cooldown_until:
            return
        if _launched:
            return
 
    amplitude = _rms(indata)
 
    if amplitude < CLAP_THRESHOLD:
        return
 
    with _lock:
        gap_since_last = now - _last_clap_time
 
        # Ignore if too soon after the previous clap (echo / reverb)
        if gap_since_last < CLAP_MIN_GAP:
            return
 
        _prev_clap_time = _last_clap_time
        _last_clap_time = now
        gap = now - _prev_clap_time
 
        double_clap = (CLAP_MIN_GAP < gap <= CLAP_MAX_GAP) and (_prev_clap_time > 0)
 
        if double_clap:
            _cooldown_until = now + CLAP_COOLDOWN
            _launched       = True
 
    if double_clap:
        _launch()
 
 
def _launch():
    print("\n✅  Double clap detected — launching JARVIS...\n")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                LAUNCH_CMD,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            subprocess.Popen(LAUNCH_CMD)
    except Exception as e:
        print(f"❌  Failed to launch main.py: {e}")
    # Exit the launcher after firing
    time.sleep(0.5)
    os._exit(0)
 
 
def _print_banner():
    print("=" * 48)
    print("  J.A.R.V.I.S  —  Clap Launcher")
    print("=" * 48)
    print("  Listening for a double clap...")
    print(f"  Threshold : {CLAP_THRESHOLD} RMS")
    print(f"  Max gap   : {CLAP_MAX_GAP * 1000:.0f} ms between claps")
    print("  Press Ctrl+C to exit.")
    print("=" * 48 + "\n")
 
 
def main():
    _print_banner()
 
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=_on_chunk,
        ):
            while True:
                time.sleep(0.1)
 
    except KeyboardInterrupt:
        print("\n🔴  Clap launcher stopped.")
    except Exception as e:
        print(f"❌  Microphone error: {e}")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()
 
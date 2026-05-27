import os
import sys
import time
import subprocess
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd


# ─── Config ───────────────────────────────────────────────────────────────────
SAMPLE_RATE    = 16000
CHUNK_DURATION = 0.03                          # 30 ms per chunk
CHUNK_SIZE     = int(SAMPLE_RATE * CHUNK_DURATION)

CLAP_THRESHOLD = 2500   # RMS to count as a clap — raise if false triggers
CLAP_MIN_GAP   = 0.10   # seconds — min gap between two claps (blocks echo)
CLAP_MAX_GAP   = 0.55   # seconds — max gap for double clap to count

BASE_DIR   = Path(__file__).resolve().parent
LAUNCH_CMD = [sys.executable, str(BASE_DIR / "main.py")]


# ─── Detector ─────────────────────────────────────────────────────────────────
class ClapDetector:
    def __init__(self):
        self._first_clap_time = 0.0   # time of the most recent clap
        self._in_clap         = False  # True while audio is above threshold
        self._lock            = threading.Lock()

    def feed(self, amplitude: float) -> bool:
        """
        Feed one RMS amplitude value.
        Returns True the moment a valid double-clap is confirmed.
        """
        now = time.time()

        with self._lock:
            is_loud = amplitude >= CLAP_THRESHOLD

            # Rising edge — new clap starts
            if is_loud and not self._in_clap:
                self._in_clap = True
                gap = now - self._first_clap_time

                if self._first_clap_time == 0.0:
                    # Very first clap ever — just record it
                    self._first_clap_time = now
                    return False

                if gap < CLAP_MIN_GAP:
                    # Too soon — same clap / echo, ignore
                    return False

                if gap <= CLAP_MAX_GAP:
                    # Second clap within window → double clap!
                    self._first_clap_time = 0.0   # reset so it can't re-trigger
                    return True

                # Gap too long — this becomes the new first clap
                self._first_clap_time = now
                return False

            # Falling edge
            if not is_loud and self._in_clap:
                self._in_clap = False

            return False


_detector = ClapDetector()
_launched = False


def _on_chunk(indata: np.ndarray, frames: int, time_info, status):
    global _launched
    if _launched:
        return

    amplitude = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2)))

    if _detector.feed(amplitude):
        _launched = True
        threading.Thread(target=_launch, daemon=True).start()


def _launch():
    print("\n  Double clap detected — launching JARVIS...\n")
    try:
        if sys.platform == "win32":
            subprocess.Popen(LAUNCH_CMD, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(LAUNCH_CMD)
    except Exception as e:
        print(f"  Failed to launch: {e}")
    time.sleep(0.5)
    os._exit(0)


def _calibrate():
    """Sample ambient noise for 1 second and suggest a threshold."""
    print("  Calibrating... stay silent for 1 second.")
    samples = []

    def _cb(indata, frames, t, status):
        rms = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2)))
        samples.append(rms)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK_SIZE, callback=_cb):
        time.sleep(1.2)

    if samples:
        noise_floor = max(samples)
        suggested   = max(int(noise_floor * 4), 800)
        print(f"  Noise floor peak : {noise_floor:.0f} RMS")
        print(f"  Suggested threshold : {suggested}  (current: {CLAP_THRESHOLD})")
        if suggested > CLAP_THRESHOLD:
            print(f"  ⚠  Room is noisy — edit CLAP_THRESHOLD to {suggested} at the top of the file.")
    print()


def main():
    print("=" * 50)
    print("  J.A.R.V.I.S  —  Clap Launcher")
    print("=" * 50)
    _calibrate()
    print(f"  Threshold : {CLAP_THRESHOLD} RMS")
    print(f"  Window    : {CLAP_MIN_GAP*1000:.0f} – {CLAP_MAX_GAP*1000:.0f} ms between claps")
    print("  Double-clap to launch JARVIS")
    print("  Ctrl+C to quit\n")

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=CHUNK_SIZE,
                            callback=_on_chunk):
            while not _launched:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n  Stopped.")
    except Exception as e:
        print(f"  Mic error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
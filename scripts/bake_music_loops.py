"""Generate bundled background loops (WAV) without ffmpeg — used by SudarVid static/music/."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "music"


def _write_stereo_sine(path: Path, frequency: float, duration_sec: float = 8.0, sample_rate: int = 44100) -> None:
    n = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(n):
            v = int(12000 * math.sin(2 * math.pi * frequency * i / sample_rate))
            w.writeframes(struct.pack("<hh", v, v))


def main() -> None:
    _write_stereo_sine(OUT / "loop_ambient.wav", 220.0)
    _write_stereo_sine(OUT / "loop_soft.wav", 330.0)
    _write_stereo_sine(OUT / "loop_energetic.wav", 440.0)
    _write_stereo_sine(OUT / "loop_retro.wav", 165.0)
    print(f"Wrote loops under {OUT}")


if __name__ == "__main__":
    main()

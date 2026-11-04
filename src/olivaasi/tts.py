"""Offline speech: one clip per sentence, joined into one track with exact timings.

Backends, tried in order:
  * macOS `say` with the system Tamil voice (Vani) and an Indian English voice.
  * `espeak-ng` on Linux or Windows (has Tamil; robotic but intelligible).
If neither exists, conversion still works and the page simply has no audio.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

RATE = 22050
MARK_MS = 1200  # silence placed between sentences in a batched call
SILENCE = 200  # sample amplitude below which audio counts as silent


@dataclass
class Clip:
    text: str
    lang: str  # "ta" or "en"
    pause_ms: int = 350


@dataclass
class Timing:
    start: float
    end: float


class Backend:
    name = "none"

    def voice_for(self, lang: str) -> str | None:  # pragma: no cover - interface
        return None

    def synth(self, text: str, lang: str, out: Path) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def speak_many(self, texts: list[str], lang: str, tmp: Path, workers: int = 4) -> list[np.ndarray]:
        """Audio for each text, in order. Default: one engine call per text, in parallel."""
        paths = [tmp / f"{lang}-{i:04d}.wav" for i in range(len(texts))]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda pt: self.synth(pt[1], lang, pt[0]), zip(paths, texts)))
        return [trim(_read_wav(p)) for p in paths]


class MacSay(Backend):
    name = "macOS say"
    PREFERRED = {"ta": ["Vani"], "en": ["Rishi", "Tara", "Aman", "Veena", "Samantha", "Daniel"]}

    def __init__(self) -> None:
        self.voices = _mac_voices()

    def voice_for(self, lang: str) -> str | None:
        for name in self.PREFERRED.get(lang, []):
            if name in self.voices:
                return name
        prefix = "ta_" if lang == "ta" else "en_"
        for name, locale in self.voices.items():
            if locale.startswith(prefix):
                return name
        return None

    def synth(self, text: str, lang: str, out: Path) -> None:
        voice = self.voice_for(lang)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            src = f.name
        try:
            cmd = ["say", "-o", str(out), f"--data-format=LEI16@{RATE}", "-f", src]
            if voice:
                cmd[1:1] = ["-v", voice]
            subprocess.run(cmd, check=True, capture_output=True)
        finally:
            os.unlink(src)

    def speak_many(self, texts: list[str], lang: str, tmp: Path, workers: int = 4) -> list[np.ndarray]:
        """One `say` call for many sentences.

        Starting `say` costs about 0.8 s and the speech service handles one
        request at a time, so a page of 25 sentences took 13 s one by one.
        Instead the sentences are joined with a long embedded silence and the
        result is cut at those silences. If the cut does not give exactly one
        piece per sentence, fall back to one call per sentence.
        """
        if len(texts) == 1:
            return super().speak_many(texts, lang, tmp, workers)
        joined = f" [[slnc {MARK_MS}]] ".join(safe_for_say(t) for t in texts)
        out = tmp / f"{lang}-batch.wav"
        self.synth(joined, lang, out)
        pieces = split_on_gaps(_read_wav(out), len(texts))
        if pieces is None:
            return super().speak_many(texts, lang, tmp, workers)
        return pieces


class Espeak(Backend):
    name = "espeak-ng"

    def __init__(self, exe: str) -> None:
        self.exe = exe

    def voice_for(self, lang: str) -> str | None:
        return "ta" if lang == "ta" else "en-gb"

    def synth(self, text: str, lang: str, out: Path) -> None:
        subprocess.run([self.exe, "-v", self.voice_for(lang), "-s", "150", "-w", str(out), text], check=True, capture_output=True)


@lru_cache(maxsize=1)
def _mac_voices() -> dict[str, str]:
    try:
        listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    voices: dict[str, str] = {}
    for line in listing.splitlines():
        m = re.match(r"^(.+?)\s+([a-z]{2,3}_[A-Z0-9]{2,3})\s+#", line)
        if m:
            voices[m.group(1).strip()] = m.group(2)
    return voices


def pick_backend() -> Backend | None:
    if os.environ.get("OLIVAASI_TTS") == "none":
        return None
    if shutil.which("say") and _mac_voices():
        return MacSay()
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if exe:
        return Espeak(exe)
    return None


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate, width, ch = w.getframerate(), w.getsampwidth(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16 if width == 2 else np.uint8)
    if width != 2:
        data = ((data.astype(np.int16) - 128) * 256).astype(np.int16)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if rate != RATE and len(data):
        n = int(len(data) * RATE / rate)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.int16)
    return data


def safe_for_say(text: str) -> str:
    """Stop recognised text from being read as a `say` embedded command."""
    return text.replace("[[", "(").replace("]]", ")")


def trim(audio: np.ndarray, threshold: int = SILENCE) -> np.ndarray:
    """Cut leading and trailing silence, keeping 40 ms either side."""
    loud = np.nonzero(np.abs(audio) > threshold)[0]
    if len(loud) == 0:
        return audio[:0]
    keep = int(0.04 * RATE)
    return audio[max(0, loud[0] - keep) : loud[-1] + keep]


def split_on_gaps(audio: np.ndarray, n: int, min_gap_s: float = 0.8) -> list[np.ndarray] | None:
    """Split speech into n pieces at the n-1 longest silences of at least min_gap_s."""
    if n <= 1:
        return [trim(audio)]
    hop = int(0.01 * RATE)
    frames = len(audio) // hop
    if frames == 0:
        return None
    loud = np.abs(audio[: frames * hop].reshape(frames, hop)).max(axis=1) > SILENCE
    runs: list[tuple[int, int]] = []  # (start frame, length)
    start = None
    for i, is_loud in enumerate(loud):
        if not is_loud and start is None:
            start = i
        elif is_loud and start is not None:
            runs.append((start, i - start))
            start = None
    runs = [r for r in runs if r[0] > 0 and r[1] * 0.01 >= min_gap_s]
    if len(runs) != n - 1:
        return None
    cuts = [0] + [(s + length // 2) * hop for s, length in runs] + [len(audio)]
    return [trim(audio[a:b]) for a, b in zip(cuts, cuts[1:])]


def build_track(clips: list[Clip], out_dir: Path, backend: Backend, name: str = "audio") -> tuple[Path, list[Timing]]:
    """Speak each clip, join them with short pauses, and return the track and per-clip timings."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audio: list[np.ndarray] = []
    with tempfile.TemporaryDirectory(prefix="olivaasi-tts-") as tmp:
        i = 0
        while i < len(clips):  # consecutive clips in the same language share one voice call
            j = i
            while j < len(clips) and clips[j].lang == clips[i].lang:
                j += 1
            batch_dir = Path(tmp) / str(i)
            batch_dir.mkdir()
            audio.extend(backend.speak_many([c.text for c in clips[i:j]], clips[i].lang, batch_dir))
            i = j
    pieces: list[np.ndarray] = []
    timings: list[Timing] = []
    t = 0.0
    for clip, sound in zip(clips, audio):
        dur = len(sound) / RATE
        timings.append(Timing(round(t, 3), round(t + dur, 3)))
        gap = np.zeros(int(RATE * clip.pause_ms / 1000), dtype=np.int16)
        pieces += [sound, gap]
        t += dur + len(gap) / RATE
    wav_path = out_dir / f"{name}.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.concatenate(pieces).tobytes() if pieces else b"")
    return compress(wav_path), timings


def compress(wav: Path) -> Path:
    """Make a small AAC file if a local encoder exists; otherwise keep the WAV."""
    m4a = wav.with_suffix(".m4a")
    if shutil.which("afconvert"):
        cmd = ["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(wav), str(m4a)]
    elif shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "48k", str(m4a)]
    else:
        return wav
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return wav
    wav.unlink()
    return m4a

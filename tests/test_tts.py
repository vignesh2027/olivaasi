import numpy as np

from padi import tts


def tone(seconds):
    t = np.arange(int(tts.RATE * seconds)) / tts.RATE
    return (8000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16)


def silence(seconds):
    return np.zeros(int(tts.RATE * seconds), dtype=np.int16)


def test_split_on_gaps_finds_marker_silences_and_ignores_short_pauses():
    audio = np.concatenate([silence(0.1), tone(0.5), silence(0.2), tone(0.4), silence(1.2), tone(0.7), silence(1.2), tone(0.3)])
    pieces = tts.split_on_gaps(audio, 3)
    assert pieces is not None and len(pieces) == 3
    lengths = [len(p) / tts.RATE for p in pieces]
    assert abs(lengths[0] - (0.5 + 0.2 + 0.4 + 0.08)) < 0.03  # short pause kept inside the sentence
    assert abs(lengths[1] - (0.7 + 0.08)) < 0.03


def test_split_on_gaps_reports_mismatch():
    audio = np.concatenate([tone(0.5), silence(1.2), tone(0.5)])
    assert tts.split_on_gaps(audio, 3) is None


def test_safe_for_say_blocks_embedded_commands():
    assert "[[" not in tts.safe_for_say("x [[rate 500]] y")


class FakeBackend(tts.Backend):
    name = "fake"

    def speak_many(self, texts, lang, tmp, workers=4):
        return [tone(0.1 * len(t.split())) for t in texts]


def test_build_track_timings_follow_clip_lengths_and_pauses(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "compress", lambda p: p)
    clips = [tts.Clip("one two", "ta", 300), tts.Clip("three", "ta", 300), tts.Clip("four five six", "en", 700)]
    path, timings = tts.build_track(clips, tmp_path, FakeBackend())
    assert path.exists()
    assert [(t.start, t.end) for t in timings] == [(0.0, 0.2), (0.5, 0.6), (0.9, 1.2)]

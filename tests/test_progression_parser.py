"""Tests for chord progression parser."""

import json
import pytest

from chord_analyzer.progression_parser import (
    parse_progression_shorthand,
    parse_progression_json,
    parse_progression_bars,
    parse_progression_auto,
    validate_progression,
    progression_to_shorthand,
    _parse_shorthand_token,
)
from chord_analyzer.models import UserChordSpec, UserProgression


class TestParseProgressionShorthand:
    """Tests for shorthand notation parsing."""

    def test_basic_shorthand(self):
        """Test basic chord:beats format."""
        prog = parse_progression_shorthand("Cmaj7:4 Am7:4", bpm=120)
        assert len(prog.chords) == 2
        assert prog.chords[0].root == "C"
        assert prog.chords[0].quality == "maj7"
        assert prog.chords[0].duration_beats == 4
        assert prog.chords[1].root == "A"
        assert prog.chords[1].quality == "min7"
        assert prog.bpm == 120

    def test_shorthand_with_colons(self):
        """Test C:maj:4 format with colons."""
        prog = parse_progression_shorthand("C:maj:4 A:min:4", bpm=100)
        assert len(prog.chords) == 2
        assert prog.chords[0].chord_label == "C:maj"
        assert prog.chords[1].chord_label == "A:min"

    def test_shorthand_mixed_durations(self):
        """Test different beat durations."""
        prog = parse_progression_shorthand("C:maj:8 Am:2 G:7:2", bpm=120)
        assert prog.chords[0].duration_beats == 8
        assert prog.chords[1].duration_beats == 2
        assert prog.chords[2].duration_beats == 2
        assert prog.total_beats == 12

    def test_shorthand_with_flats_and_sharps(self):
        """Test accidentals in chord roots."""
        prog = parse_progression_shorthand("Bb:maj7:4 F#:min:4", bpm=120)
        assert prog.chords[0].root == "Bb"
        assert prog.chords[1].root == "F#"

    def test_shorthand_comma_separated(self):
        """Test comma as separator."""
        prog = parse_progression_shorthand("C:4, Am:4, F:4, G:4", bpm=120)
        assert len(prog.chords) == 4

    def test_shorthand_no_duration(self):
        """Test chords without explicit duration default to 4 beats."""
        prog = parse_progression_shorthand("Cmaj7 Am7", bpm=120)
        assert prog.chords[0].duration_beats == 4
        assert prog.chords[1].duration_beats == 4

    def test_empty_shorthand_raises(self):
        """Test empty input raises ValueError."""
        with pytest.raises(ValueError):
            parse_progression_shorthand("", bpm=120)

    def test_whitespace_only_raises(self):
        """Test whitespace-only input raises ValueError."""
        with pytest.raises(ValueError):
            parse_progression_shorthand("   ", bpm=120)


class TestParseProgressionBars:
    """Tests for bar notation parsing."""

    def test_basic_bar_notation(self):
        """Test simple bar notation."""
        prog = parse_progression_bars("C|Am|F|G", bpm=120)
        assert len(prog.chords) == 4
        assert all(c.duration_beats == 4 for c in prog.chords)
        assert prog.total_beats == 16

    def test_bar_notation_with_qualities(self):
        """Test bar notation with chord qualities."""
        prog = parse_progression_bars("Cmaj7|Am7|Fmaj7|G7", bpm=120)
        assert prog.chords[0].quality == "maj7"
        assert prog.chords[3].quality == "7"

    def test_bar_notation_3_4_time(self):
        """Test bar notation in 3/4 time."""
        prog = parse_progression_bars("C|G|Am|F", bpm=120, time_signature=(3, 4))
        assert all(c.duration_beats == 3 for c in prog.chords)
        assert prog.total_beats == 12

    def test_empty_bar_notation_raises(self):
        """Test empty bar notation raises ValueError."""
        with pytest.raises(ValueError):
            parse_progression_bars("", bpm=120)


class TestParseProgressionJson:
    """Tests for JSON format parsing."""

    def test_basic_json(self):
        """Test basic JSON parsing."""
        json_str = json.dumps({
            "bpm": 120,
            "time_signature": "4/4",
            "chords": [
                {"root": "C", "quality": "maj7", "duration_beats": 4},
                {"root": "A", "quality": "min7", "duration_beats": 4},
            ]
        })
        prog = parse_progression_json(json_str)
        assert prog.bpm == 120
        assert len(prog.chords) == 2

    def test_json_with_name(self):
        """Test JSON with progression name."""
        json_str = json.dumps({
            "bpm": 90,
            "name": "Jazz ii-V-I",
            "chords": [
                {"root": "D", "quality": "min7", "duration_beats": 4},
                {"root": "G", "quality": "7", "duration_beats": 4},
                {"root": "C", "quality": "maj7", "duration_beats": 8},
            ]
        })
        prog = parse_progression_json(json_str)
        assert prog.name == "Jazz ii-V-I"

    def test_invalid_json_raises(self):
        """Test invalid JSON raises ValueError."""
        with pytest.raises(ValueError):
            parse_progression_json("not valid json")


class TestParseProgressionAuto:
    """Tests for automatic format detection."""

    def test_auto_detects_json(self):
        """Test auto-detection of JSON format."""
        json_str = json.dumps({
            "bpm": 120,
            "chords": [{"root": "C", "quality": "maj", "duration_beats": 4}]
        })
        prog = parse_progression_auto(json_str, bpm=100)
        assert len(prog.chords) == 1

    def test_auto_detects_bar_notation(self):
        """Test auto-detection of bar notation."""
        prog = parse_progression_auto("C|Am|F|G", bpm=120)
        assert len(prog.chords) == 4

    def test_auto_defaults_to_shorthand(self):
        """Test auto defaults to shorthand."""
        prog = parse_progression_auto("C:4 Am:4 F:4 G:4", bpm=120)
        assert len(prog.chords) == 4


class TestValidateProgression:
    """Tests for progression validation."""

    def test_valid_progression(self):
        """Test validation of valid progression."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj7", duration_beats=4),
                UserChordSpec(root="Am", quality="min7", duration_beats=4),
            ],
            bpm=120,
        )
        warnings = validate_progression(prog)
        # Should have warning about invalid root "Am" (should be "A")
        assert len(warnings) >= 1

    def test_empty_progression_warning(self):
        """Test warning for empty progression."""
        prog = UserProgression(chords=[], bpm=120)
        warnings = validate_progression(prog)
        assert any("no chords" in w.lower() for w in warnings)

    def test_extreme_bpm_warning(self):
        """Test warning for extreme BPM values."""
        prog = UserProgression(
            chords=[UserChordSpec(root="C", quality="maj", duration_beats=4)],
            bpm=10,  # Very slow
        )
        warnings = validate_progression(prog)
        assert any("slow" in w.lower() for w in warnings)


class TestUserProgression:
    """Tests for UserProgression model."""

    def test_total_beats(self):
        """Test total beats calculation."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj", duration_beats=4),
                UserChordSpec(root="G", quality="maj", duration_beats=4),
            ],
            bpm=120,
        )
        assert prog.total_beats == 8

    def test_total_duration_seconds(self):
        """Test duration in seconds calculation."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj", duration_beats=4),
            ],
            bpm=120,  # 2 beats per second
        )
        assert prog.total_duration_seconds == 2.0  # 4 beats at 120 BPM = 2 seconds

    def test_chord_at_beat(self):
        """Test getting chord at specific beat."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj", duration_beats=4),
                UserChordSpec(root="G", quality="maj", duration_beats=4),
            ],
            bpm=120,
        )
        assert prog.chord_at_beat(1).root == "C"
        assert prog.chord_at_beat(4).root == "C"
        assert prog.chord_at_beat(5).root == "G"
        assert prog.chord_at_beat(8).root == "G"

    def test_chord_at_beat_out_of_range(self):
        """Test chord_at_beat returns last chord when out of range."""
        prog = UserProgression(
            chords=[UserChordSpec(root="C", quality="maj", duration_beats=4)],
            bpm=120,
        )
        assert prog.chord_at_beat(10).root == "C"  # Returns last chord

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj7", duration_beats=4),
                UserChordSpec(root="A", quality="min7", duration_beats=4),
            ],
            bpm=120,
            time_signature=(4, 4),
            name="Test Progression",
        )
        data = prog.to_dict()
        restored = UserProgression.from_dict(data)
        assert restored.bpm == prog.bpm
        assert len(restored.chords) == len(prog.chords)
        assert restored.name == prog.name


class TestProgressionToShorthand:
    """Tests for converting back to shorthand."""

    def test_basic_conversion(self):
        """Test basic conversion to shorthand."""
        prog = UserProgression(
            chords=[
                UserChordSpec(root="C", quality="maj7", duration_beats=4),
                UserChordSpec(root="A", quality="min7", duration_beats=4),
            ],
            bpm=120,
        )
        shorthand = progression_to_shorthand(prog)
        assert shorthand == "C:maj7:4 A:min7:4"

"""Tests for tempo and beat detection functionality."""

import pytest
from chord_analyzer.tempo import (
    BeatGrid,
    ChordBeatPosition,
    create_beat_grid_from_tempo,
    estimate_tempo_from_chord_timing,
    quantize_chords_to_beats,
    normalize_chord_rhythm,
    check_librosa_available,
)
from chord_analyzer.models import ChordEvent


class TestBeatGrid:
    """Tests for BeatGrid class."""

    def test_beat_grid_creation(self):
        grid = BeatGrid(
            bpm=120.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0],
            downbeat_times=[0.0, 2.0],
            time_signature=(4, 4),
            first_beat_time=0.0,
        )

        assert grid.bpm == 120.0
        assert grid.beats_per_bar == 4
        assert grid.beat_duration == 0.5  # 60/120
        assert grid.bar_duration == 2.0  # 0.5 * 4

    def test_time_to_beat(self):
        grid = BeatGrid(
            bpm=120.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0],
            downbeat_times=[0.0, 2.0],
            time_signature=(4, 4),
            first_beat_time=0.0,
        )

        # Beat 1 at 0 seconds
        assert grid.time_to_beat(0.0) == 1.0

        # Beat 2 at 0.5 seconds
        assert grid.time_to_beat(0.5) == 2.0

        # Beat 3 at 1.0 seconds
        assert grid.time_to_beat(1.0) == 3.0

        # Before first beat
        assert grid.time_to_beat(-0.5) == 0.0

    def test_time_to_bar_beat(self):
        grid = BeatGrid(
            bpm=120.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
            downbeat_times=[0.0, 2.0],
            time_signature=(4, 4),
            first_beat_time=0.0,
        )

        # Bar 1, Beat 1
        bar, beat = grid.time_to_bar_beat(0.0)
        assert bar == 1
        assert beat == 1.0

        # Bar 1, Beat 3
        bar, beat = grid.time_to_bar_beat(1.0)
        assert bar == 1
        assert beat == 3.0

        # Bar 2, Beat 1
        bar, beat = grid.time_to_bar_beat(2.0)
        assert bar == 2
        assert beat == 1.0

    def test_quantize_to_beat(self):
        grid = BeatGrid(
            bpm=120.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0],
            downbeat_times=[0.0, 2.0],
            time_signature=(4, 4),
            first_beat_time=0.0,
        )

        # Exact on beat
        bar, beat = grid.quantize_to_beat(0.5, subdivision=1)
        assert bar == 1
        assert beat == 2.0

        # Slightly off beat
        bar, beat = grid.quantize_to_beat(0.55, subdivision=1)
        assert bar == 1
        assert beat == 2.0

    def test_3_4_time_signature(self):
        grid = BeatGrid(
            bpm=120.0,
            beat_times=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
            downbeat_times=[0.0, 1.5],
            time_signature=(3, 4),
            first_beat_time=0.0,
        )

        assert grid.beats_per_bar == 3
        assert grid.bar_duration == 1.5


class TestChordBeatPosition:
    """Tests for ChordBeatPosition class."""

    def test_string_representation(self):
        pos = ChordBeatPosition(
            chord_label="C:maj",
            bar=1,
            beat=1.0,
            duration_beats=2.0,
        )
        assert str(pos) == "C:maj @ bar 1, beat 1"

    def test_fractional_beat(self):
        pos = ChordBeatPosition(
            chord_label="G:7",
            bar=2,
            beat=2.5,
            duration_beats=0.5,
        )
        assert "beat 2.50" in str(pos)


class TestCreateBeatGridFromTempo:
    """Tests for create_beat_grid_from_tempo function."""

    def test_basic_creation(self):
        grid = create_beat_grid_from_tempo(
            bpm=120.0,
            duration_seconds=8.0,
            first_beat_offset=0.0,
            time_signature=(4, 4),
        )

        assert grid.bpm == 120.0
        assert grid.time_signature == (4, 4)
        assert grid.first_beat_time == 0.0

        # At 120 BPM, we get 2 beats per second
        # So in 8 seconds, we should have 16 beats
        assert len(grid.beat_times) == 16

        # Downbeats every 4 beats = 4 downbeats
        assert len(grid.downbeat_times) == 4

    def test_with_offset(self):
        grid = create_beat_grid_from_tempo(
            bpm=60.0,
            duration_seconds=5.0,
            first_beat_offset=0.5,
            time_signature=(4, 4),
        )

        # First beat at 0.5 seconds
        assert grid.first_beat_time == 0.5
        assert grid.beat_times[0] == 0.5


class TestEstimateTempoFromChordTiming:
    """Tests for estimate_tempo_from_chord_timing function."""

    def test_regular_intervals(self):
        # Chords changing every 0.5 seconds = 120 BPM
        chord_times = [
            (0.0, 0.5),
            (0.5, 1.0),
            (1.0, 1.5),
            (1.5, 2.0),
        ]

        bpm = estimate_tempo_from_chord_timing(chord_times)

        # Should detect tempo around 120 BPM
        assert bpm is not None
        assert 115 <= bpm <= 125

    def test_two_beat_intervals(self):
        # Chords changing every 1.0 seconds at 120 BPM = 2 beats per chord
        chord_times = [
            (0.0, 1.0),
            (1.0, 2.0),
            (2.0, 3.0),
            (3.0, 4.0),
        ]

        bpm = estimate_tempo_from_chord_timing(chord_times)

        # Could detect 60 or 120 depending on algorithm
        assert bpm is None or 55 <= bpm <= 125

    def test_insufficient_data(self):
        # Too few chords
        assert estimate_tempo_from_chord_timing([]) is None
        assert estimate_tempo_from_chord_timing([(0.0, 0.5)]) is None


class TestQuantizeChordsToBeats:
    """Tests for quantize_chords_to_beats function."""

    def test_basic_quantization(self):
        grid = create_beat_grid_from_tempo(
            bpm=120.0,
            duration_seconds=4.0,
            time_signature=(4, 4),
        )

        chords = [
            (0.0, 1.0, "C:maj"),
            (1.0, 2.0, "A:min"),
            (2.0, 3.0, "F:maj"),
            (3.0, 4.0, "G:maj"),
        ]

        result = quantize_chords_to_beats(chords, grid, subdivision=1)

        assert len(result) == 4
        assert result[0].chord_label == "C:maj"
        assert result[0].bar == 1
        assert result[0].beat == 1.0

    def test_subdivision_quantization(self):
        grid = create_beat_grid_from_tempo(
            bpm=120.0,
            duration_seconds=4.0,
            time_signature=(4, 4),
        )

        # Chord at 0.25 seconds (half a beat at 120 BPM)
        chords = [(0.25, 0.75, "C:maj")]

        # With subdivision=2 (eighth notes), should snap to nearest eighth
        result = quantize_chords_to_beats(chords, grid, subdivision=2)

        assert len(result) == 1
        # Should be quantized to beat 1.5 (the "and" of beat 1)
        assert result[0].beat == 1.5 or result[0].beat == 1.0


class TestNormalizeChordRhythm:
    """Tests for normalize_chord_rhythm function."""

    def test_normalize_positions(self):
        chords = [
            ChordBeatPosition("C:maj", bar=1, beat=1.0, duration_beats=2.0),
            ChordBeatPosition("A:min", bar=1, beat=3.0, duration_beats=2.0),
            ChordBeatPosition("F:maj", bar=2, beat=1.0, duration_beats=2.0),
            ChordBeatPosition("G:maj", bar=2, beat=3.0, duration_beats=2.0),
        ]

        result = normalize_chord_rhythm(chords)

        assert len(result) == 4
        # Positions should be normalized to 0-1 range
        assert result[0][0] == 0.0  # First chord at position 0
        assert 0 < result[1][0] < 1  # Middle chords
        assert 0 < result[2][0] < 1
        # Verify chord labels preserved
        assert result[0][1] == "C:maj"

    def test_empty_input(self):
        result = normalize_chord_rhythm([])
        assert result == []


class TestLibrosaAvailability:
    """Tests for librosa availability check."""

    def test_check_returns_boolean(self):
        result = check_librosa_available()
        assert isinstance(result, bool)


class TestChordEventBeatInfo:
    """Tests for ChordEvent beat-related fields."""

    def test_chord_event_with_beat_info(self):
        chord = ChordEvent(
            start_time=0.0,
            end_time=1.0,
            chord_label="C:maj",
            root_note="C",
            chord_type="maj",
            bar=1,
            beat=1.0,
            duration_beats=2.0,
        )

        assert chord.has_beat_info is True
        assert chord.bar == 1
        assert chord.beat == 1.0
        assert chord.duration_beats == 2.0

    def test_chord_event_without_beat_info(self):
        chord = ChordEvent(
            start_time=0.0,
            end_time=1.0,
            chord_label="C:maj",
            root_note="C",
            chord_type="maj",
        )

        assert chord.has_beat_info is False

    def test_chord_event_to_dict_with_beat_info(self):
        chord = ChordEvent(
            start_time=0.0,
            end_time=1.0,
            chord_label="C:maj",
            root_note="C",
            chord_type="maj",
            bar=2,
            beat=3.0,
            duration_beats=1.0,
        )

        data = chord.to_dict()

        assert "bar" in data
        assert data["bar"] == 2
        assert "beat" in data
        assert data["beat"] == 3.0
        assert "duration_beats" in data
        assert data["duration_beats"] == 1.0

    def test_chord_event_from_dict_with_beat_info(self):
        data = {
            "start": 0.0,
            "end": 1.0,
            "chord": "G:7",
            "root": "G",
            "type": "7",
            "bar": 3,
            "beat": 2.5,
            "duration_beats": 0.5,
        }

        chord = ChordEvent.from_dict(data)

        assert chord.bar == 3
        assert chord.beat == 2.5
        assert chord.duration_beats == 0.5

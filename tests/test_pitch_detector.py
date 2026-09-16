"""Tests for pitch detection module."""

import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock

from chord_analyzer.pitch_detector import (
    hz_to_midi,
    midi_to_pitch_class,
    midi_to_note_name,
    compute_file_hash,
    check_pitch_detection_available,
    _segment_notes_from_frames,
    _finalize_note,
    SUPPORTED_FORMATS,
    NATIVE_FORMATS,
    FFMPEG_FORMATS,
    CAF_FORMATS,
)
from chord_analyzer.models import NoteEvent


class TestHzToMidi:
    """Tests for Hz to MIDI conversion."""

    def test_a440(self):
        """Test A440 converts to MIDI 69."""
        assert hz_to_midi(440.0) == 69

    def test_middle_c(self):
        """Test middle C (C4) at ~261.63 Hz converts to MIDI 60."""
        assert hz_to_midi(261.63) == 60

    def test_a3(self):
        """Test A3 at 220 Hz converts to MIDI 57."""
        assert hz_to_midi(220.0) == 57

    def test_a5(self):
        """Test A5 at 880 Hz converts to MIDI 81."""
        assert hz_to_midi(880.0) == 81

    def test_zero_frequency(self):
        """Test zero frequency returns 0."""
        assert hz_to_midi(0.0) == 0

    def test_negative_frequency(self):
        """Test negative frequency returns 0."""
        assert hz_to_midi(-100.0) == 0


class TestMidiToPitchClass:
    """Tests for MIDI to pitch class conversion."""

    def test_middle_c(self):
        """Test MIDI 60 (C4) has pitch class 0."""
        assert midi_to_pitch_class(60) == 0

    def test_a4(self):
        """Test MIDI 69 (A4) has pitch class 9."""
        assert midi_to_pitch_class(69) == 9

    def test_e4(self):
        """Test MIDI 64 (E4) has pitch class 4."""
        assert midi_to_pitch_class(64) == 4

    def test_octave_invariance(self):
        """Test same pitch class across octaves."""
        # All C notes should have pitch class 0
        assert midi_to_pitch_class(24) == 0  # C1
        assert midi_to_pitch_class(36) == 0  # C2
        assert midi_to_pitch_class(48) == 0  # C3
        assert midi_to_pitch_class(60) == 0  # C4
        assert midi_to_pitch_class(72) == 0  # C5


class TestMidiToNoteName:
    """Tests for MIDI to note name conversion."""

    def test_middle_c(self):
        """Test MIDI 60 converts to C4."""
        assert midi_to_note_name(60) == "C4"

    def test_a4(self):
        """Test MIDI 69 converts to A4."""
        assert midi_to_note_name(69) == "A4"

    def test_low_notes(self):
        """Test low MIDI notes."""
        assert midi_to_note_name(24) == "C1"
        assert midi_to_note_name(21) == "A0"

    def test_high_notes(self):
        """Test high MIDI notes."""
        assert midi_to_note_name(84) == "C6"
        assert midi_to_note_name(96) == "C7"


class TestSupportedFormats:
    """Tests for supported audio format constants."""

    def test_native_formats(self):
        """Test native formats include expected types."""
        assert ".wav" in NATIVE_FORMATS
        assert ".aiff" in NATIVE_FORMATS
        assert ".aif" in NATIVE_FORMATS
        assert ".flac" in NATIVE_FORMATS

    def test_ffmpeg_formats(self):
        """Test FFmpeg formats include expected types."""
        assert ".mp3" in FFMPEG_FORMATS
        assert ".aac" in FFMPEG_FORMATS
        assert ".m4a" in FFMPEG_FORMATS
        assert ".ogg" in FFMPEG_FORMATS

    def test_caf_formats(self):
        """Test CAF format is included."""
        assert ".caf" in CAF_FORMATS

    def test_supported_formats_comprehensive(self):
        """Test SUPPORTED_FORMATS contains all format types."""
        for fmt in NATIVE_FORMATS:
            assert fmt in SUPPORTED_FORMATS
        for fmt in FFMPEG_FORMATS:
            assert fmt in SUPPORTED_FORMATS
        for fmt in CAF_FORMATS:
            assert fmt in SUPPORTED_FORMATS


class TestSegmentNotesFromFrames:
    """Tests for frame-to-note segmentation."""

    def test_single_sustained_note(self):
        """Test detecting a single sustained note."""
        # 10 frames of A4 (440 Hz) at 100ms per frame
        f0 = np.array([440.0] * 10)
        times = np.linspace(0, 1.0, 10)
        confidences = np.ones(10)
        amplitudes = np.ones(10)

        notes = _segment_notes_from_frames(
            f0, times, confidences, amplitudes,
            min_confidence=0.5, min_duration=0.05
        )

        assert len(notes) == 1
        assert notes[0].midi_note == 69  # A4
        assert notes[0].pitch_class == 9
        assert notes[0].start_time == 0.0

    def test_two_separate_notes(self):
        """Test detecting two separate notes with silence between."""
        # Note 1: C4 (261.63 Hz) for first half
        # Silence (NaN) in middle
        # Note 2: E4 (329.63 Hz) for second half
        f0 = np.array([261.63] * 4 + [np.nan] * 2 + [329.63] * 4)
        times = np.linspace(0, 1.0, 10)
        confidences = np.ones(10)
        amplitudes = np.ones(10)

        notes = _segment_notes_from_frames(
            f0, times, confidences, amplitudes,
            min_confidence=0.5, min_duration=0.05
        )

        assert len(notes) == 2
        assert notes[0].pitch_class == 0  # C
        assert notes[1].pitch_class == 4  # E

    def test_low_confidence_filtered(self):
        """Test that low confidence frames are filtered out."""
        f0 = np.array([440.0] * 10)
        times = np.linspace(0, 1.0, 10)
        confidences = np.array([0.1] * 10)  # Low confidence
        amplitudes = np.ones(10)

        notes = _segment_notes_from_frames(
            f0, times, confidences, amplitudes,
            min_confidence=0.5, min_duration=0.05
        )

        assert len(notes) == 0

    def test_short_note_filtered(self):
        """Test that notes shorter than min_duration are filtered."""
        f0 = np.array([440.0] * 2)  # Only 2 frames
        times = np.array([0.0, 0.01])  # 10ms total
        confidences = np.ones(2)
        amplitudes = np.ones(2)

        notes = _segment_notes_from_frames(
            f0, times, confidences, amplitudes,
            min_confidence=0.5, min_duration=0.05  # Require 50ms
        )

        assert len(notes) == 0

    def test_unvoiced_frames(self):
        """Test handling of unvoiced (NaN) frames."""
        f0 = np.array([np.nan, np.nan, 440.0, 440.0, 440.0, np.nan, np.nan])
        times = np.linspace(0, 0.7, 7)
        confidences = np.ones(7)
        amplitudes = np.ones(7)

        notes = _segment_notes_from_frames(
            f0, times, confidences, amplitudes,
            min_confidence=0.5, min_duration=0.05
        )

        assert len(notes) == 1
        # Note should start at frame 2 (0.2s) and end at frame 5 (0.5s)
        assert notes[0].start_time == pytest.approx(0.2, abs=0.05)


class TestFinalizeNote:
    """Tests for note finalization."""

    def test_basic_finalization(self):
        """Test basic note creation from frame data."""
        note_data = {
            "start_time": 0.0,
            "frequencies": [440.0, 441.0, 439.0],  # A4 with slight variation
            "midi_notes": [69, 69, 69],
            "confidences": [0.9, 0.95, 0.92],
            "amplitudes": [0.8, 0.85, 0.82],
        }

        note = _finalize_note(note_data, end_time=0.5, min_duration=0.05)

        assert note is not None
        assert note.midi_note == 69
        assert note.pitch_class == 9
        assert note.start_time == 0.0
        assert note.end_time == 0.5
        assert note.duration == 0.5

    def test_too_short_returns_none(self):
        """Test that notes shorter than min_duration return None."""
        note_data = {
            "start_time": 0.0,
            "frequencies": [440.0],
            "midi_notes": [69],
            "confidences": [0.9],
            "amplitudes": [0.8],
        }

        note = _finalize_note(note_data, end_time=0.01, min_duration=0.05)

        assert note is None

    def test_median_values(self):
        """Test that median is used for frequency and MIDI."""
        note_data = {
            "start_time": 0.0,
            "frequencies": [200.0, 440.0, 440.0, 440.0, 800.0],  # Outliers
            "midi_notes": [55, 69, 69, 69, 83],  # Outliers
            "confidences": [0.9] * 5,
            "amplitudes": [0.8] * 5,
        }

        note = _finalize_note(note_data, end_time=0.5, min_duration=0.05)

        # Median should handle outliers
        assert note.midi_note == 69  # Median of [55, 69, 69, 69, 83]


class TestCheckPitchDetectionAvailable:
    """Tests for dependency availability check."""

    def test_returns_tuple(self):
        """Test that function returns a tuple."""
        result = check_pitch_detection_available()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_boolean_first_element(self):
        """Test that first element is boolean."""
        is_available, _ = check_pitch_detection_available()
        assert isinstance(is_available, bool)

    def test_string_second_element(self):
        """Test that second element is string."""
        _, message = check_pitch_detection_available()
        assert isinstance(message, str)


class TestComputeFileHash:
    """Tests for file hash computation."""

    def test_hash_format(self, tmp_path):
        """Test that hash is returned as hex string."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        hash_value = compute_file_hash(str(test_file))

        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 produces 32 hex characters

    def test_same_content_same_hash(self, tmp_path):
        """Test that same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "Identical content"
        file1.write_text(content)
        file2.write_text(content)

        assert compute_file_hash(str(file1)) == compute_file_hash(str(file2))

    def test_different_content_different_hash(self, tmp_path):
        """Test that different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        assert compute_file_hash(str(file1)) != compute_file_hash(str(file2))


class TestNoteEventProperties:
    """Tests for NoteEvent model properties relevant to pitch detection."""

    def test_duration_calculation(self):
        """Test duration is calculated correctly."""
        note = NoteEvent(
            start_time=1.0,
            end_time=2.5,
            pitch_hz=440.0,
            midi_note=69,
            pitch_class=9,
            note_name="A4",
            confidence=0.9,
            amplitude=0.8,
        )
        assert note.duration == 1.5

    def test_beat_info_initially_absent(self):
        """Test has_beat_info is False when no beat info."""
        note = NoteEvent(
            start_time=0.0,
            end_time=0.5,
            pitch_hz=440.0,
            midi_note=69,
            pitch_class=9,
            note_name="A4",
            confidence=0.9,
            amplitude=0.8,
        )
        assert note.has_beat_info is False

    def test_with_beat_info(self):
        """Test with_beat_info creates new note with beat data."""
        note = NoteEvent(
            start_time=0.0,
            end_time=0.5,
            pitch_hz=440.0,
            midi_note=69,
            pitch_class=9,
            note_name="A4",
            confidence=0.9,
            amplitude=0.8,
        )

        note_with_beat = note.with_beat_info(bar=1, beat=2.0)

        assert note_with_beat.has_beat_info is True
        assert note_with_beat.bar == 1
        assert note_with_beat.beat == 2.0
        # Original note unchanged
        assert note.has_beat_info is False

"""Tests for enhanced key and scale detection module."""

import pytest
from chord_analyzer.key_detection import (
    KeyQuality,
    ScaleMode,
    KeyDetectionResult,
    ScaleDetectionResult,
    KeyAnalysisResult,
    detect_key_from_chroma,
    detect_key_from_chords,
    detect_scale_mode,
    detect_scale_from_chords,
    combine_key_detections,
    KRUMHANSL_MAJOR,
    KRUMHANSL_MINOR,
    SCALE_TEMPLATES,
    check_librosa_available,
)


class TestKeyProfiles:
    """Tests for key profile constants."""

    def test_krumhansl_major_length(self):
        assert len(KRUMHANSL_MAJOR) == 12

    def test_krumhansl_minor_length(self):
        assert len(KRUMHANSL_MINOR) == 12

    def test_major_tonic_highest(self):
        # The tonic (first element) should have highest value in major
        assert KRUMHANSL_MAJOR[0] == max(KRUMHANSL_MAJOR)

    def test_minor_tonic_highest(self):
        # The tonic (first element) should have highest value in minor
        assert KRUMHANSL_MINOR[0] == max(KRUMHANSL_MINOR)

    def test_scale_templates_count(self):
        # Should have 9 scale templates
        assert len(SCALE_TEMPLATES) == 9

    def test_scale_template_lengths(self):
        for mode, intervals in SCALE_TEMPLATES.items():
            assert len(intervals) == 7, f"{mode} should have 7 intervals"
            assert intervals[0] == 0, f"{mode} should start with root (0)"


class TestDetectKeyFromChroma:
    """Tests for detect_key_from_chroma function."""

    def test_c_major_chroma(self):
        # Strong C, E, G (C major triad) with other scale notes
        chroma = [
            5.0,  # C - tonic
            0.5,  # C#
            2.0,  # D
            0.5,  # D#
            3.5,  # E - major 3rd
            2.5,  # F
            0.5,  # F#
            4.0,  # G - 5th
            0.5,  # G#
            2.0,  # A
            0.5,  # A#
            2.0,  # B
        ]
        result = detect_key_from_chroma(chroma)
        assert result.root == "C"
        assert result.quality == KeyQuality.MAJOR
        assert result.confidence > 0.5

    def test_a_minor_chroma(self):
        # Strong A, C, E (A minor triad)
        chroma = [
            3.5,  # C - minor 3rd
            0.5,  # C#
            2.0,  # D
            0.5,  # D#
            3.5,  # E - 5th
            2.5,  # F
            0.5,  # F#
            2.0,  # G
            0.5,  # G#
            5.0,  # A - tonic
            0.5,  # A#
            2.0,  # B
        ]
        result = detect_key_from_chroma(chroma)
        assert result.root == "A"
        assert result.quality == KeyQuality.MINOR
        assert result.confidence > 0.5

    def test_g_major_chroma(self):
        # Strong G, B, D (G major triad)
        chroma = [
            2.0,  # C
            0.5,  # C#
            3.5,  # D - 5th from G
            0.5,  # D#
            2.0,  # E
            2.5,  # F#
            0.5,  # Gb
            5.0,  # G - tonic
            0.5,  # G#
            2.0,  # A
            0.5,  # A#
            3.5,  # B - major 3rd
        ]
        result = detect_key_from_chroma(chroma)
        assert result.root == "G"
        assert result.quality == KeyQuality.MAJOR

    def test_invalid_chroma_length(self):
        with pytest.raises(ValueError):
            detect_key_from_chroma([1.0, 2.0, 3.0])  # Only 3 elements

    def test_alternatives_populated(self):
        chroma = [1.0] * 12  # Flat distribution
        result = detect_key_from_chroma(chroma)
        assert len(result.alternatives) > 0

    def test_correlation_values_set(self):
        chroma = [5.0, 0.5, 2.0, 0.5, 3.5, 2.5, 0.5, 4.0, 0.5, 2.0, 0.5, 2.0]
        result = detect_key_from_chroma(chroma)
        assert result.correlation_major is not None
        assert result.correlation_minor is not None


class TestDetectKeyFromChords:
    """Tests for detect_key_from_chords function."""

    def test_c_major_progression(self):
        # Classic I-IV-V-I in C major
        chords = ["C:maj", "F:maj", "G:maj", "C:maj"]
        result = detect_key_from_chords(chords)
        assert result is not None
        assert result.root == "C"
        assert result.quality == KeyQuality.MAJOR

    def test_a_minor_progression(self):
        # i-iv-V-i in A minor
        chords = ["A:min", "D:min", "E:maj", "A:min"]
        result = detect_key_from_chords(chords)
        assert result is not None
        assert result.root == "A"
        assert result.quality == KeyQuality.MINOR

    def test_g_major_progression(self):
        # I-vi-IV-V in G major
        chords = ["G:maj", "E:min", "C:maj", "D:maj"]
        result = detect_key_from_chords(chords)
        assert result is not None
        assert result.root == "G"
        assert result.quality == KeyQuality.MAJOR

    def test_with_durations(self):
        # Longer chords should have more weight
        chords = ["C:maj", "A:min", "F:maj", "G:7"]
        durations = [4.0, 2.0, 2.0, 4.0]
        result = detect_key_from_chords(chords, durations)
        assert result is not None
        assert result.root == "C"

    def test_empty_chords(self):
        result = detect_key_from_chords([])
        assert result is None

    def test_only_no_chord(self):
        result = detect_key_from_chords(["N", "N", "N"])
        assert result is None

    def test_seventh_chords(self):
        # Progression with 7th chords
        chords = ["Cmaj7", "Am7", "Dm7", "G7"]
        result = detect_key_from_chords(chords)
        assert result is not None
        assert result.root == "C"

    def test_method_set(self):
        chords = ["C:maj", "G:maj"]
        result = detect_key_from_chords(chords)
        assert result.method == "chord_analysis"


class TestDetectScaleMode:
    """Tests for detect_scale_mode function."""

    def test_ionian_mode(self):
        # C major scale chroma
        chroma = [5.0, 0.0, 3.0, 0.0, 3.0, 3.0, 0.0, 4.0, 0.0, 2.0, 0.0, 2.0]
        result = detect_scale_mode(chroma, "C")
        assert result is not None
        assert result.mode == ScaleMode.IONIAN
        assert result.root == "C"

    def test_aeolian_mode(self):
        # A natural minor scale chroma
        chroma = [3.0, 0.0, 2.0, 0.0, 3.0, 2.0, 0.0, 3.0, 0.0, 5.0, 0.0, 2.0]
        result = detect_scale_mode(chroma, "A")
        assert result is not None
        assert result.mode == ScaleMode.AEOLIAN

    def test_dorian_mode(self):
        # D Dorian (minor with raised 6th)
        chroma = [2.0, 0.0, 5.0, 0.0, 2.0, 3.0, 0.0, 3.0, 0.0, 3.0, 2.0, 0.0]
        result = detect_scale_mode(chroma, "D")
        assert result is not None
        # Dorian has raised 6th compared to natural minor
        assert result.mode in [ScaleMode.DORIAN, ScaleMode.AEOLIAN]

    def test_scale_notes_populated(self):
        chroma = [5.0, 0.0, 3.0, 0.0, 3.0, 3.0, 0.0, 4.0, 0.0, 2.0, 0.0, 2.0]
        result = detect_scale_mode(chroma, "C")
        assert len(result.scale_notes) == 7
        assert "C" in result.scale_notes

    def test_invalid_root(self):
        chroma = [1.0] * 12
        result = detect_scale_mode(chroma, "X")
        assert result is None

    def test_alternatives_populated(self):
        chroma = [1.0] * 12
        result = detect_scale_mode(chroma, "C")
        assert len(result.alternatives) > 0


class TestDetectScaleFromChords:
    """Tests for detect_scale_from_chords function."""

    def test_major_progression(self):
        chords = ["C:maj", "F:maj", "G:maj", "C:maj"]
        result = detect_scale_from_chords(chords, key_root="C")
        assert result is not None
        assert result.root == "C"

    def test_minor_progression(self):
        chords = ["A:min", "D:min", "E:maj", "A:min"]
        result = detect_scale_from_chords(chords, key_root="A")
        assert result is not None
        assert result.root == "A"

    def test_auto_detect_root(self):
        chords = ["G:maj", "C:maj", "D:maj", "G:maj"]
        result = detect_scale_from_chords(chords)
        assert result is not None

    def test_empty_chords(self):
        result = detect_scale_from_chords([])
        assert result is None


class TestCombineKeyDetections:
    """Tests for combine_key_detections function."""

    def test_filename_only(self):
        result = combine_key_detections(
            filename_key=("C major", "C", "major"),
            audio_result=None,
            chord_result=None,
        )
        assert result is not None
        assert result.key_result.key == "C major"
        assert result.overall_confidence > 0.9
        assert result.source == "filename"

    def test_audio_only(self):
        audio_result = KeyDetectionResult(
            key="G major",
            root="G",
            quality=KeyQuality.MAJOR,
            confidence=0.8,
            method="audio_chroma",
        )
        result = combine_key_detections(
            filename_key=None,
            audio_result=audio_result,
            chord_result=None,
        )
        assert result is not None
        assert result.key_result.key == "G major"
        assert result.source == "audio"

    def test_chord_only(self):
        chord_result = KeyDetectionResult(
            key="A minor",
            root="A",
            quality=KeyQuality.MINOR,
            confidence=0.7,
            method="chord_analysis",
        )
        result = combine_key_detections(
            filename_key=None,
            audio_result=None,
            chord_result=chord_result,
        )
        assert result is not None
        assert result.key_result.key == "A minor"
        assert result.source == "chords"

    def test_all_agree(self):
        # All sources agree on C major
        audio_result = KeyDetectionResult(
            key="C major", root="C", quality=KeyQuality.MAJOR, confidence=0.8
        )
        chord_result = KeyDetectionResult(
            key="C major", root="C", quality=KeyQuality.MAJOR, confidence=0.7
        )
        result = combine_key_detections(
            filename_key=("C major", "C", "major"),
            audio_result=audio_result,
            chord_result=chord_result,
        )
        assert result is not None
        assert result.key_result.key == "C major"
        assert result.source == "combined"
        assert result.overall_confidence > 0.9  # Boosted by agreement

    def test_filename_overrides_audio(self):
        # Filename takes priority even if audio disagrees
        audio_result = KeyDetectionResult(
            key="G major", root="G", quality=KeyQuality.MAJOR, confidence=0.8
        )
        result = combine_key_detections(
            filename_key=("C major", "C", "major"),
            audio_result=audio_result,
            chord_result=None,
        )
        # Filename has 0.6 weight vs audio 0.3, so C major wins
        assert result.key_result.key == "C major"

    def test_no_detections(self):
        result = combine_key_detections(
            filename_key=None,
            audio_result=None,
            chord_result=None,
        )
        assert result is None

    def test_method_shows_sources(self):
        audio_result = KeyDetectionResult(
            key="C major", root="C", quality=KeyQuality.MAJOR, confidence=0.8
        )
        chord_result = KeyDetectionResult(
            key="C major", root="C", quality=KeyQuality.MAJOR, confidence=0.7
        )
        result = combine_key_detections(
            filename_key=("C major", "C", "major"),
            audio_result=audio_result,
            chord_result=chord_result,
        )
        assert "filename" in result.key_result.method
        assert "audio" in result.key_result.method
        assert "chords" in result.key_result.method


class TestKeyDetectionResult:
    """Tests for KeyDetectionResult dataclass."""

    def test_str_representation(self):
        result = KeyDetectionResult(
            key="C major",
            root="C",
            quality=KeyQuality.MAJOR,
            confidence=0.85,
        )
        assert "C major" in str(result)
        assert "85" in str(result)  # 85% confidence

    def test_key_for_matching(self):
        result = KeyDetectionResult(
            key="C major",
            root="C",
            quality=KeyQuality.MAJOR,
            confidence=0.85,
        )
        assert result.key_for_matching == "C:maj"

        result_minor = KeyDetectionResult(
            key="A minor",
            root="A",
            quality=KeyQuality.MINOR,
            confidence=0.85,
        )
        assert result_minor.key_for_matching == "A:min"


class TestScaleDetectionResult:
    """Tests for ScaleDetectionResult dataclass."""

    def test_str_representation(self):
        result = ScaleDetectionResult(
            mode=ScaleMode.DORIAN,
            root="D",
            confidence=0.75,
        )
        assert "D" in str(result)
        assert "dorian" in str(result)

    def test_display_name(self):
        result = ScaleDetectionResult(
            mode=ScaleMode.HARMONIC_MINOR,
            root="A",
            confidence=0.8,
        )
        assert result.display_name == "A Harmonic Minor"


class TestKeyAnalysisResult:
    """Tests for KeyAnalysisResult dataclass."""

    def test_str_with_scale(self):
        key_result = KeyDetectionResult(
            key="C major",
            root="C",
            quality=KeyQuality.MAJOR,
            confidence=0.9,
        )
        scale_result = ScaleDetectionResult(
            mode=ScaleMode.IONIAN,
            root="C",
            confidence=0.85,
        )
        result = KeyAnalysisResult(
            key_result=key_result,
            scale_result=scale_result,
        )
        assert "C major" in str(result)
        assert "ionian" in str(result)

    def test_str_without_scale(self):
        key_result = KeyDetectionResult(
            key="C major",
            root="C",
            quality=KeyQuality.MAJOR,
            confidence=0.9,
        )
        result = KeyAnalysisResult(key_result=key_result)
        assert "C major" in str(result)


class TestLibrosaAvailability:
    """Tests for librosa availability check."""

    def test_check_returns_bool(self):
        result = check_librosa_available()
        assert isinstance(result, bool)

"""Tests for compatibility scoring engine."""

import pytest

from chord_analyzer.compatibility import (
    calculate_compatibility,
    explain_compatibility,
    rank_samples_by_compatibility,
    _score_shared_chords,
    _score_note_overlap,
    _score_harmonic_relations,
    _score_mood_match,
    _score_functional_match,
)


class TestCalculateCompatibility:
    """Tests for the main compatibility calculation."""

    def test_identical_progressions(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        result = calculate_compatibility(prog, prog)

        assert result["overall"] >= 80
        assert "shared_chords" in result["components"]
        assert len(result["reasons"]) > 0

    def test_empty_progressions(self):
        result = calculate_compatibility([], [])
        assert result["overall"] == 0
        assert "Empty progression" in result["reasons"]

    def test_one_empty_progression(self):
        prog = ["C:maj", "A:min"]
        result = calculate_compatibility(prog, [])
        assert result["overall"] == 0

    def test_compatible_progressions(self):
        prog_a = ["C:maj", "A:min", "F:maj", "G:7"]
        prog_b = ["F:maj", "C:maj", "A:min", "G:maj"]
        result = calculate_compatibility(prog_a, prog_b)

        # Should have good compatibility due to shared chords
        assert result["overall"] >= 50
        assert result["components"]["shared_chords"] > 0

    def test_incompatible_progressions(self):
        prog_a = ["C:maj", "D:maj", "E:maj"]  # All major, lots of sharps
        prog_b = ["F#:min", "G#:min", "A#:min"]  # All minor, different roots
        result = calculate_compatibility(prog_a, prog_b)

        # Should have low compatibility
        assert result["overall"] < 50

    def test_score_range(self):
        """Ensure score is always 0-100."""
        prog_a = ["C:maj"]
        prog_b = ["C:maj"]
        result = calculate_compatibility(prog_a, prog_b)
        assert 0 <= result["overall"] <= 100


class TestSharedChordsScore:
    """Tests for shared chords scoring component."""

    def test_all_shared(self):
        prog_a = ["C:maj", "A:min"]
        prog_b = ["A:min", "C:maj"]
        score, reasons = _score_shared_chords(prog_a, prog_b)
        assert score == 20  # Max score (updated from 30)
        assert len(reasons) > 0

    def test_no_shared(self):
        prog_a = ["C:maj", "D:maj"]
        prog_b = ["E:maj", "F:maj"]
        score, reasons = _score_shared_chords(prog_a, prog_b)
        assert score == 0
        assert len(reasons) == 0

    def test_partial_shared(self):
        prog_a = ["C:maj", "A:min", "F:maj"]
        prog_b = ["C:maj", "E:min", "G:maj"]
        score, reasons = _score_shared_chords(prog_a, prog_b)
        assert 0 < score < 20  # Updated from 30


class TestNoteOverlapScore:
    """Tests for note overlap scoring component."""

    def test_same_notes(self):
        notes_a = {0, 4, 7}  # C major
        notes_b = {0, 4, 7}  # Same notes
        overlap, penalty, reasons = _score_note_overlap(notes_a, notes_b)
        assert overlap == 15  # Max score (updated from 25)
        assert penalty == 0

    def test_no_overlap(self):
        notes_a = {0, 4, 7}  # C, E, G
        notes_b = {1, 3, 6}  # C#, D#, F#
        overlap, penalty, reasons = _score_note_overlap(notes_a, notes_b)
        assert overlap == 0

    def test_clash_detection(self):
        notes_a = {0}  # C
        notes_b = {1}  # C# (semitone clash)
        overlap, penalty, reasons = _score_note_overlap(notes_a, notes_b)
        assert penalty < 0
        assert len(reasons) > 0


class TestHarmonicRelationsScore:
    """Tests for harmonic relations scoring."""

    def test_same_roots(self):
        prog_a = ["C:maj"]
        prog_b = ["C:min"]  # Same root
        score, reasons = _score_harmonic_relations(prog_a, prog_b)
        assert score > 0

    def test_fifth_relation(self):
        prog_a = ["C:maj"]
        prog_b = ["G:maj"]  # Perfect 5th
        score, reasons = _score_harmonic_relations(prog_a, prog_b)
        assert score > 0

    def test_fourth_relation(self):
        prog_a = ["C:maj"]
        prog_b = ["F:maj"]  # Perfect 4th
        score, reasons = _score_harmonic_relations(prog_a, prog_b)
        assert score > 0


class TestMoodMatchScore:
    """Tests for mood (major/minor) matching."""

    def test_all_major(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["D:maj", "A:maj", "E:maj"]
        score, reasons = _score_mood_match(prog_a, prog_b)
        assert score >= 13  # High similarity (updated from 18, max is now 15)

    def test_all_minor(self):
        prog_a = ["A:min", "D:min", "E:min"]
        prog_b = ["F#:min", "B:min", "C#:min"]
        score, reasons = _score_mood_match(prog_a, prog_b)
        assert score >= 13  # Updated from 18

    def test_mixed_vs_major(self):
        prog_a = ["C:maj", "A:min", "F:maj", "G:maj"]  # 75% major
        prog_b = ["C:maj", "F:maj", "G:maj", "D:maj"]  # 100% major
        score, reasons = _score_mood_match(prog_a, prog_b)
        assert score > 0


class TestFunctionalMatchScore:
    """Tests for functional/relative matching scoring."""

    def test_exact_transposition(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["G:maj", "C:maj", "D:maj"]  # Same I-IV-V pattern
        score, reasons = _score_functional_match(prog_a, prog_b, True, 7)
        assert score == 35  # Max score for exact transposition
        assert any("transposition" in r.lower() for r in reasons)

    def test_identical_progression(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        score, reasons = _score_functional_match(prog, prog, True, 0)
        assert score == 35
        assert any("identical" in r.lower() for r in reasons)

    def test_similar_but_not_transposition(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["C:maj", "Am:min", "F:maj"]  # Different pattern
        score, reasons = _score_functional_match(prog_a, prog_b, False, None)
        assert 0 < score < 35

    def test_completely_different(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["A:min", "E:min", "B:dim"]
        score, reasons = _score_functional_match(prog_a, prog_b, False, None)
        assert score < 20  # Low functional similarity


class TestExplainCompatibility:
    """Tests for human-readable explanations."""

    def test_basic_explanation(self):
        prog_a = ["C:maj", "A:min"]
        prog_b = ["C:maj", "F:maj"]
        explanation = explain_compatibility(prog_a, prog_b)

        assert "Score" in explanation
        assert "/100" in explanation

    def test_verbose_explanation(self):
        prog_a = ["C:maj", "A:min"]
        prog_b = ["C:maj", "F:maj"]
        explanation = explain_compatibility(prog_a, prog_b, verbose=True)

        assert "Breakdown" in explanation


class TestRankSamples:
    """Tests for ranking multiple samples."""

    def test_ranking_order(self):
        target = ["C:maj", "A:min", "F:maj", "G:maj"]
        candidates = [
            ("perfect_match", ["C:maj", "A:min", "F:maj", "G:maj"]),
            ("partial_match", ["C:maj", "D:maj", "E:maj"]),
            ("no_match", ["F#:maj", "G#:maj", "A#:maj"]),
        ]

        results = rank_samples_by_compatibility(target, candidates)

        # Should be sorted by score descending
        assert results[0][0] == "perfect_match"
        assert results[0][1] > results[1][1] > results[2][1]

    def test_min_score_filter(self):
        target = ["C:maj"]
        candidates = [
            ("match", ["C:maj"]),
            ("no_match", ["F#:maj"]),
        ]

        results = rank_samples_by_compatibility(target, candidates, min_score=50)

        # Only high-scoring matches should be included
        assert len(results) >= 1
        for _, score, _ in results:
            assert score >= 50

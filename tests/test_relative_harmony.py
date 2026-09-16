"""Tests for relative/functional harmony functions."""

import pytest

from chord_analyzer.theory import (
    chord_to_roman_numeral,
    progression_to_numerals,
    get_interval_pattern,
    get_quality_pattern,
    normalize_progression,
    is_transposition,
    get_transposition_interval,
    calculate_functional_similarity,
)


class TestChordToRomanNumeral:
    """Tests for Roman numeral conversion."""

    def test_tonic_major(self):
        assert chord_to_roman_numeral("C:maj", "C") == "I"
        assert chord_to_roman_numeral("G:maj", "G") == "I"

    def test_tonic_minor(self):
        assert chord_to_roman_numeral("A:min", "A") == "i"

    def test_dominant(self):
        assert chord_to_roman_numeral("G:maj", "C") == "V"
        assert chord_to_roman_numeral("D:maj", "G") == "V"

    def test_subdominant(self):
        assert chord_to_roman_numeral("F:maj", "C") == "IV"
        assert chord_to_roman_numeral("C:maj", "G") == "IV"

    def test_relative_minor(self):
        assert chord_to_roman_numeral("A:min", "C") == "vi"
        assert chord_to_roman_numeral("E:min", "G") == "vi"

    def test_seventh_chord(self):
        assert chord_to_roman_numeral("G:7", "C") == "V7"
        assert chord_to_roman_numeral("D:min7", "C") == "ii7"

    def test_flat_seven(self):
        # Bb in key of C = bVII
        assert chord_to_roman_numeral("Bb:maj", "C") == "bVII"

    def test_diminished(self):
        assert chord_to_roman_numeral("B:dim", "C") == "vii°"

    def test_invalid_key(self):
        assert chord_to_roman_numeral("C:maj", "X") is None

    def test_invalid_chord(self):
        assert chord_to_roman_numeral("X:maj", "C") is None


class TestProgressionToNumerals:
    """Tests for converting full progressions to Roman numerals."""

    def test_common_progression_c(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        numerals = progression_to_numerals(prog, "C")
        assert numerals == ["I", "vi", "IV", "V"]

    def test_common_progression_g(self):
        prog = ["G:maj", "E:min", "C:maj", "D:maj"]
        numerals = progression_to_numerals(prog, "G")
        assert numerals == ["I", "vi", "IV", "V"]

    def test_auto_key_detection(self):
        prog = ["C:maj", "F:maj", "G:maj", "C:maj"]
        numerals = progression_to_numerals(prog)  # No key specified
        # Should detect C as key
        assert numerals == ["I", "IV", "V", "I"]

    def test_empty_progression(self):
        assert progression_to_numerals([]) == []

    def test_ii_v_i(self):
        prog = ["D:min7", "G:7", "C:maj7"]
        numerals = progression_to_numerals(prog, "C")
        assert numerals == ["ii7", "V7", "I7"]


class TestIntervalPattern:
    """Tests for extracting interval patterns."""

    def test_i_iv_v_i_pattern(self):
        # C -> F -> G -> C
        prog_c = ["C:maj", "F:maj", "G:maj", "C:maj"]
        pattern_c = get_interval_pattern(prog_c)

        # G -> C -> D -> G (same pattern, different key)
        prog_g = ["G:maj", "C:maj", "D:maj", "G:maj"]
        pattern_g = get_interval_pattern(prog_g)

        # Both should have same interval pattern: up 5, up 2, up 5
        assert pattern_c == pattern_g
        assert pattern_c == [5, 2, 5]

    def test_single_chord(self):
        assert get_interval_pattern(["C:maj"]) == []

    def test_empty_progression(self):
        assert get_interval_pattern([]) == []

    def test_descending_fifths(self):
        # Circle of fifths descending: C -> F -> Bb -> Eb
        prog = ["C:maj", "F:maj", "Bb:maj", "Eb:maj"]
        pattern = get_interval_pattern(prog)
        # Each step is up 5 semitones (perfect 4th up = perfect 5th down)
        assert pattern == [5, 5, 5]


class TestQualityPattern:
    """Tests for extracting chord quality patterns."""

    def test_mixed_qualities(self):
        prog = ["C:maj", "A:min", "F:maj", "G:7"]
        qualities = get_quality_pattern(prog)
        assert qualities == ["maj", "min", "maj", "7"]

    def test_all_major(self):
        prog = ["C:maj", "F:maj", "G:maj"]
        qualities = get_quality_pattern(prog)
        assert qualities == ["maj", "maj", "maj"]

    def test_all_minor(self):
        prog = ["A:min", "D:min", "E:min"]
        qualities = get_quality_pattern(prog)
        assert qualities == ["min", "min", "min"]


class TestNormalizeProgression:
    """Tests for normalizing progressions to key-agnostic form."""

    def test_same_progression_different_keys(self):
        # I-vi-IV-V in C
        prog_c = ["C:maj", "A:min", "F:maj", "G:maj"]
        norm_c = normalize_progression(prog_c)

        # I-vi-IV-V in G
        prog_g = ["G:maj", "E:min", "C:maj", "D:maj"]
        norm_g = normalize_progression(prog_g)

        # Should be identical when normalized
        assert norm_c == norm_g

    def test_normalization_values(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        norm = normalize_progression(prog)
        # C=0, A=9, F=5, G=7 relative to C
        assert norm == [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")]

    def test_empty_progression(self):
        assert normalize_progression([]) == []


class TestIsTransposition:
    """Tests for detecting transpositions."""

    def test_exact_transposition(self):
        prog_c = ["C:maj", "F:maj", "G:maj", "C:maj"]
        prog_g = ["G:maj", "C:maj", "D:maj", "G:maj"]
        assert is_transposition(prog_c, prog_g) is True

    def test_same_progression(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        assert is_transposition(prog, prog) is True

    def test_not_transposition_different_qualities(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["G:min", "C:maj", "D:maj"]  # Different quality on first chord
        assert is_transposition(prog_a, prog_b) is False

    def test_not_transposition_different_lengths(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["G:maj", "C:maj"]
        assert is_transposition(prog_a, prog_b) is False

    def test_not_transposition_different_intervals(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]  # up 5, up 2
        prog_b = ["G:maj", "A:maj", "D:maj"]  # up 2, up 5
        assert is_transposition(prog_a, prog_b) is False


class TestGetTranspositionInterval:
    """Tests for getting transposition interval."""

    def test_fifth_up(self):
        prog_c = ["C:maj", "F:maj", "G:maj"]
        prog_g = ["G:maj", "C:maj", "D:maj"]
        interval = get_transposition_interval(prog_c, prog_g)
        assert interval == 7  # Perfect 5th up

    def test_fourth_up(self):
        prog_c = ["C:maj", "F:maj", "G:maj"]
        prog_f = ["F:maj", "Bb:maj", "C:maj"]
        interval = get_transposition_interval(prog_c, prog_f)
        assert interval == 5  # Perfect 4th up

    def test_same_key(self):
        prog = ["C:maj", "F:maj", "G:maj"]
        interval = get_transposition_interval(prog, prog)
        assert interval == 0

    def test_not_transposition(self):
        prog_a = ["C:maj", "F:maj"]
        prog_b = ["C:min", "F:maj"]  # Different quality
        interval = get_transposition_interval(prog_a, prog_b)
        assert interval is None


class TestFunctionalSimilarity:
    """Tests for functional similarity calculation."""

    def test_identical_progressions(self):
        prog = ["C:maj", "A:min", "F:maj", "G:maj"]
        similarity = calculate_functional_similarity(prog, prog)
        assert similarity == 1.0

    def test_transposed_progressions(self):
        prog_c = ["C:maj", "A:min", "F:maj", "G:maj"]
        prog_g = ["G:maj", "E:min", "C:maj", "D:maj"]
        similarity = calculate_functional_similarity(prog_c, prog_g)
        assert similarity == 1.0  # Exact transposition

    def test_similar_progressions(self):
        prog_a = ["C:maj", "F:maj", "G:maj", "C:maj"]
        prog_b = ["C:maj", "F:maj", "Am:min", "G:maj"]  # Slightly different
        similarity = calculate_functional_similarity(prog_a, prog_b)
        assert 0.3 < similarity < 1.0  # Should have some similarity

    def test_different_progressions(self):
        prog_a = ["C:maj", "F:maj", "G:maj"]
        prog_b = ["A:min", "E:min", "B:dim"]
        similarity = calculate_functional_similarity(prog_a, prog_b)
        assert similarity < 0.5  # Should be quite different

    def test_empty_progressions(self):
        assert calculate_functional_similarity([], []) == 0.0
        assert calculate_functional_similarity(["C:maj"], []) == 0.0


class TestIntegrationWithCompatibility:
    """Integration tests for functional matching in compatibility scoring."""

    def test_transposed_progressions_high_score(self):
        from chord_analyzer.compatibility import calculate_compatibility

        prog_c = ["C:maj", "F:maj", "G:maj", "C:maj"]
        prog_g = ["G:maj", "C:maj", "D:maj", "G:maj"]

        result = calculate_compatibility(prog_c, prog_g)

        # Should score very high due to functional match
        assert result["overall"] >= 70
        assert result["is_transposition"] is True
        assert result["transposition_interval"] == 7
        assert "functional_match" in result["components"]
        assert result["components"]["functional_match"] == 35  # Max functional score

    def test_transposition_info_in_result(self):
        from chord_analyzer.compatibility import calculate_compatibility

        prog_c = ["C:maj", "A:min", "F:maj", "G:maj"]
        prog_d = ["D:maj", "B:min", "G:maj", "A:maj"]

        result = calculate_compatibility(prog_c, prog_d)

        assert result["is_transposition"] is True
        assert result["transposition_interval"] == 2  # Major 2nd up
        assert "transposition_note" in result

    def test_similar_but_not_transposition(self):
        from chord_analyzer.compatibility import calculate_compatibility

        prog_a = ["C:maj", "F:maj", "G:maj", "C:maj"]
        prog_b = ["C:maj", "Am:min", "F:maj", "G:maj"]  # Different progression

        result = calculate_compatibility(prog_a, prog_b)

        assert result["is_transposition"] is False
        assert "transposition_interval" not in result
        # Should still have some functional similarity
        assert result["components"]["functional_match"] > 0

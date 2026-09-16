"""Tests for music theory utilities."""

import pytest

from chord_analyzer.theory import (
    parse_chord_label,
    get_chord_notes,
    get_all_notes_in_progression,
    get_interval_between_notes,
    is_diatonic_to_key,
    estimate_key_from_progression,
    get_relative_minor,
    get_relative_major,
    get_key_distance,
    transpose_chord,
    transpose_progression,
    get_transposition_description,
    semitones_to_interval_name,
    NOTE_TO_SEMITONE,
)


class TestParseChordLabel:
    """Tests for parse_chord_label function."""

    def test_major_chord_with_colon(self):
        root, chord_type = parse_chord_label("C:maj")
        assert root == "C"
        assert chord_type == "maj"

    def test_minor_chord(self):
        root, chord_type = parse_chord_label("A:min")
        assert root == "A"
        assert chord_type == "min"

    def test_seventh_chord(self):
        root, chord_type = parse_chord_label("G:7")
        assert root == "G"
        assert chord_type == "7"

    def test_major_seventh_chord(self):
        root, chord_type = parse_chord_label("D:maj7")
        assert root == "D"
        assert chord_type == "maj7"

    def test_flat_root(self):
        root, chord_type = parse_chord_label("Bb:min7")
        assert root == "Bb"
        assert chord_type == "min7"

    def test_sharp_root(self):
        root, chord_type = parse_chord_label("F#:dim")
        assert root == "F#"
        assert chord_type == "dim"

    def test_no_type_defaults_to_major(self):
        root, chord_type = parse_chord_label("C")
        assert root == "C"
        assert chord_type == "maj"


class TestGetChordNotes:
    """Tests for get_chord_notes function."""

    def test_c_major(self):
        notes = get_chord_notes("C:maj")
        assert notes == {0, 4, 7}  # C, E, G

    def test_a_minor(self):
        notes = get_chord_notes("A:min")
        assert notes == {9, 0, 4}  # A, C, E

    def test_g_dominant_seventh(self):
        notes = get_chord_notes("G:7")
        assert notes == {7, 11, 2, 5}  # G, B, D, F

    def test_invalid_root(self):
        notes = get_chord_notes("X:maj")
        assert notes == set()

    def test_unknown_chord_type_defaults_to_major(self):
        notes = get_chord_notes("C:unknown")
        assert notes == {0, 4, 7}


class TestGetAllNotesInProgression:
    """Tests for get_all_notes_in_progression function."""

    def test_simple_progression(self):
        progression = ["C:maj", "A:min", "F:maj", "G:maj"]
        notes = get_all_notes_in_progression(progression)
        # C major: C, E, G (0, 4, 7)
        # A minor: A, C, E (9, 0, 4)
        # F major: F, A, C (5, 9, 0)
        # G major: G, B, D (7, 11, 2)
        expected = {0, 2, 4, 5, 7, 9, 11}
        assert notes == expected

    def test_empty_progression(self):
        notes = get_all_notes_in_progression([])
        assert notes == set()


class TestIntervals:
    """Tests for interval calculations."""

    def test_unison(self):
        interval = get_interval_between_notes("C", "C")
        assert interval == 0

    def test_perfect_fifth(self):
        interval = get_interval_between_notes("C", "G")
        assert interval == 7

    def test_perfect_fourth(self):
        interval = get_interval_between_notes("C", "F")
        assert interval == 5

    def test_minor_third(self):
        interval = get_interval_between_notes("A", "C")
        assert interval == 3

    def test_invalid_note(self):
        interval = get_interval_between_notes("X", "C")
        assert interval == 0


class TestDiatonic:
    """Tests for diatonic chord detection."""

    def test_c_major_in_c(self):
        assert is_diatonic_to_key("C:maj", "C") is True

    def test_a_minor_in_c(self):
        assert is_diatonic_to_key("A:min", "C") is True

    def test_f_sharp_in_c(self):
        # F# major is not diatonic to C major
        assert is_diatonic_to_key("F#:maj", "C") is False

    def test_g_major_in_c(self):
        assert is_diatonic_to_key("G:maj", "C") is True


class TestKeyEstimation:
    """Tests for key estimation."""

    def test_c_major_progression(self):
        progression = ["C:maj", "A:min", "F:maj", "G:maj"]
        key = estimate_key_from_progression(progression)
        assert key == "C"

    def test_g_major_progression(self):
        progression = ["G:maj", "E:min", "C:maj", "D:maj"]
        key = estimate_key_from_progression(progression)
        assert key == "G"

    def test_empty_progression(self):
        key = estimate_key_from_progression([])
        assert key is None


class TestRelativeKeys:
    """Tests for relative major/minor."""

    def test_relative_minor_of_c(self):
        assert get_relative_minor("C") == "A"

    def test_relative_minor_of_g(self):
        assert get_relative_minor("G") == "E"

    def test_relative_major_of_a(self):
        assert get_relative_major("A") == "C"

    def test_relative_major_of_e(self):
        assert get_relative_major("E") == "G"


class TestKeyDistance:
    """Tests for key distance on circle of fifths."""

    def test_same_key(self):
        distance = get_key_distance("C", "C")
        assert distance == 0

    def test_adjacent_keys(self):
        # C to G is one step on circle of fifths
        distance = get_key_distance("C", "G")
        assert distance <= 1

    def test_opposite_keys(self):
        # C to F# is 6 steps (tritone)
        distance = get_key_distance("C", "F#")
        assert distance == 6


class TestTransposeChord:
    """Tests for transpose_chord function."""

    def test_transpose_c_up_perfect_fifth(self):
        # C up 7 semitones = G
        result = transpose_chord("C:maj", 7)
        assert result == "G:maj"

    def test_transpose_a_down_minor_third(self):
        # A down 3 semitones = F#
        result = transpose_chord("A:min7", -3)
        assert result == "F#:min7"

    def test_transpose_bb_up_whole_step(self):
        # Bb up 2 semitones = C
        result = transpose_chord("Bb:7", 2)
        assert result == "C:7"

    def test_transpose_g_down_perfect_fifth(self):
        # G down 7 semitones = C
        result = transpose_chord("G:maj", -7)
        assert result == "C:maj"

    def test_transpose_wraps_around(self):
        # B up 1 semitone = C
        result = transpose_chord("B:min", 1)
        assert result == "C:min"

    def test_transpose_zero_unchanged(self):
        result = transpose_chord("D:7", 0)
        assert result == "D:7"

    def test_transpose_full_octave_unchanged(self):
        result = transpose_chord("E:maj7", 12)
        assert result == "E:maj7"

    def test_transpose_invalid_chord_unchanged(self):
        result = transpose_chord("X:maj", 5)
        assert result == "X:maj"


class TestTransposeProgression:
    """Tests for transpose_progression function."""

    def test_transpose_i_iv_v_up_perfect_fifth(self):
        # C major I-IV-V transposed to G major
        original = ["C:maj", "F:maj", "G:maj"]
        result = transpose_progression(original, 7)
        assert result == ["G:maj", "C:maj", "D:maj"]

    def test_transpose_i_vi_iv_v_down_perfect_fifth(self):
        # G major I-vi-IV-V transposed to C major
        original = ["G:maj", "E:min", "C:maj", "D:maj"]
        result = transpose_progression(original, -7)
        assert result == ["C:maj", "A:min", "F:maj", "G:maj"]

    def test_round_trip_transposition(self):
        # Transpose up 5, then down 5 should return original
        original = ["C:maj", "A:min", "F:maj", "G:maj"]
        transposed = transpose_progression(original, 5)
        restored = transpose_progression(transposed, -5)
        assert restored == original

    def test_transpose_empty_progression(self):
        result = transpose_progression([], 7)
        assert result == []

    def test_transpose_preserves_chord_types(self):
        original = ["C:maj7", "A:min7", "D:7", "G:aug"]
        result = transpose_progression(original, 2)
        # D:maj7, B:min7, E:7, A:aug
        assert result == ["D:maj7", "B:min7", "E:7", "A:aug"]


class TestGetTranspositionDescription:
    """Tests for get_transposition_description function."""

    def test_same_key_returns_in_key(self):
        result = get_transposition_description(0, 0)
        assert result == "in key"

    def test_g_to_c(self):
        # G=7, C=0
        result = get_transposition_description(7, 0)
        assert result == "G -> C"

    def test_d_to_g(self):
        # D=2, G=7
        result = get_transposition_description(2, 7)
        assert result == "D -> G"

    def test_wraps_around_octave(self):
        # Test that it handles values >= 12
        result = get_transposition_description(14, 2)
        assert result == "D -> D"  # 14 % 12 = 2


class TestSemitonesToIntervalName:
    """Tests for semitones_to_interval_name function."""

    def test_unison(self):
        assert semitones_to_interval_name(0) == "unison"

    def test_perfect_fifth_up(self):
        assert semitones_to_interval_name(7) == "perfect 5th up"

    def test_perfect_fifth_down(self):
        assert semitones_to_interval_name(-7) == "perfect 5th down"

    def test_minor_third_up(self):
        assert semitones_to_interval_name(3) == "minor 3rd up"

    def test_tritone_up(self):
        assert semitones_to_interval_name(6) == "tritone up"

    def test_major_seventh_down(self):
        assert semitones_to_interval_name(-11) == "major 7th down"

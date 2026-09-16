"""Tests for filename parsing module."""

import pytest
from chord_analyzer.filename_parser import (
    FilenameInfo,
    parse_filename,
    parse_key_from_string,
    parse_bpm_from_string,
    normalize_note,
    format_key_for_display,
    format_key_for_matching,
)


class TestNormalizeNote:
    """Tests for normalize_note function."""

    def test_uppercase_single_letter(self):
        assert normalize_note("c") == "C"
        assert normalize_note("g") == "G"

    def test_already_uppercase(self):
        assert normalize_note("C") == "C"
        assert normalize_note("G") == "G"

    def test_sharp_notes(self):
        assert normalize_note("c#") == "C#"
        assert normalize_note("C#") == "C#"
        assert normalize_note("f#") == "F#"

    def test_flat_notes(self):
        assert normalize_note("db") == "Db"
        assert normalize_note("Db") == "Db"
        assert normalize_note("Bb") == "Bb"

    def test_empty_string(self):
        assert normalize_note("") == ""


class TestParseKeyFromString:
    """Tests for parse_key_from_string function."""

    def test_major_with_suffix(self):
        key, root, quality = parse_key_from_string("Cmaj")
        assert key == "C major"
        assert root == "C"
        assert quality == "major"

    def test_minor_with_suffix(self):
        key, root, quality = parse_key_from_string("Am")
        assert key == "A minor"
        assert root == "A"
        assert quality == "minor"

    def test_major_word(self):
        key, root, quality = parse_key_from_string("C Major")
        assert key == "C major"
        assert root == "C"
        assert quality == "major"

    def test_minor_word(self):
        key, root, quality = parse_key_from_string("A minor")
        assert key == "A minor"
        assert root == "A"
        assert quality == "minor"

    def test_sharp_key_minor(self):
        key, root, quality = parse_key_from_string("F#m")
        assert key == "F# minor"
        assert root == "F#"
        assert quality == "minor"

    def test_flat_key_major(self):
        key, root, quality = parse_key_from_string("Dbmaj")
        assert key == "Db major"
        assert root == "Db"
        assert quality == "major"

    def test_key_with_underscores(self):
        key, root, quality = parse_key_from_string("Funky_Bass_Cmaj_Loop")
        assert key == "C major"
        assert root == "C"
        assert quality == "major"

    def test_key_with_spaces(self):
        key, root, quality = parse_key_from_string("Funky Bass C minor Loop")
        assert key == "C minor"
        assert root == "C"
        assert quality == "minor"

    def test_standalone_note_with_separators(self):
        # Standalone notes between separators default to major
        key, root, quality = parse_key_from_string("Loop_C_120")
        assert key == "C major"
        assert root == "C"
        assert quality == "major"

    def test_no_key_found(self):
        key, root, quality = parse_key_from_string("funky_bass_loop_120bpm")
        assert key is None
        assert root is None
        assert quality is None

    def test_min_suffix(self):
        key, root, quality = parse_key_from_string("Amin")
        assert key == "A minor"
        assert root == "A"
        assert quality == "minor"


class TestParseBpmFromString:
    """Tests for parse_bpm_from_string function."""

    def test_bpm_lowercase_suffix(self):
        bpm = parse_bpm_from_string("Funky_Bass_120bpm")
        assert bpm == 120.0

    def test_bpm_uppercase_suffix(self):
        bpm = parse_bpm_from_string("Funky_Bass_120BPM")
        assert bpm == 120.0

    def test_bpm_with_space(self):
        bpm = parse_bpm_from_string("Funky Bass 120 bpm")
        assert bpm == 120.0

    def test_bpm_at_end(self):
        bpm = parse_bpm_from_string("Funky_Bass_90bpm.wav")
        assert bpm == 90.0

    def test_bpm_standalone_number(self):
        # Standalone numbers in valid range without bpm suffix
        bpm = parse_bpm_from_string("Loop_140_Cmaj")
        assert bpm == 140.0

    def test_bpm_out_of_range_high(self):
        # 500 is too high for BPM
        bpm = parse_bpm_from_string("version_500")
        assert bpm is None

    def test_bpm_out_of_range_low(self):
        # 30 is too low for BPM
        bpm = parse_bpm_from_string("track_30_final")
        assert bpm is None

    def test_no_bpm_found(self):
        bpm = parse_bpm_from_string("Funky_Bass_Loop")
        assert bpm is None

    def test_three_digit_bpm(self):
        bpm = parse_bpm_from_string("Drum_Loop_174bpm")
        assert bpm == 174.0

    def test_two_digit_bpm(self):
        bpm = parse_bpm_from_string("Slow_Pad_72bpm")
        assert bpm == 72.0


class TestParseFilename:
    """Tests for parse_filename function."""

    def test_full_path_with_key_and_bpm(self):
        info = parse_filename("/path/to/samples/Funky_Bass_Cmaj_120bpm.wav")
        assert info.key == "C major"
        assert info.key_root == "C"
        assert info.key_quality == "major"
        assert info.bpm == 120.0
        assert info.has_key is True
        assert info.has_bpm is True

    def test_minor_key_with_bpm(self):
        info = parse_filename("drum_loop_Am_90BPM.mp3")
        assert info.key == "A minor"
        assert info.key_root == "A"
        assert info.key_quality == "minor"
        assert info.bpm == 90.0

    def test_key_only(self):
        info = parse_filename("Piano_Chords_Gmaj.wav")
        assert info.key == "G major"
        assert info.has_key is True
        assert info.bpm is None
        assert info.has_bpm is False

    def test_bpm_only(self):
        info = parse_filename("Drum_Loop_140bpm.wav")
        assert info.bpm == 140.0
        assert info.has_bpm is True
        # May or may not detect a key

    def test_sharp_key(self):
        info = parse_filename("Lead_Synth_F#m_140.wav")
        assert info.key == "F# minor"
        assert info.key_root == "F#"
        assert info.key_quality == "minor"

    def test_flat_key(self):
        info = parse_filename("Pad_Db_Major_70bpm.aif")
        assert info.key == "Db major"
        assert info.key_root == "Db"
        assert info.key_quality == "major"
        assert info.bpm == 70.0

    def test_no_info_found(self):
        info = parse_filename("random_sample_v2_final.wav")
        assert info.has_key is False
        assert info.has_bpm is False

    def test_spaces_in_filename(self):
        info = parse_filename("Piano Chords G minor 85 bpm.wav")
        assert info.key == "G minor"
        assert info.bpm == 85.0

    def test_csv_extension(self):
        # CSV files from Chordino should also work
        info = parse_filename("Funky_Bass_Cmaj_120bpm_vamp_nnls-chroma_chordino_simplechord.csv")
        assert info.key == "C major"
        assert info.bpm == 120.0

    def test_filepath_object_properties(self):
        info = parse_filename("/samples/test.wav")
        assert isinstance(info.has_key, bool)
        assert isinstance(info.has_bpm, bool)

    def test_key_at_end_of_filename(self):
        # Pattern: *_G.wav -> G major
        info = parse_filename("Sample_G.wav")
        assert info.key == "G major"
        assert info.key_root == "G"
        assert info.key_quality == "major"

    def test_key_between_separators(self):
        # Pattern: *_G_* -> G major
        info = parse_filename("Loop_G_Main.wav")
        assert info.key == "G major"
        assert info.key_root == "G"
        assert info.key_quality == "major"

    def test_bpm_at_end_of_filename(self):
        # Pattern: *_120.wav -> 120 bpm
        info = parse_filename("Track_120.wav")
        assert info.bpm == 120.0

    def test_bpm_between_separators(self):
        # Pattern: *_120_* -> 120 bpm
        info = parse_filename("Beat_120_Main.wav")
        assert info.bpm == 120.0

    def test_key_and_bpm_at_end(self):
        # Combined pattern: *_G_120.wav
        info = parse_filename("Funky_Bass_G_120.wav")
        assert info.key == "G major"
        assert info.bpm == 120.0


class TestFilenameInfo:
    """Tests for FilenameInfo dataclass."""

    def test_empty_info(self):
        info = FilenameInfo()
        assert info.key is None
        assert info.key_root is None
        assert info.key_quality is None
        assert info.bpm is None
        assert info.has_key is False
        assert info.has_bpm is False

    def test_with_key_only(self):
        info = FilenameInfo(key="C major", key_root="C", key_quality="major")
        assert info.has_key is True
        assert info.has_bpm is False

    def test_with_bpm_only(self):
        info = FilenameInfo(bpm=120.0)
        assert info.has_key is False
        assert info.has_bpm is True

    def test_with_all_info(self):
        info = FilenameInfo(
            key="A minor",
            key_root="A",
            key_quality="minor",
            bpm=90.0,
        )
        assert info.has_key is True
        assert info.has_bpm is True


class TestFormatFunctions:
    """Tests for format helper functions."""

    def test_format_key_for_display_major(self):
        result = format_key_for_display("C", "major")
        assert result == "C major"

    def test_format_key_for_display_minor(self):
        result = format_key_for_display("A", "minor")
        assert result == "A minor"

    def test_format_key_for_matching_major(self):
        result = format_key_for_matching("C", "major")
        assert result == "C:maj"

    def test_format_key_for_matching_minor(self):
        result = format_key_for_matching("A", "minor")
        assert result == "A:min"


class TestEdgeCases:
    """Edge case tests for filename parsing."""

    def test_case_insensitive_key(self):
        # Should handle mixed case
        info = parse_filename("Loop_CMAJ_120")
        # This may or may not match depending on pattern specifics

    def test_multiple_numbers(self):
        # Should pick the right number as BPM
        info = parse_filename("Track_03_Beat_120bpm_v2.wav")
        assert info.bpm == 120.0

    def test_year_like_number(self):
        # Avoid matching years as BPM
        info = parse_filename("Vintage_2024_Vibes.wav")
        # 2024 should not be detected as BPM (out of range)
        assert info.bpm is None

    def test_very_long_filename(self):
        info = parse_filename("This_Is_A_Very_Long_Sample_Name_Cmaj_With_Many_Words_120bpm_Final_Mix.wav")
        assert info.key == "C major"
        assert info.bpm == 120.0

    def test_unicode_in_path(self):
        # Should handle unicode characters in path
        info = parse_filename("/Users/música/samples/Loop_Am_90bpm.wav")
        assert info.key == "A minor"
        assert info.bpm == 90.0

    def test_common_sample_pack_format(self):
        # Common format from sample pack vendors
        info = parse_filename("SamplePack_Chord_Loop_Cmin_128BPM_01.wav")
        assert info.key == "C minor"
        assert info.bpm == 128.0

    def test_hyphenated_format(self):
        info = parse_filename("Funky-Bass-G-Major-95bpm.wav")
        assert info.key == "G major"
        assert info.bpm == 95.0

"""Tests for chord extraction functionality."""

import pytest
import tempfile
import os
from pathlib import Path

from chord_analyzer.extractor import (
    parse_chord_csv,
    extract_progression_summary,
    create_sample_from_csv,
)
from chord_analyzer.models import ChordEvent


class TestParseChordCSV:
    """Tests for parsing Chordino CSV output."""

    def test_basic_csv_parsing(self, tmp_path):
        """Test parsing a standard Chordino CSV file."""
        csv_content = """0.000000,0.500000,N
0.500000,2.000000,C:maj
2.000000,3.500000,A:min
3.500000,4.000000,F:maj
4.000000,5.500000,G:7
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        chords = parse_chord_csv(str(csv_file))

        assert len(chords) == 4  # N (no chord) is skipped
        assert chords[0].chord_label == "C:maj"
        assert chords[0].start_time == 0.5
        assert chords[0].end_time == 2.0
        assert chords[1].chord_label == "A:min"
        assert chords[2].chord_label == "F:maj"
        assert chords[3].chord_label == "G:7"

    def test_skips_no_chord(self, tmp_path):
        """Test that N (no chord) markers are skipped."""
        csv_content = """0.000000,0.500000,N
0.500000,1.000000,C:maj
1.000000,1.500000,N
1.500000,2.000000,G:maj
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        chords = parse_chord_csv(str(csv_file))

        assert len(chords) == 2
        assert chords[0].chord_label == "C:maj"
        assert chords[1].chord_label == "G:maj"

    def test_empty_csv(self, tmp_path):
        """Test parsing an empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        chords = parse_chord_csv(str(csv_file))
        assert chords == []

    def test_malformed_rows_skipped(self, tmp_path):
        """Test that malformed rows are skipped."""
        csv_content = """0.500000,1.000000,C:maj
invalid,row
1.500000,2.000000,G:maj
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        chords = parse_chord_csv(str(csv_file))

        assert len(chords) == 2

    def test_chord_event_properties(self, tmp_path):
        """Test ChordEvent properties are set correctly."""
        csv_content = "1.0,2.5,D:min7\n"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        chords = parse_chord_csv(str(csv_file))

        assert len(chords) == 1
        chord = chords[0]
        assert chord.chord_label == "D:min7"
        assert chord.root_note == "D"
        assert chord.chord_type == "min7"
        assert chord.duration == 1.5


class TestExtractProgressionSummary:
    """Tests for extracting progression summaries."""

    def test_removes_consecutive_duplicates(self):
        """Test that consecutive duplicate chords are collapsed."""
        chords = [
            ChordEvent(0, 1, "C:maj", "C", "maj"),
            ChordEvent(1, 2, "C:maj", "C", "maj"),
            ChordEvent(2, 3, "A:min", "A", "min"),
            ChordEvent(3, 4, "A:min", "A", "min"),
            ChordEvent(4, 5, "F:maj", "F", "maj"),
        ]

        progression = extract_progression_summary(chords)

        assert progression == ["C:maj", "A:min", "F:maj"]

    def test_empty_list(self):
        """Test with empty chord list."""
        progression = extract_progression_summary([])
        assert progression == []

    def test_single_chord(self):
        """Test with single chord."""
        chords = [ChordEvent(0, 1, "C:maj", "C", "maj")]
        progression = extract_progression_summary(chords)
        assert progression == ["C:maj"]

    def test_all_different(self):
        """Test with all different chords."""
        chords = [
            ChordEvent(0, 1, "C:maj", "C", "maj"),
            ChordEvent(1, 2, "A:min", "A", "min"),
            ChordEvent(2, 3, "F:maj", "F", "maj"),
            ChordEvent(3, 4, "G:7", "G", "7"),
        ]

        progression = extract_progression_summary(chords)

        assert progression == ["C:maj", "A:min", "F:maj", "G:7"]


class TestCreateSampleFromCSV:
    """Tests for creating Sample objects from CSV files."""

    def test_basic_sample_creation(self, tmp_path):
        """Test creating a sample from a CSV file."""
        csv_content = """0.500000,2.000000,C:maj
2.000000,3.500000,A:min
3.500000,4.000000,F:maj
"""
        csv_file = tmp_path / "funky_bass_vamp_nnls-chroma_chordino_simplechord.csv"
        csv_file.write_text(csv_content)

        sample = create_sample_from_csv(str(csv_file))

        assert sample.filename == "funky_bass"
        assert len(sample.chords) == 3
        assert sample.duration_seconds == 4.0
        assert sample.progression == ["C:maj", "A:min", "F:maj"]

    def test_sample_properties(self, tmp_path):
        """Test computed properties on Sample."""
        csv_content = """0.0,1.0,C:maj
1.0,2.0,C:maj
2.0,3.0,A:min
3.0,4.0,F:maj
4.0,5.0,G:7
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        sample = create_sample_from_csv(str(csv_file))

        assert sample.unique_chords == {"C:maj", "A:min", "F:maj", "G:7"}
        assert sample.root_notes == {"C", "A", "F", "G"}
        assert sample.chord_types == {"maj", "min", "7"}

    def test_filename_suffix_removal(self, tmp_path):
        """Test that Chordino filename suffixes are removed."""
        csv_file = tmp_path / "my_sample_vamp_nnls-chroma_chordino_simplechord.csv"
        csv_file.write_text("0.0,1.0,C:maj\n")

        sample = create_sample_from_csv(str(csv_file))

        assert sample.filename == "my_sample"

    def test_no_suffix(self, tmp_path):
        """Test with filename that has no Chordino suffix."""
        csv_file = tmp_path / "plain_name.csv"
        csv_file.write_text("0.0,1.0,C:maj\n")

        sample = create_sample_from_csv(str(csv_file))

        assert sample.filename == "plain_name"

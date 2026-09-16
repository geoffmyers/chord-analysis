#!/usr/bin/env python3
"""
Rebuild Splice samples database by matching CSV files with audio files.

This script:
1. Scans the Splice audio directory for all audio files
2. Creates an index of audio files by stem
3. For each CSV file, finds the matching audio file
4. Updates the database with the audio file path instead of CSV path
"""

import argparse
import os
from pathlib import Path
from typing import Dict, Optional, List
import re
from chord_analyzer import init_database, store_sample
from chord_analyzer.extractor import (
    create_sample_from_csv_with_tempo,
    create_sample_from_csv,
)

def normalize_stem(filename: str) -> str:
    """
    Normalize a filename to match different naming conventions.

    Examples:
        "05_113BPM_A#_Perc.wav" -> "05_113bpm_a_perc"
        "Bpm120_F_FtLauderdale" -> "120_f_ftlauderdale"
        "01_111BPM_E_Drop_Pad" -> "01_111bpm_e_drop_pad"
    """
    # Remove common suffixes
    stem = filename.replace("_vamp_nnls-chroma_chordino_simplechord", "")

    # Convert to lowercase
    stem = stem.lower()

    # Remove/normalize musical symbols
    stem = stem.replace("#", "sharp")
    stem = stem.replace("♭", "flat")
    stem = stem.replace("b", "flat")  # Maybe too aggressive?

    # Normalize BPM patterns
    stem = re.sub(r'bpm(\d+)', r'\1bpm', stem)  # Bpm120 -> 120bpm

    # Remove underscores and spaces for matching
    stem = re.sub(r'[_\s-]+', '_', stem)

    return stem

def build_audio_index(audio_dir: Path) -> Dict[str, List[Path]]:
    """
    Build an index of all audio files by their normalized stems.

    Returns:
        Dict mapping normalized stem to list of matching audio file paths
    """
    print(f"Scanning {audio_dir} for audio files...")

    audio_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.aif'}
    audio_files = []

    for ext in audio_extensions:
        audio_files.extend(audio_dir.rglob(f"*{ext}"))

    print(f"Found {len(audio_files)} audio files")

    # Build index
    index = {}
    for audio_file in audio_files:
        # Try both full stem and just the filename
        stems = [
            audio_file.stem,  # Full filename without extension
            normalize_stem(audio_file.stem),  # Normalized version
        ]

        for stem in stems:
            if stem not in index:
                index[stem] = []
            if audio_file not in index[stem]:
                index[stem].append(audio_file)

    print(f"Indexed {len(index)} unique stems")
    return index

def find_audio_for_csv(csv_path: Path, audio_index: Dict[str, List[Path]]) -> Optional[Path]:
    """
    Find the matching audio file for a CSV file.

    Strategy:
    1. Extract stem from CSV filename (remove _vamp_nnls-chroma_chordino_simplechord)
    2. Try exact match in index
    3. Try normalized match
    4. Try fuzzy match (substring)
    """
    # Get CSV stem
    csv_stem = csv_path.stem.replace("_vamp_nnls-chroma_chordino_simplechord", "")

    # Try exact match
    if csv_stem in audio_index:
        matches = audio_index[csv_stem]
        if len(matches) == 1:
            return matches[0]
        # Multiple matches - try to find best one
        # Prefer files with same name, shorter paths
        matches_sorted = sorted(matches, key=lambda p: (len(str(p)), str(p)))
        return matches_sorted[0]

    # Try normalized match
    normalized = normalize_stem(csv_stem)
    if normalized in audio_index:
        matches = audio_index[normalized]
        if matches:
            return matches[0]

    # Try fuzzy match - find stems that contain or are contained by csv_stem
    csv_lower = csv_stem.lower()
    for stem, paths in audio_index.items():
        stem_lower = stem.lower()
        # Skip if stems are too different in length
        if abs(len(csv_lower) - len(stem_lower)) > 20:
            continue
        # Check if one contains the other
        if csv_lower in stem_lower or stem_lower in csv_lower:
            return paths[0]

    return None

def main():
    """Rebuild the Splice samples database."""

    # Configuration. The Splice library lives in a different place on every
    # machine, so it is an argument, not a literal: --audio-dir wins, then
    # SPLICE_AUDIO_DIR, then the default Splice install location.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio-dir",
        default=os.environ.get("SPLICE_AUDIO_DIR", "~/Splice"),
        help="Splice sample library root (default: $SPLICE_AUDIO_DIR, else ~/Splice)",
    )
    parser.add_argument("--csv-dir", default="output/splice-chords",
                        help="Directory of per-sample chord CSVs")
    parser.add_argument("--db-path", default="output/splice-samples.db",
                        help="SQLite database to write")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir).expanduser()
    csv_dir = Path(args.csv_dir)
    db_path = Path(args.db_path)

    if not audio_dir.exists():
        print(f"Error: Audio directory not found: {audio_dir}")
        return 1

    if not csv_dir.exists():
        print(f"Error: CSV directory not found: {csv_dir}")
        return 1

    # Build audio index
    audio_index = build_audio_index(audio_dir)

    # Get all CSV files
    csv_files = list(csv_dir.glob("*.csv"))
    csv_files = [f for f in csv_files if f.name != "chordino.n3"]  # Skip transform file

    print(f"\nProcessing {len(csv_files)} CSV files...")

    # Initialize database
    conn = init_database(str(db_path))

    # Process each CSV
    matched = 0
    unmatched = 0
    tempo_detected = 0

    for i, csv_file in enumerate(csv_files, 1):
        if i % 100 == 0:
            print(f"  Processed {i}/{len(csv_files)} files...")

        # Find matching audio file
        audio_file = find_audio_for_csv(csv_file, audio_index)

        if audio_file:
            matched += 1
            # Use audio file path
            filepath = str(audio_file)
        else:
            unmatched += 1
            # Fall back to CSV path
            filepath = str(csv_file)

        try:
            # Try tempo-aware extraction first (auto_detect=True by default)
            sample = create_sample_from_csv_with_tempo(
                str(csv_file),
                audio_path=filepath,
                auto_detect=True,  # Enable tempo detection from audio/filename
                parse_filename_first=True,  # Try filename first (faster)
                use_enhanced_key_detection=True,  # Also detect key
            )
            if sample.estimated_bpm:
                tempo_detected += 1
        except Exception as e:
            # Fall back to basic extraction
            try:
                sample = create_sample_from_csv(str(csv_file), audio_path=filepath)
            except Exception as e2:
                print(f"\nError processing {csv_file.name}: {e2}")
                continue

        # Add to database
        store_sample(conn, sample)

    conn.commit()
    conn.close()

    print(f"\nDatabase rebuild complete!")
    print(f"  Total samples: {len(csv_files)}")
    print(f"  Matched with audio: {matched} ({matched/len(csv_files)*100:.1f}%)")
    print(f"  CSV-only (no audio found): {unmatched} ({unmatched/len(csv_files)*100:.1f}%)")
    print(f"  Tempo detected: {tempo_detected} ({tempo_detected/len(csv_files)*100:.1f}%)")
    print(f"\nDatabase saved to: {db_path}")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

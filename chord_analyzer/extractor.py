"""
Chord extraction from audio files using Sonic Annotator + Chordino.
"""

import csv
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from .models import ChordEvent, Sample
from .theory import parse_chord_label, estimate_key_from_progression
from .tempo import (
    BeatGrid,
    detect_tempo,
    detect_beats,
    create_beat_grid_from_tempo,
    estimate_tempo_from_chord_timing,
    check_librosa_available,
)
from .filename_parser import parse_filename, FilenameInfo
from .key_detection import (
    detect_key_from_audio,
    detect_key_from_chords,
    detect_scale_from_audio,
    detect_scale_from_chords,
    combine_key_detections,
    KeyDetectionResult,
    ScaleDetectionResult,
    KeyAnalysisResult,
    check_librosa_available as check_librosa_for_key,
)
from .voicing import classify_voicing_simple


def parse_chord_csv(csv_path: str) -> List[ChordEvent]:
    """
    Parse Sonic Annotator chord output CSV into structured data.

    Chordino produces CSV files with the format:
        start_time,end_time,chord_label

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of ChordEvent objects

    Example CSV content:
        0.000000,0.500000,N
        0.500000,2.000000,C:maj
        2.000000,3.500000,A:min
    """
    chords = []

    with open(csv_path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue

            try:
                start = float(row[0])

                # Handle different CSV formats
                if len(row) >= 3:
                    # Format: start, end, chord
                    end = float(row[1]) if row[1] else start + 0.5
                    chord_label = row[2]
                else:
                    # Format: start, chord (no explicit end time)
                    end = start + 0.5  # Default duration
                    chord_label = row[1]

                # Skip silence/no-chord markers
                if not chord_label or chord_label == "N":
                    continue

                root, chord_type = parse_chord_label(chord_label)

                chords.append(
                    ChordEvent(
                        start_time=start,
                        end_time=end,
                        chord_label=chord_label,
                        root_note=root,
                        chord_type=chord_type,
                    )
                )
            except (ValueError, IndexError):
                # Skip malformed rows
                continue

    return chords


def extract_progression_summary(chords: List[ChordEvent]) -> List[str]:
    """
    Extract unique chord sequence, removing repeated consecutive chords.

    Args:
        chords: List of ChordEvent objects

    Returns:
        List of chord labels representing the progression

    Example:
        [C:maj, C:maj, A:min, A:min, F:maj] -> ["C:maj", "A:min", "F:maj"]
    """
    if not chords:
        return []

    progression = [chords[0].chord_label]
    for chord in chords[1:]:
        if chord.chord_label != progression[-1]:
            progression.append(chord.chord_label)

    return progression


def create_sample_from_csv(csv_path: str, audio_path: Optional[str] = None) -> Sample:
    """
    Create a Sample object from a chord CSV file.

    Args:
        csv_path: Path to the Chordino output CSV
        audio_path: Optional path to the original audio file

    Returns:
        Sample object with chord analysis
    """
    csv_path_obj = Path(csv_path)

    # Derive audio filename from CSV name (Chordino adds suffix to filenames)
    # e.g., "funky_bass_vamp_nnls-chroma_chordino_simplechord.csv"
    filename = csv_path_obj.stem
    # Remove Chordino suffix if present
    suffixes_to_remove = [
        "_vamp_nnls-chroma_chordino_simplechord",
        "_vamp_nnls-chroma_chordino_chordnotes",
    ]
    for suffix in suffixes_to_remove:
        if filename.endswith(suffix):
            filename = filename[: -len(suffix)]
            break

    chords = parse_chord_csv(csv_path)

    # Calculate duration from last chord end time
    duration = max(c.end_time for c in chords) if chords else 0.0

    sample = Sample(
        filepath=audio_path or csv_path,
        filename=filename,
        chords=chords,
        duration_seconds=duration,
    )

    # Detect voicing type (monophonic vs polyphonic)
    sample.voicing_type = classify_voicing_simple(sample)

    return sample


def check_sonic_annotator() -> bool:
    """Check if Sonic Annotator is installed and available."""
    return shutil.which("sonic-annotator") is not None


def check_chordino_plugin() -> bool:
    """Check if Chordino VAMP plugin is installed."""
    if not check_sonic_annotator():
        return False

    try:
        result = subprocess.run(
            ["sonic-annotator", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "nnls-chroma:chordino" in result.stdout
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


def generate_transform_file(output_path: str = "chordino.n3") -> bool:
    """
    Generate the Chordino transform file for Sonic Annotator.

    Args:
        output_path: Where to save the transform file

    Returns:
        True if successful
    """
    if not check_sonic_annotator():
        raise RuntimeError("Sonic Annotator is not installed")

    try:
        result = subprocess.run(
            ["sonic-annotator", "-s", "vamp:nnls-chroma:chordino:simplechord"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout:
            with open(output_path, "w") as f:
                f.write(result.stdout)
            return True

        return False
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


def extract_chords_from_audio(
    audio_path: str,
    output_dir: str,
    transform_file: str = "chordino.n3",
) -> Optional[str]:
    """
    Extract chords from a single audio file using Sonic Annotator.

    Args:
        audio_path: Path to the audio file
        output_dir: Directory for CSV output
        transform_file: Path to Chordino transform file

    Returns:
        Path to the generated CSV file, or None if failed
    """
    if not check_sonic_annotator():
        raise RuntimeError("Sonic Annotator is not installed")

    if not Path(transform_file).exists():
        generate_transform_file(transform_file)

    audio_path_obj = Path(audio_path)
    output_dir_obj = Path(output_dir)
    output_dir_obj.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "sonic-annotator",
                "-t",
                transform_file,
                str(audio_path_obj),
                "-w",
                "csv",
                "--csv-basedir",
                str(output_dir_obj),
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per file
        )

        if result.returncode != 0:
            return None

        # Find the generated CSV file
        expected_csv = output_dir_obj / f"{audio_path_obj.stem}_vamp_nnls-chroma_chordino_simplechord.csv"
        if expected_csv.exists():
            return str(expected_csv)

        # Try to find any matching CSV
        for csv_file in output_dir_obj.glob(f"{audio_path_obj.stem}*.csv"):
            return str(csv_file)

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def batch_extract_chords(
    audio_dir: str,
    output_dir: str,
    transform_file: str = "chordino.n3",
    formats: Tuple[str, ...] = ("wav", "mp3", "flac", "aiff", "ogg"),
    recursive: bool = True,
) -> List[Tuple[str, Optional[str]]]:
    """
    Extract chords from all audio files in a directory.

    Args:
        audio_dir: Directory containing audio files
        output_dir: Directory for CSV output
        transform_file: Path to Chordino transform file
        formats: Audio file extensions to process
        recursive: Whether to process subdirectories

    Returns:
        List of (audio_path, csv_path) tuples. csv_path is None if extraction failed.
    """
    audio_dir_obj = Path(audio_dir)
    results = []

    # Collect all audio files
    audio_files = []
    for fmt in formats:
        pattern = f"**/*.{fmt}" if recursive else f"*.{fmt}"
        audio_files.extend(audio_dir_obj.glob(pattern))

    # Process each file
    for audio_file in audio_files:
        csv_path = extract_chords_from_audio(
            str(audio_file),
            output_dir,
            transform_file,
        )
        results.append((str(audio_file), csv_path))

    return results


def apply_beat_grid_to_chords(
    chords: List[ChordEvent],
    beat_grid: BeatGrid,
    subdivision: int = 1,
) -> List[ChordEvent]:
    """
    Apply beat grid timing to chord events.

    Quantizes chord start times to the nearest beat (or subdivision)
    and calculates beat-relative positions.

    Args:
        chords: List of ChordEvent objects
        beat_grid: BeatGrid object for quantization
        subdivision: 1 = quarter notes, 2 = eighth notes, 4 = sixteenths

    Returns:
        List of ChordEvent objects with beat timing filled in
    """
    result = []

    for chord in chords:
        # Quantize start position
        bar, beat = beat_grid.quantize_to_beat(chord.start_time, subdivision)

        # Calculate duration in beats
        duration_seconds = chord.end_time - chord.start_time
        duration_beats = duration_seconds / beat_grid.beat_duration

        # Quantize duration to subdivision
        subdivision_size = 1.0 / subdivision
        duration_beats = round(duration_beats / subdivision_size) * subdivision_size
        duration_beats = max(subdivision_size, duration_beats)  # Minimum one subdivision

        # Create new chord with beat info
        result.append(
            ChordEvent(
                start_time=chord.start_time,
                end_time=chord.end_time,
                chord_label=chord.chord_label,
                root_note=chord.root_note,
                chord_type=chord.chord_type,
                bar=bar,
                beat=beat,
                duration_beats=duration_beats,
            )
        )

    return result


def create_sample_from_csv_with_tempo(
    csv_path: str,
    audio_path: Optional[str] = None,
    bpm: Optional[float] = None,
    time_signature: Tuple[int, int] = (4, 4),
    subdivision: int = 1,
    auto_detect: bool = True,
    parse_filename_first: bool = True,
    use_enhanced_key_detection: bool = True,
) -> Sample:
    """
    Create a Sample object from a chord CSV file with tempo/beat analysis.

    Priority for tempo detection:
    1. Explicit bpm parameter (if provided)
    2. Filename parsing (e.g., "Funky_Bass_120bpm.wav")
    3. librosa audio analysis (if available)
    4. Chord timing estimation (fallback)

    Priority for key detection (with enhanced detection):
    1. Filename parsing (60% weight) - e.g., "Funky_Bass_Cmaj.wav"
    2. Audio chroma analysis (30% weight) - librosa-based
    3. Chord content analysis (10% weight) - derived from chord labels
    Results are combined using weighted voting for robust detection.

    Args:
        csv_path: Path to the Chordino output CSV
        audio_path: Optional path to the original audio file
        bpm: Optional known BPM (overrides all auto-detection)
        time_signature: Time signature tuple (default 4/4)
        subdivision: Beat subdivision for quantization
        auto_detect: Whether to auto-detect tempo if not provided
        parse_filename_first: Whether to try parsing key/bpm from filename first
        use_enhanced_key_detection: Use multi-source key detection with confidence

    Returns:
        Sample object with chord analysis and beat timing
    """
    # Start with basic sample
    sample = create_sample_from_csv(csv_path, audio_path)

    # Priority 1: Parse filename for key and BPM
    filename_info: Optional[FilenameInfo] = None
    filename_key_tuple: Optional[Tuple[str, str, str]] = None

    if parse_filename_first:
        # Try audio path first (more likely to have original naming)
        source_path = audio_path if audio_path else csv_path
        filename_info = parse_filename(source_path)

        if filename_info.has_key:
            filename_key_tuple = (
                filename_info.key,
                filename_info.key_root,
                filename_info.key_quality,
            )

    # Enhanced key detection with multiple sources
    if use_enhanced_key_detection:
        # Get key from audio analysis (if available)
        audio_key_result: Optional[KeyDetectionResult] = None
        if audio_path and check_librosa_for_key():
            audio_key_result = detect_key_from_audio(audio_path)

        # Get key from chord analysis
        chord_key_result: Optional[KeyDetectionResult] = None
        if sample.chords:
            chord_labels = [c.chord_label for c in sample.chords]
            chord_durations = [c.duration for c in sample.chords]
            chord_key_result = detect_key_from_chords(chord_labels, chord_durations)

        # Combine results using weighted voting
        key_analysis = combine_key_detections(
            filename_key=filename_key_tuple,
            audio_result=audio_key_result,
            chord_result=chord_key_result,
        )

        if key_analysis:
            sample.estimated_key = key_analysis.key_result.key
    else:
        # Fallback to simple filename-based detection
        if filename_info and filename_info.has_key:
            sample.estimated_key = filename_info.key
        elif sample.chords:
            # Use simple chord-based estimation
            progression = [c.chord_label for c in sample.chords]
            estimated = estimate_key_from_progression(progression)
            if estimated:
                sample.estimated_key = f"{estimated} major"

    # Determine BPM with priority:
    # 1. Explicit bpm parameter
    # 2. Filename parsing
    # 3. librosa detection
    # 4. Chord timing estimation
    detected_bpm = bpm

    if detected_bpm is None and filename_info and filename_info.has_bpm:
        # Priority 2: Use filename BPM
        detected_bpm = filename_info.bpm

    if detected_bpm is None and auto_detect:
        # Priority 3: Try librosa-based detection if audio path is available
        if audio_path and check_librosa_available():
            detected_bpm = detect_tempo(audio_path)

        # Priority 4: Fallback to chord timing estimation
        if detected_bpm is None and sample.chords:
            chord_times = [
                (c.start_time, c.end_time) for c in sample.chords
            ]
            detected_bpm = estimate_tempo_from_chord_timing(chord_times)

    if detected_bpm:
        sample.estimated_bpm = detected_bpm
        sample.time_signature = time_signature

        # Create beat grid and apply to chords
        beat_grid = create_beat_grid_from_tempo(
            bpm=detected_bpm,
            duration_seconds=sample.duration_seconds,
            first_beat_offset=0.0,
            time_signature=time_signature,
        )

        # Try librosa-based beat detection for better accuracy
        if audio_path and check_librosa_available():
            better_grid = detect_beats(audio_path)
            if better_grid:
                beat_grid = better_grid
                sample.first_beat_offset = better_grid.first_beat_time

        # Apply beat grid to chords
        sample.chords = apply_beat_grid_to_chords(
            sample.chords, beat_grid, subdivision
        )

    # Detect voicing type (monophonic vs polyphonic)
    sample.voicing_type = classify_voicing_simple(sample)

    return sample


def analyze_audio_file(
    audio_path: str,
    output_dir: str = ".",
    transform_file: str = "chordino.n3",
    bpm: Optional[float] = None,
    time_signature: Tuple[int, int] = (4, 4),
    subdivision: int = 1,
    auto_detect_tempo: bool = True,
    parse_filename_first: bool = True,
) -> Optional[Sample]:
    """
    Complete analysis pipeline for a single audio file.

    Extracts chords using Sonic Annotator/Chordino and optionally
    detects tempo and quantizes to beat grid.

    Priority for key/tempo detection:
    1. Explicit bpm parameter (if provided)
    2. Filename parsing (e.g., "Funky_Bass_Cmaj_120bpm.wav")
    3. librosa audio analysis (if available)
    4. Chord timing estimation (fallback)

    Args:
        audio_path: Path to the audio file
        output_dir: Directory for CSV output
        transform_file: Path to Chordino transform file
        bpm: Optional known BPM
        time_signature: Time signature tuple
        subdivision: Beat subdivision for quantization
        auto_detect_tempo: Whether to auto-detect tempo
        parse_filename_first: Whether to try parsing key/bpm from filename first

    Returns:
        Sample object or None if extraction failed
    """
    # Extract chords
    csv_path = extract_chords_from_audio(audio_path, output_dir, transform_file)

    if not csv_path:
        return None

    # Create sample with tempo analysis
    return create_sample_from_csv_with_tempo(
        csv_path=csv_path,
        audio_path=audio_path,
        bpm=bpm,
        time_signature=time_signature,
        subdivision=subdivision,
        auto_detect=auto_detect_tempo,
        parse_filename_first=parse_filename_first,
    )

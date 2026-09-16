"""
Chord Analysis & Sample Compatibility Matcher

A tool for analyzing chord progressions in audio samples and finding
harmonically compatible samples for music production workflows.
"""

__version__ = "0.1.0"
__author__ = "Geoff Myers"

from .models import ChordEvent, Sample, CompatibilityResult
from .theory import (
    NOTE_TO_SEMITONE,
    CHORD_INTERVALS,
    parse_chord_label,
    get_chord_notes,
    get_all_notes_in_progression,
    # Relative/functional harmony
    chord_to_roman_numeral,
    progression_to_numerals,
    get_interval_pattern,
    get_quality_pattern,
    normalize_progression,
    is_transposition,
    get_transposition_interval,
    calculate_functional_similarity,
)
from .extractor import parse_chord_csv, extract_progression_summary
from .database import (
    init_database,
    store_sample,
    get_sample_by_filepath,
    get_all_samples,
    get_sample_count,
    get_samples_page,
    get_samples_metadata_only,
    find_compatible_samples,
)
from .compatibility import (
    calculate_compatibility,
    calculate_compatibility_with_rhythm,
    calculate_rhythm_similarity,
)
from .tempo import (
    BeatGrid,
    ChordBeatPosition,
    detect_tempo,
    detect_beats,
    create_beat_grid_from_tempo,
    quantize_chords_to_beats,
    check_librosa_available,
)
from .filename_parser import (
    FilenameInfo,
    parse_filename,
    parse_key_from_string,
    parse_bpm_from_string,
)
from .key_detection import (
    KeyQuality,
    ScaleMode,
    KeyDetectionResult,
    ScaleDetectionResult,
    KeyAnalysisResult,
    detect_key_from_chroma,
    detect_key_from_audio,
    detect_key_from_chords,
    detect_scale_mode,
    detect_scale_from_audio,
    detect_scale_from_chords,
    combine_key_detections,
    KRUMHANSL_MAJOR,
    KRUMHANSL_MINOR,
    SCALE_TEMPLATES,
)

__all__ = [
    # Models
    "ChordEvent",
    "Sample",
    "CompatibilityResult",
    # Theory - absolute
    "NOTE_TO_SEMITONE",
    "CHORD_INTERVALS",
    "parse_chord_label",
    "get_chord_notes",
    "get_all_notes_in_progression",
    # Theory - relative/functional
    "chord_to_roman_numeral",
    "progression_to_numerals",
    "get_interval_pattern",
    "get_quality_pattern",
    "normalize_progression",
    "is_transposition",
    "get_transposition_interval",
    "calculate_functional_similarity",
    # Extractor
    "parse_chord_csv",
    "extract_progression_summary",
    # Database
    "init_database",
    "store_sample",
    "get_sample_by_filepath",
    "get_all_samples",
    "get_sample_count",
    "get_samples_page",
    "get_samples_metadata_only",
    "find_compatible_samples",
    # Compatibility
    "calculate_compatibility",
    "calculate_compatibility_with_rhythm",
    "calculate_rhythm_similarity",
    # Tempo/Beat
    "BeatGrid",
    "ChordBeatPosition",
    "detect_tempo",
    "detect_beats",
    "create_beat_grid_from_tempo",
    "quantize_chords_to_beats",
    "check_librosa_available",
    # Filename Parsing
    "FilenameInfo",
    "parse_filename",
    "parse_key_from_string",
    "parse_bpm_from_string",
    # Key Detection
    "KeyQuality",
    "ScaleMode",
    "KeyDetectionResult",
    "ScaleDetectionResult",
    "KeyAnalysisResult",
    "detect_key_from_chroma",
    "detect_key_from_audio",
    "detect_key_from_chords",
    "detect_scale_mode",
    "detect_scale_from_audio",
    "detect_scale_from_chords",
    "combine_key_detections",
    "KRUMHANSL_MAJOR",
    "KRUMHANSL_MINOR",
    "SCALE_TEMPLATES",
]

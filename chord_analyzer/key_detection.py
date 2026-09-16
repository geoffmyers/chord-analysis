"""
Enhanced key and scale/mode detection using audio analysis.

Uses librosa chroma features with Krumhansl-Kessler key profiles
for robust key detection, plus scale template matching for mode detection.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum

# Try to import librosa for audio analysis
try:
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

from .theory import (
    NOTE_TO_SEMITONE,
    SEMITONE_TO_NOTE,
    parse_chord_label,
    MAJOR_SCALE_INTERVALS,
)


class KeyQuality(Enum):
    """Key quality (major or minor)."""
    MAJOR = "major"
    MINOR = "minor"


class ScaleMode(Enum):
    """Common scale modes."""
    IONIAN = "ionian"  # Major
    DORIAN = "dorian"
    PHRYGIAN = "phrygian"
    LYDIAN = "lydian"
    MIXOLYDIAN = "mixolydian"
    AEOLIAN = "aeolian"  # Natural minor
    LOCRIAN = "locrian"
    HARMONIC_MINOR = "harmonic_minor"
    MELODIC_MINOR = "melodic_minor"


# Krumhansl-Kessler key profiles
# These represent the "goodness of fit" for each pitch class in a key
# Based on psychological experiments on tonal perception
KRUMHANSL_MAJOR = [
    6.35,  # C (tonic)
    2.23,  # C#
    3.48,  # D
    2.33,  # D#
    4.38,  # E
    4.09,  # F
    2.52,  # F#
    5.19,  # G
    2.39,  # G#
    3.66,  # A
    2.29,  # A#
    2.88,  # B
]

KRUMHANSL_MINOR = [
    6.33,  # C (tonic)
    2.68,  # C#
    3.52,  # D
    5.38,  # D# (minor 3rd - important)
    2.60,  # E
    3.53,  # F
    2.54,  # F#
    4.75,  # G (5th)
    3.98,  # G#
    2.69,  # A
    3.34,  # A#
    3.17,  # B
]

# Alternative: Temperley key profiles (slightly different weights)
TEMPERLEY_MAJOR = [
    5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0
]

TEMPERLEY_MINOR = [
    5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0
]


# Scale templates as interval patterns from root (in semitones)
SCALE_TEMPLATES = {
    ScaleMode.IONIAN: [0, 2, 4, 5, 7, 9, 11],          # Major
    ScaleMode.DORIAN: [0, 2, 3, 5, 7, 9, 10],          # Minor with raised 6th
    ScaleMode.PHRYGIAN: [0, 1, 3, 5, 7, 8, 10],        # Minor with flat 2nd
    ScaleMode.LYDIAN: [0, 2, 4, 6, 7, 9, 11],          # Major with raised 4th
    ScaleMode.MIXOLYDIAN: [0, 2, 4, 5, 7, 9, 10],      # Major with flat 7th
    ScaleMode.AEOLIAN: [0, 2, 3, 5, 7, 8, 10],         # Natural minor
    ScaleMode.LOCRIAN: [0, 1, 3, 5, 6, 8, 10],         # Diminished scale
    ScaleMode.HARMONIC_MINOR: [0, 2, 3, 5, 7, 8, 11],  # Minor with raised 7th
    ScaleMode.MELODIC_MINOR: [0, 2, 3, 5, 7, 9, 11],   # Minor with raised 6th and 7th
}


@dataclass
class KeyDetectionResult:
    """Result of key detection with confidence scores."""

    key: str  # e.g., "C major", "A minor"
    root: str  # e.g., "C", "A"
    quality: KeyQuality
    confidence: float  # 0.0 to 1.0

    # Alternative keys with their scores
    alternatives: List[Tuple[str, float]] = field(default_factory=list)

    # Detection method used
    method: str = "unknown"

    # Correlation scores for diagnostics
    correlation_major: Optional[float] = None
    correlation_minor: Optional[float] = None

    def __str__(self) -> str:
        return f"{self.key} ({self.confidence:.1%} confidence)"

    @property
    def key_for_matching(self) -> str:
        """Key in Chordino format for matching (e.g., 'C:maj')."""
        quality_suffix = "maj" if self.quality == KeyQuality.MAJOR else "min"
        return f"{self.root}:{quality_suffix}"


@dataclass
class ScaleDetectionResult:
    """Result of scale/mode detection."""

    mode: ScaleMode
    root: str
    confidence: float  # 0.0 to 1.0

    # Notes in this scale
    scale_notes: List[str] = field(default_factory=list)

    # Alternative modes with their scores
    alternatives: List[Tuple[ScaleMode, float]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.root} {self.mode.value} ({self.confidence:.1%})"

    @property
    def display_name(self) -> str:
        """Human-readable scale name."""
        return f"{self.root} {self.mode.value.replace('_', ' ').title()}"


@dataclass
class KeyAnalysisResult:
    """Combined key and scale analysis result."""

    key_result: KeyDetectionResult
    scale_result: Optional[ScaleDetectionResult] = None

    # Source of detection
    source: str = "audio"  # "audio", "chords", "filename", "combined"

    # Weighted confidence from all sources
    overall_confidence: float = 0.0

    def __str__(self) -> str:
        if self.scale_result:
            return f"{self.key_result.key} ({self.scale_result.mode.value})"
        return str(self.key_result)


def _rotate_profile(profile: List[float], semitones: int) -> List[float]:
    """Rotate a key profile by a number of semitones."""
    return profile[-semitones:] + profile[:-semitones]


def _correlate(chroma: List[float], profile: List[float]) -> float:
    """Calculate Pearson correlation between chroma and key profile."""
    if not LIBROSA_AVAILABLE:
        # Fallback to simple dot product normalized
        sum_chroma = sum(chroma)
        sum_profile = sum(profile)
        if sum_chroma == 0 or sum_profile == 0:
            return 0.0
        norm_chroma = [c / sum_chroma for c in chroma]
        norm_profile = [p / sum_profile for p in profile]
        return sum(c * p for c, p in zip(norm_chroma, norm_profile))

    chroma_arr = np.array(chroma)
    profile_arr = np.array(profile)

    # Normalize
    chroma_norm = chroma_arr - np.mean(chroma_arr)
    profile_norm = profile_arr - np.mean(profile_arr)

    # Correlation
    numerator = np.sum(chroma_norm * profile_norm)
    denominator = np.sqrt(np.sum(chroma_norm**2) * np.sum(profile_norm**2))

    if denominator == 0:
        return 0.0

    return float(numerator / denominator)


def detect_key_from_chroma(
    chroma: List[float],
    use_temperley: bool = False,
) -> KeyDetectionResult:
    """
    Detect key from a chroma (pitch class) histogram.

    Uses Krumhansl-Kessler or Temperley key profiles to find the
    best matching key via correlation.

    Args:
        chroma: 12-element list of pitch class intensities (C, C#, D, ...)
        use_temperley: Use Temperley profiles instead of Krumhansl

    Returns:
        KeyDetectionResult with detected key and confidence
    """
    if len(chroma) != 12:
        raise ValueError(f"Chroma must have 12 elements, got {len(chroma)}")

    # Select profiles
    major_profile = TEMPERLEY_MAJOR if use_temperley else KRUMHANSL_MAJOR
    minor_profile = TEMPERLEY_MINOR if use_temperley else KRUMHANSL_MINOR

    # Test all 24 keys (12 major + 12 minor)
    scores = []

    for semitone in range(12):
        root = SEMITONE_TO_NOTE[semitone]

        # Rotate chroma to put this root at position 0
        rotated_chroma = chroma[-semitone:] + chroma[:-semitone] if semitone > 0 else chroma

        # Correlate with major and minor profiles
        major_corr = _correlate(rotated_chroma, major_profile)
        minor_corr = _correlate(rotated_chroma, minor_profile)

        scores.append((f"{root} major", root, KeyQuality.MAJOR, major_corr))
        scores.append((f"{root} minor", root, KeyQuality.MINOR, minor_corr))

    # Sort by correlation score
    scores.sort(key=lambda x: x[3], reverse=True)

    # Best match
    best_key, best_root, best_quality, best_score = scores[0]

    # Convert correlation to confidence (correlation ranges from -1 to 1)
    # Map to 0-1 range, with higher values for strong correlations
    confidence = (best_score + 1) / 2  # Simple linear mapping
    confidence = max(0.0, min(1.0, confidence))  # Clamp

    # Get alternatives (top 5)
    alternatives = [(s[0], (s[3] + 1) / 2) for s in scores[1:6]]

    # Get major/minor correlations for the detected root
    root_semitone = NOTE_TO_SEMITONE[best_root]
    rotated = chroma[-root_semitone:] + chroma[:-root_semitone] if root_semitone > 0 else chroma

    return KeyDetectionResult(
        key=best_key,
        root=best_root,
        quality=best_quality,
        confidence=confidence,
        alternatives=alternatives,
        method="chroma_correlation",
        correlation_major=_correlate(rotated, major_profile),
        correlation_minor=_correlate(rotated, minor_profile),
    )


def detect_key_from_audio(
    audio_path: str,
    use_temperley: bool = False,
) -> Optional[KeyDetectionResult]:
    """
    Detect key from an audio file using chroma analysis.

    Args:
        audio_path: Path to the audio file
        use_temperley: Use Temperley profiles instead of Krumhansl

    Returns:
        KeyDetectionResult or None if detection failed
    """
    if not LIBROSA_AVAILABLE:
        return None

    try:
        # Load audio
        y, sr = librosa.load(audio_path, sr=None)

        # Extract chroma features
        # Use CQT-based chroma for better pitch accuracy
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Average across time to get overall pitch class distribution
        chroma_avg = np.mean(chroma, axis=1).tolist()

        result = detect_key_from_chroma(chroma_avg, use_temperley)
        result.method = "audio_chroma"

        return result
    except Exception:
        return None


def detect_key_from_chords(
    chord_labels: List[str],
    chord_durations: Optional[List[float]] = None,
) -> Optional[KeyDetectionResult]:
    """
    Detect key from a list of chord labels.

    Uses weighted pitch class histogram based on chord content.

    Args:
        chord_labels: List of chord labels (e.g., ["C:maj", "A:min", "F:maj"])
        chord_durations: Optional durations for each chord (for weighting)

    Returns:
        KeyDetectionResult or None if detection failed
    """
    if not chord_labels:
        return None

    # Build pitch class histogram from chords
    chroma = [0.0] * 12

    # Filter out "N" (no chord) labels
    valid_chords = [(c, d) for c, d in zip(
        chord_labels,
        chord_durations if chord_durations else [1.0] * len(chord_labels)
    ) if c.upper() != "N"]

    if not valid_chords:
        return None

    for chord_label, duration in valid_chords:
        root, chord_type = parse_chord_label(chord_label)
        if root not in NOTE_TO_SEMITONE:
            continue

        root_semitone = NOTE_TO_SEMITONE[root]

        # Add root note with high weight
        chroma[root_semitone] += 2.0 * duration

        # Add chord tones with lower weight
        # Determine intervals based on chord type
        if chord_type in ("min", "min7", "min9", "min6"):
            # Minor chord: root, minor 3rd, 5th
            chroma[(root_semitone + 3) % 12] += 1.0 * duration
            chroma[(root_semitone + 7) % 12] += 1.0 * duration
        elif chord_type in ("dim", "dim7", "hdim7"):
            # Diminished: root, minor 3rd, diminished 5th
            chroma[(root_semitone + 3) % 12] += 1.0 * duration
            chroma[(root_semitone + 6) % 12] += 1.0 * duration
        elif chord_type in ("aug", "aug7"):
            # Augmented: root, major 3rd, augmented 5th
            chroma[(root_semitone + 4) % 12] += 1.0 * duration
            chroma[(root_semitone + 8) % 12] += 1.0 * duration
        else:
            # Major chord: root, major 3rd, 5th
            chroma[(root_semitone + 4) % 12] += 1.0 * duration
            chroma[(root_semitone + 7) % 12] += 1.0 * duration

        # Add 7th if present
        if "7" in chord_type:
            if chord_type == "maj7":
                chroma[(root_semitone + 11) % 12] += 0.5 * duration
            else:
                chroma[(root_semitone + 10) % 12] += 0.5 * duration

    result = detect_key_from_chroma(chroma)
    result.method = "chord_analysis"

    return result


def detect_scale_mode(
    chroma: List[float],
    key_root: str,
) -> Optional[ScaleDetectionResult]:
    """
    Detect the scale/mode from chroma and a known key root.

    Args:
        chroma: 12-element pitch class histogram
        key_root: Known root note (e.g., "C", "G")

    Returns:
        ScaleDetectionResult or None if detection failed
    """
    if len(chroma) != 12:
        return None

    if key_root not in NOTE_TO_SEMITONE:
        return None

    root_semitone = NOTE_TO_SEMITONE[key_root]

    # Rotate chroma to put root at position 0
    if root_semitone > 0:
        rotated_chroma = chroma[-root_semitone:] + chroma[:-root_semitone]
    else:
        rotated_chroma = chroma

    # Test each scale template
    scores = []

    for mode, intervals in SCALE_TEMPLATES.items():
        # Create a template from intervals
        template = [0.0] * 12
        for interval in intervals:
            template[interval] = 1.0

        # Calculate weighted overlap
        score = 0.0
        total_chroma = sum(rotated_chroma)

        if total_chroma > 0:
            for i in range(12):
                if template[i] > 0:
                    score += rotated_chroma[i] / total_chroma

        scores.append((mode, score))

    # Sort by score
    scores.sort(key=lambda x: x[1], reverse=True)

    best_mode, best_score = scores[0]

    # Get scale notes
    scale_notes = []
    for interval in SCALE_TEMPLATES[best_mode]:
        note_semitone = (root_semitone + interval) % 12
        scale_notes.append(SEMITONE_TO_NOTE[note_semitone])

    return ScaleDetectionResult(
        mode=best_mode,
        root=key_root,
        confidence=best_score,
        scale_notes=scale_notes,
        alternatives=[(m, s) for m, s in scores[1:4]],
    )


def detect_scale_from_audio(
    audio_path: str,
    key_root: Optional[str] = None,
) -> Optional[ScaleDetectionResult]:
    """
    Detect scale/mode from audio file.

    If key_root is not provided, will first detect the key.

    Args:
        audio_path: Path to audio file
        key_root: Optional known root note

    Returns:
        ScaleDetectionResult or None if detection failed
    """
    if not LIBROSA_AVAILABLE:
        return None

    try:
        y, sr = librosa.load(audio_path, sr=None)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1).tolist()

        # Detect key if not provided
        if key_root is None:
            key_result = detect_key_from_chroma(chroma_avg)
            key_root = key_result.root

        return detect_scale_mode(chroma_avg, key_root)
    except Exception:
        return None


def detect_scale_from_chords(
    chord_labels: List[str],
    key_root: Optional[str] = None,
    chord_durations: Optional[List[float]] = None,
) -> Optional[ScaleDetectionResult]:
    """
    Detect scale/mode from chord labels.

    Args:
        chord_labels: List of chord labels
        key_root: Optional known root note
        chord_durations: Optional durations for weighting

    Returns:
        ScaleDetectionResult or None if detection failed
    """
    if not chord_labels:
        return None

    # Build chroma from chords
    chroma = [0.0] * 12
    valid_chords = [(c, d) for c, d in zip(
        chord_labels,
        chord_durations if chord_durations else [1.0] * len(chord_labels)
    ) if c.upper() != "N"]

    if not valid_chords:
        return None

    for chord_label, duration in valid_chords:
        root, chord_type = parse_chord_label(chord_label)
        if root not in NOTE_TO_SEMITONE:
            continue

        root_semitone = NOTE_TO_SEMITONE[root]

        # Add all chord tones
        chroma[root_semitone] += duration

        if chord_type in ("min", "min7", "min9", "min6"):
            chroma[(root_semitone + 3) % 12] += duration
            chroma[(root_semitone + 7) % 12] += duration
        elif chord_type in ("dim", "dim7"):
            chroma[(root_semitone + 3) % 12] += duration
            chroma[(root_semitone + 6) % 12] += duration
        else:
            chroma[(root_semitone + 4) % 12] += duration
            chroma[(root_semitone + 7) % 12] += duration

        if "7" in chord_type:
            if chord_type == "maj7":
                chroma[(root_semitone + 11) % 12] += duration * 0.5
            else:
                chroma[(root_semitone + 10) % 12] += duration * 0.5

    # Detect key if not provided
    if key_root is None:
        key_result = detect_key_from_chroma(chroma)
        if key_result:
            key_root = key_result.root
        else:
            return None

    return detect_scale_mode(chroma, key_root)


def combine_key_detections(
    filename_key: Optional[Tuple[str, str, str]],  # (key, root, quality)
    audio_result: Optional[KeyDetectionResult],
    chord_result: Optional[KeyDetectionResult],
    filename_weight: float = 0.6,
    audio_weight: float = 0.3,
    chord_weight: float = 0.1,
) -> Optional[KeyAnalysisResult]:
    """
    Combine key detection results from multiple sources.

    Filename detection always takes absolute priority when available, as it
    represents explicit human labeling. Audio and chord analysis are only used
    when no filename key is found.

    Args:
        filename_key: Tuple from filename parsing (key, root, quality)
        audio_result: Result from audio analysis
        chord_result: Result from chord analysis
        filename_weight: Weight for filename-based detection (default 0.6)
        audio_weight: Weight for audio-based detection (default 0.3)
        chord_weight: Weight for chord-based detection (default 0.1)

    Returns:
        Combined KeyAnalysisResult or None if no detection available
    """
    # ALWAYS use filename key if available (absolute priority)
    if filename_key and filename_key[0]:
        key, root, quality = filename_key
        quality_enum = KeyQuality.MAJOR if quality == "major" else KeyQuality.MINOR

        # Filename key always wins - return immediately
        return KeyAnalysisResult(
            key_result=KeyDetectionResult(
                key=key,
                root=root,
                quality=quality_enum,
                confidence=1.0,  # 100% confident in explicit filename labels
                method="filename",
            ),
            source="filename",
            overall_confidence=1.0,
        )

    # Only use audio/chord analysis if no filename key was found
    candidates: Dict[str, float] = {}  # key -> weighted score
    sources: Dict[str, List[str]] = {}  # key -> list of sources

    # Process audio result
    if audio_result:
        score = audio_weight * audio_result.confidence
        if audio_result.key in candidates:
            candidates[audio_result.key] += score
            sources[audio_result.key].append("audio")
        else:
            candidates[audio_result.key] = score
            sources[audio_result.key] = ["audio"]

    # Process chord result
    if chord_result:
        score = chord_weight * chord_result.confidence
        if chord_result.key in candidates:
            candidates[chord_result.key] += score
            sources[chord_result.key].append("chords")
        else:
            candidates[chord_result.key] = score
            sources[chord_result.key] = ["chords"]

    if not candidates:
        return None

    # Find best candidate
    best_key = max(candidates.keys(), key=lambda k: candidates[k])
    best_score = candidates[best_key]
    best_sources = sources[best_key]

    # Parse best key to components
    parts = best_key.split()
    root = parts[0]
    quality = KeyQuality.MAJOR if "major" in best_key.lower() else KeyQuality.MINOR

    # Normalize confidence to 0-1
    max_possible = filename_weight + audio_weight + chord_weight
    overall_confidence = min(1.0, best_score / max_possible)

    # Boost confidence if multiple sources agree
    if len(best_sources) > 1:
        overall_confidence = min(1.0, overall_confidence * 1.2)

    # Get source string
    source = "combined" if len(best_sources) > 1 else best_sources[0]

    return KeyAnalysisResult(
        key_result=KeyDetectionResult(
            key=best_key,
            root=root,
            quality=quality,
            confidence=overall_confidence,
            method=f"combined_{'+'.join(best_sources)}",
        ),
        source=source,
        overall_confidence=overall_confidence,
    )


def check_librosa_available() -> bool:
    """Check if librosa is available for audio analysis."""
    return LIBROSA_AVAILABLE

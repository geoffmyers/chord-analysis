"""
Voicing detection for audio samples.

Determines whether a sample is monophonic (single notes) or polyphonic
(multiple simultaneous notes/chords) based on chord analysis.
"""

from enum import Enum
from typing import List, Set
from dataclasses import dataclass

from .models import Sample, ChordEvent


class VoicingType(Enum):
    """Classification of sample voicing."""

    MONOPHONIC = "monophonic"      # Single notes (bass, lead, vocal)
    POLYPHONIC = "polyphonic"      # Multiple simultaneous notes (chords, harmonies)
    AMBIGUOUS = "ambiguous"        # Unclear or mixed content
    UNKNOWN = "unknown"            # No chord data available


# Chord types that indicate polyphonic content
POLYPHONIC_CHORD_TYPES = {
    # Triads and basic chords
    "maj", "min", "m", "dim", "aug",

    # 7th chords
    "maj7", "min7", "m7", "dom7", "7", "dim7", "hdim7", "m7b5",

    # Extended chords
    "maj9", "min9", "m9", "9", "maj11", "min11", "m11", "11",
    "maj13", "min13", "m13", "13",

    # Suspended and added tone chords
    "sus2", "sus4", "sus", "add9", "add11", "6", "maj6", "min6", "m6",

    # Altered chords
    "7b5", "7#5", "7b9", "7#9", "alt",
}


# Chord types that might indicate monophonic content or silence
AMBIGUOUS_CHORD_TYPES = {
    "N",  # No chord / silence
    "X",  # Unknown
}


@dataclass
class VoicingAnalysis:
    """Result of voicing detection analysis."""

    voicing_type: VoicingType
    confidence: float  # 0.0 to 1.0
    polyphonic_ratio: float  # Ratio of polyphonic chords
    total_chord_types: int  # Number of unique chord types
    reasons: List[str]  # Human-readable reasons for classification


def detect_voicing_type(sample: Sample) -> VoicingAnalysis:
    """
    Detect whether a sample is monophonic or polyphonic.

    Analysis is based on:
    1. Chord type complexity (7ths, 9ths, etc. indicate polyphony)
    2. Number of unique chord types (variety suggests polyphony)
    3. Presence of "N" (no chord) events
    4. Overall harmonic content

    Args:
        sample: Sample with chord analysis data

    Returns:
        VoicingAnalysis with classification and confidence
    """
    reasons = []

    # No chord data - unknown
    if not sample.chords:
        return VoicingAnalysis(
            voicing_type=VoicingType.UNKNOWN,
            confidence=0.0,
            polyphonic_ratio=0.0,
            total_chord_types=0,
            reasons=["No chord data available"]
        )

    # Analyze chord types
    chord_types: Set[str] = sample.chord_types
    total_chord_types = len(chord_types)

    # Count polyphonic vs ambiguous chords by duration
    polyphonic_duration = 0.0
    ambiguous_duration = 0.0
    total_duration = 0.0

    for chord in sample.chords:
        duration = chord.duration
        total_duration += duration

        if chord.chord_type in POLYPHONIC_CHORD_TYPES:
            polyphonic_duration += duration
        elif chord.chord_type in AMBIGUOUS_CHORD_TYPES:
            ambiguous_duration += duration

    # Calculate ratios
    polyphonic_ratio = polyphonic_duration / total_duration if total_duration > 0 else 0.0
    ambiguous_ratio = ambiguous_duration / total_duration if total_duration > 0 else 0.0

    # Check for complex chord types (7ths, 9ths, etc.)
    has_complex_chords = any(
        any(ext in chord_type for ext in ["7", "9", "11", "13", "sus", "add", "dim", "aug"])
        for chord_type in chord_types
        if chord_type not in AMBIGUOUS_CHORD_TYPES
    )

    # Classification logic
    confidence = 0.0
    voicing_type = VoicingType.AMBIGUOUS

    # High polyphonic content
    if polyphonic_ratio >= 0.7:
        voicing_type = VoicingType.POLYPHONIC
        confidence = min(1.0, polyphonic_ratio)
        reasons.append(f"{polyphonic_ratio*100:.1f}% polyphonic chord content")

        if has_complex_chords:
            reasons.append("Contains complex chords (7ths, extensions)")
            confidence = min(1.0, confidence + 0.2)

        if total_chord_types >= 3:
            reasons.append(f"{total_chord_types} unique chord types")

    # High ambiguous/silence content (might be monophonic or percussion)
    elif ambiguous_ratio >= 0.7:
        voicing_type = VoicingType.MONOPHONIC
        confidence = min(0.6, ambiguous_ratio)  # Lower confidence for "N" chords
        reasons.append(f"{ambiguous_ratio*100:.1f}% silence/no chord detected")
        reasons.append("Likely monophonic or percussion")

    # Low polyphonic content suggests monophonic
    elif polyphonic_ratio < 0.3:
        voicing_type = VoicingType.MONOPHONIC
        confidence = 1.0 - polyphonic_ratio
        reasons.append(f"Low polyphonic content ({polyphonic_ratio*100:.1f}%)")

        if total_chord_types <= 2:
            reasons.append(f"Simple harmonic content ({total_chord_types} chord types)")

    # Mixed content or moderate polyphony
    else:
        voicing_type = VoicingType.AMBIGUOUS
        confidence = 0.5
        reasons.append(f"Mixed content ({polyphonic_ratio*100:.1f}% polyphonic)")

        # Lean towards polyphonic if complex chords present
        if has_complex_chords:
            voicing_type = VoicingType.POLYPHONIC
            confidence = 0.7
            reasons.append("Complex chords suggest polyphonic content")

    return VoicingAnalysis(
        voicing_type=voicing_type,
        confidence=confidence,
        polyphonic_ratio=polyphonic_ratio,
        total_chord_types=total_chord_types,
        reasons=reasons
    )


def classify_voicing_simple(sample: Sample) -> str:
    """
    Simple classification returning just the voicing type string.

    Args:
        sample: Sample with chord analysis data

    Returns:
        One of: "monophonic", "polyphonic", "ambiguous", "unknown"
    """
    analysis = detect_voicing_type(sample)
    return analysis.voicing_type.value

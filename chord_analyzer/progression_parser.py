"""
Parser for user-provided chord progressions.

Supports multiple input formats:
- JSON: Full specification with metadata
- Shorthand: "Cmaj7:4 Am7:4 Fmaj7:2 G7:2" (chord:beats)
- Bar notation: "Cmaj7|Am7|Fmaj7|G7" (one chord per bar)
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .models import UserChordSpec, UserProgression
from .theory import parse_chord_label, NOTE_TO_SEMITONE


def parse_progression_json(json_str: str) -> UserProgression:
    """
    Parse a chord progression from JSON format.

    Expected JSON format:
    {
        "bpm": 120,
        "time_signature": "4/4",
        "name": "My Progression",
        "chords": [
            {"root": "C", "quality": "maj7", "duration_beats": 4},
            {"root": "A", "quality": "min7", "duration_beats": 4},
            {"root": "F", "quality": "maj7", "duration_beats": 2},
            {"root": "G", "quality": "7", "duration_beats": 2}
        ]
    }

    Args:
        json_str: JSON string containing progression data

    Returns:
        UserProgression object

    Raises:
        ValueError: If JSON is invalid or missing required fields
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    return UserProgression.from_dict(data)


def parse_progression_file(filepath: str) -> UserProgression:
    """
    Parse a chord progression from a JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        UserProgression object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Progression file not found: {filepath}")

    content = path.read_text()
    return parse_progression_json(content)


def parse_progression_shorthand(
    shorthand: str,
    bpm: float,
    time_signature: Tuple[int, int] = (4, 4),
    name: Optional[str] = None,
) -> UserProgression:
    """
    Parse a chord progression from shorthand notation.

    Format: "ChordLabel:beats ChordLabel:beats ..."
    Examples:
        "Cmaj7:4 Am7:4 Fmaj7:2 G7:2"
        "C:maj:4 A:min:4"  # With colon separator
        "Cmaj7:4, Am7:4"   # With comma separators
        "Dm7:8 G7:8 Cmaj7:16"  # Various durations

    The chord label can be in any of these formats:
    - "Cmaj7" (compact)
    - "C:maj7" (with colon)
    - "C" (just root, defaults to major)

    Args:
        shorthand: Shorthand string
        bpm: Tempo in beats per minute
        time_signature: Time signature as (numerator, denominator)
        name: Optional name for the progression

    Returns:
        UserProgression object

    Raises:
        ValueError: If shorthand format is invalid
    """
    if not shorthand or not shorthand.strip():
        raise ValueError("Empty progression shorthand")

    # Normalize separators
    normalized = shorthand.strip()
    normalized = re.sub(r"[,;]+", " ", normalized)  # Replace , ; with space
    normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace

    chords = []
    tokens = normalized.split(" ")

    for token in tokens:
        if not token:
            continue

        chord_spec = _parse_shorthand_token(token)
        if chord_spec:
            chords.append(chord_spec)

    if not chords:
        raise ValueError(f"No valid chords found in shorthand: {shorthand}")

    return UserProgression(
        chords=chords,
        bpm=bpm,
        time_signature=time_signature,
        name=name,
    )


def _parse_shorthand_token(token: str) -> Optional[UserChordSpec]:
    """
    Parse a single chord:duration token from shorthand notation.

    Supported formats:
    - "Cmaj7:4" (chord:beats)
    - "C:maj7:4" (root:quality:beats)
    - "Am:4" (compact with duration)
    - "Cmaj7" (no duration, defaults to 4 beats)

    Args:
        token: Single chord token

    Returns:
        UserChordSpec or None if invalid
    """
    if not token:
        return None

    # Split by colon to separate components
    parts = token.split(":")

    if len(parts) == 1:
        # No colon: "Cmaj7" or "Am" - default to 4 beats
        chord_label = parts[0]
        duration = 4.0
    elif len(parts) == 2:
        # Two parts: could be "Cmaj7:4" or "C:maj"
        if _is_number(parts[1]):
            # "Cmaj7:4" format
            chord_label = parts[0]
            duration = float(parts[1])
        else:
            # "C:maj" format - default duration
            chord_label = f"{parts[0]}:{parts[1]}"
            duration = 4.0
    elif len(parts) == 3:
        # "C:maj7:4" format
        chord_label = f"{parts[0]}:{parts[1]}"
        duration = float(parts[2]) if _is_number(parts[2]) else 4.0
    else:
        # Too many colons
        return None

    # Parse the chord label to extract root and quality
    root, quality = parse_chord_label(chord_label)

    if not root or root not in NOTE_TO_SEMITONE:
        return None

    return UserChordSpec(
        root=root,
        quality=quality,
        duration_beats=duration,
    )


def _is_number(s: str) -> bool:
    """Check if a string represents a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def parse_progression_bars(
    bar_notation: str,
    bpm: float,
    time_signature: Tuple[int, int] = (4, 4),
    name: Optional[str] = None,
) -> UserProgression:
    """
    Parse a chord progression from bar notation.

    Each bar is separated by "|" and contains one chord that lasts the full bar.

    Format: "Chord|Chord|Chord|Chord"
    Examples:
        "Cmaj7|Am7|Fmaj7|G7"  # One chord per bar
        "C|Am|F|G"            # Simple notation
        "Dm7|G7|Cmaj7|Cmaj7"  # Repeated chord

    Args:
        bar_notation: Bar notation string
        bpm: Tempo in beats per minute
        time_signature: Time signature as (numerator, denominator)
        name: Optional name for the progression

    Returns:
        UserProgression object

    Raises:
        ValueError: If bar notation is invalid
    """
    if not bar_notation or not bar_notation.strip():
        raise ValueError("Empty bar notation")

    beats_per_bar = time_signature[0]
    bars = bar_notation.strip().split("|")
    chords = []

    for bar in bars:
        bar = bar.strip()
        if not bar:
            continue

        root, quality = parse_chord_label(bar)
        if not root or root not in NOTE_TO_SEMITONE:
            raise ValueError(f"Invalid chord in bar notation: {bar}")

        chords.append(UserChordSpec(
            root=root,
            quality=quality,
            duration_beats=float(beats_per_bar),
        ))

    if not chords:
        raise ValueError(f"No valid chords found in bar notation: {bar_notation}")

    return UserProgression(
        chords=chords,
        bpm=bpm,
        time_signature=time_signature,
        name=name,
    )


def parse_progression_auto(
    input_str: str,
    bpm: float,
    time_signature: Tuple[int, int] = (4, 4),
    name: Optional[str] = None,
) -> UserProgression:
    """
    Automatically detect and parse progression format.

    Detects format based on input characteristics:
    - Contains '{' -> JSON format
    - Contains '|' -> Bar notation
    - Otherwise -> Shorthand notation

    Args:
        input_str: Input string in any supported format
        bpm: Tempo in beats per minute
        time_signature: Time signature as (numerator, denominator)
        name: Optional name for the progression

    Returns:
        UserProgression object

    Raises:
        ValueError: If input cannot be parsed
    """
    input_str = input_str.strip()

    if not input_str:
        raise ValueError("Empty progression input")

    # Detect JSON format
    if input_str.startswith("{"):
        prog = parse_progression_json(input_str)
        # Override BPM and time signature if specified
        if bpm:
            prog = UserProgression(
                chords=prog.chords,
                bpm=bpm,
                time_signature=time_signature,
                name=name or prog.name,
            )
        return prog

    # Detect bar notation
    if "|" in input_str:
        return parse_progression_bars(input_str, bpm, time_signature, name)

    # Default to shorthand notation
    return parse_progression_shorthand(input_str, bpm, time_signature, name)


def validate_progression(progression: UserProgression) -> List[str]:
    """
    Validate a chord progression and return any warnings.

    Checks for:
    - Empty progression
    - Invalid chord labels
    - Very short durations
    - BPM out of reasonable range

    Args:
        progression: UserProgression to validate

    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []

    if not progression.chords:
        warnings.append("Progression has no chords")
        return warnings

    # Check BPM range
    if progression.bpm < 20:
        warnings.append(f"BPM ({progression.bpm}) is very slow")
    elif progression.bpm > 300:
        warnings.append(f"BPM ({progression.bpm}) is very fast")

    # Check each chord
    for i, chord in enumerate(progression.chords):
        # Validate root note
        if chord.root not in NOTE_TO_SEMITONE:
            warnings.append(f"Chord {i + 1}: Invalid root note '{chord.root}'")

        # Check duration
        if chord.duration_beats <= 0:
            warnings.append(f"Chord {i + 1}: Invalid duration ({chord.duration_beats})")
        elif chord.duration_beats < 0.5:
            warnings.append(f"Chord {i + 1}: Very short duration ({chord.duration_beats} beats)")

    # Check total progression length
    total_beats = progression.total_beats
    if total_beats < 4:
        warnings.append(f"Progression is very short ({total_beats} beats)")
    elif total_beats > 256:
        warnings.append(f"Progression is very long ({total_beats} beats)")

    return warnings


def progression_to_shorthand(progression: UserProgression) -> str:
    """
    Convert a UserProgression back to shorthand notation.

    Args:
        progression: UserProgression to convert

    Returns:
        Shorthand string representation
    """
    parts = []
    for chord in progression.chords:
        # Use integer if duration is a whole number
        duration_str = (
            str(int(chord.duration_beats))
            if chord.duration_beats == int(chord.duration_beats)
            else str(chord.duration_beats)
        )
        parts.append(f"{chord.chord_label}:{duration_str}")

    return " ".join(parts)


def progression_to_bars(progression: UserProgression) -> str:
    """
    Convert a UserProgression to bar notation (if possible).

    Only works well if all chords have the same duration.

    Args:
        progression: UserProgression to convert

    Returns:
        Bar notation string
    """
    return "|".join(chord.chord_label for chord in progression.chords)

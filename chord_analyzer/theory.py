"""
Music theory utilities for chord analysis.
"""

from typing import Set, List, Tuple, Optional

# Chromatic note to semitone mapping (0-11)
NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "Fb": 4,
    "E#": 5,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
    "Cb": 11,
    "B#": 0,
}

# Semitone to note name (using sharps by default)
SEMITONE_TO_NOTE = {
    0: "C",
    1: "C#",
    2: "D",
    3: "D#",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "G#",
    9: "A",
    10: "A#",
    11: "B",
}

# Chord quality to interval pattern (semitones from root)
CHORD_INTERVALS = {
    # Triads
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    # Suspended
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    # Seventh chords
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dim7": [0, 3, 6, 9],
    "hdim7": [0, 3, 6, 10],  # Half-diminished
    "minmaj7": [0, 3, 7, 11],
    "aug7": [0, 4, 8, 10],
    # Extended chords
    "9": [0, 4, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "min9": [0, 3, 7, 10, 14],
    "add9": [0, 4, 7, 14],
    "11": [0, 4, 7, 10, 14, 17],
    "13": [0, 4, 7, 10, 14, 17, 21],
    # Power chord
    "5": [0, 7],
    # Sixth chords
    "6": [0, 4, 7, 9],
    "min6": [0, 3, 7, 9],
}

# Major scale intervals for key estimation
MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]

# Minor scale intervals (natural minor / Aeolian)
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

# Dorian mode intervals (for minor 7th chords)
DORIAN_SCALE_INTERVALS = [0, 2, 3, 5, 7, 9, 10]

# Mixolydian mode intervals (for dominant 7th chords)
MIXOLYDIAN_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 10]

# Lydian mode intervals (for major 7th chords, alternative)
LYDIAN_SCALE_INTERVALS = [0, 2, 4, 6, 7, 9, 11]

# Locrian mode intervals (for half-diminished chords)
LOCRIAN_SCALE_INTERVALS = [0, 1, 3, 5, 6, 8, 10]

# Diminished scale (half-whole) intervals
DIMINISHED_SCALE_INTERVALS = [0, 1, 3, 4, 6, 7, 9, 10]

# Whole tone scale intervals (for augmented chords)
WHOLETONE_SCALE_INTERVALS = [0, 2, 4, 6, 8, 10]

# Mapping from chord quality to implied scale intervals
CHORD_TO_SCALE_MAP = {
    # Major family -> Major scale (Ionian)
    "maj": MAJOR_SCALE_INTERVALS,
    "maj7": MAJOR_SCALE_INTERVALS,
    "maj9": MAJOR_SCALE_INTERVALS,
    "6": MAJOR_SCALE_INTERVALS,
    "add9": MAJOR_SCALE_INTERVALS,
    # Minor family -> Dorian (default, works well for most contexts)
    "min": DORIAN_SCALE_INTERVALS,
    "min7": DORIAN_SCALE_INTERVALS,
    "min9": DORIAN_SCALE_INTERVALS,
    "min6": DORIAN_SCALE_INTERVALS,
    "m": DORIAN_SCALE_INTERVALS,
    "m7": DORIAN_SCALE_INTERVALS,
    # Dominant family -> Mixolydian
    "7": MIXOLYDIAN_SCALE_INTERVALS,
    "9": MIXOLYDIAN_SCALE_INTERVALS,
    "11": MIXOLYDIAN_SCALE_INTERVALS,
    "13": MIXOLYDIAN_SCALE_INTERVALS,
    # Suspended -> Major scale
    "sus2": MAJOR_SCALE_INTERVALS,
    "sus4": MAJOR_SCALE_INTERVALS,
    # Diminished family -> Diminished scale
    "dim": DIMINISHED_SCALE_INTERVALS,
    "dim7": DIMINISHED_SCALE_INTERVALS,
    # Half-diminished -> Locrian
    "hdim7": LOCRIAN_SCALE_INTERVALS,
    "min7b5": LOCRIAN_SCALE_INTERVALS,
    "m7b5": LOCRIAN_SCALE_INTERVALS,
    # Augmented -> Whole tone
    "aug": WHOLETONE_SCALE_INTERVALS,
    "aug7": WHOLETONE_SCALE_INTERVALS,
    # Minor-major 7 -> Harmonic minor (approximated)
    "minmaj7": MINOR_SCALE_INTERVALS,
    # Power chord -> Major scale (neutral)
    "5": MAJOR_SCALE_INTERVALS,
}

# Circle of fifths for key relationships
CIRCLE_OF_FIFTHS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]

# Roman numeral mapping for scale degrees (major key)
# Maps semitone interval from tonic to Roman numeral
SCALE_DEGREE_TO_NUMERAL = {
    0: "I",
    1: "bII",
    2: "II",
    3: "bIII",
    4: "III",
    5: "IV",
    6: "bV",  # or #IV
    7: "V",
    8: "bVI",
    9: "VI",
    10: "bVII",
    11: "VII",
}

# Expected chord qualities for diatonic chords in major key
DIATONIC_QUALITIES_MAJOR = {
    0: "maj",   # I
    2: "min",   # ii
    4: "min",   # iii
    5: "maj",   # IV
    7: "maj",   # V (or dominant 7)
    9: "min",   # vi
    11: "dim",  # vii°
}


def parse_chord_label(chord_str: str) -> Tuple[str, str]:
    """
    Parse chord string into root note and chord type.

    Args:
        chord_str: Chord notation like "C:maj", "A:min7", "Bb:7", "E7", "Am", "Dmaj7", "E/D"

    Returns:
        Tuple of (root_note, chord_type)

    Examples:
        >>> parse_chord_label("C:maj")
        ('C', 'maj')
        >>> parse_chord_label("A:min7")
        ('A', 'min7')
        >>> parse_chord_label("Bb")
        ('Bb', 'maj')
        >>> parse_chord_label("E7")
        ('E', '7')
        >>> parse_chord_label("Am7")
        ('A', 'm7')
        >>> parse_chord_label("Dmaj7")
        ('D', 'maj7')
        >>> parse_chord_label("E/D")
        ('E', 'maj')
        >>> parse_chord_label("Am7/G")
        ('A', 'm7')
    """
    # Handle slash chords (e.g., "E/D", "Am7/G") - use the chord part before the slash
    if "/" in chord_str:
        chord_str = chord_str.split("/")[0]

    if ":" in chord_str:
        # Colon-separated format: "C:maj", "A:min7"
        parts = chord_str.split(":", 1)
        root = parts[0]
        chord_type = parts[1] if len(parts) > 1 else "maj"
    else:
        # Parse without colon: need to separate root from quality
        # Root is 1-2 characters: letter + optional accidental (# or b)
        if len(chord_str) >= 2 and chord_str[1] in ("#", "b"):
            # Two-character root (e.g., "Bb", "F#")
            root = chord_str[:2]
            chord_type = chord_str[2:] if len(chord_str) > 2 else "maj"
        elif len(chord_str) >= 1:
            # One-character root (e.g., "C", "A", "G")
            root = chord_str[0]
            chord_type = chord_str[1:] if len(chord_str) > 1 else "maj"
        else:
            # Empty string
            root = ""
            chord_type = "maj"

        # Normalize common chord type abbreviations
        if not chord_type:
            chord_type = "maj"
        # Handle 'm' vs 'min' - convert single 'm' to 'min' for consistency
        elif chord_type == "m":
            chord_type = "min"
        elif chord_type.startswith("m") and len(chord_type) > 1:
            # "m7", "m9", etc. -> "min7", "min9"
            if chord_type[1].isdigit():
                chord_type = "min" + chord_type[1:]

    return root, chord_type


def get_chord_notes(chord_str: str) -> Set[int]:
    """
    Get all notes in a chord as semitone values (0-11).

    Args:
        chord_str: Chord notation like "C:maj", "A:min"

    Returns:
        Set of semitone values for all notes in the chord

    Examples:
        >>> get_chord_notes("C:maj")
        {0, 4, 7}
        >>> get_chord_notes("A:min")
        {9, 0, 4}
    """
    root, chord_type = parse_chord_label(chord_str)

    if root not in NOTE_TO_SEMITONE:
        return set()

    root_semitone = NOTE_TO_SEMITONE[root]
    intervals = CHORD_INTERVALS.get(chord_type, CHORD_INTERVALS["maj"])

    return set((root_semitone + interval) % 12 for interval in intervals)


def get_all_notes_in_progression(progression: List[str]) -> Set[int]:
    """
    Get union of all notes across a chord progression.

    Args:
        progression: List of chord labels

    Returns:
        Set of all semitone values used in the progression
    """
    all_notes: Set[int] = set()
    for chord in progression:
        all_notes.update(get_chord_notes(chord))
    return all_notes


def chord_to_scale(chord_str: str) -> Set[int]:
    """
    Get the implied scale notes for a chord as semitone values (0-11).

    Uses chord-scale theory to determine the most appropriate scale
    for improvisation/harmony over a given chord. The scale choice
    is based on the chord quality:
    - Major chords -> Major scale (Ionian)
    - Minor chords -> Dorian mode
    - Dominant 7ths -> Mixolydian mode
    - Half-diminished -> Locrian mode
    - Diminished -> Diminished scale
    - Augmented -> Whole tone scale

    Args:
        chord_str: Chord notation like "C:maj7", "A:min7", "G:7"

    Returns:
        Set of semitone values (0-11) for the implied scale

    Examples:
        >>> chord_to_scale("C:maj7")
        {0, 2, 4, 5, 7, 9, 11}  # C major scale
        >>> chord_to_scale("A:min7")
        {9, 11, 0, 2, 4, 6, 7}  # A Dorian
        >>> chord_to_scale("G:7")
        {7, 9, 11, 0, 2, 4, 5}  # G Mixolydian
    """
    root, chord_type = parse_chord_label(chord_str)

    if root not in NOTE_TO_SEMITONE:
        return set()

    root_semitone = NOTE_TO_SEMITONE[root]

    # Get scale intervals for this chord quality
    scale_intervals = CHORD_TO_SCALE_MAP.get(chord_type, MAJOR_SCALE_INTERVALS)

    return set((root_semitone + interval) % 12 for interval in scale_intervals)


def get_scale_name(chord_type: str) -> str:
    """
    Get the name of the scale implied by a chord quality.

    Args:
        chord_type: Chord quality like "maj7", "min7", "7"

    Returns:
        Name of the implied scale
    """
    scale_names = {
        "maj": "Major (Ionian)",
        "maj7": "Major (Ionian)",
        "maj9": "Major (Ionian)",
        "min": "Dorian",
        "min7": "Dorian",
        "min9": "Dorian",
        "m": "Dorian",
        "m7": "Dorian",
        "7": "Mixolydian",
        "9": "Mixolydian",
        "11": "Mixolydian",
        "13": "Mixolydian",
        "dim": "Diminished (half-whole)",
        "dim7": "Diminished (half-whole)",
        "hdim7": "Locrian",
        "min7b5": "Locrian",
        "aug": "Whole Tone",
        "aug7": "Whole Tone",
        "sus2": "Major (Ionian)",
        "sus4": "Major (Ionian)",
    }
    return scale_names.get(chord_type, "Major (Ionian)")


def get_interval_between_notes(note_a: str, note_b: str) -> int:
    """
    Get the interval in semitones between two notes.

    Args:
        note_a: First note
        note_b: Second note

    Returns:
        Interval in semitones (0-11)
    """
    if note_a not in NOTE_TO_SEMITONE or note_b not in NOTE_TO_SEMITONE:
        return 0

    semitone_a = NOTE_TO_SEMITONE[note_a]
    semitone_b = NOTE_TO_SEMITONE[note_b]

    return (semitone_b - semitone_a) % 12


def is_diatonic_to_key(chord_str: str, key: str) -> bool:
    """
    Check if a chord is diatonic (naturally occurring) in a given major key.

    Args:
        chord_str: Chord notation
        key: Key root note (e.g., "C" for C major)

    Returns:
        True if chord is diatonic to the key
    """
    if key not in NOTE_TO_SEMITONE:
        return False

    key_semitone = NOTE_TO_SEMITONE[key]
    chord_notes = get_chord_notes(chord_str)

    # Get scale notes for this key
    scale_notes = set((key_semitone + interval) % 12 for interval in MAJOR_SCALE_INTERVALS)

    # Check if all chord notes are in the scale
    return chord_notes.issubset(scale_notes)


def estimate_key_from_progression(progression: List[str]) -> Optional[str]:
    """
    Estimate the key of a chord progression using a simple heuristic.

    Uses Krumhansl-Schmuckler style approach: check which major key
    contains the most chords diatonically.

    Args:
        progression: List of chord labels

    Returns:
        Estimated key or None if undetermined
    """
    if not progression:
        return None

    best_key = None
    best_score = 0

    for key in SEMITONE_TO_NOTE.values():
        score = sum(1 for chord in progression if is_diatonic_to_key(chord, key))
        if score > best_score:
            best_score = score
            best_key = key

    # Only return if a reasonable portion of chords fit
    if best_score >= len(progression) * 0.5:
        return best_key

    return None


def get_relative_minor(major_key: str) -> Optional[str]:
    """Get the relative minor of a major key."""
    if major_key not in NOTE_TO_SEMITONE:
        return None
    semitone = (NOTE_TO_SEMITONE[major_key] + 9) % 12
    return SEMITONE_TO_NOTE[semitone]


def get_relative_major(minor_key: str) -> Optional[str]:
    """Get the relative major of a minor key."""
    if minor_key not in NOTE_TO_SEMITONE:
        return None
    semitone = (NOTE_TO_SEMITONE[minor_key] + 3) % 12
    return SEMITONE_TO_NOTE[semitone]


def get_key_distance(key_a: str, key_b: str) -> int:
    """
    Get the distance between two keys on the circle of fifths.

    Args:
        key_a: First key
        key_b: Second key

    Returns:
        Distance (0-6, where 0 is same key, 6 is tritone away)
    """
    if key_a not in NOTE_TO_SEMITONE or key_b not in NOTE_TO_SEMITONE:
        return 6  # Maximum distance for unknown keys

    # Calculate fifths distance
    semitone_a = NOTE_TO_SEMITONE[key_a]
    semitone_b = NOTE_TO_SEMITONE[key_b]

    # Convert to fifths (7 semitones)
    # Going around the circle, each step is 7 semitones
    diff = (semitone_b - semitone_a) % 12

    # Map semitone difference to fifths distance
    fifths_forward = (diff * 7) % 12  # This gives us position in circle
    fifths_backward = (12 - fifths_forward) % 12

    return min(fifths_forward, fifths_backward)


# =============================================================================
# Relative/Functional Harmony Functions
# =============================================================================


def chord_to_roman_numeral(chord_str: str, key: str) -> Optional[str]:
    """
    Convert a chord to Roman numeral notation relative to a key.

    Args:
        chord_str: Chord notation like "C:maj", "A:min"
        key: The key to analyze relative to (e.g., "C", "G")

    Returns:
        Roman numeral with quality (e.g., "I", "ii", "V7", "bVII") or None if invalid

    Examples:
        >>> chord_to_roman_numeral("C:maj", "C")
        'I'
        >>> chord_to_roman_numeral("A:min", "C")
        'vi'
        >>> chord_to_roman_numeral("G:7", "C")
        'V7'
        >>> chord_to_roman_numeral("F:maj", "G")
        'bVII'
    """
    if key not in NOTE_TO_SEMITONE:
        return None

    root, chord_type = parse_chord_label(chord_str)
    if root not in NOTE_TO_SEMITONE:
        return None

    # Calculate interval from key root to chord root
    key_semitone = NOTE_TO_SEMITONE[key]
    root_semitone = NOTE_TO_SEMITONE[root]
    interval = (root_semitone - key_semitone) % 12

    # Get base Roman numeral
    numeral = SCALE_DEGREE_TO_NUMERAL.get(interval, "?")

    # Determine case based on chord quality (uppercase = major, lowercase = minor/diminished)
    # Minor and diminished chords use lowercase
    minor_types = {
        "min", "m", "min7", "min6", "min9", "min11", "min13",
        "dim", "dim7", "hdim7", "min7b5", "m7b5",
    }
    # Check if chord type starts with 'min' or is in minor types
    is_minor_type = (
        chord_type in minor_types or
        chord_type.startswith("min") or
        chord_type.startswith("m7") or
        chord_type.startswith("m9") or
        chord_type.startswith("m11") or
        chord_type.startswith("m13")
    )

    if is_minor_type or "dim" in chord_type:
        numeral = numeral.lower()

    # Add quality suffix for 7ths, 6ths, and other extensions
    if "7" in chord_type:
        # Half-diminished gets ø symbol
        if "m7b5" in chord_type or "min7b5" in chord_type or chord_type == "hdim7":
            numeral += "ø7"
        else:
            numeral += "7"
    elif "6" in chord_type:
        numeral += "6"
    elif "9" in chord_type and "7" not in chord_type:
        numeral += "9"
    elif chord_type == "dim":
        numeral += "°"
    elif chord_type == "aug":
        numeral += "+"

    return numeral


def progression_to_numerals(
    progression: List[str], key: Optional[str] = None
) -> List[str]:
    """
    Convert a chord progression to Roman numerals.

    If no key is provided, estimates the key from the progression.

    Args:
        progression: List of chord labels
        key: Optional key to use (if None, will be estimated)

    Returns:
        List of Roman numerals

    Examples:
        >>> progression_to_numerals(["C:maj", "A:min", "F:maj", "G:maj"])
        ['I', 'vi', 'IV', 'V']
        >>> progression_to_numerals(["G:maj", "E:min", "C:maj", "D:maj"])
        ['I', 'vi', 'IV', 'V']
    """
    if not progression:
        return []

    if key is None:
        key = estimate_key_from_progression(progression)
        if key is None:
            # Fall back to using first chord's root as key
            root, _ = parse_chord_label(progression[0])
            key = root

    numerals = []
    for chord in progression:
        numeral = chord_to_roman_numeral(chord, key)
        numerals.append(numeral if numeral else "?")

    return numerals


def get_interval_pattern(progression: List[str]) -> List[int]:
    """
    Extract the interval pattern (root movements) from a progression.

    This creates a key-agnostic representation by tracking how many
    semitones the root moves between each chord.

    Args:
        progression: List of chord labels

    Returns:
        List of intervals in semitones between consecutive roots

    Examples:
        >>> get_interval_pattern(["C:maj", "F:maj", "G:maj", "C:maj"])
        [5, 2, 5]
        >>> get_interval_pattern(["G:maj", "C:maj", "D:maj", "G:maj"])
        [5, 2, 5]  # Same pattern as above (I-IV-V-I)
    """
    if len(progression) < 2:
        return []

    intervals = []
    for i in range(len(progression) - 1):
        root_a, _ = parse_chord_label(progression[i])
        root_b, _ = parse_chord_label(progression[i + 1])

        if root_a in NOTE_TO_SEMITONE and root_b in NOTE_TO_SEMITONE:
            semitone_a = NOTE_TO_SEMITONE[root_a]
            semitone_b = NOTE_TO_SEMITONE[root_b]
            interval = (semitone_b - semitone_a) % 12
            intervals.append(interval)
        else:
            intervals.append(-1)  # Invalid/unknown

    return intervals


def get_quality_pattern(progression: List[str]) -> List[str]:
    """
    Extract the chord quality pattern from a progression.

    This captures the sequence of chord types (maj, min, 7, etc.)
    independent of the actual root notes.

    Args:
        progression: List of chord labels

    Returns:
        List of chord qualities

    Examples:
        >>> get_quality_pattern(["C:maj", "A:min", "F:maj", "G:7"])
        ['maj', 'min', 'maj', '7']
    """
    return [parse_chord_label(chord)[1] for chord in progression]


def normalize_progression(progression: List[str]) -> List[Tuple[int, str]]:
    """
    Normalize a progression to a key-agnostic representation.

    Converts to (interval_from_first_root, quality) tuples.
    This allows comparing progressions regardless of absolute key.

    Args:
        progression: List of chord labels

    Returns:
        List of (interval, quality) tuples normalized to first chord

    Examples:
        >>> normalize_progression(["C:maj", "A:min", "F:maj", "G:maj"])
        [(0, 'maj'), (9, 'min'), (5, 'maj'), (7, 'maj')]
        >>> normalize_progression(["G:maj", "E:min", "C:maj", "D:maj"])
        [(0, 'maj'), (9, 'min'), (5, 'maj'), (7, 'maj')]  # Same!
    """
    if not progression:
        return []

    first_root, first_quality = parse_chord_label(progression[0])
    if first_root not in NOTE_TO_SEMITONE:
        return []

    first_semitone = NOTE_TO_SEMITONE[first_root]
    normalized = []

    for chord in progression:
        root, quality = parse_chord_label(chord)
        if root in NOTE_TO_SEMITONE:
            interval = (NOTE_TO_SEMITONE[root] - first_semitone) % 12
            normalized.append((interval, quality))
        else:
            normalized.append((-1, quality))

    return normalized


def is_transposition(prog_a: List[str], prog_b: List[str]) -> bool:
    """
    Check if two progressions are transpositions of each other.

    Two progressions are transpositions if they have the same
    normalized representation (same intervals and qualities).

    Args:
        prog_a: First progression
        prog_b: Second progression

    Returns:
        True if progressions are transpositions of each other

    Examples:
        >>> is_transposition(
        ...     ["C:maj", "F:maj", "G:maj", "C:maj"],
        ...     ["G:maj", "C:maj", "D:maj", "G:maj"]
        ... )
        True
    """
    if len(prog_a) != len(prog_b):
        return False

    norm_a = normalize_progression(prog_a)
    norm_b = normalize_progression(prog_b)

    return norm_a == norm_b


def get_transposition_interval(prog_a: List[str], prog_b: List[str]) -> Optional[int]:
    """
    Get the transposition interval between two progressions.

    Args:
        prog_a: First progression (reference)
        prog_b: Second progression

    Returns:
        Semitones to transpose prog_a to get prog_b, or None if not a transposition

    Examples:
        >>> get_transposition_interval(
        ...     ["C:maj", "F:maj", "G:maj"],
        ...     ["G:maj", "C:maj", "D:maj"]
        ... )
        7  # Transpose up a perfect 5th
    """
    if not is_transposition(prog_a, prog_b):
        return None

    if not prog_a or not prog_b:
        return None

    root_a, _ = parse_chord_label(prog_a[0])
    root_b, _ = parse_chord_label(prog_b[0])

    if root_a not in NOTE_TO_SEMITONE or root_b not in NOTE_TO_SEMITONE:
        return None

    return (NOTE_TO_SEMITONE[root_b] - NOTE_TO_SEMITONE[root_a]) % 12


def calculate_functional_similarity(prog_a: List[str], prog_b: List[str]) -> float:
    """
    Calculate functional similarity between two progressions (0.0 to 1.0).

    This compares progressions based on their relative structure rather than
    absolute pitches, making it key-agnostic.

    Components:
    - Normalized pattern match (are they transpositions?)
    - Interval pattern similarity (similar root movements?)
    - Quality pattern similarity (similar chord types in same positions?)

    Args:
        prog_a: First progression
        prog_b: Second progression

    Returns:
        Similarity score from 0.0 (completely different) to 1.0 (identical function)
    """
    if not prog_a or not prog_b:
        return 0.0

    scores = []

    # 1. Check for exact transposition (highest weight)
    if is_transposition(prog_a, prog_b):
        return 1.0

    # 2. Interval pattern similarity
    intervals_a = get_interval_pattern(prog_a)
    intervals_b = get_interval_pattern(prog_b)

    if intervals_a and intervals_b:
        # Compare interval sequences using longest common subsequence ratio
        interval_sim = _sequence_similarity(intervals_a, intervals_b)
        scores.append(interval_sim * 0.5)  # 50% weight

    # 3. Quality pattern similarity
    qualities_a = get_quality_pattern(prog_a)
    qualities_b = get_quality_pattern(prog_b)

    if qualities_a and qualities_b:
        quality_sim = _sequence_similarity(qualities_a, qualities_b)
        scores.append(quality_sim * 0.3)  # 30% weight

    # 4. Roman numeral similarity (if we can determine keys)
    key_a = estimate_key_from_progression(prog_a)
    key_b = estimate_key_from_progression(prog_b)

    if key_a and key_b:
        numerals_a = progression_to_numerals(prog_a, key_a)
        numerals_b = progression_to_numerals(prog_b, key_b)
        numeral_sim = _sequence_similarity(numerals_a, numerals_b)
        scores.append(numeral_sim * 0.2)  # 20% weight

    return sum(scores) if scores else 0.0


def _sequence_similarity(seq_a: List, seq_b: List) -> float:
    """
    Calculate similarity between two sequences using LCS ratio.

    Uses longest common subsequence length divided by average length.
    """
    if not seq_a or not seq_b:
        return 0.0

    # Simple LCS implementation
    m, n = len(seq_a), len(seq_b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq_a[i - 1] == seq_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]
    avg_length = (m + n) / 2

    return lcs_length / avg_length if avg_length > 0 else 0.0


# =============================================================================
# Transposition Functions
# =============================================================================


def transpose_chord(chord_str: str, semitones: int) -> str:
    """
    Transpose a chord by a number of semitones.

    Args:
        chord_str: Chord notation like "C:maj", "A:min7", "Bb:7"
        semitones: Number of semitones to transpose (positive = up, negative = down)

    Returns:
        Transposed chord string

    Examples:
        >>> transpose_chord("C:maj", 7)
        'G:maj'
        >>> transpose_chord("A:min7", -3)
        'F#:min7'
        >>> transpose_chord("Bb:7", 2)
        'C:7'
    """
    root, chord_type = parse_chord_label(chord_str)

    if root not in NOTE_TO_SEMITONE:
        return chord_str  # Return unchanged if invalid

    # Get current semitone and transpose
    current_semitone = NOTE_TO_SEMITONE[root]
    new_semitone = (current_semitone + semitones) % 12

    # Convert back to note name
    new_root = SEMITONE_TO_NOTE[new_semitone]

    # Reconstruct chord label
    if ":" in chord_str:
        return f"{new_root}:{chord_type}"
    else:
        # Preserve original format (compact notation)
        return f"{new_root}{chord_type}" if chord_type != "maj" else new_root


def transpose_progression(progression: List[str], semitones: int) -> List[str]:
    """
    Transpose an entire chord progression by a number of semitones.

    Args:
        progression: List of chord labels (e.g., ["C:maj", "A:min", "F:maj", "G:maj"])
        semitones: Number of semitones to transpose (positive = up, negative = down)

    Returns:
        New list of transposed chord labels

    Examples:
        >>> transpose_progression(["C:maj", "A:min", "F:maj", "G:maj"], 7)
        ['G:maj', 'E:min', 'C:maj', 'D:maj']
        >>> transpose_progression(["G:maj", "E:min", "C:maj", "D:maj"], -7)
        ['C:maj', 'A:min', 'F:maj', 'G:maj']
    """
    return [transpose_chord(chord, semitones) for chord in progression]


def get_transposition_description(from_semitone: int, to_semitone: int) -> str:
    """
    Generate a human-readable description of a transposition.

    Args:
        from_semitone: Original key as semitone (0-11)
        to_semitone: Target key as semitone (0-11)

    Returns:
        Description like "G -> C" or "in key" if no transposition needed

    Examples:
        >>> get_transposition_description(7, 0)  # G to C
        'G -> C'
        >>> get_transposition_description(0, 0)  # C to C
        'in key'
    """
    if from_semitone == to_semitone:
        return "in key"

    from_note = SEMITONE_TO_NOTE[from_semitone % 12]
    to_note = SEMITONE_TO_NOTE[to_semitone % 12]

    return f"{from_note} -> {to_note}"


def semitones_to_interval_name(semitones: int) -> str:
    """
    Convert a semitone interval to a human-readable name.

    Args:
        semitones: Interval in semitones (can be negative)

    Returns:
        Interval name like "perfect 5th up" or "minor 3rd down"
    """
    interval_names = {
        0: "unison",
        1: "minor 2nd",
        2: "major 2nd",
        3: "minor 3rd",
        4: "major 3rd",
        5: "perfect 4th",
        6: "tritone",
        7: "perfect 5th",
        8: "minor 6th",
        9: "major 6th",
        10: "minor 7th",
        11: "major 7th",
    }

    abs_semitones = abs(semitones) % 12
    name = interval_names.get(abs_semitones, f"{abs_semitones} semitones")

    if semitones == 0:
        return name
    elif semitones > 0:
        return f"{name} up"
    else:
        return f"{name} down"

"""
Filename parser for extracting key signature and tempo from audio filenames.

Common filename patterns:
- Funky_Bass_Cmaj_120bpm.wav
- drum_loop_Am_90BPM.mp3
- Piano Chords G minor 85 bpm.wav
- Lead_Synth_F#m_140.wav
- Pad_Db_Major_70bpm.aif
- Sample_G.wav (G major - note at end of filename)
- Loop_120.wav (120 bpm - tempo at end of filename)
- Track_G_Loop.wav (G major - note between separators)
- Beat_120_Main.wav (120 bpm - tempo between separators)
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


# Note names with sharps and flats
NOTE_PATTERN = r"[A-Ga-g][#b]?"

# Key quality patterns
MAJOR_PATTERNS = [
    r"maj(?:or)?",  # maj, major
    r"M(?![a-z])",  # M (uppercase, not followed by lowercase)
]
MINOR_PATTERNS = [
    r"min(?:or)?",  # min, minor
    r"m(?![a-z])",  # m (lowercase, not followed by lowercase)
]

# Combined key pattern: C, Cm, Cmaj, C#m, Dbmaj, C minor, D# Major, etc.
KEY_PATTERN = (
    rf"(?P<root>{NOTE_PATTERN})"
    rf"[\s_-]*"
    rf"(?P<quality>{'|'.join(MAJOR_PATTERNS + MINOR_PATTERNS)})?"
)

# BPM patterns: 120bpm, 120 BPM, 120, etc.
BPM_PATTERN = r"(?P<bpm>\d{2,3})[\s_-]*(?:bpm)?(?![0-9])"


@dataclass
class FilenameInfo:
    """Parsed information from an audio filename."""

    key: Optional[str] = None  # e.g., "C major", "A minor"
    key_root: Optional[str] = None  # e.g., "C", "A"
    key_quality: Optional[str] = None  # "major" or "minor"
    bpm: Optional[float] = None

    @property
    def has_key(self) -> bool:
        return self.key is not None

    @property
    def has_bpm(self) -> bool:
        return self.bpm is not None


def normalize_note(note: str) -> str:
    """
    Normalize note name to standard format (uppercase with # or b).

    Args:
        note: Note name like 'c', 'C#', 'db'

    Returns:
        Normalized note like 'C', 'C#', 'Db'
    """
    if not note:
        return note

    # Uppercase the note letter, keep accidental as-is
    if len(note) == 1:
        return note.upper()
    else:
        return note[0].upper() + note[1].lower()


def parse_key_from_string(s: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract key signature from a string.

    Args:
        s: String that may contain key information

    Returns:
        Tuple of (full_key, root_note, quality) or (None, None, None)
        Examples: ("C major", "C", "major"), ("A minor", "A", "minor")
    """
    # Try to find key pattern in the string
    # We need to be careful not to match random letters

    # First, try patterns with explicit quality (most reliable)
    # Pattern: note + separator + quality word
    explicit_pattern = rf"(?:^|[^A-Za-z])({NOTE_PATTERN})[\s_-]*(major|minor|maj|min)(?:[^a-z]|$)"
    match = re.search(explicit_pattern, s, re.IGNORECASE)
    if match:
        root = normalize_note(match.group(1))
        quality_str = match.group(2).lower()
        quality = "major" if quality_str in ("major", "maj") else "minor"
        return f"{root} {quality}", root, quality

    # Pattern: note immediately followed by quality suffix
    # e.g., Cmaj, Am, C#m, Dbmaj
    suffix_pattern = rf"(?:^|[^A-Za-z])({NOTE_PATTERN})(maj|min|m)(?:[^a-z]|$)"
    match = re.search(suffix_pattern, s, re.IGNORECASE)
    if match:
        root = normalize_note(match.group(1))
        quality_str = match.group(2).lower()
        quality = "major" if quality_str == "maj" else "minor"
        return f"{root} {quality}", root, quality

    # Pattern: standalone note (assume major if no quality specified)
    # Only match if it looks intentional (surrounded by separators or at boundaries)
    # e.g., "_C_", "-G-", " A ", "Funky_C_Loop"
    standalone_pattern = rf"(?:^|[_\s-])({NOTE_PATTERN})(?:[_\s-]|$)"
    match = re.search(standalone_pattern, s)
    if match:
        root = normalize_note(match.group(1))
        # Only accept if it's a common key letter and looks intentional
        # Skip single letters that might be part of naming convention
        if root in ("A", "B", "C", "D", "E", "F", "G") or len(root) == 2:
            # Default to major for standalone notes
            return f"{root} major", root, "major"

    return None, None, None


def parse_bpm_from_string(s: str) -> Optional[float]:
    """
    Extract BPM from a string.

    Args:
        s: String that may contain BPM information

    Returns:
        BPM as float, or None if not found
    """
    # Pattern 1: explicit bpm suffix (most reliable)
    # e.g., 120bpm, 120BPM, 120 bpm
    explicit_pattern = r"(?:^|[^0-9])(\d{2,3})[\s_-]*bpm(?:[^a-z]|$)"
    match = re.search(explicit_pattern, s, re.IGNORECASE)
    if match:
        bpm = float(match.group(1))
        if 40 <= bpm <= 300:  # Reasonable BPM range
            return bpm

    # Pattern 2: standalone number in reasonable BPM range
    # Only if it looks like tempo (common tempo values)
    # Be conservative to avoid matching other numbers (years, versions, etc.)
    # Look for numbers that are typical tempos: 60-200
    number_pattern = r"(?:^|[_\s-])(\d{2,3})(?:[_\s-]|$)"
    for match in re.finditer(number_pattern, s):
        bpm = float(match.group(1))
        # More restrictive range for numbers without "bpm" suffix
        if 60 <= bpm <= 200:
            # Avoid common non-BPM numbers
            if bpm not in (100,):  # Could be version numbers
                return bpm

    return None


def parse_filename(filepath: str) -> FilenameInfo:
    """
    Parse key and tempo information from an audio filename.

    Args:
        filepath: Full path or filename of the audio file

    Returns:
        FilenameInfo with extracted key and BPM (if found)

    Examples:
        >>> parse_filename("Funky_Bass_Cmaj_120bpm.wav")
        FilenameInfo(key="C major", key_root="C", key_quality="major", bpm=120.0)

        >>> parse_filename("drum_loop_Am_90BPM.mp3")
        FilenameInfo(key="A minor", key_root="A", key_quality="minor", bpm=90.0)
    """
    # Extract just the filename without path and extension
    import os
    filename = os.path.basename(filepath)
    name_without_ext = os.path.splitext(filename)[0]

    # Parse key
    key, root, quality = parse_key_from_string(name_without_ext)

    # Parse BPM
    bpm = parse_bpm_from_string(name_without_ext)

    return FilenameInfo(
        key=key,
        key_root=root,
        key_quality=quality,
        bpm=bpm,
    )


def format_key_for_display(root: str, quality: str) -> str:
    """
    Format key for display (e.g., "C major", "A minor").

    Args:
        root: Root note (e.g., "C", "A")
        quality: "major" or "minor"

    Returns:
        Formatted key string
    """
    return f"{root} {quality}"


def format_key_for_matching(root: str, quality: str) -> str:
    """
    Format key for chord matching (e.g., "C:maj", "A:min").

    Args:
        root: Root note (e.g., "C", "A")
        quality: "major" or "minor"

    Returns:
        Chord-format key string
    """
    chord_quality = "maj" if quality == "major" else "min"
    return f"{root}:{chord_quality}"

"""
Data models for chord analysis.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Tuple


@dataclass
class ChordEvent:
    """Single chord occurrence with timing information."""

    start_time: float
    end_time: float
    chord_label: str
    root_note: str
    chord_type: str
    # Beat-relative timing (optional, set when beat grid is available)
    bar: Optional[int] = None  # 1-indexed bar number
    beat: Optional[float] = None  # 1-indexed beat within bar
    duration_beats: Optional[float] = None  # Duration in beats

    @property
    def duration(self) -> float:
        """Duration of this chord in seconds."""
        return self.end_time - self.start_time

    @property
    def has_beat_info(self) -> bool:
        """Check if beat-relative timing is available."""
        return self.bar is not None and self.beat is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "start": self.start_time,
            "end": self.end_time,
            "chord": self.chord_label,
            "root": self.root_note,
            "type": self.chord_type,
            "duration": self.duration,
        }
        # Include beat info if available
        if self.has_beat_info:
            result["bar"] = self.bar
            result["beat"] = self.beat
            result["duration_beats"] = self.duration_beats
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChordEvent":
        """Create from dictionary."""
        return cls(
            start_time=data["start"],
            end_time=data["end"],
            chord_label=data["chord"],
            root_note=data.get("root", ""),
            chord_type=data.get("type", "maj"),
            bar=data.get("bar"),
            beat=data.get("beat"),
            duration_beats=data.get("duration_beats"),
        )


@dataclass
class Sample:
    """Audio sample with chord analysis data."""

    filepath: str
    filename: str
    chords: List[ChordEvent] = field(default_factory=list)
    id: Optional[int] = None
    duration_seconds: float = 0.0
    estimated_key: Optional[str] = None
    estimated_bpm: Optional[float] = None
    time_signature: Tuple[int, int] = (4, 4)  # Default 4/4 time
    first_beat_offset: float = 0.0  # Time in seconds of first beat
    voicing_type: Optional[str] = None  # "monophonic", "polyphonic", "ambiguous", "unknown"

    @property
    def has_tempo_info(self) -> bool:
        """Check if tempo information is available."""
        return self.estimated_bpm is not None

    @property
    def has_beat_info(self) -> bool:
        """Check if any chords have beat-relative timing."""
        return any(c.has_beat_info for c in self.chords)

    @property
    def beats_per_bar(self) -> int:
        """Number of beats per bar based on time signature."""
        return self.time_signature[0]

    @property
    def beat_duration(self) -> Optional[float]:
        """Duration of one beat in seconds, if BPM is known."""
        if self.estimated_bpm:
            return 60.0 / self.estimated_bpm
        return None

    @property
    def bar_duration(self) -> Optional[float]:
        """Duration of one bar in seconds, if BPM is known."""
        if self.beat_duration:
            return self.beat_duration * self.beats_per_bar
        return None

    @property
    def total_bars(self) -> Optional[int]:
        """Total number of bars in the sample."""
        if self.bar_duration and self.duration_seconds > 0:
            return int(self.duration_seconds / self.bar_duration) + 1
        return None

    @property
    def progression(self) -> List[str]:
        """Extract unique chord sequence (ignoring repeated consecutive chords)."""
        if not self.chords:
            return []
        progression = [self.chords[0].chord_label]
        for chord in self.chords[1:]:
            if chord.chord_label != progression[-1]:
                progression.append(chord.chord_label)
        return progression

    @property
    def unique_chords(self) -> Set[str]:
        """Set of all unique chords in the sample."""
        return set(c.chord_label for c in self.chords)

    @property
    def root_notes(self) -> Set[str]:
        """Set of all root notes used."""
        return set(c.root_note for c in self.chords if c.root_note)

    @property
    def chord_types(self) -> Set[str]:
        """Set of all chord types used."""
        return set(c.chord_type for c in self.chords if c.chord_type)


@dataclass
class CompatibilityResult:
    """Result of compatibility calculation between two samples."""

    sample: Sample
    overall_score: float
    components: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    @property
    def functional_match_score(self) -> float:
        return self.components.get("functional_match", 0.0)

    @property
    def shared_chords_score(self) -> float:
        return self.components.get("shared_chords", 0.0)

    @property
    def note_overlap_score(self) -> float:
        return self.components.get("note_overlap", 0.0)

    @property
    def clash_penalty(self) -> float:
        return self.components.get("clash_penalty", 0.0)

    @property
    def harmonic_relations_score(self) -> float:
        return self.components.get("harmonic_relations", 0.0)

    @property
    def mood_match_score(self) -> float:
        return self.components.get("mood_match", 0.0)

    @property
    def is_transposition(self) -> bool:
        """Check if samples are transpositions of each other."""
        return "is_transposition" in self.reasons or self.functional_match_score >= 35


# =============================================================================
# Pitch-Based Analysis Models (for user chord progression matching)
# =============================================================================


@dataclass
class NoteEvent:
    """A single detected pitch with timing and metadata."""

    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    pitch_hz: float  # Detected frequency in Hz
    midi_note: int  # MIDI note number (0-127)
    pitch_class: int  # Semitone (0-11, where 0=C)
    note_name: str  # e.g., "C4", "A#3"
    confidence: float  # Detection confidence (0.0-1.0)
    amplitude: float  # Relative amplitude/loudness (0.0-1.0)
    bar: Optional[int] = None  # 1-indexed bar number
    beat: Optional[float] = None  # 1-indexed beat within bar

    @property
    def duration(self) -> float:
        """Duration of this note in seconds."""
        return self.end_time - self.start_time

    @property
    def has_beat_info(self) -> bool:
        """Check if beat-relative timing is available."""
        return self.bar is not None and self.beat is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "start": self.start_time,
            "end": self.end_time,
            "pitch_hz": self.pitch_hz,
            "midi_note": self.midi_note,
            "pitch_class": self.pitch_class,
            "note_name": self.note_name,
            "confidence": self.confidence,
            "amplitude": self.amplitude,
            "duration": self.duration,
        }
        if self.has_beat_info:
            result["bar"] = self.bar
            result["beat"] = self.beat
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NoteEvent":
        """Create from dictionary."""
        return cls(
            start_time=data["start"],
            end_time=data["end"],
            pitch_hz=data["pitch_hz"],
            midi_note=data["midi_note"],
            pitch_class=data["pitch_class"],
            note_name=data["note_name"],
            confidence=data.get("confidence", 1.0),
            amplitude=data.get("amplitude", 1.0),
            bar=data.get("bar"),
            beat=data.get("beat"),
        )

    def with_beat_info(self, bar: int, beat: float) -> "NoteEvent":
        """Return a copy with beat information added."""
        return replace(self, bar=bar, beat=beat)


@dataclass
class UserChordSpec:
    """Single chord in a user-provided progression with duration."""

    root: str  # "C", "F#", "Bb"
    quality: str  # "maj", "min", "7", "maj7", etc.
    duration_beats: float  # How many beats this chord lasts

    @property
    def chord_label(self) -> str:
        """Standard chord label format."""
        return f"{self.root}:{self.quality}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "root": self.root,
            "quality": self.quality,
            "duration_beats": self.duration_beats,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserChordSpec":
        """Create from dictionary."""
        return cls(
            root=data["root"],
            quality=data["quality"],
            duration_beats=data.get("duration_beats", 4.0),
        )


@dataclass
class UserProgression:
    """Complete user-provided chord progression with timing."""

    chords: List[UserChordSpec]
    bpm: float
    time_signature: Tuple[int, int] = (4, 4)
    name: Optional[str] = None

    @property
    def total_beats(self) -> float:
        """Total duration in beats."""
        return sum(c.duration_beats for c in self.chords)

    @property
    def total_bars(self) -> float:
        """Total duration in bars."""
        return self.total_beats / self.time_signature[0]

    @property
    def total_duration_seconds(self) -> float:
        """Total duration in seconds."""
        return self.total_beats * (60.0 / self.bpm)

    @property
    def beats_per_bar(self) -> int:
        """Number of beats per bar."""
        return self.time_signature[0]

    @property
    def beat_duration_seconds(self) -> float:
        """Duration of one beat in seconds."""
        return 60.0 / self.bpm

    @property
    def progression_labels(self) -> List[str]:
        """Get list of chord labels from the progression."""
        return [c.chord_label for c in self.chords]

    @property
    def estimated_key(self) -> Optional[str]:
        """
        Estimate the key of this progression.

        Returns:
            Key name like "C" or "G", or None if undetermined
        """
        # Import here to avoid circular imports
        from .theory import estimate_key_from_progression
        return estimate_key_from_progression(self.progression_labels)

    def to_roman_numerals(self, key: Optional[str] = None) -> List[str]:
        """
        Convert this progression to Roman numeral notation.

        Args:
            key: Optional key to use. If None, will be estimated from the progression.

        Returns:
            List of Roman numerals like ["I", "vi", "IV", "V"]
        """
        # Import here to avoid circular imports
        from .theory import progression_to_numerals
        return progression_to_numerals(self.progression_labels, key)

    def transpose(self, semitones: int) -> "UserProgression":
        """
        Return a transposed copy of this progression.

        Args:
            semitones: Number of semitones to transpose (positive = up, negative = down)

        Returns:
            New UserProgression with transposed chords
        """
        # Import here to avoid circular imports
        from .theory import transpose_chord, NOTE_TO_SEMITONE, SEMITONE_TO_NOTE

        transposed_chords = []
        for chord in self.chords:
            if chord.root in NOTE_TO_SEMITONE:
                current_semitone = NOTE_TO_SEMITONE[chord.root]
                new_semitone = (current_semitone + semitones) % 12
                new_root = SEMITONE_TO_NOTE[new_semitone]
            else:
                new_root = chord.root

            transposed_chords.append(UserChordSpec(
                root=new_root,
                quality=chord.quality,
                duration_beats=chord.duration_beats,
            ))

        return UserProgression(
            chords=transposed_chords,
            bpm=self.bpm,
            time_signature=self.time_signature,
            name=self.name,
        )

    def chord_at_beat(self, beat_number: float) -> Optional[UserChordSpec]:
        """
        Get the chord active at a specific beat position.

        Args:
            beat_number: 1-indexed beat position from start of progression

        Returns:
            The chord active at that beat, or None if out of range
        """
        if beat_number < 1:
            return None

        cumulative_beats = 0.0
        for chord in self.chords:
            cumulative_beats += chord.duration_beats
            if beat_number <= cumulative_beats:
                return chord

        # If beat is beyond progression, return last chord or None
        return self.chords[-1] if self.chords else None

    def chord_at_time(self, time_seconds: float) -> Optional[UserChordSpec]:
        """Get the chord active at a specific time in seconds."""
        beat = (time_seconds / self.beat_duration_seconds) + 1  # 1-indexed
        return self.chord_at_beat(beat)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chords": [c.to_dict() for c in self.chords],
            "bpm": self.bpm,
            "time_signature": f"{self.time_signature[0]}/{self.time_signature[1]}",
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProgression":
        """Create from dictionary."""
        chords = [UserChordSpec.from_dict(c) for c in data.get("chords", [])]
        time_sig_str = data.get("time_signature", "4/4")
        if isinstance(time_sig_str, str):
            parts = time_sig_str.split("/")
            time_sig = (int(parts[0]), int(parts[1]))
        else:
            time_sig = tuple(time_sig_str)
        return cls(
            chords=chords,
            bpm=data.get("bpm", 120.0),
            time_signature=time_sig,
            name=data.get("name"),
        )


@dataclass
class PitchAnalysisResult:
    """Result of pitch extraction from an audio file."""

    filepath: str
    notes: List[NoteEvent]
    duration_seconds: float
    is_monophonic: bool
    polyphony_level: int  # Estimated max simultaneous notes
    detected_bpm: Optional[float] = None
    file_hash: Optional[str] = None  # For cache invalidation

    @property
    def filename(self) -> str:
        """Extract filename from filepath."""
        return Path(self.filepath).stem

    @property
    def note_count(self) -> int:
        """Total number of detected notes."""
        return len(self.notes)

    @property
    def pitch_classes_present(self) -> Set[int]:
        """Set of all pitch classes (0-11) present in the sample."""
        return set(n.pitch_class for n in self.notes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "filepath": self.filepath,
            "notes": [n.to_dict() for n in self.notes],
            "duration_seconds": self.duration_seconds,
            "is_monophonic": self.is_monophonic,
            "polyphony_level": self.polyphony_level,
            "detected_bpm": self.detected_bpm,
            "file_hash": self.file_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PitchAnalysisResult":
        """Create from dictionary."""
        notes = [NoteEvent.from_dict(n) for n in data.get("notes", [])]
        return cls(
            filepath=data["filepath"],
            notes=notes,
            duration_seconds=data.get("duration_seconds", 0.0),
            is_monophonic=data.get("is_monophonic", True),
            polyphony_level=data.get("polyphony_level", 1),
            detected_bpm=data.get("detected_bpm"),
            file_hash=data.get("file_hash"),
        )


@dataclass
class BeatCompatibilityScore:
    """Score for a single beat in the progression."""

    beat_number: int  # 1-indexed global beat position
    bar_number: int  # 1-indexed bar number
    beat_in_bar: int  # 1-indexed beat within bar
    active_chord: UserChordSpec
    notes_in_beat: List[NoteEvent] = field(default_factory=list)
    in_chord_ratio: float = 0.0  # Proportion of notes that are chord tones
    in_scale_ratio: float = 0.0  # Proportion of notes that are scale tones
    clash_count: int = 0  # Number of semitone clashes with chord
    weighted_score: float = 0.0  # Combined score for this beat (0-100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "beat_number": self.beat_number,
            "bar_number": self.bar_number,
            "beat_in_bar": self.beat_in_bar,
            "chord": self.active_chord.chord_label,
            "note_count": len(self.notes_in_beat),
            "in_chord_ratio": round(self.in_chord_ratio, 3),
            "in_scale_ratio": round(self.in_scale_ratio, 3),
            "clash_count": self.clash_count,
            "weighted_score": round(self.weighted_score, 1),
        }


@dataclass
class SamplePitchCompatibilityResult:
    """Full compatibility result for one audio sample against a progression."""

    filepath: str
    filename: str
    overall_score: float  # 0-100 aggregate score
    beat_scores: List[BeatCompatibilityScore]
    avg_in_chord_ratio: float
    avg_in_scale_ratio: float
    total_clash_count: int
    pitch_analysis: PitchAnalysisResult
    reasons: List[str] = field(default_factory=list)
    progression: Optional[UserProgression] = None
    # Transposition info (populated when normalized matching is used)
    detected_key: Optional[str] = None  # Estimated key of the sample
    recommended_transposition: Optional[int] = None  # Semitones to transpose sample
    transposition_description: Optional[str] = None  # Human-readable like "G -> C"

    @property
    def detected_bpm(self) -> Optional[float]:
        """BPM from pitch analysis."""
        return self.pitch_analysis.detected_bpm

    @property
    def is_monophonic(self) -> bool:
        """Whether sample is monophonic."""
        return self.pitch_analysis.is_monophonic

    @property
    def beat_count(self) -> int:
        """Number of beats scored."""
        return len(self.beat_scores)

    @property
    def note_count(self) -> int:
        """Total notes in sample."""
        return self.pitch_analysis.note_count

    @property
    def has_transposition_info(self) -> bool:
        """Check if transposition information is available."""
        return self.recommended_transposition is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "filepath": self.filepath,
            "filename": self.filename,
            "overall_score": round(self.overall_score, 1),
            "avg_in_chord_ratio": round(self.avg_in_chord_ratio, 3),
            "avg_in_scale_ratio": round(self.avg_in_scale_ratio, 3),
            "total_clash_count": self.total_clash_count,
            "beat_count": self.beat_count,
            "note_count": self.note_count,
            "is_monophonic": self.is_monophonic,
            "detected_bpm": self.detected_bpm,
            "reasons": self.reasons,
            "beat_scores": [bs.to_dict() for bs in self.beat_scores],
        }
        # Include transposition info if available
        if self.has_transposition_info:
            result["detected_key"] = self.detected_key
            result["recommended_transposition"] = self.recommended_transposition
            result["transposition_description"] = self.transposition_description
        return result

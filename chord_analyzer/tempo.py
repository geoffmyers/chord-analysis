"""
Tempo and beat detection utilities.

Uses librosa for audio analysis when available, with fallback to
basic estimation from chord timing.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

# Try to import librosa for audio analysis
try:
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False


@dataclass
class BeatGrid:
    """Represents a beat grid for an audio sample."""

    bpm: float
    beat_times: List[float]  # Times in seconds where beats occur
    downbeat_times: List[float]  # Times where bar downbeats occur (beat 1)
    time_signature: Tuple[int, int]  # e.g., (4, 4) for 4/4 time
    first_beat_time: float  # Time of the first detected beat

    @property
    def beats_per_bar(self) -> int:
        """Number of beats per bar based on time signature."""
        return self.time_signature[0]

    @property
    def beat_duration(self) -> float:
        """Duration of one beat in seconds."""
        return 60.0 / self.bpm

    @property
    def bar_duration(self) -> float:
        """Duration of one bar in seconds."""
        return self.beat_duration * self.beats_per_bar

    def time_to_beat(self, time_seconds: float) -> float:
        """
        Convert a time in seconds to beat number (1-indexed within bar).

        Returns a float where the integer part is the beat number
        and the fractional part is the position within the beat.
        """
        if time_seconds < self.first_beat_time:
            return 0.0

        time_from_first_beat = time_seconds - self.first_beat_time
        beat_number = time_from_first_beat / self.beat_duration
        return beat_number + 1  # 1-indexed

    def time_to_bar_beat(self, time_seconds: float) -> Tuple[int, float]:
        """
        Convert a time in seconds to (bar_number, beat_in_bar).

        Both are 1-indexed. Beat is a float to capture subdivisions.
        """
        total_beats = self.time_to_beat(time_seconds)
        if total_beats <= 0:
            return (0, 0.0)

        bar_number = int((total_beats - 1) // self.beats_per_bar) + 1
        beat_in_bar = ((total_beats - 1) % self.beats_per_bar) + 1

        return (bar_number, beat_in_bar)

    def quantize_to_beat(
        self, time_seconds: float, subdivision: int = 1
    ) -> Tuple[int, float]:
        """
        Quantize a time to the nearest beat (or subdivision).

        Args:
            time_seconds: Time to quantize
            subdivision: 1 = quarter notes, 2 = eighth notes, 4 = sixteenths

        Returns:
            (bar_number, beat_in_bar) tuple, both 1-indexed
        """
        bar, beat = self.time_to_bar_beat(time_seconds)
        if bar == 0:
            return (1, 1.0)

        # Quantize to subdivision
        subdivision_size = 1.0 / subdivision
        quantized_beat = round(beat / subdivision_size) * subdivision_size

        # Handle beat overflow to next bar
        if quantized_beat > self.beats_per_bar:
            bar += 1
            quantized_beat = 1.0
        elif quantized_beat < 1:
            quantized_beat = 1.0

        return (bar, quantized_beat)


@dataclass
class ChordBeatPosition:
    """A chord with its position in bars and beats."""

    chord_label: str
    bar: int  # 1-indexed bar number
    beat: float  # 1-indexed beat within bar (float for subdivisions)
    duration_beats: float  # Duration in beats

    def __str__(self) -> str:
        if self.beat == int(self.beat):
            return f"{self.chord_label} @ bar {self.bar}, beat {int(self.beat)}"
        return f"{self.chord_label} @ bar {self.bar}, beat {self.beat:.2f}"


def detect_tempo(audio_path: str) -> Optional[float]:
    """
    Detect the tempo (BPM) of an audio file.

    Args:
        audio_path: Path to the audio file

    Returns:
        Estimated BPM or None if detection failed
    """
    if not LIBROSA_AVAILABLE:
        return None

    try:
        y, sr = librosa.load(audio_path, sr=None)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # librosa returns an array, get scalar value
        if hasattr(tempo, "__len__"):
            tempo = float(tempo[0]) if len(tempo) > 0 else float(tempo)
        else:
            tempo = float(tempo)

        return round(tempo, 1)
    except Exception:
        return None


def detect_beats(audio_path: str) -> Optional[BeatGrid]:
    """
    Detect beats and create a beat grid for an audio file.

    Args:
        audio_path: Path to the audio file

    Returns:
        BeatGrid object or None if detection failed
    """
    if not LIBROSA_AVAILABLE:
        return None

    try:
        y, sr = librosa.load(audio_path, sr=None)

        # Detect tempo and beats
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        # Convert frames to times
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        if not beat_times:
            return None

        # Get tempo as scalar
        if hasattr(tempo, "__len__"):
            tempo = float(tempo[0]) if len(tempo) > 0 else float(tempo)
        else:
            tempo = float(tempo)

        # Try to detect downbeats (bar starts)
        # For simplicity, assume 4/4 time and first beat is downbeat
        time_signature = (4, 4)
        beats_per_bar = time_signature[0]

        downbeat_times = beat_times[::beats_per_bar]

        return BeatGrid(
            bpm=round(tempo, 1),
            beat_times=beat_times,
            downbeat_times=downbeat_times,
            time_signature=time_signature,
            first_beat_time=beat_times[0] if beat_times else 0.0,
        )
    except Exception:
        return None


def estimate_tempo_from_chord_timing(
    chord_times: List[Tuple[float, float]],
    common_tempos: List[float] = None,
) -> Optional[float]:
    """
    Estimate tempo from chord change timing patterns.

    This is a fallback when audio analysis isn't available.
    Looks for common intervals between chord changes that might
    correspond to beat boundaries.

    Args:
        chord_times: List of (start_time, end_time) tuples
        common_tempos: List of likely tempos to check against

    Returns:
        Estimated BPM or None
    """
    if not chord_times or len(chord_times) < 2:
        return None

    if common_tempos is None:
        # Common tempos in music production
        common_tempos = [60, 70, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 140, 150, 160, 170, 180]

    # Calculate intervals between chord changes
    intervals = []
    for i in range(len(chord_times) - 1):
        interval = chord_times[i + 1][0] - chord_times[i][0]
        if interval > 0.1:  # Ignore very short intervals
            intervals.append(interval)

    if not intervals:
        return None

    # Find the most common interval
    # Round to 2 decimal places to group similar intervals
    rounded_intervals = [round(i, 2) for i in intervals]
    interval_counts = {}
    for interval in rounded_intervals:
        interval_counts[interval] = interval_counts.get(interval, 0) + 1

    # Get the most common interval
    most_common_interval = max(interval_counts, key=interval_counts.get)

    # Try to match to common tempos
    # Assume chord changes happen on beats (quarters, halves, or whole notes)
    best_tempo = None
    best_score = float("inf")

    for tempo in common_tempos:
        beat_duration = 60.0 / tempo

        # Check how well the interval fits various beat multiples
        for multiplier in [0.5, 1, 2, 4]:
            expected_interval = beat_duration * multiplier
            error = abs(most_common_interval - expected_interval)

            if error < best_score:
                best_score = error
                best_tempo = tempo

    # Only return if we have a reasonable match (within 10% of beat duration)
    if best_tempo and best_score < (60.0 / best_tempo) * 0.1:
        return best_tempo

    return None


def create_beat_grid_from_tempo(
    bpm: float,
    duration_seconds: float,
    first_beat_offset: float = 0.0,
    time_signature: Tuple[int, int] = (4, 4),
) -> BeatGrid:
    """
    Create a beat grid from a known tempo.

    Args:
        bpm: Tempo in beats per minute
        duration_seconds: Total duration of the audio
        first_beat_offset: Time of the first beat (default 0)
        time_signature: Time signature tuple (default 4/4)

    Returns:
        BeatGrid object
    """
    beat_duration = 60.0 / bpm
    beats_per_bar = time_signature[0]

    # Generate beat times
    beat_times = []
    current_time = first_beat_offset
    while current_time < duration_seconds:
        beat_times.append(current_time)
        current_time += beat_duration

    # Generate downbeat times
    downbeat_times = beat_times[::beats_per_bar]

    return BeatGrid(
        bpm=bpm,
        beat_times=beat_times,
        downbeat_times=downbeat_times,
        time_signature=time_signature,
        first_beat_time=first_beat_offset,
    )


def quantize_chords_to_beats(
    chords: List[Tuple[float, float, str]],
    beat_grid: BeatGrid,
    subdivision: int = 1,
) -> List[ChordBeatPosition]:
    """
    Quantize chord events to beat positions.

    Args:
        chords: List of (start_time, end_time, chord_label) tuples
        beat_grid: BeatGrid to quantize against
        subdivision: Beat subdivision (1=quarters, 2=eighths, 4=sixteenths)

    Returns:
        List of ChordBeatPosition objects
    """
    result = []

    for start_time, end_time, chord_label in chords:
        # Quantize start position
        bar, beat = beat_grid.quantize_to_beat(start_time, subdivision)

        # Calculate duration in beats
        duration_seconds = end_time - start_time
        duration_beats = duration_seconds / beat_grid.beat_duration

        # Quantize duration to subdivision
        subdivision_size = 1.0 / subdivision
        duration_beats = round(duration_beats / subdivision_size) * subdivision_size
        duration_beats = max(subdivision_size, duration_beats)  # Minimum one subdivision

        result.append(
            ChordBeatPosition(
                chord_label=chord_label,
                bar=bar,
                beat=beat,
                duration_beats=duration_beats,
            )
        )

    return result


def normalize_chord_rhythm(
    chords: List[ChordBeatPosition],
) -> List[Tuple[float, str]]:
    """
    Normalize chord positions to a rhythm-only representation.

    Converts absolute bar/beat positions to relative positions
    within a repeating pattern, making it tempo-agnostic.

    Args:
        chords: List of ChordBeatPosition objects

    Returns:
        List of (beat_position, chord_label) where beat_position
        is the position within the pattern (0-indexed)
    """
    if not chords:
        return []

    # Find the total length in beats
    if len(chords) == 1:
        total_beats = chords[0].duration_beats
    else:
        first_bar = chords[0].bar
        first_beat = chords[0].beat
        last = chords[-1]
        # Calculate span
        bar_span = last.bar - first_bar
        beat_span = (last.beat - first_beat) + last.duration_beats
        total_beats = bar_span * 4 + beat_span  # Assuming 4/4

    if total_beats <= 0:
        return []

    # Normalize positions to 0-1 range
    result = []
    first_bar = chords[0].bar
    first_beat = chords[0].beat

    for chord in chords:
        bar_offset = chord.bar - first_bar
        beat_offset = chord.beat - first_beat
        absolute_beat = bar_offset * 4 + beat_offset  # Assuming 4/4
        normalized_position = absolute_beat / total_beats
        result.append((normalized_position, chord.chord_label))

    return result


def check_librosa_available() -> bool:
    """Check if librosa is available for audio analysis."""
    return LIBROSA_AVAILABLE

"""
Beat-aligned scoring engine for pitch-based harmonic compatibility.

Scores detected notes against a user-provided chord progression
on a beat-by-beat basis, calculating what proportion of notes
are harmonically compatible with the active chord.

Supports two modes:
1. Audio analysis: Extract pitches from audio files on-demand (slower)
2. MIDI analysis: Read notes from pre-transcribed MIDI files (faster)
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

from .models import (
    NoteEvent,
    UserChordSpec,
    UserProgression,
    PitchAnalysisResult,
    BeatCompatibilityScore,
    SamplePitchCompatibilityResult,
)


@dataclass
class ScanStatistics:
    """Statistics from a sample scanning operation."""
    total_audio_files: int = 0
    midi_files_used: int = 0
    audio_files_analyzed: int = 0
    files_skipped: int = 0
    errors: int = 0

    @property
    def files_processed(self) -> int:
        return self.midi_files_used + self.audio_files_analyzed

    def __str__(self) -> str:
        parts = []
        if self.midi_files_used > 0:
            parts.append(f"{self.midi_files_used} MIDI")
        if self.audio_files_analyzed > 0:
            parts.append(f"{self.audio_files_analyzed} audio")
        if self.files_skipped > 0:
            parts.append(f"{self.files_skipped} skipped (no MIDI)")
        if self.errors > 0:
            parts.append(f"{self.errors} errors")
        return f"Processed: {', '.join(parts)}" if parts else "No files processed"


from .theory import (
    get_chord_notes,
    chord_to_scale,
    NOTE_TO_SEMITONE,
    SEMITONE_TO_NOTE,
    get_transposition_description,
)
from .pitch_detector import (
    extract_pitches_auto,
    SUPPORTED_FORMATS,
    LIBROSA_AVAILABLE,
)

# Check for pretty_midi availability (for MIDI file reading)
try:
    import pretty_midi
    PRETTY_MIDI_AVAILABLE = True
except ImportError:
    PRETTY_MIDI_AVAILABLE = False

# MIDI file suffixes from transcription backends
MIDI_BACKEND_SUFFIXES = [
    "_basic_pitch",
    "_piano_transcription",
    "_onsets_frames",
    "_omnizart",
    "_mt3",
]


def _midi_note_to_note_name(midi_note: int) -> str:
    """Convert MIDI note number to note name (e.g., 60 -> 'C4')."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    note = note_names[midi_note % 12]
    return f"{note}{octave}"


def _midi_note_to_hz(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def find_midi_for_audio(audio_path: str, backend: Optional[str] = None) -> Optional[str]:
    """
    Find a corresponding MIDI file for an audio file.

    Looks for MIDI files with the same base name plus a backend suffix.
    For example, for 'sample.wav', looks for:
    - sample_basic_pitch.mid
    - sample_piano_transcription.mid
    - etc.

    Args:
        audio_path: Path to the audio file
        backend: Optional specific backend suffix to look for (e.g., 'basic_pitch')

    Returns:
        Path to the MIDI file if found, None otherwise
    """
    audio_path = Path(audio_path)
    base_name = audio_path.stem
    parent_dir = audio_path.parent

    if backend:
        # Look for specific backend
        suffixes = [f"_{backend}"]
    else:
        # Look for any backend (prefer in order listed)
        suffixes = MIDI_BACKEND_SUFFIXES

    for suffix in suffixes:
        midi_path = parent_dir / f"{base_name}{suffix}.mid"
        if midi_path.exists():
            return str(midi_path)

    return None


def find_all_midi_for_audio(audio_path: str) -> List[Tuple[str, str]]:
    """
    Find all corresponding MIDI files for an audio file.

    Looks for MIDI files with the same base name plus any backend suffix.

    Args:
        audio_path: Path to the audio file

    Returns:
        List of tuples (midi_path, backend_name) for all found MIDI files
    """
    audio_path = Path(audio_path)
    base_name = audio_path.stem
    parent_dir = audio_path.parent

    found = []
    for suffix in MIDI_BACKEND_SUFFIXES:
        midi_path = parent_dir / f"{base_name}{suffix}.mid"
        if midi_path.exists():
            # Extract backend name from suffix (remove leading underscore)
            backend_name = suffix[1:]
            found.append((str(midi_path), backend_name))

    return found


def read_notes_from_midi(midi_path: str) -> List[NoteEvent]:
    """
    Read note events from a MIDI file.

    Args:
        midi_path: Path to the MIDI file

    Returns:
        List of NoteEvent objects extracted from the MIDI file

    Raises:
        ImportError: If pretty_midi is not installed
        FileNotFoundError: If the MIDI file doesn't exist
    """
    if not PRETTY_MIDI_AVAILABLE:
        raise ImportError(
            "pretty_midi is required for MIDI file reading. "
            "Install with: pip install pretty_midi"
        )

    midi_path = Path(midi_path)
    if not midi_path.exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes = []

    for instrument in pm.instruments:
        # Skip drum tracks
        if instrument.is_drum:
            continue

        for note in instrument.notes:
            note_event = NoteEvent(
                start_time=note.start,
                end_time=note.end,
                pitch_hz=_midi_note_to_hz(note.pitch),
                midi_note=note.pitch,
                pitch_class=note.pitch % 12,
                note_name=_midi_note_to_note_name(note.pitch),
                confidence=1.0,  # MIDI notes have full confidence
                amplitude=note.velocity / 127.0,  # Normalize velocity to 0-1
            )
            notes.append(note_event)

    # Sort by start time
    notes.sort(key=lambda n: n.start_time)
    return notes


def extract_pitches_from_midi(
    audio_path: str,
    backend: Optional[str] = None,
    merge_backends: bool = False,
) -> Optional[PitchAnalysisResult]:
    """
    Extract pitch analysis from a pre-transcribed MIDI file.

    This is much faster than extracting from audio, as the MIDI file
    already contains the transcribed notes.

    Args:
        audio_path: Path to the original audio file (used to find the MIDI file)
        backend: Optional specific backend suffix to look for
        merge_backends: If True and backend is None, merge notes from all available
                       MIDI transcriptions for the same audio file

    Returns:
        PitchAnalysisResult if a MIDI file was found and read, None otherwise
    """
    if merge_backends and backend is None:
        # Find all available MIDI files and merge their notes
        midi_files = find_all_midi_for_audio(audio_path)
        if not midi_files:
            return None

        all_notes = []
        backends_used = []
        for midi_path, backend_name in midi_files:
            try:
                notes = read_notes_from_midi(midi_path)
                if notes:
                    all_notes.extend(notes)
                    backends_used.append(backend_name)
            except Exception:
                continue

        if not all_notes:
            return None

        # Remove duplicate notes (same pitch, same time window)
        # Consider notes duplicates if they have same pitch class and overlap significantly
        unique_notes = _deduplicate_notes(all_notes)
        notes = unique_notes
    else:
        # Original single-backend behavior
        midi_path = find_midi_for_audio(audio_path, backend)
        if midi_path is None:
            return None

        try:
            notes = read_notes_from_midi(midi_path)
        except Exception:
            return None

        if not notes:
            return None

    # Calculate duration from the notes
    duration = max(n.end_time for n in notes) if notes else 0.0

    # Estimate polyphony level (max simultaneous notes)
    # Simple approach: count overlapping notes at various points
    polyphony_level = 1
    if len(notes) > 1:
        # Sample a few time points and check overlap
        for i, note in enumerate(notes):
            overlapping = sum(
                1 for other in notes
                if other.start_time < note.end_time and other.end_time > note.start_time
            )
            polyphony_level = max(polyphony_level, overlapping)

    return PitchAnalysisResult(
        filepath=audio_path,
        notes=notes,
        duration_seconds=duration,
        is_monophonic=polyphony_level == 1,
        polyphony_level=polyphony_level,
        detected_bpm=None,  # Not available from MIDI
        file_hash=None,
    )


def _deduplicate_notes(notes: List[NoteEvent], time_tolerance: float = 0.05) -> List[NoteEvent]:
    """
    Remove duplicate notes that appear in multiple MIDI transcriptions.

    Notes are considered duplicates if they have the same pitch class and
    their start times are within the time_tolerance.

    Args:
        notes: List of NoteEvent objects (possibly with duplicates)
        time_tolerance: Maximum time difference (seconds) to consider notes as duplicates

    Returns:
        List of unique NoteEvent objects
    """
    if not notes:
        return []

    # Sort by start time, then by pitch
    sorted_notes = sorted(notes, key=lambda n: (n.start_time, n.midi_note))

    unique = []
    for note in sorted_notes:
        # Check if this note is a duplicate of an already-added note
        is_duplicate = False
        for existing in unique:
            if (existing.midi_note == note.midi_note and
                abs(existing.start_time - note.start_time) < time_tolerance):
                # It's a duplicate - keep the one with longer duration
                if note.end_time - note.start_time > existing.end_time - existing.start_time:
                    unique.remove(existing)
                    unique.append(note)
                is_duplicate = True
                break

        if not is_duplicate:
            unique.append(note)

    return sorted(unique, key=lambda n: n.start_time)


def align_notes_to_beats(
    notes: List[NoteEvent],
    bpm: float,
    time_signature: Tuple[int, int] = (4, 4),
    first_beat_time: float = 0.0,
) -> List[NoteEvent]:
    """
    Assign bar/beat positions to detected notes.

    Args:
        notes: List of NoteEvent objects with timing
        bpm: Tempo in beats per minute
        time_signature: Time signature as (numerator, denominator)
        first_beat_time: Time in seconds of the first beat

    Returns:
        List of NoteEvent objects with bar/beat info added
    """
    if not notes:
        return []

    beats_per_bar = time_signature[0]
    beat_duration = 60.0 / bpm

    aligned = []
    for note in notes:
        # Calculate beat position relative to first beat
        time_from_first_beat = note.start_time - first_beat_time
        total_beats = time_from_first_beat / beat_duration

        # Convert to bar and beat (1-indexed)
        bar = int(total_beats // beats_per_bar) + 1
        beat_in_bar = (total_beats % beats_per_bar) + 1

        # Handle negative times (before first beat)
        if time_from_first_beat < 0:
            bar = 0
            beat_in_bar = beats_per_bar + (total_beats % beats_per_bar) + 1

        aligned.append(note.with_beat_info(bar=bar, beat=beat_in_bar))

    return aligned


def group_notes_by_beat(
    notes: List[NoteEvent],
    total_beats: int,
    beats_per_bar: int,
) -> dict:
    """
    Group notes by their beat position.

    Args:
        notes: List of aligned NoteEvent objects
        total_beats: Total number of beats in progression
        beats_per_bar: Beats per bar

    Returns:
        Dictionary mapping (bar, beat) -> List[NoteEvent]
    """
    groups = defaultdict(list)

    for note in notes:
        if note.has_beat_info:
            # Use integer beat for grouping
            beat_in_bar = int(note.beat)
            key = (note.bar, beat_in_bar)
            groups[key].append(note)

    return dict(groups)


def score_beat(
    notes_in_beat: List[NoteEvent],
    chord: UserChordSpec,
    chord_weight: float = 50.0,
    scale_weight: float = 30.0,
    clash_penalty_per: float = 5.0,
    max_clash_penalty: float = 20.0,
) -> Tuple[float, float, float, int]:
    """
    Score the notes occurring during a single beat against the active chord.

    Scoring formula:
    - Chord tones (50%): Notes that are part of the chord
    - Scale tones (30%): Notes in the implied scale but not chord tones
    - Clash penalty (20%): Deducted for semitone clashes with chord tones

    Notes are weighted by duration * amplitude * confidence.

    Args:
        notes_in_beat: Notes occurring during this beat
        chord: The active chord
        chord_weight: Maximum points for chord tone ratio
        scale_weight: Maximum points for scale tone ratio
        clash_penalty_per: Penalty per clash
        max_clash_penalty: Maximum total clash penalty

    Returns:
        Tuple of (weighted_score, in_chord_ratio, in_scale_ratio, clash_count)
    """
    if not notes_in_beat:
        # Empty beat gets neutral score (no penalty, no bonus)
        return 50.0, 0.0, 0.0, 0

    # Get chord tones and scale tones
    chord_tones = get_chord_notes(chord.chord_label)
    scale_tones = chord_to_scale(chord.chord_label)

    # Calculate weighted contributions
    total_weight = 0.0
    in_chord_weight = 0.0
    in_scale_weight = 0.0
    clash_count = 0

    for note in notes_in_beat:
        # Weight by duration, amplitude, and confidence
        weight = note.duration * note.amplitude * note.confidence
        total_weight += weight

        pitch_class = note.pitch_class

        if pitch_class in chord_tones:
            in_chord_weight += weight
            in_scale_weight += weight  # Chord tones are always in scale
        elif pitch_class in scale_tones:
            in_scale_weight += weight

        # Check for semitone clashes with chord tones. `abs(a - b) % 12 == 1`
        # misses the B/C wrap (pitch classes 11 and 0: abs(11-0)=11, not 1);
        # checking both neighbours mod 12 catches it. (compatibility.py's
        # _score_note_overlap fixed this same bug on 2026-09-16.)
        for chord_tone in chord_tones:
            if (pitch_class + 1) % 12 == chord_tone or (pitch_class - 1) % 12 == chord_tone:
                clash_count += 1
                break  # Only count one clash per note

    # Calculate ratios
    if total_weight > 0:
        in_chord_ratio = in_chord_weight / total_weight
        in_scale_ratio = in_scale_weight / total_weight
    else:
        in_chord_ratio = 0.0
        in_scale_ratio = 0.0

    # Calculate score components
    chord_score = in_chord_ratio * chord_weight
    scale_score = in_scale_ratio * scale_weight
    clash_deduction = min(clash_count * clash_penalty_per, max_clash_penalty)
    clash_score = max_clash_penalty - clash_deduction

    # Total weighted score
    weighted_score = chord_score + scale_score + clash_score

    return weighted_score, in_chord_ratio, in_scale_ratio, clash_count


def score_sample_against_progression(
    pitch_analysis: PitchAnalysisResult,
    progression: UserProgression,
) -> SamplePitchCompatibilityResult:
    """
    Score an entire audio sample against a user chord progression.

    Process:
    1. Align detected notes to the progression's beat grid
    2. For each beat, get the active chord and score the notes
    3. Aggregate beat scores into an overall compatibility score

    Args:
        pitch_analysis: Result from pitch extraction
        progression: User-provided chord progression

    Returns:
        SamplePitchCompatibilityResult with detailed scoring
    """
    # Align notes to beats
    aligned_notes = align_notes_to_beats(
        notes=pitch_analysis.notes,
        bpm=progression.bpm,
        time_signature=progression.time_signature,
    )

    # Group notes by beat
    total_beats = int(progression.total_beats)
    beats_per_bar = progression.beats_per_bar
    notes_by_beat = group_notes_by_beat(aligned_notes, total_beats, beats_per_bar)

    # Score each beat
    beat_scores = []
    total_in_chord = 0.0
    total_in_scale = 0.0
    total_clashes = 0
    scored_beats = 0

    for beat_num in range(1, total_beats + 1):
        # Calculate bar and beat position
        bar = ((beat_num - 1) // beats_per_bar) + 1
        beat_in_bar = ((beat_num - 1) % beats_per_bar) + 1

        # Get active chord at this beat
        chord = progression.chord_at_beat(beat_num)
        if chord is None:
            continue

        # Get notes in this beat
        notes_in_beat = notes_by_beat.get((bar, beat_in_bar), [])

        # Score the beat
        weighted_score, in_chord_ratio, in_scale_ratio, clash_count = score_beat(
            notes_in_beat, chord
        )

        beat_scores.append(BeatCompatibilityScore(
            beat_number=beat_num,
            bar_number=bar,
            beat_in_bar=beat_in_bar,
            active_chord=chord,
            notes_in_beat=notes_in_beat,
            in_chord_ratio=in_chord_ratio,
            in_scale_ratio=in_scale_ratio,
            clash_count=clash_count,
            weighted_score=weighted_score,
        ))

        # Accumulate for averages (only count beats with notes)
        if notes_in_beat:
            total_in_chord += in_chord_ratio
            total_in_scale += in_scale_ratio
            scored_beats += 1
        total_clashes += clash_count

    # Calculate overall score and averages
    if beat_scores:
        overall_score = sum(bs.weighted_score for bs in beat_scores) / len(beat_scores)
    else:
        overall_score = 50.0  # Neutral if no beats to score

    if scored_beats > 0:
        avg_in_chord = total_in_chord / scored_beats
        avg_in_scale = total_in_scale / scored_beats
    else:
        avg_in_chord = 0.0
        avg_in_scale = 0.0

    # Generate reasons
    reasons = _generate_score_reasons(
        overall_score, avg_in_chord, avg_in_scale, total_clashes, scored_beats
    )

    return SamplePitchCompatibilityResult(
        filepath=pitch_analysis.filepath,
        filename=pitch_analysis.filename,
        overall_score=overall_score,
        beat_scores=beat_scores,
        avg_in_chord_ratio=avg_in_chord,
        avg_in_scale_ratio=avg_in_scale,
        total_clash_count=total_clashes,
        pitch_analysis=pitch_analysis,
        reasons=reasons,
        progression=progression,
    )


def score_sample_with_transposition(
    pitch_analysis: PitchAnalysisResult,
    progression: UserProgression,
) -> SamplePitchCompatibilityResult:
    """
    Score an audio sample against all 12 transpositions of the progression.

    This enables key-agnostic matching by finding the transposition that
    produces the best harmonic compatibility score.

    Process:
    1. For each of 12 possible transpositions (0-11 semitones):
       - Transpose the user progression
       - Score the sample's pitches against the transposed progression
    2. Return the result with the highest score, including transposition info

    Args:
        pitch_analysis: Result from pitch extraction
        progression: User-provided chord progression

    Returns:
        SamplePitchCompatibilityResult with best score and transposition info
    """
    best_result = None
    best_score = -1.0
    best_transposition = 0

    # Get the estimated key of the user progression (target key)
    target_key = progression.estimated_key
    target_semitone = NOTE_TO_SEMITONE.get(target_key, 0) if target_key else 0

    # Try all 12 transpositions
    for transposition in range(12):
        # Transpose the progression
        transposed_prog = progression.transpose(transposition)

        # Score the sample against the transposed progression
        result = score_sample_against_progression(pitch_analysis, transposed_prog)

        if result.overall_score > best_score:
            best_score = result.overall_score
            best_result = result
            best_transposition = transposition

    if best_result is None:
        # Fallback to original progression if something went wrong
        best_result = score_sample_against_progression(pitch_analysis, progression)
        best_transposition = 0

    # Calculate the sample's implied key based on the transposition that worked best
    # If transposition=5 worked best, the sample is likely 5 semitones away from target
    if best_transposition > 0:
        # The sample's key is (target - transposition) mod 12
        # because we transposed the progression UP to match the sample
        sample_semitone = (target_semitone + best_transposition) % 12
        sample_key = SEMITONE_TO_NOTE.get(sample_semitone)

        # The recommended transposition for the SAMPLE is the negative
        # (i.e., transpose sample DOWN to match original progression)
        recommended = -best_transposition if best_transposition <= 6 else (12 - best_transposition)
        transposition_desc = get_transposition_description(sample_semitone, target_semitone)
    else:
        sample_key = target_key
        recommended = 0
        transposition_desc = "in key"

    # Create result with transposition info
    return SamplePitchCompatibilityResult(
        filepath=best_result.filepath,
        filename=best_result.filename,
        overall_score=best_result.overall_score,
        beat_scores=best_result.beat_scores,
        avg_in_chord_ratio=best_result.avg_in_chord_ratio,
        avg_in_scale_ratio=best_result.avg_in_scale_ratio,
        total_clash_count=best_result.total_clash_count,
        pitch_analysis=best_result.pitch_analysis,
        reasons=best_result.reasons,
        progression=progression,  # Original progression
        detected_key=sample_key,
        recommended_transposition=recommended,
        transposition_description=transposition_desc,
    )


def _generate_score_reasons(
    overall_score: float,
    avg_in_chord: float,
    avg_in_scale: float,
    total_clashes: int,
    scored_beats: int,
) -> List[str]:
    """Generate human-readable reasons for the score."""
    reasons = []

    # Overall assessment
    if overall_score >= 80:
        reasons.append("Excellent harmonic fit")
    elif overall_score >= 60:
        reasons.append("Good harmonic compatibility")
    elif overall_score >= 40:
        reasons.append("Moderate harmonic fit")
    else:
        reasons.append("Limited harmonic compatibility")

    # Chord tone analysis
    if avg_in_chord >= 0.7:
        reasons.append("Strong chord tone presence")
    elif avg_in_chord >= 0.4:
        reasons.append("Moderate chord tone usage")
    elif avg_in_chord < 0.2 and scored_beats > 0:
        reasons.append("Few chord tones detected")

    # Scale analysis
    if avg_in_scale >= 0.9:
        reasons.append("Almost all notes in scale")
    elif avg_in_scale >= 0.7:
        reasons.append("Most notes diatonic")
    elif avg_in_scale < 0.5 and scored_beats > 0:
        reasons.append("Some chromatic notes present")

    # Clash analysis
    if total_clashes == 0:
        reasons.append("No semitone clashes")
    elif total_clashes <= 3:
        reasons.append(f"Minor dissonance ({total_clashes} clashes)")
    else:
        reasons.append(f"Noticeable dissonance ({total_clashes} clashes)")

    return reasons


def scan_and_rank_samples(
    sample_dir: str,
    progression: UserProgression,
    formats: Tuple[str, ...] = SUPPORTED_FORMATS,
    recursive: bool = True,
    min_score: float = 0.0,
    limit: int = 50,
    force_mono: bool = False,
    force_poly: bool = False,
    progress_callback: Optional[callable] = None,
    use_midi: bool = False,
    midi_backend: Optional[str] = None,
    midi_fallback: bool = True,
    normalize: bool = False,
    return_stats: bool = False,
    merge_midi_backends: bool = False,
) -> Tuple[List[SamplePitchCompatibilityResult], Optional[ScanStatistics]]:
    """
    Scan a directory of audio files and rank by compatibility.

    Args:
        sample_dir: Directory containing audio samples
        progression: User-provided chord progression
        formats: Tuple of supported file extensions
        recursive: Whether to scan subdirectories
        min_score: Minimum score to include in results
        limit: Maximum number of results
        force_mono: Force monophonic detection (audio mode only)
        force_poly: Force polyphonic detection (audio mode only)
        progress_callback: Optional callback(filepath, result) for progress
        use_midi: Use pre-transcribed MIDI files instead of audio analysis
        midi_backend: Specific MIDI backend suffix to look for (e.g., 'basic_pitch')
        midi_fallback: Fall back to audio analysis if MIDI not found (default: True)
        normalize: Use key-agnostic matching (score against all transpositions)
        return_stats: Return scan statistics along with results
        merge_midi_backends: If True, merge notes from all available MIDI transcriptions
                            (e.g., basic_pitch + piano_transcription) for better accuracy

    Returns:
        Tuple of (results, stats) where stats is ScanStatistics if return_stats=True, else None
    """
    dir_path = Path(sample_dir)
    if not dir_path.exists():
        raise FileNotFoundError(f"Sample directory not found: {sample_dir}")

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {sample_dir}")

    # Collect audio files
    audio_files = []
    for fmt in formats:
        pattern = f"**/*{fmt}" if recursive else f"*{fmt}"
        audio_files.extend(dir_path.glob(pattern))
        # Also check uppercase extensions
        pattern_upper = f"**/*{fmt.upper()}" if recursive else f"*{fmt.upper()}"
        audio_files.extend(dir_path.glob(pattern_upper))

    # Remove duplicates
    audio_files = list(set(audio_files))

    results = []
    stats = ScanStatistics(total_audio_files=len(audio_files))

    for audio_file in audio_files:
        try:
            pitch_analysis = None

            # Try MIDI-based extraction first if enabled
            if use_midi:
                pitch_analysis = extract_pitches_from_midi(
                    str(audio_file),
                    backend=midi_backend,
                    merge_backends=merge_midi_backends,
                )
                if pitch_analysis is not None:
                    stats.midi_files_used += 1

            # Fall back to audio analysis if MIDI not found/failed
            if pitch_analysis is None:
                if use_midi and not midi_fallback:
                    # Skip files without MIDI when fallback is disabled
                    stats.files_skipped += 1
                    continue

                pitch_analysis = extract_pitches_auto(
                    str(audio_file),
                    force_mono=force_mono,
                    force_poly=force_poly,
                )
                stats.audio_files_analyzed += 1

            # Score against progression
            if normalize:
                # Key-agnostic: score against all transpositions
                result = score_sample_with_transposition(pitch_analysis, progression)
            else:
                # Standard: score against progression as-is
                result = score_sample_against_progression(pitch_analysis, progression)

            if result.overall_score >= min_score:
                results.append(result)

            if progress_callback:
                progress_callback(str(audio_file), result)

        except Exception as e:
            stats.errors += 1
            if progress_callback:
                progress_callback(str(audio_file), None)

    # Sort by score descending
    results.sort(key=lambda r: r.overall_score, reverse=True)

    return results[:limit], stats if return_stats else None


def score_single_sample(
    audio_path: str,
    progression: UserProgression,
    force_mono: bool = False,
    force_poly: bool = False,
    use_midi: bool = False,
    midi_backend: Optional[str] = None,
    midi_fallback: bool = True,
    normalize: bool = False,
) -> SamplePitchCompatibilityResult:
    """
    Score a single audio file against a chord progression.

    Convenience function for scoring one sample.

    Args:
        audio_path: Path to audio file
        progression: User-provided chord progression
        force_mono: Force monophonic detection (audio mode only)
        force_poly: Force polyphonic detection (audio mode only)
        use_midi: Use pre-transcribed MIDI file instead of audio analysis
        midi_backend: Specific MIDI backend suffix to look for (e.g., 'basic_pitch')
        midi_fallback: Fall back to audio analysis if MIDI not found (default: True)
        normalize: Use key-agnostic matching (score against all transpositions)

    Returns:
        SamplePitchCompatibilityResult with scoring details
    """
    pitch_analysis = None

    # Try MIDI-based extraction first if enabled
    if use_midi:
        pitch_analysis = extract_pitches_from_midi(audio_path, backend=midi_backend)

    # Fall back to audio analysis if MIDI not found/failed
    if pitch_analysis is None:
        if use_midi and not midi_fallback:
            raise FileNotFoundError(
                f"No MIDI file found for {audio_path} and fallback is disabled"
            )

        pitch_analysis = extract_pitches_auto(
            audio_path,
            force_mono=force_mono,
            force_poly=force_poly,
        )

    if normalize:
        return score_sample_with_transposition(pitch_analysis, progression)
    else:
        return score_sample_against_progression(pitch_analysis, progression)


def explain_compatibility(
    result: SamplePitchCompatibilityResult,
    verbose: bool = False,
) -> str:
    """
    Generate a human-readable explanation of the compatibility score.

    Args:
        result: Scoring result
        verbose: Include per-beat breakdown

    Returns:
        Formatted explanation string
    """
    lines = [
        f"Sample: {result.filename}",
        f"Overall Score: {result.overall_score:.1f}/100",
        "",
        "Analysis:",
        f"  Notes detected: {result.note_count}",
        f"  Beats scored: {result.beat_count}",
        f"  Monophonic: {'Yes' if result.is_monophonic else 'No'}",
        "",
        "Harmonic Analysis:",
        f"  Chord tone ratio: {result.avg_in_chord_ratio:.1%}",
        f"  Scale tone ratio: {result.avg_in_scale_ratio:.1%}",
        f"  Semitone clashes: {result.total_clash_count}",
        "",
    ]

    if result.reasons:
        lines.append("Assessment:")
        for reason in result.reasons:
            lines.append(f"  - {reason}")
        lines.append("")

    if verbose and result.beat_scores:
        lines.append("Per-Beat Breakdown:")
        for bs in result.beat_scores[:16]:  # Limit to first 16 beats
            notes_str = f"{len(bs.notes_in_beat)} notes" if bs.notes_in_beat else "no notes"
            lines.append(
                f"  Bar {bs.bar_number} Beat {bs.beat_in_bar}: "
                f"{bs.active_chord.chord_label} - {bs.weighted_score:.1f} ({notes_str})"
            )
        if len(result.beat_scores) > 16:
            lines.append(f"  ... and {len(result.beat_scores) - 16} more beats")

    return "\n".join(lines)

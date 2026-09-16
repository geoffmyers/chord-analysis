"""
Pitch detection from audio files.

Supports both monophonic (single voice) and polyphonic (multiple voices)
audio samples using librosa and optionally Essentia.

Audio format support:
- Native: WAV, AIFF, FLAC
- Via FFmpeg: MP3, AAC, M4A, OGG
- Via afconvert (macOS): CAF
"""

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .models import NoteEvent, PitchAnalysisResult
from .theory import SEMITONE_TO_NOTE

# Supported audio formats
NATIVE_FORMATS = (".wav", ".aiff", ".aif", ".flac")
FFMPEG_FORMATS = (".mp3", ".aac", ".m4a", ".ogg", ".wma")
CAF_FORMATS = (".caf",)
SUPPORTED_FORMATS = NATIVE_FORMATS + FFMPEG_FORMATS + CAF_FORMATS

# Check for librosa availability
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

# Check for Essentia availability
try:
    import essentia.standard as es
    ESSENTIA_AVAILABLE = True
except ImportError:
    ESSENTIA_AVAILABLE = False


def check_pitch_detection_available() -> Tuple[bool, str]:
    """
    Check if pitch detection dependencies are available.

    Returns:
        Tuple of (is_available, status_message)
    """
    if not LIBROSA_AVAILABLE:
        return False, "librosa not installed. Install with: pip install librosa"

    message = "librosa available"
    if ESSENTIA_AVAILABLE:
        message += " (Essentia also available for enhanced polyphonic detection)"

    return True, message


def load_audio(
    audio_path: str,
    sr: int = 22050,
    mono: bool = True,
) -> Tuple[np.ndarray, int]:
    """
    Load audio file, handling format conversion if needed.

    Args:
        audio_path: Path to audio file
        sr: Target sample rate
        mono: Convert to mono if True

    Returns:
        Tuple of (audio_samples, sample_rate)

    Raises:
        FileNotFoundError: If file doesn't exist
        RuntimeError: If audio cannot be loaded
    """
    if not LIBROSA_AVAILABLE:
        raise RuntimeError("librosa not available for audio loading")

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    suffix = path.suffix.lower()

    # Try native loading first
    try:
        y, sr_actual = librosa.load(str(path), sr=sr, mono=mono)
        return y, sr_actual
    except Exception as native_error:
        # Try conversion for non-native formats
        if suffix in CAF_FORMATS:
            converted_path = _convert_caf(str(path))
            if converted_path:
                try:
                    y, sr_actual = librosa.load(converted_path, sr=sr, mono=mono)
                    # Clean up temp file
                    Path(converted_path).unlink(missing_ok=True)
                    return y, sr_actual
                except Exception:
                    pass

        raise RuntimeError(f"Failed to load audio: {native_error}")


def _convert_caf(caf_path: str) -> Optional[str]:
    """
    Convert CAF file to WAV using macOS afconvert or ffmpeg.

    Args:
        caf_path: Path to CAF file

    Returns:
        Path to converted WAV file, or None if conversion failed
    """
    # Create temp file for output
    temp_dir = tempfile.gettempdir()
    output_path = Path(temp_dir) / f"{Path(caf_path).stem}_converted.wav"

    # Try afconvert (macOS)
    try:
        result = subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", caf_path, str(output_path)],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try ffmpeg as fallback
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", caf_path, "-acodec", "pcm_s16le", str(output_path)],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def compute_file_hash(filepath: str) -> str:
    """
    Compute MD5 hash of a file for cache invalidation.

    Args:
        filepath: Path to file

    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def hz_to_midi(freq: float) -> int:
    """Convert frequency in Hz to MIDI note number."""
    if freq <= 0:
        return 0
    return int(round(12 * np.log2(freq / 440.0) + 69))


def midi_to_pitch_class(midi_note: int) -> int:
    """Convert MIDI note number to pitch class (0-11)."""
    return midi_note % 12


def midi_to_note_name(midi_note: int) -> str:
    """Convert MIDI note number to note name (e.g., 'C4', 'A#3')."""
    pitch_class = midi_note % 12
    octave = (midi_note // 12) - 1
    note_name = SEMITONE_TO_NOTE.get(pitch_class, "?")
    return f"{note_name}{octave}"


def detect_pitches_monophonic(
    audio_path: str,
    min_freq: float = 60.0,
    max_freq: float = 2000.0,
    hop_length: int = 512,
    min_confidence: float = 0.5,
    min_duration: float = 0.05,
) -> List[NoteEvent]:
    """
    Detect pitches in monophonic audio using pYIN algorithm.

    pYIN is optimized for single-voice detection (vocals, bass, lead).

    Args:
        audio_path: Path to audio file
        min_freq: Minimum frequency to detect (Hz)
        max_freq: Maximum frequency to detect (Hz)
        hop_length: Hop length for analysis frames
        min_confidence: Minimum confidence to include a note
        min_duration: Minimum note duration in seconds

    Returns:
        List of NoteEvent objects
    """
    if not LIBROSA_AVAILABLE:
        raise RuntimeError("librosa required for pitch detection")

    y, sr = load_audio(audio_path)

    # pYIN pitch detection
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=min_freq,
        fmax=max_freq,
        sr=sr,
        hop_length=hop_length,
    )

    # Get frame times
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    # Compute amplitude envelope for weighting
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    if len(rms) > len(f0):
        rms = rms[: len(f0)]
    elif len(rms) < len(f0):
        rms = np.pad(rms, (0, len(f0) - len(rms)), mode="edge")

    # Normalize amplitude
    max_rms = np.max(rms) if np.max(rms) > 0 else 1.0
    normalized_rms = rms / max_rms

    # Segment pitched frames into notes
    notes = _segment_notes_from_frames(
        f0=f0,
        times=times,
        confidences=voiced_probs,
        amplitudes=normalized_rms,
        min_confidence=min_confidence,
        min_duration=min_duration,
    )

    return notes


def detect_pitches_polyphonic(
    audio_path: str,
    hop_length: int = 512,
    threshold: float = 0.3,
    min_duration: float = 0.05,
) -> List[NoteEvent]:
    """
    Detect multiple simultaneous pitches using chromagram analysis.

    Uses CQT-based chroma features to detect pitch classes, then
    estimates specific octaves from spectral peaks.

    Args:
        audio_path: Path to audio file
        hop_length: Hop length for analysis frames
        threshold: Minimum chroma activation to consider a pitch present
        min_duration: Minimum note duration in seconds

    Returns:
        List of NoteEvent objects
    """
    if not LIBROSA_AVAILABLE:
        raise RuntimeError("librosa required for pitch detection")

    y, sr = load_audio(audio_path)

    # Compute CQT-based chromagram
    chroma = librosa.feature.chroma_cqt(
        y=y, sr=sr, hop_length=hop_length, n_chroma=12
    )

    # Get frame times
    times = librosa.times_like(chroma, sr=sr, hop_length=hop_length)
    frame_duration = times[1] - times[0] if len(times) > 1 else hop_length / sr

    # Compute RMS for amplitude
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    if len(rms) > chroma.shape[1]:
        rms = rms[: chroma.shape[1]]
    elif len(rms) < chroma.shape[1]:
        rms = np.pad(rms, (0, chroma.shape[1] - len(rms)), mode="edge")

    max_rms = np.max(rms) if np.max(rms) > 0 else 1.0
    normalized_rms = rms / max_rms

    # Detect active pitch classes per frame
    notes = []
    active_notes = {}  # pitch_class -> start_time, cumulative_amplitude

    for frame_idx in range(chroma.shape[1]):
        time = times[frame_idx]
        amplitude = normalized_rms[frame_idx]

        for pitch_class in range(12):
            activation = chroma[pitch_class, frame_idx]
            is_active = activation >= threshold

            if is_active:
                if pitch_class not in active_notes:
                    # Start new note
                    active_notes[pitch_class] = {
                        "start_time": time,
                        "amplitudes": [amplitude * activation],
                        "activations": [activation],
                    }
                else:
                    # Continue existing note
                    active_notes[pitch_class]["amplitudes"].append(amplitude * activation)
                    active_notes[pitch_class]["activations"].append(activation)
            else:
                if pitch_class in active_notes:
                    # End note
                    note_data = active_notes.pop(pitch_class)
                    duration = time - note_data["start_time"]

                    if duration >= min_duration:
                        avg_amplitude = np.mean(note_data["amplitudes"])
                        avg_activation = np.mean(note_data["activations"])

                        # Estimate octave (assume middle range for chroma)
                        midi_note = 60 + pitch_class  # C4 + pitch_class

                        notes.append(NoteEvent(
                            start_time=note_data["start_time"],
                            end_time=time,
                            pitch_hz=librosa.midi_to_hz(midi_note),
                            midi_note=midi_note,
                            pitch_class=pitch_class,
                            note_name=midi_to_note_name(midi_note),
                            confidence=avg_activation,
                            amplitude=avg_amplitude,
                        ))

    # Close any remaining active notes
    final_time = times[-1] if len(times) > 0 else 0
    for pitch_class, note_data in active_notes.items():
        duration = final_time - note_data["start_time"]
        if duration >= min_duration:
            avg_amplitude = np.mean(note_data["amplitudes"])
            avg_activation = np.mean(note_data["activations"])
            midi_note = 60 + pitch_class

            notes.append(NoteEvent(
                start_time=note_data["start_time"],
                end_time=final_time,
                pitch_hz=librosa.midi_to_hz(midi_note),
                midi_note=midi_note,
                pitch_class=pitch_class,
                note_name=midi_to_note_name(midi_note),
                confidence=avg_activation,
                amplitude=avg_amplitude,
            ))

    # Sort by start time
    notes.sort(key=lambda n: n.start_time)

    return notes


def detect_pitches_essentia(
    audio_path: str,
    min_freq: float = 60.0,
    max_freq: float = 2000.0,
    min_duration: float = 0.05,
) -> List[NoteEvent]:
    """
    Detect pitches using Essentia's PredominantPitchMelodia.

    Essentia provides more accurate pitch tracking than librosa
    for many use cases, especially with complex audio.

    Args:
        audio_path: Path to audio file
        min_freq: Minimum frequency to detect
        max_freq: Maximum frequency to detect
        min_duration: Minimum note duration

    Returns:
        List of NoteEvent objects
    """
    if not ESSENTIA_AVAILABLE:
        raise RuntimeError("Essentia not available")

    # Load audio with Essentia
    loader = es.MonoLoader(filename=audio_path)
    audio = loader()
    sr = 44100  # Essentia default

    # Run PredominantPitchMelodia
    pitch_extractor = es.PredominantPitchMelodia(
        minFrequency=min_freq,
        maxFrequency=max_freq,
    )
    pitches, confidence = pitch_extractor(audio)

    # Convert to times
    hop_size = 128  # Default hop for PredominantPitchMelodia
    times = np.arange(len(pitches)) * hop_size / sr

    # Segment into notes
    notes = _segment_notes_from_frames(
        f0=pitches,
        times=times,
        confidences=confidence,
        amplitudes=confidence,  # Use confidence as proxy for amplitude
        min_confidence=0.5,
        min_duration=min_duration,
    )

    return notes


def _segment_notes_from_frames(
    f0: np.ndarray,
    times: np.ndarray,
    confidences: np.ndarray,
    amplitudes: np.ndarray,
    min_confidence: float = 0.5,
    min_duration: float = 0.05,
) -> List[NoteEvent]:
    """
    Segment frame-level pitch data into discrete note events.

    Args:
        f0: Array of fundamental frequencies (Hz), NaN for unvoiced
        times: Array of frame times
        confidences: Array of confidence values
        amplitudes: Array of amplitude values
        min_confidence: Minimum confidence threshold
        min_duration: Minimum note duration

    Returns:
        List of NoteEvent objects
    """
    notes = []
    current_note = None

    for i in range(len(f0)):
        freq = f0[i]
        time = times[i]
        conf = confidences[i] if i < len(confidences) else 1.0
        amp = amplitudes[i] if i < len(amplitudes) else 1.0

        # Check if this frame is pitched
        is_pitched = (
            not np.isnan(freq)
            and freq > 0
            and conf >= min_confidence
        )

        if is_pitched:
            midi = hz_to_midi(freq)
            pitch_class = midi_to_pitch_class(midi)

            if current_note is None:
                # Start new note
                current_note = {
                    "start_time": time,
                    "frequencies": [freq],
                    "midi_notes": [midi],
                    "confidences": [conf],
                    "amplitudes": [amp],
                }
            else:
                # Check if same note continues (within 2 semitones)
                avg_midi = np.median(current_note["midi_notes"])
                if abs(midi - avg_midi) <= 2:
                    # Continue current note
                    current_note["frequencies"].append(freq)
                    current_note["midi_notes"].append(midi)
                    current_note["confidences"].append(conf)
                    current_note["amplitudes"].append(amp)
                else:
                    # End current note, start new one
                    note = _finalize_note(current_note, time, min_duration)
                    if note:
                        notes.append(note)
                    current_note = {
                        "start_time": time,
                        "frequencies": [freq],
                        "midi_notes": [midi],
                        "confidences": [conf],
                        "amplitudes": [amp],
                    }
        else:
            # End current note if any
            if current_note is not None:
                note = _finalize_note(current_note, time, min_duration)
                if note:
                    notes.append(note)
                current_note = None

    # Finalize last note
    if current_note is not None:
        final_time = times[-1] if len(times) > 0 else 0
        note = _finalize_note(current_note, final_time, min_duration)
        if note:
            notes.append(note)

    return notes


def _finalize_note(note_data: dict, end_time: float, min_duration: float) -> Optional[NoteEvent]:
    """Create a NoteEvent from accumulated frame data."""
    duration = end_time - note_data["start_time"]
    if duration < min_duration:
        return None

    avg_freq = np.median(note_data["frequencies"])
    midi = int(round(np.median(note_data["midi_notes"])))
    pitch_class = midi_to_pitch_class(midi)
    avg_conf = np.mean(note_data["confidences"])
    avg_amp = np.mean(note_data["amplitudes"])

    return NoteEvent(
        start_time=note_data["start_time"],
        end_time=end_time,
        pitch_hz=avg_freq,
        midi_note=midi,
        pitch_class=pitch_class,
        note_name=midi_to_note_name(midi),
        confidence=avg_conf,
        amplitude=avg_amp,
    )


def detect_voicing_type(audio_path: str) -> Tuple[bool, int]:
    """
    Determine if audio is monophonic or polyphonic.

    Uses spectral analysis to estimate the number of simultaneous voices.

    Args:
        audio_path: Path to audio file

    Returns:
        Tuple of (is_monophonic, estimated_polyphony_level)
    """
    if not LIBROSA_AVAILABLE:
        return True, 1  # Assume monophonic if can't analyze

    try:
        y, sr = load_audio(audio_path)

        # Compute chromagram
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Count average number of active pitch classes per frame
        threshold = 0.3
        active_per_frame = np.sum(chroma > threshold, axis=0)
        avg_active = np.mean(active_per_frame)
        max_active = np.max(active_per_frame)

        # Determine voicing type
        if avg_active <= 1.5 and max_active <= 3:
            return True, 1  # Monophonic
        elif avg_active <= 3:
            return False, int(round(avg_active))  # Light polyphony
        else:
            return False, int(round(avg_active))  # Dense polyphony

    except Exception:
        return True, 1  # Default to monophonic on error


def extract_pitches_auto(
    audio_path: str,
    force_mono: bool = False,
    force_poly: bool = False,
    use_essentia: bool = True,
) -> PitchAnalysisResult:
    """
    Automatically detect voicing type and extract pitches.

    This is the main entry point for pitch extraction.

    Args:
        audio_path: Path to audio file
        force_mono: Force monophonic detection
        force_poly: Force polyphonic detection
        use_essentia: Use Essentia if available (better accuracy)

    Returns:
        PitchAnalysisResult with extracted notes
    """
    # Validate file exists
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Get file hash for caching
    file_hash = compute_file_hash(str(path))

    # Get audio duration
    if LIBROSA_AVAILABLE:
        duration = librosa.get_duration(path=str(path))
    else:
        duration = 0.0

    # Determine voicing type
    if force_mono:
        is_mono, polyphony = True, 1
    elif force_poly:
        is_mono, polyphony = False, 3
    else:
        is_mono, polyphony = detect_voicing_type(str(path))

    # Extract pitches using appropriate method
    if is_mono:
        # Prefer Essentia for monophonic if available
        if use_essentia and ESSENTIA_AVAILABLE:
            try:
                notes = detect_pitches_essentia(str(path))
            except Exception:
                notes = detect_pitches_monophonic(str(path))
        else:
            notes = detect_pitches_monophonic(str(path))
    else:
        # Polyphonic - use chromagram-based detection
        notes = detect_pitches_polyphonic(str(path))

    # Detect BPM
    detected_bpm = None
    if LIBROSA_AVAILABLE:
        try:
            y, sr = load_audio(str(path))
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            detected_bpm = float(tempo) if isinstance(tempo, (int, float)) else float(tempo[0])
        except Exception:
            pass

    return PitchAnalysisResult(
        filepath=str(path),
        notes=notes,
        duration_seconds=duration,
        is_monophonic=is_mono,
        polyphony_level=polyphony,
        detected_bpm=detected_bpm,
        file_hash=file_hash,
    )

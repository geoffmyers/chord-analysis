"""
Audio to MIDI transcription using state-of-the-art models.

Supported transcription backends:
- basic_pitch: Spotify's Basic Pitch (lightweight, instrument-agnostic)
- onsets_frames: Google Magenta's Onsets and Frames (piano-focused)
- piano_transcription: ByteDance's Piano Transcription (high-accuracy piano)
- omnizart: Multi-instrument transcription (music, drums, vocals, chords)
- mt3: Google Magenta's Music Transcription with Transformers (multi-instrument)

Each backend appends its name to the output MIDI filename:
  input.wav -> input_basic_pitch.mid
"""

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from enum import Enum
from multiprocessing import cpu_count
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Dict, Any, Union
from dataclasses import dataclass, field

# Supported audio formats for transcription
TRANSCRIPTION_AUDIO_FORMATS = (".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".m4a", ".caf")


class TranscriptionBackend(str, Enum):
    """Available transcription backends."""

    BASIC_PITCH = "basic_pitch"
    ONSETS_FRAMES = "onsets_frames"
    PIANO_TRANSCRIPTION = "piano_transcription"
    OMNIZART = "omnizart"
    MT3 = "mt3"

    @classmethod
    def all_backends(cls) -> List["TranscriptionBackend"]:
        """Return all available backend enum values."""
        return list(cls)


# Backend descriptions for help text
BACKEND_DESCRIPTIONS = {
    TranscriptionBackend.BASIC_PITCH: "Spotify's lightweight, instrument-agnostic transcriber",
    TranscriptionBackend.ONSETS_FRAMES: "Google Magenta's piano-optimized transcriber",
    TranscriptionBackend.PIANO_TRANSCRIPTION: "ByteDance's high-accuracy piano transcriber",
    TranscriptionBackend.OMNIZART: "Multi-instrument transcriber (music, drums, vocals)",
    TranscriptionBackend.MT3: "Google's transformer-based multi-instrument transcriber",
}

# Installation commands for each backend
BACKEND_INSTALL_COMMANDS = {
    TranscriptionBackend.BASIC_PITCH: "pip install basic-pitch",
    TranscriptionBackend.ONSETS_FRAMES: "pip install magenta",
    TranscriptionBackend.PIANO_TRANSCRIPTION: "pip install piano_transcription_inference",
    TranscriptionBackend.OMNIZART: "pip install omnizart && omnizart download-checkpoints",
    TranscriptionBackend.MT3: "pip install t5x && git clone https://github.com/magenta/mt3",
}


# Check for Basic Pitch availability
try:
    from basic_pitch.inference import predict as bp_predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from pathlib import Path as _Path

    # Prefer ONNX model for better compatibility
    _onnx_model_path = _Path(ICASSP_2022_MODEL_PATH).parent / "nmp.onnx"
    if _onnx_model_path.exists():
        BASIC_PITCH_MODEL_PATH = str(_onnx_model_path)
    else:
        BASIC_PITCH_MODEL_PATH = ICASSP_2022_MODEL_PATH

    BASIC_PITCH_AVAILABLE = True
except ImportError:
    BASIC_PITCH_AVAILABLE = False
    BASIC_PITCH_MODEL_PATH = None

# Check for Magenta/Onsets and Frames availability
try:
    import note_seq
    from magenta.models.onsets_frames_transcription import transcribe_audio as of_transcribe

    ONSETS_FRAMES_AVAILABLE = True
except ImportError:
    ONSETS_FRAMES_AVAILABLE = False

# Check for Piano Transcription availability
try:
    from piano_transcription_inference import PianoTranscription, sample_rate

    PIANO_TRANSCRIPTION_AVAILABLE = True
except ImportError:
    PIANO_TRANSCRIPTION_AVAILABLE = False

# Check for Omnizart availability
try:
    import omnizart
    from omnizart.music import app as omnizart_music_app

    OMNIZART_AVAILABLE = True
except ImportError:
    OMNIZART_AVAILABLE = False

# Check for MT3 availability (via command line)
try:
    # MT3 is typically run via command line or Colab
    # Check if the mt3 module is importable
    import mt3

    MT3_AVAILABLE = True
except ImportError:
    MT3_AVAILABLE = False


# ============================================================================
# Docker Backend Support (constants only - functions defined after dataclasses)
# ============================================================================

# Docker images for the backends that need an isolated environment. These are
# local tags: the images are built from docker/docker-compose.yml and are not
# published to any registry, so the ghcr.io prefix is only part of the name.
DOCKER_IMAGES = {
    TranscriptionBackend.ONSETS_FRAMES: "ghcr.io/geoffmyers/chord-analyzer-magenta:latest",
    TranscriptionBackend.OMNIZART: "ghcr.io/geoffmyers/chord-analyzer-omnizart:latest",
    TranscriptionBackend.MT3: "ghcr.io/geoffmyers/chord-analyzer-mt3:latest",
}

# The docker-compose.yml service that builds each image.
DOCKER_SERVICES = {
    TranscriptionBackend.ONSETS_FRAMES: "magenta",
    TranscriptionBackend.OMNIZART: "omnizart",
    TranscriptionBackend.MT3: "mt3",
}

# Backends that can run via Docker
DOCKER_BACKENDS = set(DOCKER_IMAGES.keys())


@dataclass
class TranscriptionResult:
    """Result of a single audio-to-MIDI transcription."""

    input_path: str
    output_path: str
    backend: TranscriptionBackend
    success: bool
    error_message: Optional[str] = None
    note_count: int = 0
    duration_seconds: float = 0.0

    @property
    def input_filename(self) -> str:
        """Extract input filename without extension."""
        return Path(self.input_path).stem

    @property
    def output_filename(self) -> str:
        """Extract output filename."""
        return Path(self.output_path).name if self.output_path else ""


@dataclass
class MultiBackendResult:
    """Result of transcription with multiple backends."""

    input_path: str
    results: Dict[TranscriptionBackend, TranscriptionResult] = field(default_factory=dict)

    @property
    def successful_backends(self) -> List[TranscriptionBackend]:
        """Return list of backends that succeeded."""
        return [b for b, r in self.results.items() if r.success]

    @property
    def failed_backends(self) -> List[TranscriptionBackend]:
        """Return list of backends that failed."""
        return [b for b, r in self.results.items() if not r.success]

    @property
    def all_succeeded(self) -> bool:
        """Return True if all backends succeeded."""
        return all(r.success for r in self.results.values())

    @property
    def any_succeeded(self) -> bool:
        """Return True if any backend succeeded."""
        return any(r.success for r in self.results.values())


@dataclass
class BatchTranscriptionResult:
    """Result of batch transcription operation."""

    total_files: int
    successful: int
    failed: int
    results: List[TranscriptionResult]
    backend: Union[TranscriptionBackend, List[TranscriptionBackend]]

    @property
    def success_rate(self) -> float:
        """Percentage of successful transcriptions."""
        if self.total_files == 0:
            return 0.0
        return (self.successful / self.total_files) * 100


@dataclass
class MultiBatchTranscriptionResult:
    """Result of batch transcription with multiple backends."""

    total_files: int
    results: List[MultiBackendResult]
    backends: List[TranscriptionBackend]

    @property
    def successful_by_backend(self) -> Dict[TranscriptionBackend, int]:
        """Count of successful transcriptions per backend."""
        counts = {b: 0 for b in self.backends}
        for result in self.results:
            for backend, r in result.results.items():
                if r.success:
                    counts[backend] += 1
        return counts


# ============================================================================
# Docker Backend Functions
# ============================================================================


def is_docker_available() -> bool:
    """
    Check if Docker is available on the system.

    Returns:
        True if Docker is installed and running
    """
    if shutil.which("docker") is None:
        return False

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def check_docker_image(image: str) -> bool:
    """
    Check if a Docker image exists locally.

    Args:
        image: Docker image name with tag

    Returns:
        True if image exists locally
    """
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def pull_docker_image(image: str, timeout: int = 600) -> bool:
    """
    Pull a Docker image from the registry.

    Args:
        image: Docker image name with tag
        timeout: Pull timeout in seconds

    Returns:
        True if pull succeeded
    """
    try:
        result = subprocess.run(
            ["docker", "pull", image],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def get_docker_available_backends() -> List[TranscriptionBackend]:
    """
    Get list of backends available via Docker.

    Returns:
        List of backends that have Docker images available locally
    """
    if not is_docker_available():
        return []

    available = []
    for backend, image in DOCKER_IMAGES.items():
        if check_docker_image(image):
            available.append(backend)

    return available


# ============================================================================
# Backend Availability Functions
# ============================================================================


def check_transcription_backends(include_docker: bool = True) -> Dict[str, Dict[str, bool]]:
    """
    Check which transcription backends are available.

    Args:
        include_docker: Include Docker availability check (may be slow)

    Returns:
        Dictionary mapping backend name to availability info:
        {
            "backend_name": {
                "native": bool,   # Available natively (pip installed)
                "docker": bool,   # Available via Docker
            }
        }
    """
    docker_available = is_docker_available() if include_docker else False

    result = {}
    for backend in TranscriptionBackend.all_backends():
        native = False
        docker = False

        if backend == TranscriptionBackend.BASIC_PITCH:
            native = BASIC_PITCH_AVAILABLE
        elif backend == TranscriptionBackend.ONSETS_FRAMES:
            native = ONSETS_FRAMES_AVAILABLE
            if docker_available and backend in DOCKER_IMAGES:
                docker = check_docker_image(DOCKER_IMAGES[backend])
        elif backend == TranscriptionBackend.PIANO_TRANSCRIPTION:
            native = PIANO_TRANSCRIPTION_AVAILABLE
        elif backend == TranscriptionBackend.OMNIZART:
            native = OMNIZART_AVAILABLE
            if docker_available and backend in DOCKER_IMAGES:
                docker = check_docker_image(DOCKER_IMAGES[backend])
        elif backend == TranscriptionBackend.MT3:
            native = MT3_AVAILABLE
            if docker_available and backend in DOCKER_IMAGES:
                docker = check_docker_image(DOCKER_IMAGES[backend])

        result[backend.value] = {"native": native, "docker": docker}

    return result


def get_available_backends(include_docker: bool = True) -> List[TranscriptionBackend]:
    """
    Get list of available transcription backends.

    Args:
        include_docker: Include backends available via Docker

    Returns:
        List of available TranscriptionBackend values
    """
    available = []

    # Check native availability
    if BASIC_PITCH_AVAILABLE:
        available.append(TranscriptionBackend.BASIC_PITCH)
    if ONSETS_FRAMES_AVAILABLE:
        available.append(TranscriptionBackend.ONSETS_FRAMES)
    if PIANO_TRANSCRIPTION_AVAILABLE:
        available.append(TranscriptionBackend.PIANO_TRANSCRIPTION)
    if OMNIZART_AVAILABLE:
        available.append(TranscriptionBackend.OMNIZART)
    if MT3_AVAILABLE:
        available.append(TranscriptionBackend.MT3)

    # Add Docker-available backends if requested
    if include_docker and is_docker_available():
        docker_backends = get_docker_available_backends()
        for backend in docker_backends:
            if backend not in available:
                available.append(backend)

    return available


def is_backend_available(backend: TranscriptionBackend, include_docker: bool = True) -> bool:
    """
    Check if a specific backend is available (native or Docker).

    Args:
        backend: Backend to check
        include_docker: Include Docker availability

    Returns:
        True if backend is available
    """
    # Check native
    if backend == TranscriptionBackend.BASIC_PITCH and BASIC_PITCH_AVAILABLE:
        return True
    if backend == TranscriptionBackend.ONSETS_FRAMES and ONSETS_FRAMES_AVAILABLE:
        return True
    if backend == TranscriptionBackend.PIANO_TRANSCRIPTION and PIANO_TRANSCRIPTION_AVAILABLE:
        return True
    if backend == TranscriptionBackend.OMNIZART and OMNIZART_AVAILABLE:
        return True
    if backend == TranscriptionBackend.MT3 and MT3_AVAILABLE:
        return True

    # Check Docker
    if include_docker and backend in DOCKER_BACKENDS:
        if is_docker_available() and check_docker_image(DOCKER_IMAGES[backend]):
            return True

    return False


def get_output_path(
    input_path: str,
    backend: TranscriptionBackend,
    output_dir: Optional[str] = None,
) -> str:
    """
    Generate output MIDI path with backend suffix.

    Args:
        input_path: Path to input audio file
        backend: Transcription backend being used
        output_dir: Optional output directory (defaults to same as input)

    Returns:
        Path for output MIDI file
    """
    input_path = Path(input_path)
    stem = input_path.stem
    suffix = f"_{backend.value}"

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = input_path.parent

    return str(out_dir / f"{stem}{suffix}.mid")


def transcribe_docker(
    audio_path: str,
    backend: TranscriptionBackend,
    output_path: Optional[str] = None,
    timeout: int = 600,
    **kwargs,
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using a Docker container.

    Args:
        audio_path: Path to input audio file
        backend: Transcription backend to use (must be in DOCKER_BACKENDS)
        output_path: Path for output MIDI file (auto-generated if None)
        timeout: Container execution timeout in seconds
        **kwargs: Backend-specific options passed to worker

    Returns:
        TranscriptionResult with transcription details
    """
    if backend not in DOCKER_BACKENDS:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=backend,
            success=False,
            error_message=f"Backend {backend.value} does not support Docker execution",
        )

    if not is_docker_available():
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=backend,
            success=False,
            error_message="Docker is not available. Install Docker or use a native backend.",
        )

    image = DOCKER_IMAGES[backend]
    if not check_docker_image(image):
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=backend,
            success=False,
            error_message=(
                f"Docker image not found: {image}. Build it from the project root: "
                f"docker compose -f docker/docker-compose.yml build {DOCKER_SERVICES[backend]}"
            ),
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, backend)

    # Resolve to absolute paths
    audio_path = str(Path(audio_path).resolve())
    output_path = str(Path(output_path).resolve())

    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Container paths
    container_input = f"/app/input/{Path(audio_path).name}"
    container_output = f"/app/output/{Path(output_path).name}"

    try:
        # Build docker run command
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{Path(audio_path).parent}:/app/input:ro",
            "-v", f"{Path(output_path).parent}:/app/output",
            image,
            container_input,
            container_output,
        ]

        # Add backend-specific options
        if backend == TranscriptionBackend.OMNIZART:
            mode = kwargs.get("mode", "music")
            cmd.extend(["--mode", mode])
        elif backend == TranscriptionBackend.MT3:
            model = kwargs.get("model", "mt3")
            cmd.extend(["--model", model])

        # Run container
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            # Try to parse JSON error from worker
            try:
                output_data = json.loads(result.stdout)
                error_msg = output_data.get("error_message", result.stderr or "Unknown error")
            except (json.JSONDecodeError, Exception):
                error_msg = result.stderr or result.stdout or "Unknown error"

            return TranscriptionResult(
                input_path=audio_path,
                output_path=output_path,
                backend=backend,
                success=False,
                error_message=error_msg,
            )

        # Parse JSON output from worker
        try:
            output_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            output_data = {}

        if not output_data.get("success", False):
            return TranscriptionResult(
                input_path=audio_path,
                output_path=output_path,
                backend=backend,
                success=False,
                error_message=output_data.get("error_message", "Unknown error"),
            )

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=backend,
            success=True,
            note_count=output_data.get("note_count", 0),
            duration_seconds=output_data.get("duration_seconds", 0.0),
        )

    except subprocess.TimeoutExpired:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=backend,
            success=False,
            error_message=f"Docker container timed out (>{timeout}s)",
        )
    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=backend,
            success=False,
            error_message=str(e),
        )


# ============================================================================
# Native Backend Functions
# ============================================================================


def transcribe_basic_pitch(
    audio_path: str,
    output_path: Optional[str] = None,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 127.7,
    minimum_frequency: Optional[float] = None,
    maximum_frequency: Optional[float] = None,
    multiple_pitch_bends: bool = False,
    melodia_trick: bool = True,
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using Spotify's Basic Pitch.

    Basic Pitch is lightweight, instrument-agnostic, and supports
    polyphonic transcription with pitch bend detection.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file (auto-generated if None)
        onset_threshold: Minimum confidence for note onset (0-1)
        frame_threshold: Minimum confidence for note frame (0-1)
        minimum_note_length: Minimum note duration in ms
        minimum_frequency: Minimum frequency to transcribe (Hz)
        maximum_frequency: Maximum frequency to transcribe (Hz)
        multiple_pitch_bends: Allow multiple simultaneous pitch bends
        melodia_trick: Use melodia trick for better F0 estimation

    Returns:
        TranscriptionResult with transcription details
    """
    if not BASIC_PITCH_AVAILABLE:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=False,
            error_message="basic-pitch not installed. Install with: pip install basic-pitch",
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, TranscriptionBackend.BASIC_PITCH)

    try:
        # Run Basic Pitch prediction (API v0.3.0+)
        model_output, midi_data, note_events = bp_predict(
            audio_path,
            BASIC_PITCH_MODEL_PATH,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length,
            minimum_frequency=minimum_frequency,
            maximum_frequency=maximum_frequency,
            multiple_pitch_bends=multiple_pitch_bends,
            melodia_trick=melodia_trick,
        )

        # Save MIDI file
        midi_data.write(output_path)

        # Get note count and duration
        note_count = len(note_events)
        duration = midi_data.get_end_time() if midi_data.instruments else 0.0

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
            note_count=note_count,
            duration_seconds=duration,
        )

    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.BASIC_PITCH,
            success=False,
            error_message=str(e),
        )


def transcribe_onsets_frames(
    audio_path: str,
    output_path: Optional[str] = None,
    checkpoint_path: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using Google Magenta's Onsets and Frames.

    Onsets and Frames is optimized for piano transcription and achieves
    high accuracy on piano recordings.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file (auto-generated if None)
        checkpoint_path: Path to model checkpoint (uses default if None)

    Returns:
        TranscriptionResult with transcription details
    """
    if not ONSETS_FRAMES_AVAILABLE:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.ONSETS_FRAMES,
            success=False,
            error_message="magenta not installed. Install with: pip install magenta",
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, TranscriptionBackend.ONSETS_FRAMES)

    try:
        # Run Onsets and Frames transcription
        # Note: This requires a pre-downloaded checkpoint
        ns = of_transcribe.transcribe_audio(
            audio_path,
            checkpoint_path or of_transcribe.DEFAULT_CHECKPOINT_PATH,
        )

        # Save as MIDI
        note_seq.sequence_proto_to_midi_file(ns, output_path)

        # Get note count and duration
        note_count = len(ns.notes)
        duration = ns.total_time if ns.notes else 0.0

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.ONSETS_FRAMES,
            success=True,
            note_count=note_count,
            duration_seconds=duration,
        )

    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.ONSETS_FRAMES,
            success=False,
            error_message=str(e),
        )


def transcribe_piano_transcription(
    audio_path: str,
    output_path: Optional[str] = None,
    device: str = "cpu",
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using ByteDance's Piano Transcription.

    High-accuracy piano transcription using neural networks trained
    on the MAESTRO dataset.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file (auto-generated if None)
        device: Device for inference ('cpu' or 'cuda')

    Returns:
        TranscriptionResult with transcription details
    """
    if not PIANO_TRANSCRIPTION_AVAILABLE:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.PIANO_TRANSCRIPTION,
            success=False,
            error_message="piano_transcription_inference not installed. Install with: pip install piano_transcription_inference",
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, TranscriptionBackend.PIANO_TRANSCRIPTION)

    try:
        # Load audio using librosa (more compatible than piano_transcription's load_audio)
        import librosa
        audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)

        # Initialize transcriber
        transcriptor = PianoTranscription(device=device)

        # Transcribe to MIDI
        transcribed_dict = transcriptor.transcribe(audio, output_path)

        # Get note count (estimate from output file)
        try:
            import pretty_midi

            pm = pretty_midi.PrettyMIDI(output_path)
            note_count = sum(len(inst.notes) for inst in pm.instruments)
            duration = pm.get_end_time()
        except Exception:
            note_count = 0
            duration = 0.0

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.PIANO_TRANSCRIPTION,
            success=True,
            note_count=note_count,
            duration_seconds=duration,
        )

    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.PIANO_TRANSCRIPTION,
            success=False,
            error_message=str(e),
        )


def transcribe_omnizart(
    audio_path: str,
    output_path: Optional[str] = None,
    mode: str = "music",
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using Omnizart.

    Omnizart supports multiple transcription modes:
    - music: Pitched instruments
    - drum: Percussive instruments
    - vocal: Vocal melody

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file (auto-generated if None)
        mode: Transcription mode ('music', 'drum', 'vocal')

    Returns:
        TranscriptionResult with transcription details
    """
    if not OMNIZART_AVAILABLE:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.OMNIZART,
            success=False,
            error_message="omnizart not installed. Install with: pip install omnizart && omnizart download-checkpoints",
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, TranscriptionBackend.OMNIZART)

    try:
        # Use omnizart command-line interface
        # The Python API is less well-documented, so CLI is more reliable
        output_dir = str(Path(output_path).parent)
        output_name = Path(output_path).stem

        # Run omnizart transcription
        result = subprocess.run(
            ["omnizart", mode, "transcribe", audio_path, "-o", output_dir],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Omnizart failed: {result.stderr}")

        # Omnizart outputs with a default name, rename to our expected name
        # Find the generated file
        expected_omnizart_output = Path(output_dir) / f"{Path(audio_path).stem}.mid"
        if expected_omnizart_output.exists() and str(expected_omnizart_output) != output_path:
            expected_omnizart_output.rename(output_path)

        # Get note count
        try:
            import pretty_midi

            pm = pretty_midi.PrettyMIDI(output_path)
            note_count = sum(len(inst.notes) for inst in pm.instruments)
            duration = pm.get_end_time()
        except Exception:
            note_count = 0
            duration = 0.0

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.OMNIZART,
            success=True,
            note_count=note_count,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.OMNIZART,
            success=False,
            error_message="Transcription timed out (>5 minutes)",
        )
    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.OMNIZART,
            success=False,
            error_message=str(e),
        )


def transcribe_mt3(
    audio_path: str,
    output_path: Optional[str] = None,
    model: str = "mt3",
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using Google Magenta's MT3.

    MT3 (Music Transcription with Transformers) supports multi-instrument
    transcription using a transformer architecture.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file (auto-generated if None)
        model: Model variant ('mt3' for multi-instrument, 'ismir2021' for piano)

    Returns:
        TranscriptionResult with transcription details
    """
    if not MT3_AVAILABLE:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.MT3,
            success=False,
            error_message="MT3 not installed. See: https://github.com/magenta/mt3",
        )

    # Generate output path if not provided
    if output_path is None:
        output_path = get_output_path(audio_path, TranscriptionBackend.MT3)

    try:
        # MT3 API (if available as Python module)
        # Note: MT3 is typically used via Colab, Python API may vary
        from mt3 import transcribe as mt3_transcribe

        result = mt3_transcribe(audio_path, output_path, model=model)

        # Get note count
        try:
            import pretty_midi

            pm = pretty_midi.PrettyMIDI(output_path)
            note_count = sum(len(inst.notes) for inst in pm.instruments)
            duration = pm.get_end_time()
        except Exception:
            note_count = 0
            duration = 0.0

        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path,
            backend=TranscriptionBackend.MT3,
            success=True,
            note_count=note_count,
            duration_seconds=duration,
        )

    except Exception as e:
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=TranscriptionBackend.MT3,
            success=False,
            error_message=str(e),
        )


def transcribe_audio(
    audio_path: str,
    backend: TranscriptionBackend = TranscriptionBackend.BASIC_PITCH,
    output_path: Optional[str] = None,
    use_docker: Optional[bool] = None,
    docker_fallback: bool = True,
    **kwargs,
) -> TranscriptionResult:
    """
    Transcribe audio to MIDI using specified backend.

    The function automatically selects the best execution method:
    1. Native Python (if backend is installed)
    2. Docker container (if native not available and docker_fallback=True)

    Args:
        audio_path: Path to input audio file
        backend: Transcription backend to use
        output_path: Path for output MIDI file (auto-generated if None)
        use_docker: Force Docker execution (None=auto, True=force Docker, False=native only)
        docker_fallback: Automatically fall back to Docker if native unavailable
        **kwargs: Backend-specific options

    Returns:
        TranscriptionResult with transcription details
    """
    # Native backend availability
    native_available = {
        TranscriptionBackend.BASIC_PITCH: BASIC_PITCH_AVAILABLE,
        TranscriptionBackend.ONSETS_FRAMES: ONSETS_FRAMES_AVAILABLE,
        TranscriptionBackend.PIANO_TRANSCRIPTION: PIANO_TRANSCRIPTION_AVAILABLE,
        TranscriptionBackend.OMNIZART: OMNIZART_AVAILABLE,
        TranscriptionBackend.MT3: MT3_AVAILABLE,
    }

    backend_functions = {
        TranscriptionBackend.BASIC_PITCH: transcribe_basic_pitch,
        TranscriptionBackend.ONSETS_FRAMES: transcribe_onsets_frames,
        TranscriptionBackend.PIANO_TRANSCRIPTION: transcribe_piano_transcription,
        TranscriptionBackend.OMNIZART: transcribe_omnizart,
        TranscriptionBackend.MT3: transcribe_mt3,
    }

    # Determine execution method
    if use_docker is True:
        # Force Docker
        if backend not in DOCKER_BACKENDS:
            return TranscriptionResult(
                input_path=audio_path,
                output_path=output_path or "",
                backend=backend,
                success=False,
                error_message=f"Backend {backend.value} does not support Docker execution",
            )
        return transcribe_docker(audio_path, backend, output_path, **kwargs)

    if use_docker is False:
        # Force native
        func = backend_functions.get(backend)
        if func:
            return func(audio_path, output_path, **kwargs)
        return TranscriptionResult(
            input_path=audio_path,
            output_path=output_path or "",
            backend=backend,
            success=False,
            error_message=f"Unknown backend: {backend}",
        )

    # Auto mode (use_docker=None)
    # Try native first, fall back to Docker if needed
    if native_available.get(backend, False):
        func = backend_functions.get(backend)
        if func:
            return func(audio_path, output_path, **kwargs)

    # Native not available, try Docker fallback
    if docker_fallback and backend in DOCKER_BACKENDS:
        if is_docker_available() and check_docker_image(DOCKER_IMAGES[backend]):
            return transcribe_docker(audio_path, backend, output_path, **kwargs)

    # Neither available
    func = backend_functions.get(backend)
    if func:
        # This will return the "not installed" error message
        return func(audio_path, output_path, **kwargs)

    return TranscriptionResult(
        input_path=audio_path,
        output_path=output_path or "",
        backend=backend,
        success=False,
        error_message=f"Unknown backend: {backend}",
    )


def transcribe_audio_multi(
    audio_path: str,
    backends: Optional[List[TranscriptionBackend]] = None,
    output_dir: Optional[str] = None,
    use_docker: Optional[bool] = None,
    docker_fallback: bool = True,
    **kwargs,
) -> MultiBackendResult:
    """
    Transcribe audio to MIDI using multiple backends.

    Args:
        audio_path: Path to input audio file
        backends: List of backends to use (defaults to all available)
        output_dir: Output directory for MIDI files
        use_docker: Force Docker execution (None=auto, True=force, False=native only)
        docker_fallback: Automatically fall back to Docker if native unavailable
        **kwargs: Backend-specific options

    Returns:
        MultiBackendResult with results from each backend
    """
    if backends is None:
        backends = get_available_backends()

    if not backends:
        # No backends available, try all and let them fail with helpful messages
        backends = TranscriptionBackend.all_backends()

    result = MultiBackendResult(input_path=audio_path)

    for backend in backends:
        output_path = get_output_path(audio_path, backend, output_dir)
        transcription_result = transcribe_audio(
            audio_path,
            backend,
            output_path,
            use_docker=use_docker,
            docker_fallback=docker_fallback,
            **kwargs,
        )
        result.results[backend] = transcription_result

    return result


# ============================================================================
# Parallel Processing Support
# ============================================================================


def _transcribe_worker(args: Tuple[str, str, str, Dict[str, Any]]) -> TranscriptionResult:
    """
    Worker function for parallel transcription.

    This function is designed to be called by ProcessPoolExecutor.
    Each worker process loads its own model and processes files independently.

    Args:
        args: Tuple of (audio_path, backend_value, output_path, kwargs)

    Returns:
        TranscriptionResult with transcription details
    """
    audio_path, backend_value, output_path, kwargs = args

    # Convert string back to enum (enums can't be pickled directly in some cases)
    backend = TranscriptionBackend(backend_value)

    # Perform transcription
    return transcribe_audio(audio_path, backend, output_path, **kwargs)


def _transcribe_multi_worker(
    args: Tuple[str, List[str], Optional[str], Dict[str, Any]]
) -> MultiBackendResult:
    """
    Worker function for parallel multi-backend transcription.

    Args:
        args: Tuple of (audio_path, backend_values, output_dir, kwargs)

    Returns:
        MultiBackendResult with results from each backend
    """
    audio_path, backend_values, output_dir, kwargs = args

    # Convert strings back to enums
    backends = [TranscriptionBackend(v) for v in backend_values]

    return transcribe_audio_multi(audio_path, backends=backends, output_dir=output_dir, **kwargs)


def transcribe_directory(
    input_dir: str,
    backend: TranscriptionBackend = TranscriptionBackend.BASIC_PITCH,
    output_dir: Optional[str] = None,
    recursive: bool = False,
    formats: Tuple[str, ...] = TRANSCRIPTION_AUDIO_FORMATS,
    overwrite: bool = False,
    progress_callback: Optional[Callable[[str, TranscriptionResult], None]] = None,
    workers: int = 1,
    **kwargs,
) -> BatchTranscriptionResult:
    """
    Transcribe all audio files in a directory to MIDI.

    Args:
        input_dir: Directory containing audio files
        backend: Transcription backend to use
        output_dir: Output directory (defaults to same as input files)
        recursive: Process subdirectories
        formats: Tuple of audio file extensions to process
        overwrite: Overwrite existing MIDI files
        progress_callback: Optional callback(filepath, result) for progress
        workers: Number of parallel worker processes (1=sequential, 0=auto/cpu_count)
        **kwargs: Backend-specific options

    Returns:
        BatchTranscriptionResult with all transcription results

    Note:
        When workers > 1, each worker process loads its own copy of the model.
        This increases memory usage but allows true parallel processing across
        CPU cores. For memory-constrained systems, use workers=1.
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Directory not found: {input_dir}")

    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    # Collect audio files
    audio_files = []
    for fmt in formats:
        pattern = f"**/*{fmt}" if recursive else f"*{fmt}"
        audio_files.extend(input_path.glob(pattern))
        # Also check uppercase
        pattern_upper = f"**/*{fmt.upper()}" if recursive else f"*{fmt.upper()}"
        audio_files.extend(input_path.glob(pattern_upper))

    # Remove duplicates and sort
    audio_files = sorted(set(audio_files))

    results = []
    successful = 0
    failed = 0

    # Prepare tasks: determine output paths and filter out skipped files
    tasks_to_process = []
    skipped_results = []

    for audio_file in audio_files:
        # Determine output path
        if output_dir:
            # Preserve relative directory structure
            if recursive:
                rel_path = audio_file.relative_to(input_path)
                out_subdir = Path(output_dir) / rel_path.parent
                out_subdir.mkdir(parents=True, exist_ok=True)
                out_path = get_output_path(str(audio_file), backend, str(out_subdir))
            else:
                out_path = get_output_path(str(audio_file), backend, output_dir)
        else:
            out_path = get_output_path(str(audio_file), backend)

        # Skip if exists and not overwriting
        if not overwrite and Path(out_path).exists():
            result = TranscriptionResult(
                input_path=str(audio_file),
                output_path=out_path,
                backend=backend,
                success=True,
                error_message="Skipped (already exists)",
            )
            skipped_results.append(result)
            successful += 1
            if progress_callback:
                progress_callback(str(audio_file), result)
        else:
            # Add to processing queue
            tasks_to_process.append((str(audio_file), backend.value, out_path, kwargs))

    # Add skipped results to the results list
    results.extend(skipped_results)

    # Determine number of workers
    num_workers = workers if workers > 0 else cpu_count()

    # Process files
    if num_workers == 1 or len(tasks_to_process) <= 1:
        # Sequential processing (original behavior)
        for audio_path, backend_value, out_path, task_kwargs in tasks_to_process:
            result = transcribe_audio(audio_path, backend, out_path, **task_kwargs)
            results.append(result)

            if result.success:
                successful += 1
            else:
                failed += 1

            if progress_callback:
                progress_callback(audio_path, result)
    else:
        # Parallel processing with ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(_transcribe_worker, task): task[0]
                for task in tasks_to_process
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_path):
                audio_path = future_to_path[future]
                try:
                    result = future.result()
                except Exception as e:
                    # Handle unexpected errors from worker
                    result = TranscriptionResult(
                        input_path=audio_path,
                        output_path="",
                        backend=backend,
                        success=False,
                        error_message=f"Worker error: {str(e)}",
                    )

                results.append(result)

                if result.success:
                    successful += 1
                else:
                    failed += 1

                if progress_callback:
                    progress_callback(audio_path, result)

    return BatchTranscriptionResult(
        total_files=len(audio_files),
        successful=successful,
        failed=failed,
        results=results,
        backend=backend,
    )


def transcribe_directory_multi(
    input_dir: str,
    backends: Optional[List[TranscriptionBackend]] = None,
    output_dir: Optional[str] = None,
    recursive: bool = False,
    formats: Tuple[str, ...] = TRANSCRIPTION_AUDIO_FORMATS,
    overwrite: bool = False,
    progress_callback: Optional[Callable[[str, MultiBackendResult], None]] = None,
    workers: int = 1,
    **kwargs,
) -> MultiBatchTranscriptionResult:
    """
    Transcribe all audio files in a directory using multiple backends.

    Args:
        input_dir: Directory containing audio files
        backends: List of backends to use (defaults to all available)
        output_dir: Output directory (defaults to same as input files)
        recursive: Process subdirectories
        formats: Tuple of audio file extensions to process
        overwrite: Overwrite existing MIDI files
        progress_callback: Optional callback(filepath, multi_result) for progress
        workers: Number of parallel worker processes (1=sequential, 0=auto/cpu_count)
        **kwargs: Backend-specific options

    Returns:
        MultiBatchTranscriptionResult with results from all backends

    Note:
        When workers > 1, each worker process loads its own copy of the models.
        This increases memory usage but allows true parallel processing across
        CPU cores. For memory-constrained systems, use workers=1.
    """
    if backends is None:
        backends = get_available_backends()

    if not backends:
        backends = TranscriptionBackend.all_backends()

    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Directory not found: {input_dir}")

    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    # Collect audio files
    audio_files = []
    for fmt in formats:
        pattern = f"**/*{fmt}" if recursive else f"*{fmt}"
        audio_files.extend(input_path.glob(pattern))
        pattern_upper = f"**/*{fmt.upper()}" if recursive else f"*{fmt.upper()}"
        audio_files.extend(input_path.glob(pattern_upper))

    audio_files = sorted(set(audio_files))

    results = []

    # Prepare tasks with output directories
    tasks_to_process = []
    backend_values = [b.value for b in backends]

    for audio_file in audio_files:
        # Determine base output directory
        if output_dir:
            if recursive:
                rel_path = audio_file.relative_to(input_path)
                out_subdir = Path(output_dir) / rel_path.parent
                out_subdir.mkdir(parents=True, exist_ok=True)
                file_output_dir = str(out_subdir)
            else:
                file_output_dir = output_dir
        else:
            file_output_dir = str(audio_file.parent)

        tasks_to_process.append((str(audio_file), backend_values, file_output_dir, kwargs))

    # Determine number of workers
    num_workers = workers if workers > 0 else cpu_count()

    # Process files
    if num_workers == 1 or len(tasks_to_process) <= 1:
        # Sequential processing (original behavior)
        for audio_path, _, file_output_dir, task_kwargs in tasks_to_process:
            multi_result = transcribe_audio_multi(
                audio_path,
                backends=backends,
                output_dir=file_output_dir,
                **task_kwargs,
            )
            results.append(multi_result)

            if progress_callback:
                progress_callback(audio_path, multi_result)
    else:
        # Parallel processing with ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(_transcribe_multi_worker, task): task[0]
                for task in tasks_to_process
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_path):
                audio_path = future_to_path[future]
                try:
                    multi_result = future.result()
                except Exception as e:
                    # Handle unexpected errors from worker
                    multi_result = MultiBackendResult(input_path=audio_path)
                    for backend in backends:
                        multi_result.results[backend] = TranscriptionResult(
                            input_path=audio_path,
                            output_path="",
                            backend=backend,
                            success=False,
                            error_message=f"Worker error: {str(e)}",
                        )

                results.append(multi_result)

                if progress_callback:
                    progress_callback(audio_path, multi_result)

    return MultiBatchTranscriptionResult(
        total_files=len(audio_files),
        results=results,
        backends=backends,
    )


def explain_transcription_result(result: TranscriptionResult) -> str:
    """
    Generate human-readable explanation of transcription result.

    Args:
        result: TranscriptionResult to explain

    Returns:
        Formatted explanation string
    """
    lines = [
        f"Input: {result.input_filename}",
        f"Backend: {result.backend.value}",
        f"Status: {'Success' if result.success else 'Failed'}",
    ]

    if result.success:
        lines.extend(
            [
                f"Output: {result.output_filename}",
                f"Notes transcribed: {result.note_count}",
                f"Duration: {result.duration_seconds:.2f}s",
            ]
        )
    else:
        lines.append(f"Error: {result.error_message}")

    return "\n".join(lines)


def explain_multi_result(result: MultiBackendResult) -> str:
    """
    Generate human-readable explanation of multi-backend result.

    Args:
        result: MultiBackendResult to explain

    Returns:
        Formatted explanation string
    """
    lines = [f"Input: {Path(result.input_path).name}", ""]

    for backend, r in result.results.items():
        status = "OK" if r.success else "FAIL"
        if r.success:
            lines.append(f"  [{status}] {backend.value}: {r.note_count} notes -> {r.output_filename}")
        else:
            lines.append(f"  [{status}] {backend.value}: {r.error_message}")

    return "\n".join(lines)

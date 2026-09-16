"""Tests for MIDI transcription module."""

import pytest
from pathlib import Path

from chord_analyzer.midi_transcriber import (
    TranscriptionBackend,
    TranscriptionResult,
    BatchTranscriptionResult,
    MultiBackendResult,
    MultiBatchTranscriptionResult,
    check_transcription_backends,
    get_available_backends,
    get_output_path,
    TRANSCRIPTION_AUDIO_FORMATS,
    BACKEND_DESCRIPTIONS,
    BACKEND_INSTALL_COMMANDS,
)


class TestTranscriptionBackend:
    """Tests for TranscriptionBackend enum."""

    def test_basic_pitch_value(self):
        """Test basic_pitch enum value."""
        assert TranscriptionBackend.BASIC_PITCH.value == "basic_pitch"

    def test_onsets_frames_value(self):
        """Test onsets_frames enum value."""
        assert TranscriptionBackend.ONSETS_FRAMES.value == "onsets_frames"

    def test_piano_transcription_value(self):
        """Test piano_transcription enum value."""
        assert TranscriptionBackend.PIANO_TRANSCRIPTION.value == "piano_transcription"

    def test_omnizart_value(self):
        """Test omnizart enum value."""
        assert TranscriptionBackend.OMNIZART.value == "omnizart"

    def test_mt3_value(self):
        """Test mt3 enum value."""
        assert TranscriptionBackend.MT3.value == "mt3"

    def test_string_conversion(self):
        """Test string conversion for backend."""
        backend = TranscriptionBackend("basic_pitch")
        assert backend == TranscriptionBackend.BASIC_PITCH

    def test_all_backends_returns_all(self):
        """Test all_backends class method."""
        all_backends = TranscriptionBackend.all_backends()
        assert len(all_backends) == 5
        assert TranscriptionBackend.BASIC_PITCH in all_backends
        assert TranscriptionBackend.ONSETS_FRAMES in all_backends
        assert TranscriptionBackend.PIANO_TRANSCRIPTION in all_backends
        assert TranscriptionBackend.OMNIZART in all_backends
        assert TranscriptionBackend.MT3 in all_backends


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful transcription result."""
        result = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="/path/to/audio_basic_pitch.mid",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
            note_count=100,
            duration_seconds=30.5,
        )
        assert result.success is True
        assert result.note_count == 100
        assert result.duration_seconds == 30.5
        assert result.error_message is None

    def test_failed_result(self):
        """Test creating a failed transcription result."""
        result = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=False,
            error_message="File format not supported",
        )
        assert result.success is False
        assert result.error_message == "File format not supported"

    def test_input_filename_property(self):
        """Test input_filename property extracts stem."""
        result = TranscriptionResult(
            input_path="/long/path/to/my_audio_file.wav",
            output_path="/path/to/my_audio_file_basic_pitch.mid",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
        )
        assert result.input_filename == "my_audio_file"

    def test_output_filename_property(self):
        """Test output_filename property extracts filename."""
        result = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="/path/to/audio_basic_pitch.mid",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
        )
        assert result.output_filename == "audio_basic_pitch.mid"

    def test_output_filename_empty_path(self):
        """Test output_filename with empty path."""
        result = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=False,
        )
        assert result.output_filename == ""


class TestMultiBackendResult:
    """Tests for MultiBackendResult dataclass."""

    def test_empty_result(self):
        """Test empty multi-backend result."""
        result = MultiBackendResult(input_path="/path/to/audio.wav")
        assert result.successful_backends == []
        assert result.failed_backends == []
        assert result.all_succeeded is True  # Vacuously true
        assert result.any_succeeded is False

    def test_all_succeeded(self):
        """Test when all backends succeed."""
        result = MultiBackendResult(input_path="/path/to/audio.wav")
        result.results[TranscriptionBackend.BASIC_PITCH] = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="/path/to/audio_basic_pitch.mid",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
        )
        result.results[TranscriptionBackend.PIANO_TRANSCRIPTION] = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="/path/to/audio_piano_transcription.mid",
            backend=TranscriptionBackend.PIANO_TRANSCRIPTION,
            success=True,
        )
        assert result.all_succeeded is True
        assert result.any_succeeded is True
        assert len(result.successful_backends) == 2
        assert len(result.failed_backends) == 0

    def test_partial_success(self):
        """Test when some backends succeed and some fail."""
        result = MultiBackendResult(input_path="/path/to/audio.wav")
        result.results[TranscriptionBackend.BASIC_PITCH] = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="/path/to/audio_basic_pitch.mid",
            backend=TranscriptionBackend.BASIC_PITCH,
            success=True,
        )
        result.results[TranscriptionBackend.MT3] = TranscriptionResult(
            input_path="/path/to/audio.wav",
            output_path="",
            backend=TranscriptionBackend.MT3,
            success=False,
            error_message="Not installed",
        )
        assert result.all_succeeded is False
        assert result.any_succeeded is True
        assert TranscriptionBackend.BASIC_PITCH in result.successful_backends
        assert TranscriptionBackend.MT3 in result.failed_backends


class TestBatchTranscriptionResult:
    """Tests for BatchTranscriptionResult dataclass."""

    def test_basic_batch_result(self):
        """Test creating a batch transcription result."""
        results = [
            TranscriptionResult(
                input_path="/path/to/a.wav",
                output_path="/path/to/a_basic_pitch.mid",
                backend=TranscriptionBackend.BASIC_PITCH,
                success=True,
            ),
            TranscriptionResult(
                input_path="/path/to/b.wav",
                output_path="/path/to/b_basic_pitch.mid",
                backend=TranscriptionBackend.BASIC_PITCH,
                success=True,
            ),
            TranscriptionResult(
                input_path="/path/to/c.wav",
                output_path="",
                backend=TranscriptionBackend.BASIC_PITCH,
                success=False,
                error_message="Error",
            ),
        ]

        batch = BatchTranscriptionResult(
            total_files=3,
            successful=2,
            failed=1,
            results=results,
            backend=TranscriptionBackend.BASIC_PITCH,
        )

        assert batch.total_files == 3
        assert batch.successful == 2
        assert batch.failed == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        batch = BatchTranscriptionResult(
            total_files=10,
            successful=7,
            failed=3,
            results=[],
            backend=TranscriptionBackend.BASIC_PITCH,
        )
        assert batch.success_rate == 70.0

    def test_success_rate_all_successful(self):
        """Test success rate when all files succeed."""
        batch = BatchTranscriptionResult(
            total_files=5,
            successful=5,
            failed=0,
            results=[],
            backend=TranscriptionBackend.BASIC_PITCH,
        )
        assert batch.success_rate == 100.0

    def test_success_rate_all_failed(self):
        """Test success rate when all files fail."""
        batch = BatchTranscriptionResult(
            total_files=5,
            successful=0,
            failed=5,
            results=[],
            backend=TranscriptionBackend.BASIC_PITCH,
        )
        assert batch.success_rate == 0.0

    def test_success_rate_empty(self):
        """Test success rate with no files."""
        batch = BatchTranscriptionResult(
            total_files=0,
            successful=0,
            failed=0,
            results=[],
            backend=TranscriptionBackend.BASIC_PITCH,
        )
        assert batch.success_rate == 0.0


class TestMultiBatchTranscriptionResult:
    """Tests for MultiBatchTranscriptionResult dataclass."""

    def test_successful_by_backend(self):
        """Test counting successes by backend."""
        backends = [TranscriptionBackend.BASIC_PITCH, TranscriptionBackend.PIANO_TRANSCRIPTION]

        # Create mock results
        multi_results = []
        for i in range(3):
            mr = MultiBackendResult(input_path=f"/path/to/file{i}.wav")
            mr.results[TranscriptionBackend.BASIC_PITCH] = TranscriptionResult(
                input_path=f"/path/to/file{i}.wav",
                output_path=f"/path/to/file{i}_basic_pitch.mid",
                backend=TranscriptionBackend.BASIC_PITCH,
                success=True,
            )
            # Only first two succeed for piano_transcription
            mr.results[TranscriptionBackend.PIANO_TRANSCRIPTION] = TranscriptionResult(
                input_path=f"/path/to/file{i}.wav",
                output_path=f"/path/to/file{i}_piano_transcription.mid" if i < 2 else "",
                backend=TranscriptionBackend.PIANO_TRANSCRIPTION,
                success=(i < 2),
            )
            multi_results.append(mr)

        batch = MultiBatchTranscriptionResult(
            total_files=3,
            results=multi_results,
            backends=backends,
        )

        counts = batch.successful_by_backend
        assert counts[TranscriptionBackend.BASIC_PITCH] == 3
        assert counts[TranscriptionBackend.PIANO_TRANSCRIPTION] == 2


class TestCheckTranscriptionBackends:
    """Tests for check_transcription_backends function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = check_transcription_backends()
        assert isinstance(result, dict)

    def test_contains_all_backend_keys(self):
        """Test that all backend keys exist."""
        result = check_transcription_backends()
        assert "basic_pitch" in result
        assert "onsets_frames" in result
        assert "piano_transcription" in result
        assert "omnizart" in result
        assert "mt3" in result

    def test_values_are_dicts_with_native_docker(self):
        """Test that all values are dicts with 'native' and 'docker' keys."""
        result = check_transcription_backends()
        for key, value in result.items():
            assert isinstance(value, dict)
            assert "native" in value
            assert "docker" in value
            assert isinstance(value["native"], bool)
            assert isinstance(value["docker"], bool)


class TestGetAvailableBackends:
    """Tests for get_available_backends function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        result = get_available_backends()
        assert isinstance(result, list)

    def test_contains_only_backend_enums(self):
        """Test that list contains only TranscriptionBackend values."""
        result = get_available_backends()
        for backend in result:
            assert isinstance(backend, TranscriptionBackend)


class TestGetOutputPath:
    """Tests for get_output_path function."""

    def test_basic_pitch_suffix(self):
        """Test output path has basic_pitch suffix."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.BASIC_PITCH,
        )
        assert result.endswith("_basic_pitch.mid")

    def test_onsets_frames_suffix(self):
        """Test output path has onsets_frames suffix."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.ONSETS_FRAMES,
        )
        assert result.endswith("_onsets_frames.mid")

    def test_piano_transcription_suffix(self):
        """Test output path has piano_transcription suffix."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.PIANO_TRANSCRIPTION,
        )
        assert result.endswith("_piano_transcription.mid")

    def test_omnizart_suffix(self):
        """Test output path has omnizart suffix."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.OMNIZART,
        )
        assert result.endswith("_omnizart.mid")

    def test_mt3_suffix(self):
        """Test output path has mt3 suffix."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.MT3,
        )
        assert result.endswith("_mt3.mid")

    def test_preserves_stem(self):
        """Test that original file stem is preserved."""
        result = get_output_path(
            "/path/to/my_song.wav",
            TranscriptionBackend.BASIC_PITCH,
        )
        assert "my_song_basic_pitch.mid" in result

    def test_default_directory(self):
        """Test output goes to same directory as input by default."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.BASIC_PITCH,
        )
        assert result.startswith("/path/to/")

    def test_custom_output_directory(self):
        """Test custom output directory."""
        result = get_output_path(
            "/path/to/audio.wav",
            TranscriptionBackend.BASIC_PITCH,
            output_dir="/custom/output",
        )
        assert result.startswith("/custom/output/")
        assert result.endswith("audio_basic_pitch.mid")

    def test_handles_various_extensions(self):
        """Test handling various audio extensions."""
        for ext in [".wav", ".mp3", ".aiff", ".flac"]:
            result = get_output_path(
                f"/path/to/audio{ext}",
                TranscriptionBackend.BASIC_PITCH,
            )
            assert result.endswith("_basic_pitch.mid")
            assert ext not in result


class TestBackendDescriptions:
    """Tests for BACKEND_DESCRIPTIONS constant."""

    def test_all_backends_have_descriptions(self):
        """Test that all backends have descriptions."""
        for backend in TranscriptionBackend.all_backends():
            assert backend in BACKEND_DESCRIPTIONS
            assert len(BACKEND_DESCRIPTIONS[backend]) > 0


class TestBackendInstallCommands:
    """Tests for BACKEND_INSTALL_COMMANDS constant."""

    def test_all_backends_have_install_commands(self):
        """Test that all backends have install commands."""
        for backend in TranscriptionBackend.all_backends():
            assert backend in BACKEND_INSTALL_COMMANDS
            assert len(BACKEND_INSTALL_COMMANDS[backend]) > 0


class TestTranscriptionAudioFormats:
    """Tests for TRANSCRIPTION_AUDIO_FORMATS constant."""

    def test_is_tuple(self):
        """Test that formats is a tuple."""
        assert isinstance(TRANSCRIPTION_AUDIO_FORMATS, tuple)

    def test_contains_wav(self):
        """Test that WAV format is supported."""
        assert ".wav" in TRANSCRIPTION_AUDIO_FORMATS

    def test_contains_mp3(self):
        """Test that MP3 format is supported."""
        assert ".mp3" in TRANSCRIPTION_AUDIO_FORMATS

    def test_contains_aiff(self):
        """Test that AIFF formats are supported."""
        assert ".aiff" in TRANSCRIPTION_AUDIO_FORMATS or ".aif" in TRANSCRIPTION_AUDIO_FORMATS

    def test_contains_flac(self):
        """Test that FLAC format is supported."""
        assert ".flac" in TRANSCRIPTION_AUDIO_FORMATS

    def test_all_lowercase(self):
        """Test that all formats are lowercase."""
        for fmt in TRANSCRIPTION_AUDIO_FORMATS:
            assert fmt == fmt.lower()

    def test_all_start_with_dot(self):
        """Test that all formats start with a dot."""
        for fmt in TRANSCRIPTION_AUDIO_FORMATS:
            assert fmt.startswith(".")


class TestDockerImagesAreBuiltLocally:
    """The images are not published, so a missing one must be built, not pulled."""

    def test_every_docker_backend_names_a_compose_service_that_builds_its_image(self):
        import re
        from chord_analyzer.midi_transcriber import DOCKER_IMAGES, DOCKER_SERVICES

        compose = (Path(__file__).parent.parent / "docker" / "docker-compose.yml").read_text()
        # service name -> the text of its block (two-space-indented keys under services:)
        services = dict(re.findall(r"^  ([a-z0-9_-]+):\n((?:    .*\n|\n)*)", compose, re.M))
        assert set(DOCKER_SERVICES) == set(DOCKER_IMAGES)
        for backend, service in DOCKER_SERVICES.items():
            assert service in services, f"no '{service}' service in docker-compose.yml"
            block = services[service]
            assert "build:" in block
            assert f"image: {DOCKER_IMAGES[backend]}" in block

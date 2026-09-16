"""
Command-line interface for the chord analyzer.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .database import (
    init_database,
    store_sample,
    get_sample_by_filepath,
    get_all_samples,
    find_compatible_samples,
    get_database_stats,
    clear_compatibility_cache,
)
from .extractor import (
    parse_chord_csv,
    create_sample_from_csv,
    create_sample_from_csv_with_tempo,
    check_sonic_annotator,
    check_chordino_plugin,
    batch_extract_chords,
    generate_transform_file,
)
from .compatibility import calculate_compatibility, explain_compatibility
from .theory import estimate_key_from_progression
from .tempo import check_librosa_available


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="chord-analyzer",
        description="Analyze chord progressions and find compatible samples",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze audio files and build database"
    )
    analyze_parser.add_argument(
        "--audio-dir",
        type=str,
        help="Directory containing audio files (for extraction)",
    )
    analyze_parser.add_argument(
        "--csv-dir",
        type=str,
        required=True,
        help="Directory containing/for chord CSV files",
    )
    analyze_parser.add_argument(
        "--db",
        type=str,
        default="samples.db",
        help="Database file path (default: samples.db)",
    )
    analyze_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't process subdirectories (default: recursive)",
    )
    analyze_parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract chords from audio (requires Sonic Annotator)",
    )
    analyze_parser.add_argument(
        "--bpm",
        type=float,
        help="Override BPM detection with a specific value",
    )
    analyze_parser.add_argument(
        "--detect-tempo",
        action="store_true",
        help="Enable tempo detection (requires librosa)",
    )
    analyze_parser.add_argument(
        "--time-sig",
        type=str,
        default="4/4",
        help="Time signature (default: 4/4)",
    )

    # find command
    find_parser = subparsers.add_parser(
        "find", help="Find compatible samples"
    )
    find_parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target sample filepath",
    )
    find_parser.add_argument(
        "--db",
        type=str,
        default="samples.db",
        help="Database file path",
    )
    find_parser.add_argument(
        "--min-score",
        type=float,
        default=50.0,
        help="Minimum compatibility score (0-100)",
    )
    find_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results to return",
    )
    find_parser.add_argument(
        "--explain",
        action="store_true",
        help="Show detailed score breakdown",
    )
    find_parser.add_argument(
        "--use-rhythm",
        action="store_true",
        help="Include rhythm pattern comparison (requires tempo data)",
    )

    # info command
    info_parser = subparsers.add_parser(
        "info", help="Show analysis info for a sample"
    )
    info_parser.add_argument(
        "filepath",
        type=str,
        help="Sample filepath",
    )
    info_parser.add_argument(
        "--db",
        type=str,
        default="samples.db",
        help="Database file path",
    )

    # stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Display database statistics"
    )
    stats_parser.add_argument(
        "--db",
        type=str,
        default="samples.db",
        help="Database file path",
    )

    # compare command
    compare_parser = subparsers.add_parser(
        "compare", help="Compare two samples directly"
    )
    compare_parser.add_argument(
        "sample_a",
        type=str,
        help="First sample CSV path",
    )
    compare_parser.add_argument(
        "sample_b",
        type=str,
        help="Second sample CSV path",
    )
    compare_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed breakdown",
    )

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check system dependencies"
    )

    # transcribe command
    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio files to MIDI using state-of-the-art models",
    )
    transcribe_parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input audio file or directory",
    )
    transcribe_parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        help="Output directory for MIDI files (default: same as input)",
    )
    transcribe_parser.add_argument(
        "--backend",
        "-b",
        type=str,
        nargs="+",
        choices=["basic_pitch", "onsets_frames", "piano_transcription", "omnizart", "mt3", "all"],
        default=None,
        help="Transcription backend(s). Use 'all' for all available backends (default: all available)",
    )
    transcribe_parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "cuda"],
        default="cpu",
        help="Device for inference (piano_transcription only, default: cpu)",
    )
    transcribe_parser.add_argument(
        "--omnizart-mode",
        type=str,
        choices=["music", "drum", "vocal"],
        default="music",
        help="Omnizart transcription mode (default: music)",
    )
    transcribe_parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Process subdirectories",
    )
    transcribe_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing MIDI files",
    )
    transcribe_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help="Number of parallel worker processes (default: 1, use 0 for auto/cpu_count)",
    )
    transcribe_parser.add_argument(
        "--onset-threshold",
        type=float,
        default=0.5,
        help="Note onset confidence threshold 0-1 (basic_pitch only, default: 0.5)",
    )
    transcribe_parser.add_argument(
        "--frame-threshold",
        type=float,
        default=0.3,
        help="Note frame confidence threshold 0-1 (basic_pitch only, default: 0.3)",
    )
    transcribe_parser.add_argument(
        "--min-note-length",
        type=float,
        default=127.7,
        help="Minimum note length in ms (basic_pitch only, default: 127.7)",
    )
    transcribe_parser.add_argument(
        "--multiple-pitch-bends",
        action="store_true",
        help="Allow multiple simultaneous pitch bends (basic_pitch only)",
    )
    transcribe_parser.add_argument(
        "--no-melodia-trick",
        action="store_true",
        help="Disable melodia trick for F0 estimation (basic_pitch only)",
    )
    transcribe_parser.add_argument(
        "--use-docker",
        action="store_true",
        help="Force Docker execution for supported backends (magenta, omnizart, mt3)",
    )
    transcribe_parser.add_argument(
        "--no-docker-fallback",
        action="store_true",
        help="Disable automatic Docker fallback when native backend unavailable",
    )
    transcribe_parser.add_argument(
        "--docker-timeout",
        type=int,
        default=600,
        help="Docker container timeout in seconds (default: 600)",
    )

    # pitch-score command
    pitch_score_parser = subparsers.add_parser(
        "pitch-score",
        help="Score audio samples against a chord progression by analyzing detected pitches",
    )
    pitch_score_parser.add_argument(
        "--sample-dir",
        type=str,
        required=True,
        help="Directory containing audio samples to analyze",
    )
    pitch_score_parser.add_argument(
        "--progression",
        type=str,
        help="Chord progression in shorthand: 'Cmaj7:4 Am7:4 Fmaj7:2 G7:2'",
    )
    pitch_score_parser.add_argument(
        "--progression-file",
        type=str,
        help="Path to JSON file with chord progression",
    )
    pitch_score_parser.add_argument(
        "--bpm",
        type=float,
        help="Tempo in BPM (required if using --progression)",
    )
    pitch_score_parser.add_argument(
        "--time-sig",
        type=str,
        default="4/4",
        help="Time signature (default: 4/4)",
    )
    pitch_score_parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Minimum compatibility score (0-100, default: 0)",
    )
    pitch_score_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results to return (default: 20)",
    )
    pitch_score_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't process subdirectories (default: recursive)",
    )
    pitch_score_parser.add_argument(
        "--output",
        type=str,
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    pitch_score_parser.add_argument(
        "--explain",
        action="store_true",
        help="Show detailed per-beat analysis for top results",
    )
    pitch_score_parser.add_argument(
        "--mono",
        action="store_true",
        help="Force monophonic pitch detection (audio mode only)",
    )
    pitch_score_parser.add_argument(
        "--poly",
        action="store_true",
        help="Force polyphonic pitch detection (audio mode only)",
    )
    pitch_score_parser.add_argument(
        "--use-midi",
        action="store_true",
        help="Use pre-transcribed MIDI files instead of analyzing audio (much faster)",
    )
    pitch_score_parser.add_argument(
        "--midi-backend",
        type=str,
        choices=["basic_pitch", "piano_transcription", "onsets_frames", "omnizart", "mt3"],
        help="Specific MIDI backend to use (default: auto-detect)",
    )
    pitch_score_parser.add_argument(
        "--no-midi-fallback",
        action="store_true",
        help="Don't fall back to audio analysis if MIDI not found",
    )
    pitch_score_parser.add_argument(
        "--midi-only",
        action="store_true",
        help="Only process files with existing MIDI transcriptions (fast mode, skips audio analysis)",
    )
    pitch_score_parser.add_argument(
        "--normalize",
        action="store_true",
        help="Use key-agnostic matching (finds samples in any key, shows transposition needed)",
    )
    pitch_score_parser.add_argument(
        "--show-transposition",
        action="store_true",
        help="Show recommended transposition for each result (implied by --normalize)",
    )
    pitch_score_parser.add_argument(
        "--merge-backends",
        action="store_true",
        help="Merge notes from all available MIDI transcriptions (basic_pitch + piano_transcription) for better accuracy",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # Dispatch to command handler
    handlers = {
        "analyze": cmd_analyze,
        "find": cmd_find,
        "info": cmd_info,
        "stats": cmd_stats,
        "compare": cmd_compare,
        "check": cmd_check,
        "transcribe": cmd_transcribe,
        "pitch-score": cmd_pitch_score,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


def cmd_analyze(args) -> int:
    """Handle the analyze command."""
    csv_dir = Path(args.csv_dir)

    # Mapping from CSV files to original audio files
    audio_csv_mapping = {}

    # If extract flag is set, run Sonic Annotator first
    if args.extract:
        if not args.audio_dir:
            print("Error: --audio-dir required when using --extract")
            return 1

        if not check_sonic_annotator():
            print("Error: Sonic Annotator is not installed")
            print("Install with: brew install sonic-annotator (macOS)")
            return 1

        if not check_chordino_plugin():
            print("Error: Chordino VAMP plugin not found")
            print("Download from: https://code.soundsoftware.ac.uk/projects/nnls-chroma/files")
            return 1

        print(f"Extracting chords from audio files in {args.audio_dir}...")

        # Generate transform file if needed
        transform_file = csv_dir / "chordino.n3"
        if not transform_file.exists():
            csv_dir.mkdir(parents=True, exist_ok=True)
            generate_transform_file(str(transform_file))

        results = batch_extract_chords(
            args.audio_dir,
            str(csv_dir),
            str(transform_file),
            recursive=not args.no_recursive,
        )

        success = sum(1 for _, csv in results if csv)
        print(f"Extracted chords from {success}/{len(results)} files")

        # Build mapping from CSV path to original audio path
        for audio_path, csv_path in results:
            if csv_path:
                audio_csv_mapping[csv_path] = audio_path

    # Process CSV files into database
    if not csv_dir.exists():
        print(f"Error: CSV directory not found: {csv_dir}")
        return 1

    print(f"Building database from {csv_dir}...")

    # Parse time signature
    time_sig_parts = args.time_sig.split("/")
    time_signature = (int(time_sig_parts[0]), int(time_sig_parts[1]))

    # Check tempo detection availability
    tempo_enabled = args.detect_tempo or args.bpm is not None
    if tempo_enabled and not args.bpm and not check_librosa_available():
        print("Warning: librosa not installed, tempo detection disabled")
        print("Install with: pip install librosa")
        tempo_enabled = False

    conn = init_database(args.db)
    pattern = "**/*.csv" if not args.no_recursive else "*.csv"

    csv_files = list(csv_dir.glob(pattern))
    if not csv_files:
        print("No CSV files found")
        return 1

    processed = 0
    tempo_detected = 0
    for csv_file in csv_files:
        try:
            # Get original audio path if available
            audio_path = audio_csv_mapping.get(str(csv_file))

            if tempo_enabled:
                # Use tempo-aware extraction
                sample = create_sample_from_csv_with_tempo(
                    str(csv_file),
                    audio_path=audio_path,
                    bpm=args.bpm,
                    time_signature=time_signature,
                    auto_detect=args.detect_tempo,
                )
                if sample.estimated_bpm:
                    tempo_detected += 1
            else:
                sample = create_sample_from_csv(str(csv_file), audio_path=audio_path)

            # Use original audio path as filepath if available
            if audio_path:
                sample.filepath = audio_path
                sample.filename = Path(audio_path).stem

            # Estimate key from progression
            if sample.progression:
                sample.estimated_key = estimate_key_from_progression(sample.progression)

            store_sample(conn, sample)
            processed += 1
        except Exception as e:
            print(f"Warning: Failed to process {csv_file}: {e}")

    conn.close()
    print(f"Processed {processed} samples into {args.db}")
    if tempo_enabled:
        print(f"Tempo detected for {tempo_detected}/{processed} samples")

    return 0


def cmd_find(args) -> int:
    """Handle the find command."""
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    conn = init_database(args.db)

    # Get target sample
    target = get_sample_by_filepath(conn, args.target)
    if not target:
        print(f"Error: Target sample not found: {args.target}")
        conn.close()
        return 1

    print(f"\nFinding samples compatible with: {target.filename}")
    print(f"Progression: {' -> '.join(target.progression[:6])}")
    if target.estimated_key:
        print(f"Key: {target.estimated_key}")
    if target.estimated_bpm:
        print(f"BPM: {target.estimated_bpm}")

    # Check rhythm comparison availability
    use_rhythm = args.use_rhythm
    if use_rhythm and not target.has_beat_info:
        print("Warning: Target sample has no beat info, rhythm comparison disabled")
        use_rhythm = False
    elif use_rhythm:
        print("Using rhythm pattern comparison")
    print()

    results = find_compatible_samples(
        conn,
        args.target,
        min_score=args.min_score,
        limit=args.limit,
        use_rhythm=use_rhythm,
    )

    if not results:
        print(f"No matches found with score >= {args.min_score}")
        conn.close()
        return 0

    # Display results
    if RICH_AVAILABLE:
        _display_results_rich(results, args.explain)
    else:
        _display_results_plain(results, args.explain)

    conn.close()
    return 0


def cmd_info(args) -> int:
    """Handle the info command."""
    # Check if it's a CSV file (direct analysis) or database lookup
    filepath = Path(args.filepath)

    if filepath.suffix == ".csv" and filepath.exists():
        # Direct CSV analysis
        sample = create_sample_from_csv(str(filepath))
        if sample.progression:
            sample.estimated_key = estimate_key_from_progression(sample.progression)
    else:
        # Database lookup
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: Database not found: {db_path}")
            return 1

        conn = init_database(args.db)
        sample = get_sample_by_filepath(conn, args.filepath)
        conn.close()

        if not sample:
            print(f"Error: Sample not found: {args.filepath}")
            return 1

    # Display sample info
    print(f"\nSample: {sample.filename}")
    print(f"Duration: {sample.duration_seconds:.1f} seconds")

    if sample.estimated_key:
        print(f"Estimated Key: {sample.estimated_key}")

    # Tempo/Beat info
    if sample.estimated_bpm:
        print(f"\nTempo Info:")
        print(f"  BPM: {sample.estimated_bpm}")
        time_sig = f"{sample.time_signature[0]}/{sample.time_signature[1]}"
        print(f"  Time Signature: {time_sig}")
        if sample.total_bars:
            print(f"  Total Bars: {sample.total_bars}")
        if sample.first_beat_offset > 0:
            print(f"  First Beat Offset: {sample.first_beat_offset:.3f}s")

    print(f"\nChord Progression:")
    has_beat_info = sample.has_beat_info

    for i, chord in enumerate(sample.chords[:20]):
        if has_beat_info and chord.has_beat_info:
            # Show bar/beat info
            beat_str = int(chord.beat) if chord.beat == int(chord.beat) else f"{chord.beat:.1f}"
            duration_str = f"({chord.duration_beats:.1f} beats)" if chord.duration_beats else ""
            print(f"  Bar {chord.bar}, Beat {beat_str}: {chord.chord_label} {duration_str}")
        else:
            print(f"  {chord.start_time:.1f}s - {chord.end_time:.1f}s: {chord.chord_label}")

    if len(sample.chords) > 20:
        print(f"  ... and {len(sample.chords) - 20} more chords")

    print(f"\nSummary:")
    print(f"  Unique Chords: {', '.join(sorted(sample.unique_chords))}")
    print(f"  Root Notes: {', '.join(sorted(sample.root_notes))}")
    print(f"  Chord Types: {', '.join(sorted(sample.chord_types))}")

    return 0


def cmd_stats(args) -> int:
    """Handle the stats command."""
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    conn = init_database(args.db)
    stats = get_database_stats(conn)
    conn.close()

    print(f"\nDatabase Statistics: {args.db}")
    print(f"{'=' * 40}")
    print(f"Total Samples: {stats['total_samples']}")
    print(f"Average Duration: {stats['avg_duration']} seconds")
    print(f"Cached Comparisons: {stats['cached_comparisons']}")

    # Tempo statistics
    if stats.get("samples_with_tempo", 0) > 0:
        print(f"\nTempo Analysis:")
        print(f"  Samples with tempo: {stats['samples_with_tempo']}/{stats['total_samples']}")
        if "bpm_min" in stats:
            print(f"  BPM Range: {stats['bpm_min']} - {stats['bpm_max']}")
            print(f"  BPM Average: {stats['bpm_avg']}")

    # Time signature distribution
    if stats.get("time_signatures"):
        print(f"\nTime Signatures:")
        for sig, count in list(stats["time_signatures"].items())[:5]:
            print(f"  {sig}: {count}")

    if stats["keys"]:
        print(f"\nSamples by Key:")
        for key, count in list(stats["keys"].items())[:10]:
            print(f"  {key}: {count}")

    return 0


def cmd_compare(args) -> int:
    """Handle the compare command."""
    path_a = Path(args.sample_a)
    path_b = Path(args.sample_b)

    if not path_a.exists():
        print(f"Error: File not found: {path_a}")
        return 1
    if not path_b.exists():
        print(f"Error: File not found: {path_b}")
        return 1

    sample_a = create_sample_from_csv(str(path_a))
    sample_b = create_sample_from_csv(str(path_b))

    print(f"\nComparing:")
    print(f"  A: {sample_a.filename}")
    print(f"     {' -> '.join(sample_a.progression[:6])}")
    print(f"  B: {sample_b.filename}")
    print(f"     {' -> '.join(sample_b.progression[:6])}")
    print()

    explanation = explain_compatibility(
        sample_a.progression,
        sample_b.progression,
        verbose=args.verbose,
    )
    print(explanation)

    return 0


def cmd_check(args) -> int:
    """Handle the check command."""
    print("\nSystem Dependency Check")
    print("=" * 40)

    # Check Sonic Annotator
    sonic_ok = check_sonic_annotator()
    status = "[OK]" if sonic_ok else "[MISSING]"
    print(f"{status} Sonic Annotator")

    # Check Chordino plugin
    if sonic_ok:
        chordino_ok = check_chordino_plugin()
        status = "[OK]" if chordino_ok else "[MISSING]"
        print(f"{status} Chordino VAMP Plugin")
    else:
        print("[SKIP] Chordino VAMP Plugin (requires Sonic Annotator)")

    # Check librosa for tempo detection
    librosa_ok = check_librosa_available()
    status = "[OK]" if librosa_ok else "[OPTIONAL]"
    print(f"{status} librosa (tempo/beat detection)")

    # Check Rich
    status = "[OK]" if RICH_AVAILABLE else "[OPTIONAL]"
    print(f"{status} Rich (terminal formatting)")

    # Check Docker
    try:
        from .midi_transcriber import (
            is_docker_available,
            check_transcription_backends,
            DOCKER_IMAGES,
            BACKEND_DESCRIPTIONS,
        )

        docker_ok = is_docker_available()
        status = "[OK]" if docker_ok else "[OPTIONAL]"
        print(f"{status} Docker (container execution)")

        # Check transcription backends
        print("\nTranscription Backends:")
        backends = check_transcription_backends(include_docker=docker_ok)
        for name, avail in backends.items():
            native = avail.get("native", False)
            docker = avail.get("docker", False)
            if native:
                status = "[OK]"
            elif docker:
                status = "[DOCKER]"
            else:
                status = "[MISSING]"
            print(f"  {status} {name}")
    except ImportError:
        print("\n[SKIP] Transcription backends (import error)")

    print()

    if not sonic_ok:
        print("To install Sonic Annotator:")
        print("  macOS: brew install sonic-annotator")
        print("  Linux: sudo apt-get install sonic-annotator")
        print()
        print("To install Chordino:")
        print("  Download from: https://code.soundsoftware.ac.uk/projects/nnls-chroma/files")
        print("  Place in ~/Library/Audio/Plug-Ins/Vamp/ (macOS)")
        print("  or ~/.vamp/ (Linux)")
        print()

    if not librosa_ok:
        print("To enable tempo detection:")
        print("  pip install librosa")
        print()

    return 0 if sonic_ok else 1


def _display_results_rich(results, explain: bool) -> None:
    """Display results using Rich formatting."""
    console = Console()

    table = Table(title="Compatible Samples")
    table.add_column("Score", justify="right", style="cyan")
    table.add_column("Sample", style="green")
    table.add_column("Progression")

    if explain:
        table.add_column("Details", style="dim")

    for result in results:
        progression_str = " -> ".join(result.sample.progression[:5])
        if len(result.sample.progression) > 5:
            progression_str += " ..."

        if explain:
            details = "; ".join(result.reasons) if result.reasons else ""
            table.add_row(
                f"{result.overall_score:.1f}",
                result.sample.filename,
                progression_str,
                details,
            )
        else:
            table.add_row(
                f"{result.overall_score:.1f}",
                result.sample.filename,
                progression_str,
            )

    console.print(table)
    console.print(f"\nFound {len(results)} compatible samples")


def _display_results_plain(results, explain: bool) -> None:
    """Display results using plain text."""
    for result in results:
        progression_str = " -> ".join(result.sample.progression[:5])
        if len(result.sample.progression) > 5:
            progression_str += " ..."

        print(f"  {result.overall_score:5.1f}  {result.sample.filename}")
        print(f"         Progression: {progression_str}")

        if explain and result.reasons:
            print(f"         {'; '.join(result.reasons)}")
        print()

    print(f"Found {len(results)} compatible samples")


def _get_backend_options(args, backend) -> dict:
    """Get backend-specific options from CLI args."""
    from .midi_transcriber import TranscriptionBackend

    options = {}
    if backend == TranscriptionBackend.BASIC_PITCH:
        options = {
            "onset_threshold": args.onset_threshold,
            "frame_threshold": args.frame_threshold,
            "minimum_note_length": args.min_note_length,
            "multiple_pitch_bends": args.multiple_pitch_bends,
            "melodia_trick": not args.no_melodia_trick,
        }
    elif backend == TranscriptionBackend.PIANO_TRANSCRIPTION:
        options = {
            "device": args.device,
        }
    elif backend == TranscriptionBackend.OMNIZART:
        options = {
            "mode": args.omnizart_mode,
        }
    return options


def cmd_transcribe(args) -> int:
    """Handle the transcribe command."""
    try:
        from .midi_transcriber import (
            TranscriptionBackend,
            transcribe_audio,
            transcribe_audio_multi,
            transcribe_directory,
            transcribe_directory_multi,
            check_transcription_backends,
            get_available_backends,
            is_docker_available,
            DOCKER_IMAGES,
            TRANSCRIPTION_AUDIO_FORMATS,
            BACKEND_DESCRIPTIONS,
            BACKEND_INSTALL_COMMANDS,
            explain_multi_result,
        )
    except ImportError as e:
        print(f"Error: Missing transcription dependencies: {e}")
        print("Install with: pip install basic-pitch")
        return 1

    # Check available backends (include Docker availability)
    available_backends = check_transcription_backends(include_docker=True)

    # Determine Docker availability
    docker_available = is_docker_available()
    use_docker = True if args.use_docker else None  # None = auto mode
    docker_fallback = not args.no_docker_fallback

    if args.use_docker and not docker_available:
        print("Error: --use-docker specified but Docker is not available")
        return 1

    # Parse backend argument
    backend_names = args.backend
    if backend_names is None or "all" in backend_names:
        # Use all available backends by default (native OR Docker)
        backends_to_use = []
        for name, availability in available_backends.items():
            if availability["native"] or (docker_fallback and availability["docker"]):
                backends_to_use.append(TranscriptionBackend(name))

        if not backends_to_use:
            print("Error: No transcription backends are available.")
            print("\nAvailable backends:")
            for backend in TranscriptionBackend.all_backends():
                desc = BACKEND_DESCRIPTIONS.get(backend, "")
                install = BACKEND_INSTALL_COMMANDS.get(backend, "")
                avail = available_backends.get(backend.value, {})
                status = []
                if avail.get("native"):
                    status.append("native")
                if avail.get("docker"):
                    status.append("docker")
                status_str = f"[{', '.join(status)}]" if status else "[not installed]"
                print(f"  {backend.value} {status_str}: {desc}")
                print(f"    Install: {install}")
            return 1
    else:
        # Use specified backends
        backends_to_use = []
        for name in backend_names:
            if name == "all":
                continue
            backend = TranscriptionBackend(name)
            avail = available_backends.get(name, {})
            native_ok = avail.get("native", False)
            docker_ok = avail.get("docker", False) and docker_fallback

            if not native_ok and not docker_ok:
                print(f"Warning: Backend '{name}' is not available, skipping.")
                if backend.value in DOCKER_IMAGES and not docker_available:
                    print(f"  (Docker image available but Docker not running)")
                print(f"  Install with: {BACKEND_INSTALL_COMMANDS.get(backend, 'see documentation')}")
            else:
                backends_to_use.append(backend)

        if not backends_to_use:
            print("Error: None of the specified backends are available.")
            return 1

    # Determine if using single or multiple backends
    use_multi = len(backends_to_use) > 1

    input_path = Path(args.input)

    # Check if input exists
    if not input_path.exists():
        print(f"Error: Input not found: {args.input}")
        return 1

    # Display backend info with availability status
    backend_status = []
    for b in backends_to_use:
        avail = available_backends.get(b.value, {})
        if avail.get("native"):
            backend_status.append(f"{b.value}")
        elif avail.get("docker"):
            backend_status.append(f"{b.value}[docker]")
        else:
            backend_status.append(f"{b.value}[?]")
    print(f"Backends: {', '.join(backend_status)}")
    if docker_available and docker_fallback:
        print("Docker fallback: enabled")

    # Single file transcription
    if input_path.is_file():
        print(f"Transcribing: {input_path.name}")
        print()

        if use_multi:
            # Multi-backend transcription
            multi_result = transcribe_audio_multi(
                str(input_path),
                backends=backends_to_use,
                output_dir=args.output_dir,
                use_docker=use_docker,
                docker_fallback=docker_fallback,
            )

            print(explain_multi_result(multi_result))

            if multi_result.any_succeeded:
                return 0
            else:
                return 1
        else:
            # Single backend transcription
            backend = backends_to_use[0]

            # Prepare backend-specific options
            backend_options = _get_backend_options(args, backend)

            result = transcribe_audio(
                str(input_path),
                backend=backend,
                output_path=None,  # Auto-generate
                use_docker=use_docker,
                docker_fallback=docker_fallback,
                **backend_options,
            )

            if result.success:
                print(f"\nSuccess!")
                print(f"  Output: {result.output_path}")
                print(f"  Notes: {result.note_count}")
                print(f"  Duration: {result.duration_seconds:.2f}s")
                return 0
            else:
                print(f"\nFailed: {result.error_message}")
                return 1

    # Directory transcription
    elif input_path.is_dir():
        from multiprocessing import cpu_count
        num_workers = args.workers if args.workers > 0 else cpu_count()
        print(f"Transcribing directory: {input_path}")
        if not args.no_recursive:
            print("  (including subdirectories)")
        if args.output_dir:
            print(f"Output directory: {args.output_dir}")
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        if num_workers > 1:
            print(f"Workers: {num_workers} (parallel processing)")
        print()

        if use_multi:
            # Multi-backend directory transcription
            if RICH_AVAILABLE:
                console = Console()
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                )

                def progress_callback(filepath, multi_result):
                    succeeded = len(multi_result.successful_backends)
                    total = len(multi_result.results)
                    progress.update(
                        task_id,
                        description=f"[cyan]{Path(filepath).name} [{succeeded}/{total} OK]",
                    )

                with progress:
                    task_id = progress.add_task("[cyan]Transcribing...", total=None)
                    batch_result = transcribe_directory_multi(
                        str(input_path),
                        backends=backends_to_use,
                        output_dir=args.output_dir,
                        recursive=not args.no_recursive,
                        overwrite=args.overwrite,
                        progress_callback=progress_callback,
                        workers=args.workers,
                    )
            else:
                def progress_callback(filepath, multi_result):
                    succeeded = len(multi_result.successful_backends)
                    total = len(multi_result.results)
                    print(f"  {Path(filepath).name}: {succeeded}/{total} OK")

                batch_result = transcribe_directory_multi(
                    str(input_path),
                    backends=backends_to_use,
                    output_dir=args.output_dir,
                    recursive=not args.no_recursive,
                    overwrite=args.overwrite,
                    progress_callback=progress_callback,
                    workers=args.workers,
                )

            # Summary for multi-backend
            print(f"\nTranscription Complete")
            print(f"  Total files: {batch_result.total_files}")
            print(f"\n  Results by backend:")
            for backend, count in batch_result.successful_by_backend.items():
                print(f"    {backend.value}: {count}/{batch_result.total_files} succeeded")

            return 0

        else:
            # Single backend directory transcription
            backend = backends_to_use[0]
            backend_options = _get_backend_options(args, backend)

            if RICH_AVAILABLE:
                console = Console()
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                )

                def progress_callback(filepath, result):
                    status = "OK" if result.success else "FAIL"
                    progress.update(
                        task_id,
                        description=f"[cyan]{Path(filepath).name} [{status}]",
                    )

                with progress:
                    task_id = progress.add_task("[cyan]Transcribing...", total=None)
                    batch_result = transcribe_directory(
                        str(input_path),
                        backend=backend,
                        output_dir=args.output_dir,
                        recursive=not args.no_recursive,
                        overwrite=args.overwrite,
                        progress_callback=progress_callback,
                        workers=args.workers,
                        **backend_options,
                    )
            else:
                def progress_callback(filepath, result):
                    status = "OK" if result.success else "FAIL"
                    print(f"  {Path(filepath).name}: {status}")

                batch_result = transcribe_directory(
                    str(input_path),
                    backend=backend,
                    output_dir=args.output_dir,
                    recursive=not args.no_recursive,
                    overwrite=args.overwrite,
                    progress_callback=progress_callback,
                    workers=args.workers,
                    **backend_options,
                )

        # Summary
        print(f"\nTranscription Complete")
        print(f"  Total files: {batch_result.total_files}")
        print(f"  Successful: {batch_result.successful}")
        print(f"  Failed: {batch_result.failed}")
        print(f"  Success rate: {batch_result.success_rate:.1f}%")

        # Show failures
        failed_results = [r for r in batch_result.results if not r.success]
        if failed_results:
            print(f"\nFailed files:")
            for r in failed_results[:10]:
                print(f"  {Path(r.input_path).name}: {r.error_message}")
            if len(failed_results) > 10:
                print(f"  ... and {len(failed_results) - 10} more")

        return 0 if batch_result.failed == 0 else 1

    else:
        print(f"Error: Invalid input path: {args.input}")
        return 1


def cmd_pitch_score(args) -> int:
    """Handle the pitch-score command."""
    # Import pitch-specific modules
    try:
        from .progression_parser import (
            parse_progression_shorthand,
            parse_progression_file,
            validate_progression,
        )
        from .pitch_compatibility import (
            scan_and_rank_samples,
            explain_compatibility,
        )
        from .pitch_detector import check_pitch_detection_available
    except ImportError as e:
        print(f"Error: Missing dependencies for pitch analysis: {e}")
        print("Install with: pip install librosa")
        return 1

    # Check dependencies
    available, message = check_pitch_detection_available()
    if not available:
        print(f"Error: {message}")
        return 1

    # Parse time signature
    time_sig_parts = args.time_sig.split("/")
    time_signature = (int(time_sig_parts[0]), int(time_sig_parts[1]))

    # Parse progression
    if args.progression_file:
        try:
            progression = parse_progression_file(args.progression_file)
            # Override BPM if specified
            if args.bpm:
                from .models import UserProgression
                progression = UserProgression(
                    chords=progression.chords,
                    bpm=args.bpm,
                    time_signature=time_signature,
                    name=progression.name,
                )
        except FileNotFoundError:
            print(f"Error: Progression file not found: {args.progression_file}")
            return 1
        except ValueError as e:
            print(f"Error parsing progression file: {e}")
            return 1
    elif args.progression:
        if not args.bpm:
            print("Error: --bpm is required when using --progression")
            return 1
        try:
            progression = parse_progression_shorthand(
                args.progression,
                bpm=args.bpm,
                time_signature=time_signature,
            )
        except ValueError as e:
            print(f"Error parsing progression: {e}")
            return 1
    else:
        print("Error: Must provide --progression or --progression-file")
        return 1

    # Validate progression
    warnings = validate_progression(progression)
    for warning in warnings:
        print(f"Warning: {warning}")

    # Display progression info
    print(f"\nScoring samples against progression:")
    print(f"  Chords: {' -> '.join(c.chord_label for c in progression.chords)}")

    # Show detected key and Roman numerals
    estimated_key = progression.estimated_key
    if estimated_key:
        print(f"  Key: {estimated_key} major (detected)")
        roman_numerals = progression.to_roman_numerals(estimated_key)
        print(f"  Roman numerals: {' -> '.join(roman_numerals)}")

    print(f"  BPM: {progression.bpm}")
    print(f"  Time Signature: {args.time_sig}")
    print(f"  Total: {progression.total_beats} beats ({progression.total_bars:.1f} bars)")

    # Show matching mode
    if args.normalize:
        print(f"  Mode: Normalized (key-agnostic matching enabled)")

    print(f"\nScanning: {args.sample_dir}")
    if not args.no_recursive:
        print("  (including subdirectories)")
    if args.midi_only:
        backend_str = args.midi_backend if args.midi_backend else "auto-detect"
        merge_str = ", merging all backends" if args.merge_backends else ""
        print(f"  Mode: MIDI-only (fast mode, backend: {backend_str}{merge_str})")
    elif args.use_midi:
        backend_str = args.midi_backend if args.midi_backend else "auto-detect"
        fallback_str = "disabled" if args.no_midi_fallback else "enabled"
        merge_str = ", merging all backends" if args.merge_backends else ""
        print(f"  Using MIDI files (backend: {backend_str}, audio fallback: {fallback_str}{merge_str})")
    print()

    # Progress callback for Rich
    processed = [0]
    total_files = [0]

    if RICH_AVAILABLE:
        console = Console()
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )

        def progress_callback(filepath, result):
            processed[0] += 1
            status = f"{result.overall_score:.1f}" if result else "error"
            progress.update(
                task_id,
                description=f"[cyan]Processing: {Path(filepath).name} ({status})",
            )
    else:
        progress = None

        def progress_callback(filepath, result):
            processed[0] += 1
            status = f"{result.overall_score:.1f}" if result else "error"
            print(f"  [{processed[0]}] {Path(filepath).name}: {status}")

    # Handle --midi-only as convenience alias
    use_midi = args.use_midi or args.midi_only
    midi_fallback = not (args.no_midi_fallback or args.midi_only)

    # Scan and rank samples
    try:
        if RICH_AVAILABLE and progress:
            with progress:
                task_id = progress.add_task("[cyan]Scanning samples...", total=None)
                results, stats = scan_and_rank_samples(
                    sample_dir=args.sample_dir,
                    progression=progression,
                    recursive=not args.no_recursive,
                    min_score=args.min_score,
                    limit=args.limit,
                    force_mono=args.mono,
                    force_poly=args.poly,
                    progress_callback=progress_callback,
                    use_midi=use_midi,
                    midi_backend=args.midi_backend,
                    midi_fallback=midi_fallback,
                    normalize=args.normalize,
                    return_stats=True,
                    merge_midi_backends=args.merge_backends,
                )
        else:
            print("Processing samples...")
            results, stats = scan_and_rank_samples(
                sample_dir=args.sample_dir,
                progression=progression,
                recursive=not args.no_recursive,
                min_score=args.min_score,
                limit=args.limit,
                force_mono=args.mono,
                force_poly=args.poly,
                progress_callback=progress_callback,
                use_midi=use_midi,
                midi_backend=args.midi_backend,
                midi_fallback=midi_fallback,
                normalize=args.normalize,
                return_stats=True,
                merge_midi_backends=args.merge_backends,
            )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1

    # Display scan statistics
    if stats:
        print(f"\n{stats}")

    if not results:
        print(f"\nNo samples found with score >= {args.min_score}")
        return 0

    # Display results based on output format
    print()
    # --normalize implies --show-transposition
    show_transposition = args.show_transposition or args.normalize
    if args.output == "json":
        _display_pitch_results_json(results)
    elif args.output == "csv":
        _display_pitch_results_csv(results, show_transposition)
    else:
        if RICH_AVAILABLE:
            _display_pitch_results_rich(results, args.explain, show_transposition)
        else:
            _display_pitch_results_plain(results, args.explain, show_transposition)

    return 0


def _display_pitch_results_rich(results, explain: bool, show_transposition: bool = False) -> None:
    """Display pitch scoring results using Rich formatting."""
    console = Console()

    table = Table(title="Pitch Compatibility Results")
    table.add_column("Rank", justify="right", style="cyan", width=4)
    table.add_column("Score", justify="right", style="green", width=6)
    table.add_column("Sample", style="blue")
    table.add_column("Notes", justify="right", width=6)
    table.add_column("Chord%", justify="right", width=7)
    table.add_column("Scale%", justify="right", width=7)

    if show_transposition:
        table.add_column("Transpose", style="yellow", width=12)

    if explain:
        table.add_column("Assessment", style="dim")

    for i, result in enumerate(results, 1):
        row = [
            str(i),
            f"{result.overall_score:.1f}",
            result.filename,
            str(result.note_count),
            f"{result.avg_in_chord_ratio:.0%}",
            f"{result.avg_in_scale_ratio:.0%}",
        ]
        if show_transposition:
            if result.has_transposition_info:
                trans = result.recommended_transposition
                desc = result.transposition_description
                if trans == 0:
                    row.append("in key")
                else:
                    sign = "+" if trans > 0 else ""
                    row.append(f"{sign}{trans} ({desc})")
            else:
                row.append("-")
        if explain:
            row.append("; ".join(result.reasons[:2]) if result.reasons else "")
        table.add_row(*row)

    console.print(table)
    console.print(f"\nFound {len(results)} compatible samples")

    # Show detailed explanation for top result if --explain
    if explain and results:
        console.print("\n[bold]Top Result Details:[/bold]")
        from .pitch_compatibility import explain_compatibility
        explanation = explain_compatibility(results[0], verbose=True)
        console.print(explanation)


def _display_pitch_results_plain(results, explain: bool, show_transposition: bool = False) -> None:
    """Display pitch scoring results using plain text."""
    print("Pitch Compatibility Results")
    print("=" * 60)

    for i, result in enumerate(results, 1):
        print(f"{i:3}. {result.overall_score:5.1f}  {result.filename}")
        details = [
            f"Notes: {result.note_count}",
            f"Chord: {result.avg_in_chord_ratio:.0%}",
            f"Scale: {result.avg_in_scale_ratio:.0%}",
        ]
        if show_transposition and result.has_transposition_info:
            trans = result.recommended_transposition
            desc = result.transposition_description
            if trans == 0:
                details.append("Transpose: in key")
            else:
                sign = "+" if trans > 0 else ""
                details.append(f"Transpose: {sign}{trans} ({desc})")
        print(f"     {', '.join(details)}")
        if explain and result.reasons:
            print(f"     {'; '.join(result.reasons[:2])}")
        print()

    print(f"Found {len(results)} compatible samples")


def _display_pitch_results_json(results) -> None:
    """Display pitch scoring results as JSON."""
    import json
    output = {
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }
    print(json.dumps(output, indent=2))


def _display_pitch_results_csv(results, show_transposition: bool = False) -> None:
    """Display pitch scoring results as CSV."""
    header = "rank,score,filename,notes,chord_ratio,scale_ratio,clashes,monophonic,bpm"
    if show_transposition:
        header += ",detected_key,transposition,transposition_desc"
    print(header)
    for i, result in enumerate(results, 1):
        bpm = result.detected_bpm or ""
        row = (f"{i},{result.overall_score:.1f},{result.filename},"
               f"{result.note_count},{result.avg_in_chord_ratio:.3f},"
               f"{result.avg_in_scale_ratio:.3f},{result.total_clash_count},"
               f"{result.is_monophonic},{bpm}")
        if show_transposition:
            key = result.detected_key or ""
            trans = result.recommended_transposition if result.has_transposition_info else ""
            desc = result.transposition_description or ""
            row += f",{key},{trans},{desc}"
        print(row)


if __name__ == "__main__":
    sys.exit(main())

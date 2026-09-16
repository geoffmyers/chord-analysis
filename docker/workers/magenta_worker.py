#!/usr/bin/env python3
"""
Magenta Onsets and Frames transcription worker.

This script runs inside a Docker container and handles audio-to-MIDI
transcription using Google Magenta's Onsets and Frames model.

Usage:
    python magenta_worker.py <input_audio> <output_midi> [--checkpoint <path>]

Output (JSON to stdout):
    {
        "success": true/false,
        "note_count": int,
        "duration_seconds": float,
        "error_message": string (if failed)
    }
"""

import argparse
import json
import sys
from pathlib import Path


def transcribe(audio_path: str, output_path: str, checkpoint_path: str = None) -> dict:
    """
    Transcribe audio to MIDI using Onsets and Frames.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file
        checkpoint_path: Optional path to model checkpoint

    Returns:
        Dict with transcription results
    """
    try:
        import note_seq
        from magenta.models.onsets_frames_transcription import (
            configs,
            constants,
            train_util,
        )
        from magenta.models.onsets_frames_transcription.transcribe import (
            transcribe_audio,
        )

        # Use default checkpoint if not specified
        if checkpoint_path is None:
            # Download or use cached checkpoint
            checkpoint_path = train_util.get_default_hparams_path()

        # Transcribe audio
        ns = transcribe_audio(audio_path, checkpoint_path)

        # Save as MIDI
        note_seq.sequence_proto_to_midi_file(ns, output_path)

        # Get statistics
        note_count = len(ns.notes)
        duration = ns.total_time if ns.notes else 0.0

        return {
            "success": True,
            "note_count": note_count,
            "duration_seconds": duration,
            "output_path": output_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error_message": str(e),
            "note_count": 0,
            "duration_seconds": 0.0,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio to MIDI using Magenta Onsets and Frames"
    )
    parser.add_argument("input", help="Input audio file path")
    parser.add_argument("output", help="Output MIDI file path")
    parser.add_argument(
        "--checkpoint",
        help="Path to model checkpoint (uses default if not specified)",
    )

    args = parser.parse_args()

    # Validate input
    if not Path(args.input).exists():
        result = {
            "success": False,
            "error_message": f"Input file not found: {args.input}",
            "note_count": 0,
            "duration_seconds": 0.0,
        }
        print(json.dumps(result))
        sys.exit(1)

    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Run transcription
    result = transcribe(args.input, args.output, args.checkpoint)

    # Output result as JSON
    print(json.dumps(result))

    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Omnizart multi-instrument transcription worker.

This script runs inside a Docker container and handles audio-to-MIDI
transcription using Omnizart's multi-instrument models.

Usage:
    python omnizart_worker.py <input_audio> <output_midi> [--mode music|drum|vocal]

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
import subprocess
import sys
from pathlib import Path


def transcribe(audio_path: str, output_path: str, mode: str = "music") -> dict:
    """
    Transcribe audio to MIDI using Omnizart.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file
        mode: Transcription mode ('music', 'drum', 'vocal')

    Returns:
        Dict with transcription results
    """
    try:
        import pretty_midi

        # Create temp output directory
        output_dir = Path(output_path).parent
        output_name = Path(output_path).stem

        # Run omnizart transcription via CLI (more reliable than Python API)
        result = subprocess.run(
            ["omnizart", mode, "transcribe", audio_path, "-o", str(output_dir)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Omnizart failed: {result.stderr}")

        # Omnizart outputs with default name, rename if needed
        expected_output = output_dir / f"{Path(audio_path).stem}.mid"
        if expected_output.exists() and str(expected_output) != output_path:
            expected_output.rename(output_path)

        # Get statistics from output MIDI
        if Path(output_path).exists():
            pm = pretty_midi.PrettyMIDI(output_path)
            note_count = sum(len(inst.notes) for inst in pm.instruments)
            duration = pm.get_end_time()
        else:
            note_count = 0
            duration = 0.0

        return {
            "success": True,
            "note_count": note_count,
            "duration_seconds": duration,
            "output_path": output_path,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error_message": "Transcription timed out (>10 minutes)",
            "note_count": 0,
            "duration_seconds": 0.0,
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
        description="Transcribe audio to MIDI using Omnizart"
    )
    parser.add_argument("input", help="Input audio file path")
    parser.add_argument("output", help="Output MIDI file path")
    parser.add_argument(
        "--mode",
        choices=["music", "drum", "vocal"],
        default="music",
        help="Transcription mode (default: music)",
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
    result = transcribe(args.input, args.output, args.mode)

    # Output result as JSON
    print(json.dumps(result))

    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

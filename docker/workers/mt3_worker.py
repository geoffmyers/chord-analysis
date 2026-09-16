#!/usr/bin/env python3
"""
MT3 (Music Transcription with Transformers) transcription worker.

This script runs inside a Docker container and handles audio-to-MIDI
transcription using Google Magenta's MT3 transformer model.

Usage:
    python mt3_worker.py <input_audio> <output_midi> [--model mt3|ismir2021]

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
import os
import sys
from pathlib import Path


def transcribe(audio_path: str, output_path: str, model: str = "mt3") -> dict:
    """
    Transcribe audio to MIDI using MT3.

    Args:
        audio_path: Path to input audio file
        output_path: Path for output MIDI file
        model: Model variant ('mt3' for multi-instrument, 'ismir2021' for piano)

    Returns:
        Dict with transcription results
    """
    try:
        import functools

        import librosa
        import note_seq
        import numpy as np
        import pretty_midi
        import t5
        import t5x
        from mt3 import inference_model, preprocessors, vocabularies

        # Load checkpoint
        checkpoint_path = os.environ.get(
            "MT3_CHECKPOINT_PATH",
            f"/app/checkpoints/{model}"
        )

        if not Path(checkpoint_path).exists():
            raise FileNotFoundError(
                f"MT3 checkpoint not found at {checkpoint_path}. "
                "Run `gsutil -m cp -r gs://mt3/checkpoints/{model} /app/checkpoints/`"
            )

        # Load model
        model_instance = inference_model.InferenceModel(
            checkpoint_path,
            vocabularies.build_codec(
                vocabularies.DEFAULT_NUM_VELOCITY_BINS
            )
        )

        # Load and preprocess audio
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)

        # Transcribe
        est_ns = model_instance(audio)

        # Save as MIDI
        note_seq.sequence_proto_to_midi_file(est_ns, output_path)

        # Get statistics
        note_count = len(est_ns.notes)
        duration = est_ns.total_time if est_ns.notes else 0.0

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
        description="Transcribe audio to MIDI using MT3"
    )
    parser.add_argument("input", help="Input audio file path")
    parser.add_argument("output", help="Output MIDI file path")
    parser.add_argument(
        "--model",
        choices=["mt3", "ismir2021"],
        default="mt3",
        help="Model variant (default: mt3 for multi-instrument)",
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
    result = transcribe(args.input, args.output, args.model)

    # Output result as JSON
    print(json.dumps(result))

    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

# Architecture

A Python package (`chord_analyzer/`) with a CLI, a Streamlit UI and an optional
set of Docker transcription backends.

## Layout

| Path | What lives there |
|---|---|
| `chord_analyzer/extractor.py` | Top-level pipeline: walk a library, analyse each file, store results. |
| `chord_analyzer/pitch_detector.py`, `key_detection.py`, `tempo.py` | Signal analysis — pitch, key and tempo estimation. |
| `chord_analyzer/midi_transcriber.py` | Audio → MIDI transcription. |
| `chord_analyzer/progression_parser.py`, `compatibility.py`, `pitch_compatibility.py` | Turning detected pitches into progressions, and scoring how well two samples fit together. |
| `chord_analyzer/filename_parser.py` | Recovers key/BPM hints that producers encode in filenames. |
| `chord_analyzer/database.py`, `models.py` | SQLite persistence and the shared data model. |
| `chord_analyzer/cli.py`, `__main__.py` | Command-line entry point. |
| `docker/` | Optional heavyweight transcription backends (Magenta, MT3, Omnizart), each pinned in its own image. |

## Notes

- Analysis is expensive, so results are cached in SQLite and keyed by file.
- The Docker backends are **optional** — the core package runs without them,
  using librosa-based detection.
- `rebuild_database.py` takes `--audio-dir` (or `$SPLICE_AUDIO_DIR`); the
  library location is an argument, never a literal.
- The Streamlit UI paginates the sample browser (`database.get_samples_page`)
  rather than loading every row, and never embeds audio as base64 in the
  page. An earlier build did both, which pushed browser memory into the
  gigabytes on a large library — keep new UI code on the paginated,
  file-served path.

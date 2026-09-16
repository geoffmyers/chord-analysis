# CLAUDE.md - Chord Analysis Development Guide

This document provides context and guidelines for AI-assisted development on the chord analysis project.

## Project Overview

**Purpose**: Analyze chord progressions in audio samples and find harmonically compatible samples for music production workflows.

**Target User**: Music producers who work with sample packs and want to find samples that will sound good together.

**Key Insight**: Two samples are "compatible" if they can be used together in a production, which means:
1. They share common chords or notes
2. They have similar harmonic progressions (even in different keys - can be transposed)
3. They have similar rhythmic patterns (tempo can be adjusted)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI (cli.py)                           │
│   analyze | find | info | stats | compare | check           │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    Core Modules                              │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│ extractor   │ database    │ compat-     │ tempo            │
│ .py         │ .py         │ ibility.py  │ .py              │
│             │             │             │                  │
│ CSV parsing │ SQLite ops  │ Scoring     │ BPM detection    │
│ Chord       │ Sample CRUD │ engine      │ Beat grid        │
│ extraction  │ Caching     │ Multi-      │ Quantization     │
│             │             │ factor      │                  │
└─────────────┴─────────────┴─────────────┴──────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Foundation Layer                           │
├──────────────────────────┬──────────────────────────────────┤
│ models.py                │ theory.py                        │
│                          │                                  │
│ ChordEvent               │ Note/chord parsing               │
│ Sample                   │ Semitone math                    │
│ CompatibilityResult      │ Roman numerals                   │
│                          │ Transposition detection          │
└──────────────────────────┴──────────────────────────────────┘
```

## Module Responsibilities

### models.py
- **ChordEvent**: Single chord occurrence with timing (absolute and beat-relative)
- **Sample**: Audio sample with all chord data, tempo, time signature
- **CompatibilityResult**: Score breakdown between two samples

### theory.py
- Note/chord parsing (`C:maj` -> root="C", type="maj")
- Semitone calculations and chord intervals
- Roman numeral conversion for key-agnostic analysis
- Transposition detection and functional similarity

### extractor.py
- Parse Chordino CSV output
- Create Sample objects from CSV files
- Apply beat grids to chords
- Integration with tempo detection

### database.py
- SQLite schema and operations
- Sample storage with JSON-serialized chord data
- Compatibility score caching

### compatibility.py
- Multi-factor scoring engine
- Functional match (key-agnostic)
- Shared chords, note overlap, harmonic relations
- Mood matching and clash detection
- Rhythm pattern comparison

### tempo.py
- BPM detection via librosa
- Beat grid creation and manipulation
- Chord quantization to beat positions
- Fallback tempo estimation from chord timing

### cli.py
- argparse-based CLI
- Commands: analyze, find, info, stats, compare, check
- Rich table output (optional)

### filename_parser.py
- Regex-based key/tempo extraction from filenames
- Supports common sample pack naming conventions
- Priority: Filename > librosa > chord timing estimation
- Patterns: `Cmaj`, `Am`, `F#m`, `120bpm`, `120BPM`

## Key Data Structures

### FilenameInfo
```python
@dataclass
class FilenameInfo:
    key: Optional[str]          # "C major", "A minor"
    key_root: Optional[str]     # "C", "A"
    key_quality: Optional[str]  # "major" or "minor"
    bpm: Optional[float]        # 120.0

    @property
    def has_key(self) -> bool

    @property
    def has_bpm(self) -> bool
```

### ChordEvent
```python
@dataclass
class ChordEvent:
    start_time: float          # Absolute time in seconds
    end_time: float
    chord_label: str           # "C:maj", "A:min7", etc.
    root_note: str             # "C", "A", etc.
    chord_type: str            # "maj", "min7", etc.
    # Beat-relative (optional)
    bar: Optional[int]         # 1-indexed
    beat: Optional[float]      # 1-indexed, can be fractional
    duration_beats: Optional[float]
```

### Sample
```python
@dataclass
class Sample:
    filepath: str
    filename: str
    chords: List[ChordEvent]
    id: Optional[int]
    duration_seconds: float
    estimated_key: Optional[str]
    estimated_bpm: Optional[float]
    time_signature: Tuple[int, int]  # (4, 4)
    first_beat_offset: float
```

### Compatibility Result
```python
{
    "overall": 85.5,           # 0-100 score
    "components": {
        "functional_match": 35.0,
        "shared_chords": 20.0,
        "note_overlap": 12.5,
        "harmonic_relations": 10.0,
        "mood_match": 13.0,
        "clash_penalty": -5.0,
    },
    "reasons": ["Exact transposition (perfect 5th)", "Similar major tonality"],
    "is_transposition": True,
    "transposition_interval": 7,
    "transposition_note": "G",
}
```

## Scoring Algorithm

### Current Weights (Total: 100 max)

| Component | Max | Weight Rationale |
|-----------|-----|------------------|
| functional_match | 35 | Most important - key-agnostic patterns |
| shared_chords | 20 | Direct matches in same key |
| note_overlap | 15 | Scale compatibility |
| harmonic_relations | 15 | Circle of fifths proximity |
| mood_match | 15 | Major/minor balance |
| rhythm_match | 15 | Beat patterns (when available) |
| clash_penalty | -15 | Semitone conflicts |

### Functional Match Logic
1. Check if progressions are exact transpositions (35 pts)
2. Calculate interval pattern similarity
3. Compare chord quality sequences
4. Use weighted combination for partial matches

### Transposition Detection
```python
# Normalize to intervals from first chord
prog_a = ["C:maj", "F:maj", "G:maj"]  # -> [0, 5, 7] semitones
prog_b = ["G:maj", "C:maj", "D:maj"]  # -> [0, 5, 7] semitones
# Same pattern = transposition
```

## Development Guidelines

### Code Style
- Python 3.9+ with type hints
- Dataclasses for data models
- Clear docstrings with Args/Returns
- pytest for testing

### Adding New Features

#### New Scoring Factor
1. Add function in `compatibility.py`: `_score_new_factor() -> tuple[float, List[str]]`
2. Call from `calculate_compatibility()`
3. Add to `components` dict
4. Add tests in `test_compatibility.py`
5. Consider weight impact on total score

#### New CLI Command
1. Add parser in `cli.py`: `subparsers.add_parser("cmd_name", ...)`
2. Implement handler: `cmd_new_command(args) -> int`
3. Add to handlers dict
4. Update README.md

#### New Model Field
1. Add field to dataclass in `models.py`
2. Update `to_dict()` and `from_dict()` methods
3. Update database schema in `database.py`
4. Update `_row_to_sample()` to handle backwards compatibility

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/test_tempo.py -v
pytest tests/test_filename_parser.py -v

# With coverage
pytest tests/ --cov=chord_analyzer --cov-report=html
```

### Test Coverage Goals
- theory.py: >90% (core music logic)
- compatibility.py: >85% (scoring engine)
- tempo.py: >80% (optional feature)
- filename_parser.py: >85% (filename parsing)
- database.py: >75% (CRUD operations)

## External Dependencies

### Required
- **SQLite3**: Built into Python, used for sample database

### Optional
- **Sonic Annotator + Chordino**: For chord extraction from audio
- **librosa**: For tempo/beat detection
- **Rich**: For pretty CLI output

### Checking Availability
```python
from chord_analyzer.tempo import check_librosa_available
from chord_analyzer.extractor import check_sonic_annotator, check_chordino_plugin

if check_librosa_available():
    # Can use tempo detection
if check_sonic_annotator() and check_chordino_plugin():
    # Can extract chords from audio
```

## Database Schema

```sql
CREATE TABLE samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT,
    chords_json TEXT,           -- JSON array of ChordEvent dicts
    progression_json TEXT,      -- JSON array of chord labels
    root_notes_json TEXT,       -- JSON array of unique roots
    chord_types_json TEXT,      -- JSON array of unique types
    duration_seconds REAL,
    estimated_key TEXT,
    estimated_bpm REAL,
    time_signature TEXT,        -- "4/4", "3/4", etc.
    first_beat_offset REAL,
    created_at TIMESTAMP,
    analyzed_at TIMESTAMP
);

CREATE TABLE compatibility_cache (
    sample_a_id INTEGER NOT NULL,
    sample_b_id INTEGER NOT NULL,
    score REAL NOT NULL,
    components_json TEXT,
    reasons_json TEXT,
    calculated_at TIMESTAMP,
    PRIMARY KEY (sample_a_id, sample_b_id)
);
```

## Common Tasks

### Process New Samples
```bash
# Extract chords from audio
python -m chord_analyzer analyze \
    --audio-dir /path/to/samples \
    --csv-dir ./chord_data \
    --db samples.db \
    --extract \
    --detect-tempo
```

### Find Compatible Samples
```bash
# Basic search (key-normalized)
python -m chord_analyzer find \
    --target "./chord_data/my_sample.csv" \
    --db samples.db \
    --min-score 70 \
    --explain

# With rhythm pattern comparison (requires tempo data)
python -m chord_analyzer find \
    --target "./chord_data/my_sample.csv" \
    --db samples.db \
    --min-score 70 \
    --use-rhythm \
    --explain
```

### Debug Compatibility Score
```python
from chord_analyzer import calculate_compatibility, calculate_compatibility_with_rhythm

prog_a = ["C:maj", "A:min", "F:maj", "G:maj"]
prog_b = ["G:maj", "E:min", "C:maj", "D:maj"]

# String-based comparison (key-normalized)
result = calculate_compatibility(prog_a, prog_b)
print(f"Score: {result['overall']}")
print(f"Components: {result['components']}")
print(f"Reasons: {result['reasons']}")
print(f"Is transposition: {result['is_transposition']}")

# With rhythm comparison (requires ChordEvent objects with beat info)
# result = calculate_compatibility_with_rhythm(sample_a.chords, sample_b.chords)
```

## Known Limitations

1. **Chord Detection Accuracy**: Depends on Chordino, which can struggle with complex harmonies
2. **Tempo Detection**: librosa may have trouble with non-4/4 time or tempo changes
3. **Key Estimation**: Simple heuristic, not robust for modal or atonal music
4. **Rhythm Comparison**: Requires tempo data; falls back gracefully when unavailable

## Future Development Ideas

> **GitHub Issue:** [#226 — Chord Analysis: feature roadmap](https://github.com/geoffmyers/chord-analysis/issues)

### High Priority
- [x] Web UI for visual sample browsing — shipped (Streamlit, `chord_analyzer/web_app.py`)
- [ ] Bulk operations CLI improvements
- [ ] Improved key detection algorithm

### Medium Priority
- [ ] DAW plugin integration (VST/AU)
- [ ] Audio preview in CLI
- [ ] Export to MIDI

### Low Priority / Research
- [ ] ML-based chord detection (replace Chordino)
- [ ] Embedding-based similarity (train on large sample library)
- [ ] Cloud sync for sample libraries

## Troubleshooting

### "librosa not available"
```bash
pip install librosa
# May also need:
# macOS: brew install libsndfile
# Linux: apt-get install libsndfile1
```

### "Sonic Annotator not found"
```bash
# macOS
brew install sonic-annotator

# Linux
sudo apt-get install sonic-annotator
```

### Database Migration
If schema changes, simplest approach is to rebuild:
```bash
rm samples.db
python -m chord_analyzer analyze --csv-dir ./chord_data --db samples.db
```

## Gotchas

- This is a git subtree published as a **one-commit orphan snapshot**. Its public
  history shares no ancestry with anything this repo can split, so a subtree push
  can never fast-forward. Publish with:
  `scripts/publish-subtree-snapshot.sh --prefix=music/chord-analysis --publish`
- **NEVER run `git subtree push` or `git subtree split`.** A raw split has twice
  pushed the entire mono-repo history — and the secrets in it — to a public remote
  (see `docs/security/2026-02-04-` and `2026-05-12-credential-leak-audit.md`). A
  pre-push hook now refuses it.

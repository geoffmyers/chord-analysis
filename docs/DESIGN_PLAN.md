# Chord Analysis & Sample Compatibility Matcher

## Design Plan

A Python-based tool for analyzing chord progressions in audio samples and finding harmonically compatible samples for music production workflows.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Goals & Requirements](#goals--requirements)
3. [System Architecture](#system-architecture)
4. [Implementation Phases](#implementation-phases)
5. [Technical Specifications](#technical-specifications)
6. [Data Models](#data-models)
7. [Algorithm Design](#algorithm-design)
8. [CLI Interface](#cli-interface)
9. [Future Enhancements](#future-enhancements)
10. [Dependencies & Setup](#dependencies--setup)

---

## Project Overview

### Problem Statement

When producing music, finding samples that work harmonically together is time-consuming. Producers often have large sample libraries but lack tools to quickly identify which loops, one-shots, and stems will blend well based on their harmonic content.

### Solution

Build an automated system that:
1. Extracts chord progressions from audio files using machine learning
2. Stores harmonic metadata in a searchable database
3. Calculates compatibility scores between samples based on music theory
4. Provides a CLI (and eventually web UI) for querying compatible samples

### Target Users

- Music producers with large sample libraries
- DJs looking for harmonically compatible tracks
- Sound designers organizing sample collections

---

## Goals & Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Extract chord progressions from WAV/MP3/FLAC files | High |
| FR-2 | Store chord data with timestamps in a database | High |
| FR-3 | Calculate harmonic compatibility scores between samples | High |
| FR-4 | Query for compatible samples given a target sample | High |
| FR-5 | Batch process entire sample library directories | High |
| FR-6 | Support common audio formats (WAV, MP3, FLAC, AIFF) | Medium |
| FR-7 | Export compatibility reports | Low |
| FR-8 | Web-based UI for browsing matches | Low |

### Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Process 1000 samples in under 30 minutes | Performance |
| NFR-2 | Database size under 1MB per 1000 samples | Storage |
| NFR-3 | Compatibility query response under 500ms | Performance |
| NFR-4 | Run on macOS and Linux | Compatibility |

---

## System Architecture

### High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHORD ANALYSIS PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────────┐    ┌──────────────┐    ┌─────────────┐
│              │    │                  │    │              │    │             │
│ Audio Files  │───▶│ Chord Extraction │───▶│  CSV Output  │───▶│  Database   │
│ (WAV/MP3)    │    │ (Sonic Annotator │    │ (Timestamped │    │  (SQLite)   │
│              │    │  + Chordino)     │    │   Chords)    │    │             │
└──────────────┘    └──────────────────┘    └──────────────┘    └─────────────┘
                                                                       │
                                                                       ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐    ┌─────────────┐
│              │    │                  │    │              │    │             │
│   Results    │◀───│  Query Interface │◀───│ Compatibility│◀───│   Sample    │
│  (Ranked     │    │     (CLI)        │    │    Engine    │    │   Metadata  │
│   Matches)   │    │                  │    │              │    │             │
└──────────────┘    └──────────────────┘    └──────────────┘    └─────────────┘
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Application Layer                              │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │   CLI App   │  │   Web UI        │  │   Python API                    │  │
│  │  (argparse) │  │   (Flask/       │  │   (Library functions)           │  │
│  │             │  │    Streamlit)   │  │                                 │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Service Layer                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │  ChordExtractor     │  │  CompatibilityEngine│  │  SampleRepository   │  │
│  │  - extract()        │  │  - calculate_score()│  │  - find_compatible()│  │
│  │  - parse_csv()      │  │  - rank_matches()   │  │  - get_by_id()      │  │
│  │  - get_progression()│  │  - explain_score()  │  │  - search()         │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Layer                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         SQLite Database                              │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐    │    │
│  │  │    samples    │  │    chords     │  │   compatibility_cache │    │    │
│  │  └───────────────┘  └───────────────┘  └───────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           External Dependencies                             │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────────┐   │
│  │   Sonic Annotator   │  │           Chordino VAMP Plugin              │   │
│  │   (CLI tool)        │  │           (nnls-chroma)                     │   │
│  └─────────────────────┘  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

> Tracked upstream in the mono repo this project is developed in.

### Phase 1: Core Infrastructure (MVP)

**Objective:** Build the foundational chord extraction and database storage.

#### Tasks

- [ ] Set up project structure and virtual environment
- [ ] Install and configure Sonic Annotator + Chordino
- [ ] Implement chord CSV parser
- [ ] Design and create SQLite database schema
- [ ] Implement batch audio processing script
- [ ] Write unit tests for core parsing functions

#### Deliverables

- Working chord extraction pipeline
- Database with sample metadata
- Basic CLI for processing files

---

### Phase 2: Compatibility Engine

**Objective:** Implement the harmonic analysis and scoring algorithms.

#### Tasks

- [ ] Implement music theory utilities (intervals, chord parsing)
- [ ] Build compatibility scoring algorithm
- [ ] Add multiple scoring factors (shared chords, note overlap, etc.)
- [ ] Implement clash detection
- [ ] Create ranking and filtering system
- [ ] Write comprehensive tests for scoring accuracy

#### Deliverables

- Compatibility calculation engine
- Scored and ranked match results
- Explanation text for why samples match

---

### Phase 3: CLI Interface

**Objective:** Create a user-friendly command-line interface.

#### Tasks

- [ ] Design CLI command structure
- [ ] Implement `analyze` command for batch processing
- [ ] Implement `find` command for compatibility queries
- [ ] Add `info` command to inspect single samples
- [ ] Add progress bars and colored output
- [ ] Write CLI usage documentation

#### Deliverables

- Full-featured CLI application
- Help documentation
- Example usage scripts

---

### Phase 4: Enhancements

**Objective:** Add advanced features and optimizations.

#### Tasks

- [ ] Add key detection (global key estimation)
- [ ] Implement tempo/BPM extraction
- [ ] Add functional harmony pattern detection
- [ ] Create compatibility caching for performance
- [ ] Add export functionality (JSON, CSV reports)
- [ ] Build optional web UI with Streamlit

#### Deliverables

- Enhanced analysis features
- Performance optimizations
- Web-based interface (optional)

---

## Technical Specifications

### Chord Extraction

#### Tool: Sonic Annotator + Chordino

Sonic Annotator is a command-line batch processor for audio analysis using VAMP plugins. Chordino is a VAMP plugin specifically designed for chord recognition.

**Installation (macOS):**

```bash
# Install Sonic Annotator via Homebrew
brew install sonic-annotator

# Download Chordino plugin from:
# https://code.soundsoftware.ac.uk/projects/nnls-chroma/files

# Install plugin to VAMP path
mkdir -p ~/Library/Audio/Plug-Ins/Vamp/
cp nnls-chroma.dylib ~/Library/Audio/Plug-Ins/Vamp/
```

**Installation (Linux):**

```bash
# Ubuntu/Debian
sudo apt-get install sonic-annotator

# Download and install Chordino
mkdir -p ~/.vamp
# Copy nnls-chroma.so to ~/.vamp/
```

**Transform File (chordino.n3):**

```bash
# Generate default transform configuration
sonic-annotator -s vamp:nnls-chroma:chordino:simplechord > chordino.n3
```

**Batch Processing:**

```bash
# Process all audio files in a directory
sonic-annotator -t chordino.n3 \
    /path/to/samples/*.wav \
    -w csv \
    --csv-basedir /path/to/output/
```

#### Output Format

Chordino produces CSV files with the following structure:

```csv
0.000000,0.500000,N
0.500000,2.000000,C:maj
2.000000,3.500000,A:min
3.500000,4.000000,F:maj
4.000000,5.500000,G:7
```

| Column | Description |
|--------|-------------|
| 1 | Start time (seconds) |
| 2 | End time (seconds) |
| 3 | Chord label (root:quality or "N" for no chord) |

#### Chord Notation

| Notation | Meaning |
|----------|---------|
| `C:maj` | C major |
| `A:min` | A minor |
| `G:7` | G dominant 7th |
| `D:maj7` | D major 7th |
| `E:min7` | E minor 7th |
| `B:dim` | B diminished |
| `F:aug` | F augmented |
| `N` | No chord / silence |

---

### Database Schema

#### SQLite Tables

```sql
-- Main samples table
CREATE TABLE samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT,
    file_hash TEXT,
    duration_seconds REAL,
    sample_rate INTEGER,
    channels INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzed_at TIMESTAMP
);

-- Chord events with timing
CREATE TABLE chord_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    chord_label TEXT NOT NULL,
    root_note TEXT,
    chord_type TEXT,
    duration REAL,
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
);

-- Derived analysis data (for fast queries)
CREATE TABLE sample_analysis (
    sample_id INTEGER PRIMARY KEY,
    progression_json TEXT,
    unique_chords_json TEXT,
    root_notes_json TEXT,
    chord_types_json TEXT,
    estimated_key TEXT,
    estimated_bpm REAL,
    major_minor_ratio REAL,
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
);

-- Compatibility cache (optional, for performance)
CREATE TABLE compatibility_cache (
    sample_a_id INTEGER NOT NULL,
    sample_b_id INTEGER NOT NULL,
    score REAL NOT NULL,
    components_json TEXT,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sample_a_id, sample_b_id),
    FOREIGN KEY (sample_a_id) REFERENCES samples(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_b_id) REFERENCES samples(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_chord_events_sample ON chord_events(sample_id);
CREATE INDEX idx_sample_analysis_key ON sample_analysis(estimated_key);
CREATE INDEX idx_compatibility_score ON compatibility_cache(score DESC);
```

---

## Data Models

### Python Classes

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class ChordEvent:
    """Single chord occurrence with timing."""
    start_time: float
    end_time: float
    chord_label: str
    root_note: str
    chord_type: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

@dataclass
class Sample:
    """Audio sample with chord analysis."""
    id: Optional[int]
    filepath: str
    filename: str
    duration_seconds: float
    chords: List[ChordEvent]
    progression: List[str]
    unique_chords: set
    root_notes: set
    chord_types: set
    estimated_key: Optional[str] = None
    estimated_bpm: Optional[float] = None

@dataclass
class CompatibilityResult:
    """Result of compatibility calculation."""
    sample: Sample
    overall_score: float
    shared_chords_score: float
    note_overlap_score: float
    clash_penalty: float
    harmonic_relations_score: float
    mood_match_score: float
    reasons: List[str]
```

---

## Algorithm Design

### Compatibility Scoring

The compatibility engine uses multiple weighted factors to calculate an overall score (0-100):

| Factor | Weight | Description |
|--------|--------|-------------|
| Shared Chords | 30 pts | Exact chord matches between progressions |
| Note Overlap | 25 pts | Common notes suggest compatible scales |
| Harmonic Relations | 25 pts | Circle of fifths relationships |
| Mood Match | 20 pts | Major/minor balance similarity |
| Clash Penalty | -15 pts | Semitone conflicts between notes |

#### Shared Chords Score

```python
def score_shared_chords(prog_a: List[str], prog_b: List[str]) -> float:
    """Score based on exact chord matches."""
    set_a, set_b = set(prog_a), set(prog_b)
    shared = set_a & set_b
    ratio = len(shared) / max(len(set_a), len(set_b))
    return ratio * 30  # Max 30 points
```

#### Note Overlap Score

```python
def score_note_overlap(notes_a: set, notes_b: set) -> float:
    """Score based on shared scale notes."""
    if not notes_a or not notes_b:
        return 0
    overlap = len(notes_a & notes_b) / len(notes_a | notes_b)
    return overlap * 25  # Max 25 points
```

#### Harmonic Relations Score

Strong harmonic relationships based on interval theory:

| Interval | Relationship | Points |
|----------|--------------|--------|
| Unison (0) | Same root | +2 |
| Perfect 4th (5) | Strong relation | +2 |
| Perfect 5th (7) | Dominant/subdominant | +2 |
| Minor 3rd (3) | Relative minor | +1 |
| Major 3rd (4) | Relative major | +1 |
| Minor 6th (8) | Relative key | +1 |
| Major 6th (9) | Relative key | +1 |

#### Clash Detection

Penalize potential dissonance from semitone conflicts:

```python
def calculate_clash_penalty(notes_a: set, notes_b: set) -> float:
    """Penalize semitone clashes between note sets."""
    clash_count = 0
    for note in notes_a:
        if (note + 1) % 12 in notes_b or (note - 1) % 12 in notes_b:
            clash_count += 1
    return min(clash_count * 5, 15)  # Max -15 points
```

### Music Theory Constants

```python
# Chromatic note to semitone mapping
NOTE_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
    'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

# Chord quality intervals (semitones from root)
CHORD_INTERVALS = {
    'maj':  [0, 4, 7],          # Major triad
    'min':  [0, 3, 7],          # Minor triad
    '7':    [0, 4, 7, 10],      # Dominant 7th
    'maj7': [0, 4, 7, 11],      # Major 7th
    'min7': [0, 3, 7, 10],      # Minor 7th
    'dim':  [0, 3, 6],          # Diminished
    'dim7': [0, 3, 6, 9],       # Diminished 7th
    'aug':  [0, 4, 8],          # Augmented
    'sus2': [0, 2, 7],          # Suspended 2nd
    'sus4': [0, 5, 7],          # Suspended 4th
    '9':    [0, 4, 7, 10, 14],  # Dominant 9th
    'add9': [0, 4, 7, 14],      # Add 9
}
```

---

## CLI Interface

### Command Structure

```
chord-analyzer <command> [options]

Commands:
  analyze     Analyze audio files and build database
  find        Find compatible samples
  info        Show analysis info for a sample
  stats       Display database statistics
  export      Export compatibility data

Global Options:
  --db PATH        Database file path (default: samples.db)
  --verbose, -v    Verbose output
  --help, -h       Show help
```

### Command Details

#### `analyze` - Batch Analysis

```bash
chord-analyzer analyze \
    --audio-dir ~/Music/Samples \
    --csv-dir ./chord_data \
    --db samples.db \
    --recursive \
    --formats wav,mp3,flac
```

| Option | Description |
|--------|-------------|
| `--audio-dir` | Directory containing audio files |
| `--csv-dir` | Output directory for chord CSVs |
| `--recursive` | Process subdirectories |
| `--formats` | Audio formats to process |
| `--force` | Re-analyze existing samples |

#### `find` - Compatibility Search

```bash
chord-analyzer find \
    --target "funky_bass_loop.wav" \
    --min-score 60 \
    --limit 20 \
    --explain
```

| Option | Description |
|--------|-------------|
| `--target` | Target sample filepath |
| `--min-score` | Minimum compatibility score (0-100) |
| `--limit` | Maximum results to return |
| `--explain` | Show detailed score breakdown |
| `--key` | Filter by estimated key |

#### `info` - Sample Details

```bash
chord-analyzer info "funky_bass_loop.wav"
```

Output:
```
Sample: funky_bass_loop.wav
Duration: 4.2 seconds
Estimated Key: C major
BPM: 120

Chord Progression:
  0.0s - 1.0s: C:maj
  1.0s - 2.0s: A:min
  2.0s - 3.0s: F:maj
  3.0s - 4.0s: G:7

Unique Chords: C:maj, A:min, F:maj, G:7
Root Notes: C, A, F, G
Chord Types: maj, min, 7
```

---

## Future Enhancements

### 1. Advanced Chord Detection

Replace Chordino with more accurate ML models:

| Model | Accuracy | Speed | Notes |
|-------|----------|-------|-------|
| Chordino | ~70% | Fast | Current solution |
| BTC (Transformer) | ~85% | Medium | Better accuracy |
| Omnizart | ~80% | Slow | Multi-task model |

### 2. Key Estimation

Add global key detection to improve compatibility matching:

```python
def estimate_key(chords: List[ChordEvent]) -> str:
    """Estimate global key from chord progression."""
    # Use Krumhansl-Schmuckler key-finding algorithm
    # Weight by chord duration
    pass
```

### 3. Tempo-Aware Matching

Factor BPM into compatibility:

```python
def tempo_compatibility(bpm_a: float, bpm_b: float) -> float:
    """Score tempo compatibility (including half/double time)."""
    ratio = bpm_a / bpm_b
    # Perfect match, half-time, or double-time
    if ratio in [1.0, 0.5, 2.0]:
        return 1.0
    # Close tempo
    if 0.95 <= ratio <= 1.05:
        return 0.8
    return 0.5
```

### 4. Functional Harmony Detection

Recognize common progressions:

| Pattern | Numerals | Example in C |
|---------|----------|--------------|
| ii-V-I | ii-V-I | Dm-G-C |
| I-IV-V | I-IV-V | C-F-G |
| I-V-vi-IV | I-V-vi-IV | C-G-Am-F |
| i-iv-v | i-iv-v | Am-Dm-Em |

### 5. Web UI

Build a Streamlit or Flask interface:

```python
# streamlit_app.py
import streamlit as st

st.title("Sample Compatibility Finder")

uploaded_file = st.file_uploader("Upload a sample")
if uploaded_file:
    # Analyze and find matches
    matches = find_compatible_samples(uploaded_file)

    for match in matches:
        st.write(f"**{match.filename}** - Score: {match.score}")
        st.audio(match.filepath)
```

---

## Dependencies & Setup

### Requirements

**System Dependencies:**

```bash
# macOS
brew install sonic-annotator ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install sonic-annotator ffmpeg
```

**Python Dependencies (requirements.txt):**

```
# Core
sqlite3  # Built-in
pathlib  # Built-in

# CLI
argparse  # Built-in
rich>=13.0.0  # Pretty terminal output

# Audio (optional, for format conversion)
pydub>=0.25.0
ffmpeg-python>=0.2.0

# Web UI (optional)
streamlit>=1.28.0
flask>=3.0.0

# Testing
pytest>=7.0.0
pytest-cov>=4.0.0
```

### Project Structure

```
chord-analysis/
├── DESIGN_PLAN.md           # This document
├── README.md                # User documentation
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
├── chordino.n3             # Sonic Annotator transform file
│
├── chord_analyzer/          # Main package
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── extractor.py        # Chord extraction
│   ├── compatibility.py    # Scoring engine
│   ├── database.py         # Database operations
│   ├── models.py           # Data classes
│   └── theory.py           # Music theory utils
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_extractor.py
│   ├── test_compatibility.py
│   └── test_database.py
│
├── data/                    # Sample data
│   └── test_samples/
│
└── output/                  # Generated files
    ├── chord_data/         # CSV outputs
    └── samples.db          # SQLite database
```

### Quick Start

```bash
# 1. Clone and setup
cd chord-analysis
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Install Sonic Annotator and Chordino
brew install sonic-annotator
# Download Chordino from https://code.soundsoftware.ac.uk/projects/nnls-chroma/files

# 3. Generate transform file
sonic-annotator -s vamp:nnls-chroma:chordino:simplechord > chordino.n3

# 4. Analyze samples
sonic-annotator -t chordino.n3 ~/Music/Samples/*.wav -w csv --csv-basedir ./output/chord_data/

# 5. Build database
python -m chord_analyzer analyze \
    --audio-dir ~/Music/Samples \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db

# 6. Find compatible samples
python -m chord_analyzer find \
    --target "./output/chord_data/funky_bass_loop.csv" \
    --min-score 60
```

---

## Appendix A: Full Implementation Reference

### A.1 Chord CSV Parser

```python
import csv
from typing import List
from models import ChordEvent

def parse_chord_csv(csv_path: str) -> List[ChordEvent]:
    """Parse Sonic Annotator chord output into structured data."""
    chords = []
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                start = float(row[0])
                end = float(row[1]) if row[1] else start + 0.5
                chord = row[2] if len(row) > 2 else row[1]

                if chord and chord != 'N':  # Skip silence/no-chord
                    root, chord_type = parse_chord_label(chord)
                    chords.append(ChordEvent(
                        start_time=start,
                        end_time=end,
                        chord_label=chord,
                        root_note=root,
                        chord_type=chord_type
                    ))
    return chords

def parse_chord_label(chord_str: str) -> tuple:
    """Parse chord string into root note and type."""
    if ':' in chord_str:
        root, chord_type = chord_str.split(':', 1)
    else:
        root = chord_str
        chord_type = 'maj'
    return root, chord_type
```

### A.2 Compatibility Engine

```python
from collections import Counter
from typing import List, Dict

NOTE_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
    'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

CHORD_INTERVALS = {
    'maj': [0, 4, 7],
    'min': [0, 3, 7],
    '7': [0, 4, 7, 10],
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'dim': [0, 3, 6],
    'aug': [0, 4, 8],
    'sus4': [0, 5, 7],
    'sus2': [0, 2, 7],
}

def get_chord_notes(chord_str: str) -> set:
    """Get all notes in a chord as semitone values."""
    root, chord_type = parse_chord_label(chord_str)
    if root not in NOTE_TO_SEMITONE:
        return set()

    root_semitone = NOTE_TO_SEMITONE[root]
    intervals = CHORD_INTERVALS.get(chord_type, CHORD_INTERVALS['maj'])
    return set((root_semitone + i) % 12 for i in intervals)

def calculate_compatibility(prog_a: List[str], prog_b: List[str]) -> Dict:
    """
    Calculate harmonic compatibility score between two progressions.
    Returns a dict with overall score and component scores.
    """
    if not prog_a or not prog_b:
        return {'overall': 0, 'reasons': ['Empty progression']}

    scores = {}
    reasons = []

    # 1. Shared chords (exact matches)
    set_a = set(prog_a)
    set_b = set(prog_b)
    shared = set_a & set_b
    shared_ratio = len(shared) / max(len(set_a), len(set_b))
    scores['shared_chords'] = shared_ratio * 30
    if shared:
        reasons.append(f"Shared chords: {', '.join(shared)}")

    # 2. Note overlap
    notes_a = set()
    notes_b = set()
    for chord in prog_a:
        notes_a.update(get_chord_notes(chord))
    for chord in prog_b:
        notes_b.update(get_chord_notes(chord))

    if notes_a and notes_b:
        note_overlap = len(notes_a & notes_b) / len(notes_a | notes_b)
        scores['note_overlap'] = note_overlap * 25

        # Clash penalty
        clash_count = 0
        for note in notes_a:
            if (note + 1) % 12 in notes_b or (note - 1) % 12 in notes_b:
                clash_count += 1
        scores['clash_penalty'] = -min(clash_count * 5, 15)
        if clash_count > 0:
            reasons.append(f"Potential clashes: {clash_count}")

    # 3. Root note relationships
    roots_a = [parse_chord_label(c)[0] for c in prog_a]
    roots_b = [parse_chord_label(c)[0] for c in prog_b]

    root_semitones_a = set(NOTE_TO_SEMITONE.get(r, 0) for r in roots_a)
    root_semitones_b = set(NOTE_TO_SEMITONE.get(r, 0) for r in roots_b)

    strong_relations = 0
    for ra in root_semitones_a:
        for rb in root_semitones_b:
            interval = abs(ra - rb) % 12
            if interval in [0, 5, 7]:  # Unison, P4, P5
                strong_relations += 2
            elif interval in [3, 4, 8, 9]:  # 3rds, 6ths
                strong_relations += 1

    scores['harmonic_relations'] = min(strong_relations * 3, 25)

    # 4. Mood match
    types_a = Counter(parse_chord_label(c)[1] for c in prog_a)
    types_b = Counter(parse_chord_label(c)[1] for c in prog_b)

    major_a = types_a.get('maj', 0) + types_a.get('maj7', 0)
    minor_a = types_a.get('min', 0) + types_a.get('min7', 0)
    major_b = types_b.get('maj', 0) + types_b.get('maj7', 0)
    minor_b = types_b.get('min', 0) + types_b.get('min7', 0)

    if (major_a + minor_a) > 0 and (major_b + minor_b) > 0:
        ratio_a = major_a / (major_a + minor_a)
        ratio_b = major_b / (major_b + minor_b)
        mood_similarity = 1 - abs(ratio_a - ratio_b)
        scores['mood_match'] = mood_similarity * 20

        if mood_similarity > 0.7:
            mood = "major" if ratio_a > 0.5 else "minor"
            reasons.append(f"Similar {mood} tonality")

    overall = max(0, min(100, sum(scores.values())))

    return {
        'overall': round(overall, 1),
        'components': scores,
        'reasons': reasons
    }
```

### A.3 Database Operations

```python
import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from models import Sample, ChordEvent

def init_database(db_path: str) -> sqlite3.Connection:
    """Create SQLite database for sample storage."""
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY,
            filepath TEXT UNIQUE,
            filename TEXT,
            chords_json TEXT,
            progression_json TEXT,
            root_notes_json TEXT,
            chord_types_json TEXT,
            duration_seconds REAL
        )
    ''')
    conn.commit()
    return conn

def store_sample(conn: sqlite3.Connection, sample: Sample) -> int:
    """Store a sample in the database."""
    cursor = conn.execute('''
        INSERT OR REPLACE INTO samples
        (filepath, filename, chords_json, progression_json,
         root_notes_json, chord_types_json, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        sample.filepath,
        sample.filename,
        json.dumps([{
            'start': c.start_time,
            'end': c.end_time,
            'chord': c.chord_label
        } for c in sample.chords]),
        json.dumps(sample.progression),
        json.dumps(list(sample.root_notes)),
        json.dumps(list(sample.chord_types)),
        sample.duration_seconds
    ))
    conn.commit()
    return cursor.lastrowid

def find_compatible_samples(
    db_path: str,
    target_filepath: str,
    min_score: float = 50,
    limit: int = 20
) -> List[dict]:
    """Find samples compatible with a target sample."""
    conn = sqlite3.connect(db_path)

    # Get target progression
    cursor = conn.execute(
        'SELECT progression_json FROM samples WHERE filepath = ?',
        (target_filepath,)
    )
    row = cursor.fetchone()
    if not row:
        return []

    target_progression = json.loads(row[0])

    # Compare against all other samples
    cursor = conn.execute(
        'SELECT filepath, filename, progression_json FROM samples WHERE filepath != ?',
        (target_filepath,)
    )

    results = []
    for filepath, filename, prog_json in cursor:
        progression = json.loads(prog_json)
        compatibility = calculate_compatibility(target_progression, progression)

        if compatibility['overall'] >= min_score:
            results.append({
                'filepath': filepath,
                'filename': filename,
                'progression': progression,
                'score': compatibility['overall'],
                'details': compatibility
            })

    conn.close()
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]
```

---

## Appendix B: Example Outputs

### Sample Compatibility Query

```
$ chord-analyzer find --target "funky_bass_loop.wav" --min-score 60 --explain

Top matches for: funky_bass_loop.wav
Progression: C:maj → A:min → F:maj → G:7

  85.3  soul_keys_72bpm.wav
        Progression: F:maj → C:maj → A:min → G:maj
        Shared chords: C:maj, A:min, F:maj
        Similar major tonality

  78.1  jazzy_guitar_loop.wav
        Progression: A:min → D:min → G:7 → C:maj
        Shared chords: A:min, G:7, C:maj
        Similar major tonality

  72.4  rhodes_chords_cmaj.wav
        Progression: C:maj → E:min → F:maj → G:maj
        Shared chords: C:maj, F:maj
        Strong harmonic relations

  64.2  synth_pad_aminor.wav
        Progression: A:min → F:maj → C:maj → G:maj
        Shared chords: A:min, F:maj, C:maj
        Similar major tonality

Found 4 compatible samples (score >= 60)
```

---

*Document Version: 1.0*
*Last Updated: January 2026*

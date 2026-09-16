# 🎧 AUDIO I/O & PREPROCESSING

These libraries let you load and manipulate audio files reliably in Python.

### ✅ soundfile

* Python binding for Libsndfile
* **Reads & writes WAV/FLAC/AIF/…)**
* Simple and robust
* Useful for loading samples before processing
* (Does not do analysis itself)

Install:

```bash
pip install soundfile
```

---

### ✅ pydub

* Simplifies audio file handling
* Can transcode via `ffmpeg`
* Helpful for *normalizing*, *slicing*, *resampling*, *batch handling*

Install:

```bash
pip install pydub
```

---

# 🕒 BEAT & TEMPO DETECTION

You’ll need beat grids to *align notes to bars/beats*.

### ✅ librosa

* Python audio analysis toolkit
* `librosa.beat.beat_track` gives tempo and beat frames
* Can compute chroma features

Install:

```bash
pip install librosa
```

**Pros**

* Solid beat tracking for steady loops
* Works fine for most musical audio

**Cons**

* Not as accurate on complex polyphonic content as some alternatives

---

### 📌 madmom

* Python library focused on **music signal processing**
* Excellent beat and onset detection
* Often more accurate than librosa

Install:

```bash
pip install madmom
```

**Best for:** beat/tempo detection for loops and regular music

---

# 🎼 PITCH & NOTE ESTIMATION

This is core to your project — extract *notes/pitches* from audio.

## 🟢 Monophonic / Melody Detection

These work best on monophonic or lightly polyphonic loops.

### ✅ CREPE (Deep learning pitch tracker)

* High accuracy monophonic pitch detection
* Outputs *precise frequency estimates*
* Converts easily to MIDI note numbers

Install:

```bash
pip install crepe
```

**Pros**

* Works well on monophonic content
* Good time resolution

**Cons**

* Not designed for full polyphony

---

### 🟡 aubio

* Lightweight DSP-based library
* Includes pitch detection and onset detection

Install:

```bash
pip install aubio
```

**Good for:** quick prototyping and monophonic audio

---

## 🔥 Polyphonic Transcription & Source Separation

Polyphony is hard — these tools help you parse multiple simultaneous notes.

### 🧩 Option A — Source Separation (practical MVP+)

#### Spleeter

* Deezer’s music source separation
* Splits audio into stems (vocals/drums/bass/other)
* Then run monophonic pitch detection per stem

Install & use via CLI:

```bash
pip install spleeter
```

**Pros**

* Practical workaround for polyphony
* Faster than full transcription

**Cons**

* Stem separation errors can cause noise

---

#### Demucs

* More advanced source separation model
* Often higher quality stems

Install:

```bash
pip install demucs
```

**Better for:** multi-instrument loops

---

### 🧠 Option B — Polyphonic Transcription Models

For higher-fidelity multi-note extraction:

#### Magenta Onsets and Frames

* Neural architecture specifically for music transcription
* Gives *note onset* and *frame* predictions
* Works decently on piano-like audio

Website: [https://github.com/magenta/magenta/tree/main/magenta/models/onsets\_frames](https://github.com/magenta/magenta/tree/main/magenta/models/onsets\_frames)

**Pros**

* Better than naive multipitch detection

**Cons**

* Heavy; model inference takes GPU for performance

---

#### Other Research Models

There are academic models (OpenLMD, MT3) trained for polyphonic transcription. You can integrate them if you need quality beyond Spleeter/Magenta.

---

# 🎵 CHROMA & HARMONIC ANALYSIS

These libraries help extract **pitch class features** and derive harmonic descriptors.

---

### 💠 librosa chroma

`librosa.feature.chroma_stft` / `chroma_cqt`

Turn audio into a *time-binned pitch class histogram* — good intermediate representation.

Install: same as above.

**Use for:** fast quantization of per-frame pitch energy.

---

### 🎼 music21

* Music theory library in Python
* Can compute scales, chord tones, intervals, and more
* Great for *harmonic compatibility logic*
* Works with custom scales/modes

Install:

```bash
pip install music21
```

**Pros**

* High-level API for *scale membership, chord tones, modal logic*

---

### 🎹 pretty_midi

* MIDI representation library
* Useful for generating piano-rolls and exporting
* Great for debugging & visualization

Install:

```bash
pip install pretty_midi
```

---

# 📊 UTILITIES & VISUALIZATION

### 🖼 plotly / matplotlib

* For generating piano rolls and heatmaps of harmonic compatibility

Install:

```bash
pip install matplotlib plotly
```

---

# 🐍 PYTHON FRAMEWORKS (CLI & API)

Covers the tool itself.

### 🔹 typer or click — CLI

* Build a rich CLI with commands and options

Install:

```bash
pip install click typer
```

---

### 🔹 FastAPI — Web/API

* Serve analysis results via JSON API
* Easy UI integration

Install:

```bash
pip install fastapi uvicorn
```

---

## 🔁 Optional: Batch Job Queues

For heavy workloads (polyphonic extraction, long directories):

* **Celery + Redis**
* **RQ + Redis**

---

# 📦 PACKAGING & DISTRIBUTION

* Use `poetry` or `pipenv` to manage dependencies
* Dockerize with FFmpeg support (`ffmpeg` required for audio I/O/transcoding)

---

# HOW THESE FIT YOUR SYSTEM

| Feature                        | Library                             |
| ------------------------------ | ----------------------------------- |
| Load audio / read samples      | `soundfile`, `pydub`                |
| Beat / tempo detection         | `librosa`, `madmom`                 |
| Monophonic pitch detection     | `crepe`, `aubio`                    |
| Polyphonic separation          | `spleeter`, `demucs`                |
| Polyphonic transcription       | `magenta/onsets\_frames` (optional) |
| Pitch/time quantisation        | `librosa` + custom logic            |
| Music theory (scales & chords) | `music21`                           |
| Export/visualize MIDI          | `pretty_midi`                       |
| CLI                            | `typer` / `click`                   |
| Web API                        | `FastAPI`                           |
| Visualization                  | `matplotlib`, `plotly`              |

---

# PRACTICAL INTEGRATION EXAMPLE

### Step 1 — Load audio + detect tempo

```python
import librosa

y, sr = librosa.load(file_path, sr=None)
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
```

---

### Step 2 — Extract monophonic pitches (CREPE)

```python
import crepe

time, frequency, confidence, activation = crepe.predict(y, sr, model='tiny')
```

Convert frequency → MIDI → *pitch class*

---

### Step 3 — Source separation (polyphonic)

```bash
spleeter separate -i loop.wav -p spleeter:4stems -o output_folder
```

Then analyze each stem with CREPE/aubio.

---

### Step 4 — Map pitches → harmonic score

```python
from music21 import chord, scale, pitch

# For each beat, get active chord
active_chord = chord.Chord(["C4", "E4", "G4"])
```

Check if detected pitch belongs to:

* chord tones
* diatonic scale
* neighbor tone
* dissonant intervals

---

# NOTES, TRADE-OFFS & TIPS

✅ Start with **librosa + CREPE + music21** for the MVP — simpler and effective for monophonic loops.
⚠️ Polyphony is challenging — consider *source separation first* (Spleeter/Demucs) before full transcription models.
🎹 Use **pretty_midi** to debug and export detected notes as MIDI — super helpful for visual QA.

---

## HIGH-LEVEL IMPLEMENTATION TRAJECTORY

| Phase                      | Libraries                              |
| -------------------------- | -------------------------------------- |
| MVP (monophonic)           | librosa, crepe, music21                |
| MVP+ (polyphony via stems) | spleeter/demucs + monophonic detection |
| Higher polyphonic accuracy | Magenta onsets & frames                |
| Scoring & visualization    | music21 + matplotlib/plotly            |
| CLI                        | typer/click                            |
| Web UI                     | FastAPI + React                        |

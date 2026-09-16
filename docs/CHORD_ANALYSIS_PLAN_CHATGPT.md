# Plan overview (high level)

1. **MVP (CLI)** — support: user chord progression, directory of audio loops, automatic beat/tempo detection, monophonic note extraction, beat-by-beat harmonic-compatibility scoring, JSON/CSV ranking output, simple piano-roll visualization (ASCII or optional PNG).
2. **MVP+ (CLI v2)** — add polyphonic handling via source separation and/or polyphonic transcription models; better time/beat quantization; per-sample detail reports.
3. **GUI / Web app** — server-side analysis (heavy lifting) + browser UI: upload samples, piano-roll editor, visual compatibility heatmap, interactive auditioning, filtering/sorting.
4. **Future ML/UX** — learn user preferences, train ranking models, offer auto-matching suggestions and remix tools.

---

# Data models & file formats

### 1) Chord progression (input)

Use a JSON list of chord objects. Example:

```json
[
  {
    "start_bar": 1,
    "start_beat": 1,
    "duration_bars": 2,
    "duration_beats": 0,
    "root": "C",
    "quality": "maj7",
    "time_signature": "4/4",
    "tempo": 120
  },
  {
    "start_bar": 3,
    "start_beat": 1,
    "duration_bars": 2,
    "root": "A",
    "quality": "min7"
  }
]
```

Notes:

* Normalise times to a grid of bars/beats using `tempo` & `time_signature`. Allow global tempo/time signature in a header if not per-chord.

### 2) Sample representation (after analysis)

Each sample file -> JSON:

```json
{
  "file": "loop01.wav",
  "duration_seconds": 8.0,
  "tempo": 120,
  "time_signature": "4/4",
  "detected_notes": [
    {"pitch_class": "C", "midi": 60, "start_time_s": 0.0, "end_time_s": 0.5, "start_bar": 1, "start_beat": 1},
    {"pitch_class": "E", "midi": 64, "start_time_s": 0.5, "end_time_s": 1.0, "start_bar": 1, "start_beat": 2}
  ],
  "metadata": {
    "polyphonic": false,
    "confidence": 0.92
  }
}
```

* Use pitch class (ignoring octave) for harmonic compatibility; keep `midi` for octave-sensitive features if needed.

### 3) Output ranking

CSV or JSON ranking with score and breakdown:

```json
[
  {
    "file":"loop01.wav",
    "score":0.87,
    "matched_notes": 34,
    "total_notes": 40,
    "percent_chord_tones": 0.6,
    "percent_diatonic": 0.25,
    "avg_note_weight": 0.78
  },
  ...
]
```

---

# Core pipeline (step-by-step)

### A. Preprocessing

1. **Load audio** (resample to 44.1k or 48k as desired).
2. **Normalize** amplitude (avoid clipping).
3. **Detect tempo & beat grid**:

   * Use beat tracking (e.g., `librosa.beat.beat_track`) or `madmom` for robustness.
   * If sample contains embedded tempo (e.g., loop metadata), allow user to pass it.
4. **If user-supplied tempo/time signature exists**, use it to quantize; otherwise rely on detection and allow manual override.

### B. Note / pitch extraction

**Monophonic** (easy/accurate):

* Use `CREPE` or `aubio/piptrack` for fundamental frequency detection.
* Convert frequency -> MIDI note -> pitch class.
* Detect onsets to determine note segments (onset detection: `madmom`, `librosa.onset`).

**Polyphonic** (harder — options):

* **Option 1:** Source separation first. Use `spleeter` or `demucs` to split into stems (vocal, bass, drums, other) then run monophonic detection per stem. Pros: simple to stitch; cons: not perfect.
* **Option 2:** Use a polyphonic transcription model (e.g., Onsets-and-Frames piano transcription by Magenta or the more recent research models trained on MusicNet). These models are heavier but return note events for multiple notes at once.
* **Heuristic approach:** Short-time Fourier transform + multi-pitch detection (e.g., `pYIN` variants) or `essentia`'s multi-pitch detectors — OK for modest polyphony.
* **Recommendation:** Start with Option 1 (source separation) for MVP+, add a polyphonic transcription model later if needed.

Quantize detected note start times to the beat grid (bars/beats) — compute `start_bar` and `start_beat` from `start_time_s` using tempo & time_signature.

### C. Map detected notes -> chord progression (beat-by-beat)

* For each quantized beat (or smaller unit like 8th-note), determine the **active chord** from the progression.
* For each detected note that lands inside that beat window, evaluate harmonic relationship to the active chord.

### D. Harmonic compatibility scoring (beat-by-beat)

Define scoring tiers (example weights — tunable):

* `chord_tone_weight = 1.0` (notes that are chord members: root, 3rd, 5th, 7th where applicable)
* `scale_tone_weight = 0.6` (notes in the chord’s diatonic scale/mode)
* `neighbor_weight = 0.3` (non-diatonic but common neighbor/approach tone)
* `dissonant_penalty = -0.2` for strongly dissonant pitches (e.g., augmented 4th/tritone against chord)

Algorithm (per sample):

1. For each detected note `n`:

   * Map to pitch class (C, C#, D, ...).
   * Identify active chord `c` at `n`’s time.
   * Compute `note_score`:

     * if `n` in chord tones: `note_score = chord_tone_weight`
     * else if `n` in diatonic scale of `c`: `note_score = scale_tone_weight`
     * else if `n` is chromatic neighbor (one semitone above/below a chord tone): `note_score = neighbor_weight`
     * else if interval is strongly dissonant (tritone against chord root/3rd/5th): `note_score = dissonant_penalty`
     * else `note_score = 0.0`
   * Multiply `note_score` by `note_prominence` (see below) to weight long/sustained or loud notes more.
2. **Prominence weighting**:

   * Optionally weight by note duration (longer notes more important) or amplitude (if extractable), or spectral salience (how loud/clear the harmonic).
   * e.g., `note_prominence = min(1.0, duration_seconds / 0.5)` or normalized RMS.
3. Sum note scores across the entire sample: `raw_score = Σ(note_score * prominence)`.
4. **Normalize**: divide by maximum possible (if all notes were chord tones with max prominence) to get `0..1`.

   * Or compute `score = raw_score / Σ(max_possible_per_note)` where `max_possible_per_note = chord_tone_weight * prominence`.
5. Optionally compute per-bar and per-beat compatibility profiles for visualization.

This yields a final compatibility score per sample between 0 and 1. Sort descending for output.

### E. Output

* Sorted list (JSON/CSV) with breakdown fields: total notes, percent chord tones, percent diatonic, average prominence, per-bar heatmap, processing confidence.
* Save per-sample piano-roll PNG or MIDI for manual inspection (use `pretty_midi` to synthesize detected notes into a MIDI for QA).

---

# Pseudocode (pipeline)

```python
for file in sample_dir:
    audio, sr = load_audio(file)
    tempo, beats = detect_tempo_and_beats(audio, sr)
    if sample_is_marked_monophonic:
        notes = detect_mono_notes(audio, sr)
    else:
        stems = source_separate(audio)
        notes = []
        for stem in stems:
            notes += detect_mono_notes(stem, sr)
    quantized_notes = quantize_notes_to_grid(notes, tempo, time_signature)
    score, breakdown = score_sample(quantized_notes, chord_progression)
    results.append({ "file": file, "score": score, "breakdown": breakdown })
sort results by score desc
write_results_to_json_and_csv(results)
```

---

# Libraries & tools recommendations

**Python (server & CLI)** — main stack

* `librosa` — beat/tempo detection, STFT, some pitch utilities.
* `soundfile` (pysoundfile) — audio I/O.
* `numpy`, `scipy` — numerical ops.
* `madmom` — robust onset/beat detection.
* `aubio` — pitch trackers (fast).
* `crepe` — high-accuracy monophonic pitch detection (DL-based).
* `spleeter` or `demucs` — source separation for polyphonic samples.
* `essentia` — audio analysis + multipitch detection utilities (C++/python).
* `pretty_midi` — for MIDI export & piano-roll rendering.
* `music21` — music theory utilities (scales, intervals, chord tone detection).
* `pydub` — helpful for quick file handling.
* Optional heavy polyphonic model: Magenta's Onsets-and-Frames or other transcription models.

**Frontend / GUI**

* Backend API: `FastAPI` or `Flask` to run analysis tasks and serve results.
* Frontend: `React` + `Tone.js` or `WebAudio` for playback; `react-piano-roll` or custom Canvas to render piano-rolls.
* Visualizations: `d3` / `recharts` for per-bar heatmaps.
* If heavy compute is server-side, UI only requests analysis jobs and displays results.

**Packaging / Distribution**

* Package CLI as `pip` package with console entrypoint.
* Distribute analysis-heavy parts in a Docker image (helps with FFmpeg, Spleeter dependencies).
* CI: GitHub Actions for tests and build.

---

# CLI UX & commands (example)

```
# Basic usage
$ chordmatch analyze --chords chords.json --samples ./loops --out results.json

# Options
--tempo 120                 # override tempo
--time-signature 4/4
--polyphonic auto           # auto, true, false
--stem-separation demucs    # choose spleeter | demucs
--grid-resolution 8         # quantize to 8th notes
--report formats: json,csv  # outputs
--save-midi ./midis         # save detected notes as MIDI for inspection
--threads 4
```

CLI should print progress and final top-n ranking and path to saved reports. Keep JSON detailed so GUI can reuse.

---

# GUI / Web app features (post-CLI)

* Upload chord progression or paste JSON.
* Upload / point to sample directory (or allow user uploads).
* Live job queue: submit analysis jobs; status updates.
* Visual results:

  * Sorted list with score badges.
  * Click a sample → open piano-roll aligned to chord timeline.
  * Per-beat compatibility heatmap overlay.
  * Play sample while highlighting matching notes and current chord.
  * Allow manual edits (adjust detected notes, re-score).
  * Download MIDI/Mashup suggestion (optional).
* Filters: by score threshold, percent chord tone, file length, instrument stem.
* Export options: CSV/JSON/MIDI.

Frontend tech choices: React + Next.js for SSR if needed; host analysis in FastAPI microservice.

---

# Testing & evaluation plan

### Ground-truth tests

* Use datasets with aligned MIDI/audio pairs (e.g., MAPS, MusicNet, or your own recorded loops with MIDI ground truth).
* Create synthetic loops from MIDI using clean instrument samples to measure detection accuracy.

### Unit tests

* Tempo/beat detection: test with known BPM loops.
* Note detection: compare detected notes -> ground truth MIDI.
* Scoring: deterministic tests where notes are known chord tones vs. non-tones.

### Manual QA

* Random sample of real loops; inspect piano-roll vs audio by ear.
* Gather user feedback on scoring (do top results “sound” compatible?).

### Metrics

* **Note detection accuracy** (precision/recall, onset timing tolerance).
* **Ranking quality**: use pairwise preference tests (human annotators compare two loops for compatibility).
* **Runtime / performance** on average loop directory.

---

# Performance & deployment considerations

* Large directories: batch and parallelize file processing; cache results keyed by file hash.
* Heavy models (CREPE/Magenta): optional GPU acceleration; run in Docker with CUDA for speed.
* For GUI, offload heavy tasks to backend worker queue (e.g., Celery + Redis).
* Keep precomputed results persisted (SQLite or simple JSON DB) for fast UI listing.

---

# Edge cases & limitations (be explicit)

* **Polyphonic transcription is hard.** Expect imperfect results. Use source separation as a practical workaround for many loops; allow user manual correction in GUI.
* **Tempo/Time signature mismatches.** Some loops don’t strictly match a grid; allow tolerance windows and user override of tempo.
* **Pitch ambiguity & tuning.** Samples might be tuned differently (A=440 vs 432). Add an auto-tuning detection step (estimate tuning offset via harmonic centroid and snap frequencies to nearest equal-tempered pitch).
* **Noise / non-pitched audio.** Percussive loops or heavily processed sounds may show little harmonic info; detect pitchless samples and mark confidence low.
* **File formats & codec issues.** Convert input files to WAV/AIFF for analysis using `ffmpeg` for consistency.

---

# Implementation roadmap (phased with milestones)

**Phase 0 — Scoping & prototyping (1–2 weeks)**

* Build a small prototype that:

  * Loads audio, detects tempo and beats
  * Runs CREPE or aubio on monophonic files
  * Implements simple scoring (chord tones vs diatonic)
  * Outputs JSON ranked list
* Validate with a handful of loops.

**Phase 1 — CLI MVP (2–4 weeks)**

* Full CLI with options, robust I/O, multi-threaded processing.
* Unit tests, example chords.json, sample dataset for testing.
* Export JSON/CSV and MIDI.

**Phase 2 — Polyphony & quality (4–8 weeks)**

* Add source separation (spleeter/demucs) plus stem note extraction.
* Improve quantization & tuning detection.
* Add per-beat compatibility profile outputs; produce piano-roll PNGs.
* Add caching & Docker packaging.

**Phase 3 — GUI / Web app initial (6–12 weeks)**

* FastAPI backend exposing endpoints for analyze, fetch results.
* React frontend with list view, piano-roll, playback synchronization.
* Worker queue (Celery/Redis or RQ) for background analyses.

**Phase 4 — polish & ML improvements (ongoing)**

* Train learned ranking model from user feedback (pairwise preferences).
* Add advanced transcription models for polyphony.
* Add collaborative / sharing features.

*Timings above are estimates for a small dev team; adjust for single-developer bandwidth.*

---

# Example scoring formula (concrete)

For one sample:

* For note `i`, let:

  * `p_i` = pitch class
  * `w_prom_i` = prominence ∈ (0,1]
  * `S_chord = 1.0, S_scale = 0.6, S_neighbor = 0.3, S_disson = -0.2`
* `note_score_i =`

  * `S_chord` if p_i in chord_tones
  * else `S_scale` if p_i in diatonic scale
  * else `S_neighbor` if chromatic neighbor (±1 semitone of chord tone)
  * else `S_disson` if interval is tritone vs chord root/3rd/5th
  * else `0`
* `weighted_sum = Σ (note_score_i * w_prom_i)`
* `max_possible = Σ (S_chord * w_prom_i)` (if every note were chord tone)
* `compatibility_score = (weighted_sum - min_possible) / (max_possible - min_possible)`, clipped to [0,1].

  * Set `min_possible` to `Σ(min_note_score * w_prom_i)`, e.g., if we allow negative penalties.
    Simpler: `compatibility_score = max(0, weighted_sum / max_possible)`.

---

# Practical tips & gotchas

* **Allow user overrides**: allow specifying whether samples are monophonic or polyphonic; allow tempo override or beat grid file.
* **Tuning detection**: compute median deviation from nearest equal-tempered pitch and shift frequencies so the sample is in standard tuning before mapping to pitch classes.
* **Enharmonic equivalence**: treat C# and Db as same pitch class, normalize naming consistently.
* **Time quantization tolerance**: use a small tolerance (e.g., 1/32 note) to match notes to beats to accommodate groove.
* **Confidence metadata**: include confidence per note and per-file so users can filter low-confidence results.

---

# Quick example: sample CLI workflow

1. `chordmatch init-chords` — create sample `chords.json` template.
2. `chordmatch analyze --chords chords.json --samples ./loops --out ./results.json`
3. Inspect `results.json`, open top sample with:

   * `chordmatch inspect ./results.json --sample loop01.wav` -> prints breakdown and path to generated MIDI/piano-roll image.
4. Later: `chordmatch serve` spins up a local web UI for interactive correction.

---

# Final notes & suggestions

* **Start simple:** focus on monophonic detection and a solid scoring model for the CLI MVP. That will already be extremely useful.
* **Measure & iterate:** build tools to visualize and audit detections — a piano-roll MIDI export is invaluable for debugging and user trust.
* **Expect imperfect polyphony:** treat polyphonic handling as an iterative improvement and provide users the tools to correct/override results in the GUI.
* **Make outputs interoperable:** JSON + MIDI + images let other tools/DAWs reuse the results.

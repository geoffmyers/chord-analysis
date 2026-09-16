# Best Piano-Specific Audio-to-MIDI Transcription Models (2025)

This document covers the top algorithms and models for piano transcription, ranked by accuracy and practical usability.

---

## Tier 1: State-of-the-Art

### 1. Onsets and Frames (Google Magenta)

| Aspect | Details |
|--------|---------|
| Accuracy | ~88% frame F1, ~84% note F1 on MAPS |
| Speed | Near real-time with GPU |
| Output | MIDI with velocity |
| Best for | Clean solo piano recordings |

**Links:**
- GitHub: [magenta/onsets-frames-transcription](https://github.com/magenta/magenta/tree/main/magenta/models/onsets_frames_transcription)
- Pre-trained checkpoints available

---

### 2. Basic Pitch (Spotify)

| Aspect | Details |
|--------|---------|
| Accuracy | Comparable to Onsets and Frames |
| Speed | Fast inference, CPU-friendly |
| Output | MIDI, note events, pitch/onset/note arrays |
| Best for | General use, easy integration |

**Advantages:**
- Simple Python API
- Lightweight model
- Works on polyphonic audio beyond just piano
- Active maintenance

```python
from basic_pitch.inference import predict

model_output, midi_data, note_events = predict('piano.wav')
midi_data.write('output.mid')
```

**Links:**
- GitHub: [spotify/basic-pitch](https://github.com/spotify/basic-pitch)
- Web demo: [basicpitch.spotify.com](https://basicpitch.spotify.com)

---

### 3. MT3 (Multi-Task Music Transcription Transformer)

| Aspect | Details |
|--------|---------|
| Accuracy | State-of-the-art on MAESTRO |
| Architecture | T5-based Transformer |
| Output | MIDI-like token sequences |
| Best for | Research, multi-instrument (but excels at piano) |

**Advantages:**
- Handles multiple instruments simultaneously
- Better temporal modeling via attention
- Can output instrument labels

**Limitations:**
- Large model size
- Slower inference
- More complex setup

**Links:**
- GitHub: [magenta/mt3](https://github.com/magenta/mt3)
- Paper: "MT3: Multi-Task Multitrack Music Transcription" (ICLR 2022)

---

## Tier 2: Production-Ready Alternatives

### 4. Piano Transcription (ByteDance)

| Aspect | Details |
|--------|---------|
| Accuracy | Competitive with Onsets and Frames |
| Speed | Optimized for efficiency |
| Output | MIDI with pedal events |

**Advantages:**
- Includes sustain pedal transcription
- Well-documented codebase
- Good balance of speed/accuracy

**Links:**
- GitHub: [bytedance/piano_transcription](https://github.com/bytedance/piano_transcription)

---

### 5. High-Resolution Piano Transcription (Kong et al.)

| Aspect | Details |
|--------|---------|
| Accuracy | ~90%+ on MAESTRO |
| Resolution | Higher temporal precision |
| Output | MIDI with velocity and pedal |

**Advantages:**
- State-of-the-art on MAESTRO benchmark
- Pedal detection included
- Regression-based onset detection (more precise)

**Links:**
- GitHub: [qiuqiangkong/piano_transcription_inference](https://github.com/qiuqiangkong/piano_transcription_inference)
- Paper: "High-Resolution Piano Transcription with Pedals" (TASLP 2021)

---

### 6. Omnizart

| Aspect | Details |
|--------|---------|
| Scope | Multi-purpose (piano, drums, vocals, chords) |
| Ease of use | CLI and Python API |
| Output | MIDI |

**Advantages:**
- All-in-one music transcription toolkit
- Multiple pre-trained models
- Active development

```bash
omnizart music transcribe piano.wav
```

**Links:**
- GitHub: [Music-and-Culture-Technology-Lab/omnizart](https://github.com/Music-and-Culture-Technology-Lab/omnizart)

---

## Tier 3: Specialized / Research

### 7. MAESTRO Models (Various)

Several models trained specifically on the MAESTRO dataset:
- Largest high-quality piano dataset (~200 hours)
- Perfectly aligned audio-MIDI pairs from Yamaha Disklavier
- Multiple research implementations available

---

### 8. madmom

| Aspect | Details |
|--------|---------|
| Focus | Beat/onset detection, some pitch |
| Architecture | RNN-based |
| Best for | Onset detection preprocessing |

```python
from madmom.features.onsets import RNNOnsetProcessor
proc = RNNOnsetProcessor()
onsets = proc('piano.wav')
```

**Links:**
- GitHub: [CPJKU/madmom](https://github.com/CPJKU/madmom)

---

## Comparison Table

| Model | Frame F1 | Note F1 | Pedal | Velocity | Speed | Ease of Use |
|-------|----------|---------|-------|----------|-------|-------------|
| **Basic Pitch** | 85% | 82% | No | Yes | Fast | Excellent |
| **Onsets and Frames** | 88% | 84% | No | Yes | Medium | Good |
| **Kong et al.** | 90% | 87% | Yes | Yes | Medium | Good |
| **ByteDance** | 88% | 85% | Yes | Yes | Fast | Good |
| **MT3** | 91% | 88% | No | Yes | Slow | Complex |
| **Omnizart** | 85% | 80% | No | Yes | Medium | Excellent |

---

## Recommendations by Use Case

### For Quick Prototyping
**Basic Pitch** — Simple API, fast, good enough for most applications

### For Best Accuracy
**Kong et al. / High-Resolution** — Best benchmark scores, includes pedal

### For Production Pipeline
**ByteDance Piano Transcription** — Good balance of features, speed, and accuracy

### For Research
**MT3** — Most sophisticated architecture, best for extending/fine-tuning

### For All-in-One Solution
**Omnizart** — Handles piano, drums, vocals, chords in one package

---

## Quick Start: Basic Pitch

The easiest way to get started:

```bash
pip install basic-pitch
```

```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

# Transcribe
model_output, midi_data, note_events = predict(
    'piano_recording.wav',
    ICASSP_2022_MODEL_PATH,
    onset_threshold=0.5,
    frame_threshold=0.3,
    minimum_note_length=58,  # ms
    minimum_frequency=32.7,  # C1
    maximum_frequency=4186,  # C8
)

# Save MIDI
midi_data.write('transcription.mid')

# Access raw predictions
pitches = model_output['note']      # Frame-level pitch activation
onsets = model_output['onset']      # Onset probabilities
contours = model_output['contour']  # Pitch contours
```

---

## Quick Start: Kong et al. (High-Resolution)

```bash
pip install piano_transcription_inference
```

```python
from piano_transcription_inference import PianoTranscription, sample_rate, load_audio

# Load audio
audio, _ = load_audio('piano.wav', sr=sample_rate, mono=True)

# Initialize transcriber
transcriptor = PianoTranscription(device='cuda')  # or 'cpu'

# Transcribe
transcribed_dict = transcriptor.transcribe(audio, 'output.mid')

# transcribed_dict contains:
# - 'est_note_events': list of (onset, offset, pitch, velocity)
# - 'est_pedal_events': list of (onset, offset)
```

---

## Datasets for Training/Evaluation

| Dataset | Hours | Source | Notes |
|---------|-------|--------|-------|
| **MAESTRO** | 200 | Yamaha Disklavier | Gold standard, perfect alignment |
| **MAPS** | 65 | Software + real pianos | Multiple piano types |
| **MusicNet** | 34 | Chamber music | Not piano-specific |
| **GiantMIDI-Piano** | 10,000+ | Transcribed recordings | Large but noisier labels |

---

## References

- Hawthorne, C., et al. "Onsets and Frames: Dual-Objective Piano Transcription." ISMIR, 2018.
- Bittner, R., et al. "A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation." ICASSP, 2022. (Basic Pitch)
- Gardner, J., et al. "MT3: Multi-Task Multitrack Music Transcription." ICLR, 2022.
- Kong, Q., et al. "High-Resolution Piano Transcription with Pedals by Regressing Onset and Offset Times." IEEE/ACM TASLP, 2021.
- Wu, Y., et al. "Omnizart: A General Toolbox for Automatic Music Transcription." arXiv, 2021.

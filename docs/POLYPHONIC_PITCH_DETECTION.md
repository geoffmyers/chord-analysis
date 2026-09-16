# Polyphonic Pitch Detection Algorithms

Polyphonic pitch detection—identifying multiple simultaneous pitches in an audio signal—is significantly more complex than monophonic detection. This document covers the main approaches and their implementations.

---

## The Core Challenge

When multiple notes play simultaneously, their frequencies overlap and interact:

- Harmonics from different notes interleave and sometimes coincide
- Lower notes can mask higher ones
- Timbre variations add non-harmonic components
- Onset times may not align perfectly

---

## 1. Spectrogram-Based Methods

### Basic Approach

1. **Short-Time Fourier Transform (STFT)** converts audio into time-frequency representation
2. **Peak picking** identifies frequency bins with local maxima
3. **Harmonic grouping** clusters peaks that share a common fundamental

### Limitations

- Frequency resolution vs. time resolution tradeoff
- Harmonics from different notes at same frequency (e.g., A4's 2nd harmonic ≈ E5's fundamental)

---

## 2. Non-Negative Matrix Factorization (NMF)

### Core Principle

Decompose a spectrogram **V** into two matrices:

- **W** (basis matrix): Spectral templates for each pitch
- **H** (activation matrix): When each pitch is active

```
V ≈ W × H
```

### Process

1. Initialize W with harmonic templates (or learn from data)
2. Iteratively update W and H to minimize reconstruction error
3. Read pitch activations from H matrix

### Variants

- **Sparse NMF**: Encourages fewer simultaneous activations
- **Convolutive NMF**: Models attack/decay envelopes
- **Supervised NMF**: Pre-trained templates for specific instruments

---

## 3. Probabilistic Models

### Probabilistic Latent Component Analysis (PLCA)

Treats spectrogram as probability distribution:

- Each time-frequency bin is a "draw" from a mixture model
- Pitches are latent variables
- Uses Expectation-Maximization (EM) to infer active pitches

### Hidden Markov Models (HMM)

- States represent pitch combinations
- Transitions model musical continuity (notes don't randomly jump)
- Observations are spectral features

---

## 4. Neural Network Approaches

### Convolutional Neural Networks (CNNs)

**Architecture:**

```
Spectrogram → Conv layers → Fully connected → 88 sigmoid outputs (piano roll)
```

**Training:**

- Input: Spectrograms (often Constant-Q Transform)
- Output: Binary piano roll (pitch active/inactive per frame)
- Loss: Binary cross-entropy

**Notable Models:**

- **Onsets and Frames** (Google Magenta)
- **Deep Salience** (Bittner et al.)

### Recurrent Networks (RNN/LSTM)

Add temporal context:

- Previous frame predictions inform current frame
- Better handles sustained notes and transitions

### Transformer-Based

- Self-attention captures long-range dependencies
- State-of-the-art on many benchmarks
- Examples: **MT3** (Music Transcription Transformer)

---

## 5. Constant-Q Transform (CQT) Methods

### Why CQT?

- Frequency bins are logarithmically spaced (like musical pitches)
- Each octave has same number of bins
- Better matches how we perceive pitch

### Process

1. Compute CQT spectrogram
2. Apply harmonic/percussive separation (optional)
3. Feed into NMF or neural network

---

## 6. Harmonic-Percussive Source Separation (HPSS)

### Pre-processing Step

Separate audio into:

- **Harmonic component**: Sustained tonal content
- **Percussive component**: Transients, drums

### Benefit

Pitch detection on harmonic component is cleaner—percussive transients don't confuse the algorithm.

---

## 7. Salience-Based Methods

### Pitch Salience Function

For each candidate pitch, compute a "salience" score based on:

- Energy at fundamental frequency
- Energy at expected harmonic locations
- Weighted by harmonic number (lower harmonics weighted more)

```python
def pitch_salience(f0, spectrum, num_harmonics=10):
    salience = 0
    for h in range(1, num_harmonics + 1):
        freq = f0 * h
        weight = 1 / h  # Lower harmonics weighted more
        salience += weight * spectrum[freq_to_bin(freq)]
    return salience
```

### Multi-Pitch Selection

- Compute salience for all candidate pitches
- Select peaks above threshold
- Iteratively subtract detected pitches and repeat (subtractive method)

---

## 8. Subtractive/Iterative Methods

### Process

1. Detect most prominent pitch
2. Synthesize and subtract it from the signal
3. Repeat on residual
4. Stop when residual energy is low

### Challenges

- Errors compound (wrong subtraction corrupts residual)
- Order of subtraction matters

---

## Comparison of Approaches

| Method | Pros | Cons |
|--------|------|------|
| **NMF** | Interpretable, unsupervised | Needs good templates |
| **CNN** | State-of-the-art accuracy | Requires large training data |
| **Salience** | Fast, tunable | Struggles with complex textures |
| **HMM** | Models temporal continuity | Computational complexity |
| **Transformer** | Best long-range context | Very large models |

---

## Key Spectral Representations

| Transform | Description | Use Case |
|-----------|-------------|----------|
| **STFT** | Fixed frequency resolution | General purpose |
| **CQT** | Log-frequency bins | Pitch detection |
| **Mel Spectrogram** | Perceptually-weighted | Neural networks |
| **Chromagram** | Pitch class (octave-folded) | Chord detection |
| **HCQT** | Harmonic CQT (multiple harmonics stacked) | Deep learning |

---

## Open Source Implementations

| Library | Language | Method |
|---------|----------|--------|
| **librosa** | Python | Salience-based (`librosa.pyin` for monophonic) |
| **madmom** | Python | RNN-based, state-of-the-art |
| **Essentia** | C++/Python | Multiple algorithms |
| **crepe** | Python | CNN for monophonic, adaptable |
| **basic-pitch** | Python | Neural network (Spotify) |
| **Onsets and Frames** | TensorFlow | Google Magenta's piano transcription |
| **MT3** | Python | Transformer-based multi-instrument |

---

## Practical Considerations

### For Real-Time Applications

- Salience methods or small CNNs
- Trade accuracy for latency

### For Offline Transcription

- Transformer or large CNN models
- Can use bidirectional context

### For Specific Instruments

- Train/fine-tune on instrument-specific data
- Use appropriate frequency range constraints

---

## Current State of the Art

As of 2024-2025, the best results come from:

1. **MT3** (Multi-Task Music Transcription Transformer) — handles multiple instruments
2. **Onsets and Frames** — excellent for piano
3. **Basic Pitch** (Spotify) — good balance of speed and accuracy
4. **Hybrid approaches** combining neural networks with post-processing HMMs

Accuracy on standard benchmarks (MAPS, MusicNet) has reached ~85-90% frame-level F1 for piano, lower for mixed ensembles.

---

## References

- Benetos, E., et al. "Automatic Music Transcription: An Overview." IEEE Signal Processing Magazine, 2019.
- Hawthorne, C., et al. "Onsets and Frames: Dual-Objective Piano Transcription." ISMIR, 2018.
- Gardner, J., et al. "MT3: Multi-Task Multitrack Music Transcription." ICLR, 2022.
- Bittner, R., et al. "Deep Salience Representations for F0 Estimation in Polyphonic Music." ISMIR, 2017.
- Smaragdis, P. & Brown, J.C. "Non-Negative Matrix Factorization for Polyphonic Music Transcription." WASPAA, 2003.

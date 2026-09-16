# Music Theory Frameworks for Harmonic Compatibility Analysis

This document outlines established frameworks for determining scale/pitch compatibility with chord progressions, from most practical to most theoretical.

---

## 1. Chord-Scale Theory (Berklee/Jazz Method)

The most widely taught approach in jazz education.

### Core Principle

Each chord implies a parent scale based on its chord tones and extensions.

### Process

1. Identify chord quality (maj7, m7, dom7, etc.)
2. Map to default scale choices
3. Adjust for context (what comes before/after)

### Standard Mappings

| Chord Type | Default Scale(s) |
|------------|------------------|
| maj7 | Ionian, Lydian |
| m7 | Dorian, Aeolian, Phrygian |
| 7 (dominant) | Mixolydian, Lydian Dominant, Altered |
| m7b5 | Locrian, Locrian #2 |
| dim7 | Diminished (whole-half) |
| sus4 | Mixolydian, Dorian |

### Limitation

Treats chords in isolation; doesn't account for horizontal (melodic) voice leading.

---

## 2. Avoid Note Theory

A refinement of chord-scale theory focusing on dissonance.

### Core Principle

Within any scale, certain notes create undesirable dissonance against chord tones (typically a minor 9th interval above a chord tone).

### Example

- Over **Cmaj7**, the note F creates a minor 9th against E (the 3rd)
- Therefore F is an "avoid note" in C Ionian over Cmaj7
- **C Lydian** (with F#) eliminates this avoid note

### Application

Filter scale choices by removing those with avoid notes, or treat avoid notes as passing tones only.

---

## 3. Upper Structure / Chord Tone Hierarchy

### Core Principle

Rank pitches by consonance level relative to the chord.

### Hierarchy (most to least stable)

1. **Chord tones** (1, 3, 5, 7) — Target notes, can be held
2. **Primary tensions** (9, 11, 13) — Color tones, mild tension
3. **Passing tones** — Chromatic connections, don't linger
4. **Avoid notes** — Create harsh dissonance, use sparingly

### Quantifiable Scoring

```
Chord tone:     +3 points
Tension:        +1 point
Neutral:         0 points
Avoid note:     -2 points
```

This allows numeric comparison of scales against a chord.

---

## 4. Negative Harmony / Ernst Levy's Harmonic Theory

### Core Principle

Chords and scales have "mirror" equivalents around an axis (typically the axis between the root and fifth).

### Application

Find compatible scales by reflecting known compatible scales around the harmonic axis.

### Example

If G Major works over a chord, its negative harmony reflection might reveal alternative compatible scales.

---

## 5. Pitch Class Set Theory (Forte/Atonal Theory)

Academic framework from 20th-century music analysis.

### Core Principle

Reduce chords and scales to abstract pitch-class sets (0-11) and measure similarity using:

- **Interval Vector:** Count of each interval class in the set
- **Subset/Superset Relations:** Does the chord fit within the scale?
- **Similarity Index:** Ic (interval class) similarity between sets

### Example

- G#m7 = {8, 11, 3, 6} → pitch classes
- E Dorian = {4, 6, 7, 9, 11, 1, 2}
- Calculate overlap and interval compatibility

### Limitation

Highly abstract; ignores tonal context and voice leading.

---

## 6. Neo-Riemannian Theory

### Core Principle

Analyze chord relationships through transformations (P, L, R) rather than Roman numerals.

- **P (Parallel):** C major <-> C minor
- **L (Leading-tone):** C major <-> E minor
- **R (Relative):** C major <-> A minor

### Application

Chords connected by fewer transformations share more compatible scales.

### Example

- G -> G#m7 isn't a standard P/L/R move — it's chromatic
- This framework would flag it as requiring special treatment

---

## 7. Harmonic Entropy / Psychoacoustic Models

Modern computational approach based on perception research.

### Core Principle

Consonance/dissonance can be modeled mathematically based on:

- Frequency ratios (simpler = more consonant)
- Critical bandwidth interference
- Virtual pitch perception

### Tools

- **Harmonic Entropy Calculator** — Measures perceived dissonance
- **Spectral analysis** — Examine overtone conflicts

### Application

Score each scale degree against each chord tone using harmonic entropy values.

---

## 8. Algorithmic/Computational Approaches

Modern software implementations combine multiple frameworks.

### Common Algorithm

```python
def score_scale_against_progression(scale, progression):
    score = 0
    for chord in progression:
        for note in scale:
            if note in chord.chord_tones:
                score += 3
            elif note in chord.tensions:
                score += 1
            elif note in chord.avoid_notes:
                score -= 2
        # Weight by chord duration
    return score
```

### Tools/Libraries

- **music21** (Python) — Academic music analysis
- **Tonal.js** (JavaScript) — Scale/chord relationship functions
- **ChordMate**, **Scaler 2** — Commercial plugins with compatibility scoring

---

## Recommended Practical Framework

For analyzing arbitrary progressions, a **hybrid approach** works best:

### Step 1: Chord-Scale Mapping

Assign 2-3 candidate scales per chord using standard jazz mappings.

### Step 2: Pitch-Class Overlap Analysis

For each candidate scale, count:

- Chord tones present (weight: 3)
- Available tensions present (weight: 1)
- Avoid notes present (weight: -2)

### Step 3: Voice Leading Consideration

Bonus points for scales that allow smooth voice leading between adjacent chords (stepwise motion).

### Step 4: Aggregate Scoring

Sum scores across all chords, weighted by duration.

---

## Example Analysis: Chromatic Progression

Given the progression:

```
G | G#m7 | Gmaj7 | G#m7 | Aadd11 | Esus4 | Dadd9 | Esus4 | Em7 | Fmaj7 | G6 | F6
```

### Scale Compatibility Ranking

| Rank | Scale | Score | Best For |
|------|-------|-------|----------|
| 1 | E Dorian | 8.5/12 | G, Em7, Dadd9, Esus4 sections |
| 2 | G Major | 8/12 | G, Gmaj7, Em7, Dadd9 sections |
| 3 | C Major | 7.5/12 | Fmaj7, F6, Em7, G sections |
| 4 | D Major | 7/12 | Dadd9, Aadd11, G sections |
| 5 | A Dorian | 7/12 | Aadd11, Dadd9 sections |
| 6 | G# Aeolian | 5/12 | G#m7 only |

### Observations

- No single scale works for the entire progression
- The G#m7 chord is a chromatic outlier requiring scale switching
- Best approach: E Dorian/G Major for most chords, switch to G# Dorian or B Major for G#m7, switch to C Major or F Lydian for Fmaj7/F6

---

## References

- Nettles, Barrie & Graf, Richard. *The Chord Scale Theory & Jazz Harmony*
- Levy, Ernst. *A Theory of Harmony*
- Forte, Allen. *The Structure of Atonal Music*
- Cohn, Richard. *Audacious Euphony: Chromatic Harmony and the Triad's Second Nature*
- Sethares, William. *Tuning, Timbre, Spectrum, Scale*

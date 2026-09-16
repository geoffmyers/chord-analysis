# Existing Similar Tools

## 🎛️ 1. Tools That Analyze Audio for Harmony or Chords

### **Chord extraction / chord detection (but not full compatibility scoring)**

These tools take an audio file and detect chord labels or harmonic content:

* **Chordify** — Web/mobile platform that extracts chords from audio and synchronizes them to playback. It gives you chord progressions but *doesn’t score/rank samples against a custom chord progression or extract individual pitches per beat* in a detailed data structure. ([Wikipedia][1])
* **ChordMini** — AI-powered chord and beat detection tool that identifies chords and tempo from audio. Useful for finding harmonic content but again *not designed for harmonic compatibility scoring with a custom progression*. ([halotool][2])
* **Various DAW plugins / key detection tools** such as **Scaler 3** and key/scale detection plugins (HoRNet SongKey MK4, etc) can analyze audio or MIDI for chords and keys, *but they don’t extract detailed timed pitch arrays per beat or produce harmonic compatibility rankings*. ([Scaler Music][3])
* **Song Surgeon / audio slowdown apps** – Tools like Song Surgeon can detect tempo, key, and display chord suggestions, but again lack structured note-by-note extraction and harmonic ranking. ([songsurgeon.com][4])

> **Summary:** Existing “chord detection” tools excel at extracting a *single* chord progression from audio or finding the key, but don’t break down audio into time-aligned pitch events and *score loops against another progression*. They are *partial solutions* to your broader problem but don’t fully solve it.

---

## 🎚️ 2. Audio Analysis / Music Information Retrieval (MIR) Tools

These are technical frameworks and research libraries that handle deeper audio analysis:

### **Sonic Visualiser + Vamp Plugins**

* Sonic Visualiser is an analysis/visualization tool that, via plugins, can extract onsets, melody, chords, etc., from audio. ([Wikipedia][5])
* It can show pitch and harmonic information visually, but it’s *not an automated ranking system* nor a CLI/web service out of the box.

### **Academic chord estimation research (ACE)**

* The task of automatic chord estimation (ACE) is a well-studied problem in music information retrieval. Models such as in the DECIBEL study improve chord detection accuracy from audio. ([arXiv][6])
* This research helps with *better chord labels*, which is a component of your goal, but it’s not wrapped in an integrated, scalable tool for scoring samples.

---

## 🎧 3. Tools for Note Extraction / Transcription

These aren’t full products but examples of tech you might incorporate:

* **Melodyne / Direct Note Access** — Commercial software that can detect individual notes in polyphonic audio (e.g., chords) and let you edit them like MIDI, though it’s not automated as a batch analyzer or ranking engine. ([WIRED][7])
* **DAW audio-to-MIDI features (e.g., Logic’s Flex to MIDI)** and *chord-detection plugins within DAWs* can convert loops to pitch data, but scaling that up is manual. ([Reddit][8])
* **Open-source MIR libraries** (like those referenced in academic work) can detect chroma features, pitch class profiles, etc., but you’d still need to build a analyzer + scoring layer on top.

---

## 🎛️ 4. Tools for Sorting by Harmonic Compatibility (DJ Tools)

Some products *partially* address harmonic compatibility, but only at the *track/key* level, not at the *beat-accurate note level* you want:

* **Mixed In Key / Rapid Evolution / beaTunes** — These DJ tools analyze audio for *key* and *BPM* and suggest harmonically compatible tracks, but they do not actually extract all pitch events nor score them against another progression in detail. ([Wikipedia][9])

---

## 🧠 Summary of What Exists vs. Your Vision

| Feature                                              | Exists                   | Gap                                                       |
| ---------------------------------------------------- | ------------------------ | --------------------------------------------------------- |
| Chord detection from audio                           | ✔️ (Chordify, plugins)   | Only chord labels, not detailed pitch events              |
| Note/pitch extraction                                | ✔️ (DAW tools, Melodyne) | Not automated for batch and scoring                       |
| Beat/tempo detection                                 | ✔️                       | Works standalone, but not integrated with scoring         |
| Harmonic compatibility ranking vs custom progression | ❌                        | No existing standalone tool                               |
| Polyphonic transcription at high quality             | ⚠️                       | Partially via expensive tools, not in automated batch CLI |

---

## 🧪 Key Gaps / Why the Problem Isn’t Already Solved

1. **Cycle of complexity:** Western audio analysis (especially polyphonic note detection) is still imperfect; existing tools focus on *educational* or *DJ* use cases, not *programmatic harmonic scoring*.
2. **Lack of scoring frameworks:** Tools extract chords/keys but don’t assign formal scores on how well audio content fits against a user-supplied progression.
3. **No integrated batch ranking solution:** There isn’t a packaged CLI or API that combines audio analysis, pitch extraction, harmonic theory, and ranking — which is exactly your innovation.

---

## 📌 Research / Technical Foundations (but not products)

* There’s active research into **automatic chord estimation and harmonic feature extraction** (e.g., ACE systems), which forms part of what’s needed for your tool. ([arXiv][6])
* Music information retrieval (MIR) libraries and models (not products) exist to extract chroma features and pitch distributions; these are useful building blocks.

---

## 🧠 Conclusion

* **Partial solutions exist:** You can use Chordify, DAW audio-to-MIDI converters, DJ key detection tools, and MIR libraries to extract parts of the data you need.
* **No existing complete solution:** There’s **no tool I could find that fully implements** the beat-accurate, per-note harmonic compatibility scoring and ranking of loops relative to a custom chord progression that you described.

[1]: https://en.wikipedia.org/wiki/Chordify?utm_source=chatgpt.com "Chordify"
[2]: https://halotool.com/tool/chordmini?utm_source=chatgpt.com "ChordMini - AI-powered chord recognition and beat detection for music analysis."
[3]: https://scalermusic.com/products/scaler-3/?utm_source=chatgpt.com "Scaler 3"
[4]: https://songsurgeon.com/?utm_source=chatgpt.com "Song Surgeon Version 6, Audio Slow Downer, Beat & Chord ..."
[5]: https://en.wikipedia.org/wiki/Sonic_Visualiser?utm_source=chatgpt.com "Sonic Visualiser"
[6]: https://arxiv.org/abs/2002.09748?utm_source=chatgpt.com "DECIBEL: Improving Audio Chord Estimation for Popular Music by Alignment and Integration of Crowd-Sourced Symbolic Representations"
[7]: https://www.wired.com/2009/11/can-celemonys-breakthrough-software-handle-the-hard-days-night-chord?utm_source=chatgpt.com "Celemony's Melodyne Makes Easy Work of 'Hard Day's Night'"
[8]: https://www.reddit.com/r/LogicPro/comments/1flta2d?utm_source=chatgpt.com "Is there any software that can identify notes in chord samples? In jungle/DNB sample packs, these types of samples are everywhere but they're hard to fit to key and to fit to a sampler instrument"
[9]: https://en.wikipedia.org/wiki/Mixed_In_Key?utm_source=chatgpt.com "Mixed In Key"

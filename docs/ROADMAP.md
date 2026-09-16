# Chord Analysis Roadmap

## To Do

- ...

## In Progress

- ...

## Done

- Add Roman numeral notation to chord timeline visualization and real-time playback indicator.
  - Enhanced `generate_chord_timeline()` to display both absolute chord names and Roman numeral notation on the same blocks
  - Chord labels shown on top, Roman numerals shown below in italic blue font
  - Created `generate_interactive_chord_player()` for real-time synchronized playback
  - Interactive player features:
    - Moving red vertical line (playback head) syncs with audio playback
    - Current chord highlighted with red border
    - Real-time display of current bar, beat, and chord name
    - Arrow indicator at top of playback head
    - Updates at 30 FPS for smooth animation
    - "▶️ Play with Indicator" button to start synchronized playback
  - Integrated interactive player into Sample Browser and Find Compatible pages
  - Available for samples with beat information and BPM data
  - Graceful fallback to standard audio player for samples without timing data
- Add temporal visualization of chord progressions with bars and beats timeline, replacing text-based chord progressions.
  - Created `generate_chord_timeline()` function to visualize chords on a timeline with measures/bars
  - Timeline displays:
    - Vertical bar lines marking measure boundaries
    - Dashed beat markers within each bar
    - Color-coded rectangular blocks showing chord duration
    - Chord labels displayed on blocks
    - Roman numeral notation shown below blocks
    - Bar numbers labeled at top
  - Integrated timeline into Sample Browser card view (replaces "Chords:" and "Roman:" text)
  - Integrated timeline into Find Compatible target sample display
  - Integrated timeline into Find Compatible results card view
  - Graceful fallback to text-based progression for samples without beat information
  - Maximum 8 bars displayed by default for optimal visualization

- Replace the "Tempo Statistics" chart on the "Dashboard" with "Samples by Tempo" with a histogram chart showing the distribution of tempos across all samples (split groups every 10 BPM, e.g. 60-69 BPM, 70-79 BPM, 80-89 BPM).
  - Added tempo_distribution calculation to get_database_stats() with 10 BPM buckets
  - Replaced Tempo Statistics metrics with bar chart histogram
  - Histogram shows count of samples in each tempo range (60-69, 70-79, 80-89, etc.)
  - Maintained fallback to basic tempo statistics if distribution data unavailable
- Add audio playback functionality to the "Find Compatible" page, allowing users to listen to and compare compatible samples.
  - Added audio player for target sample display
  - Added sample ID selection and audio playback for table view results
  - Added audio player to each compatible sample in card view
- Replace the "Time Signatures" chart on the "Dashboard" with "Samples by Chord Progression". Split the "Samples by Key" chart into 2 separate charts: "Samples by Key" (e.g. A, B, C) and "Samples by Scale" (e.g. Major, Minor).
  - Updated `get_database_stats()` to calculate key_roots, scales, and chord_progressions statistics
  - Split "Samples by Key" into separate "Samples by Key" (root notes) and "Samples by Scale" (Major/Minor) charts
  - Replaced "Time Signatures" chart with "Top Chord Progressions" chart showing most common Roman numeral patterns
- Add audio waveform visualization with chord annotations/markers to the sample detail view for better analysis of audio samples.
  - Added `generate_waveform_with_chords()` function using librosa and matplotlib
  - Integrated waveform visualization into Sample Browser card view (behind expander)
  - Integrated waveform visualization into Find Compatible card view (behind expander)
  - Waveforms display chord changes with vertical lines, labels, and color-coded legend
  - Added matplotlib to requirements.txt

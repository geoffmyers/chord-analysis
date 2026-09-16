# Audio File Detection Fix

## Problem

After implementing the performance optimization to disable audio embedding:
- ALL samples showed "Audio file not available - showing chord timeline only"
- NO samples had "Play" buttons
- This occurred even when audio files existed

## Root Cause

The `_render_timeline_only()` function had a hardcoded message:

```html
<div class="no-audio">Audio file not available - showing chord timeline only</div>
```

This message appeared for **all** samples when `ENABLE_AUDIO_EMBEDDING = False`, regardless of whether audio files existed.

## Solution

### 1. Made the warning message conditional

Updated `_render_timeline_only()` to accept a parameter:

```python
def _render_timeline_only(viz_data: dict, height: int = 200, show_no_audio_message: bool = False):
    # Only show message if explicitly requested
    if show_no_audio_message:
        no_audio_html = '<div class="no-audio">Audio file not available...</div>'
    else:
        no_audio_html = ''  # No message for normal lightweight rendering
```

### 2. Updated render logic in `render_chord_visualizer()`

**Performance mode (audio embedding disabled):**
```python
if not ENABLE_AUDIO_EMBEDDING:
    # Check if audio file exists
    audio_path = find_audio_file_for_sample(sample)
    has_audio = audio_path and audio_path.exists()

    # Render timeline - only show warning if audio truly unavailable
    _render_timeline_only(viz_data, height, show_no_audio_message=not has_audio)

    # Show Play button ONLY if audio available
    if has_audio:
        if st.button("▶️ Play", key=f"play_{sample.id}"):
            st.audio(str(audio_path))
```

**Legacy mode (audio file not found):**
```python
if audio_path is None:
    st.warning(f"Audio file not found for: {sample.filepath}")
    _render_timeline_only(viz_data, height, show_no_audio_message=True)  # Show warning
```

## Results

### Before Fix
- ❌ All samples: "Audio file not available" message
- ❌ No Play buttons anywhere
- ❌ Confusing user experience

### After Fix
✅ **Samples WITH audio files:**
- Clean timeline (no warning message)
- ▶️ Play button appears
- Clicking Play loads audio using Streamlit's efficient serving

✅ **Samples WITHOUT audio files:**
- Warning message: "Audio file not available - showing chord timeline only"
- NO Play button (correct - nothing to play)

## Verification (Chrome Testing)

Tested via Chrome automation:

**Sample: `01_111BPM_E_Drop_Pad`**
- File: `~/Splice/.../01_111BPM_E_Drop_Pad.wav` ✓
- Result: Clean timeline + Play button
- Audio player: Appears when clicked (showed "0:00 / 0:32")

**Sample: `016_Bass_Loop_A`**
- File: `output/splice-chords/016_Bass_Loop_A_vamp_nnls-chroma_chordino_simplechord.csv`
- Audio search: No audio file found
- Result: Warning message + NO Play button ✓

**Sample: `02_113BPM_D`**
- Result: Warning message + NO Play button ✓

## Database Analysis

The database contains two types of filepaths:

1. **Direct audio paths** (most samples):
   ```
   ~/Splice/.../sample.wav
   ```
   → `find_audio_file_for_sample()` returns the path directly

2. **CSV paths** (some samples):
   ```
   output/splice-chords/sample_vamp_nnls-chroma_chordino_simplechord.csv
   ```
   → `find_audio_file_for_sample()` searches for corresponding audio file
   → If not found, returns `None`

## User Experience

Users now see appropriate messaging:

1. **Most samples** (with audio): Clean interface, Play button works
2. **Some samples** (CSV-only, no audio): Clear message explaining why no audio

This is honest and transparent - the app doesn't promise audio that doesn't exist.

## Files Modified

- `run_web.py`:
  - Modified `_render_timeline_only()` to accept `show_no_audio_message` parameter
  - Updated performance mode logic to check audio availability
  - Updated legacy mode to pass `show_no_audio_message=True`

## Performance Impact

No change to performance - the optimization is still fully effective:
- Browser memory: ~150MB (was 2GB)
- No base64 audio embedding
- Audio served efficiently via Streamlit when Play is clicked

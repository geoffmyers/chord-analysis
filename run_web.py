#!/usr/bin/env python3
"""
Streamlit Web UI Launcher for Chord Analyzer.

Usage:
    streamlit run run_web.py

Or with custom port:
    streamlit run run_web.py --server.port 8080
"""

import warnings
import logging

# Suppress benign Tornado WebSocket warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*WebSocketClosedError.*")
warnings.filterwarnings("ignore", message=".*Stream is closed.*")

# Reduce Tornado logging verbosity
logging.getLogger("tornado.access").setLevel(logging.ERROR)
logging.getLogger("tornado.application").setLevel(logging.ERROR)
logging.getLogger("tornado.general").setLevel(logging.ERROR)

import streamlit as st
from pathlib import Path
from typing import Optional
import sys

# Add package to path
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================================
# PERFORMANCE CONFIGURATION
# ============================================================================
# CRITICAL: Audio embedding uses 300+ MB of browser memory for 50 samples!
# Set to False to dramatically improve performance
ENABLE_AUDIO_EMBEDDING = False  # Change to True to re-enable audio playback

# Samples to show per page (lower = faster, less memory)
DEFAULT_PAGE_SIZE = 20  # Was implicitly 50, now configurable
# ============================================================================

from chord_analyzer.database import (
    init_database,
    get_all_samples,
    get_sample_count,
    get_samples_page,
    get_samples_metadata_only,
    get_sample_by_filepath,
    find_compatible_samples,
    get_database_stats,
)
from chord_analyzer.compatibility import calculate_compatibility
from chord_analyzer.extractor import create_sample_from_csv, create_sample_from_csv_with_tempo
from chord_analyzer.filename_parser import parse_filename
from chord_analyzer.theory import progression_to_numerals, estimate_key_from_progression


# Page config
st.set_page_config(
    page_title="Chord Analyzer",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_connection(db_path: str = "samples.db"):
    """Get or create database connection."""
    if "db_conn" not in st.session_state or st.session_state.get("db_path") != db_path:
        st.session_state.db_conn = init_database(db_path)
        st.session_state.db_path = db_path
    return st.session_state.db_conn


# =============================================================================
# HTML/JS Chord Visualizer Functions
# =============================================================================

def prepare_visualization_data(sample) -> dict:
    """
    Prepare chord data for JavaScript visualization.

    Args:
        sample: Sample object with chords and metadata

    Returns:
        Dictionary containing all data needed for JS visualization
    """
    from chord_analyzer.theory import chord_to_roman_numeral

    chords_data = []

    # Extract just the root note from the key (e.g., "E major" -> "E", "C# minor" -> "C#")
    key_root = None
    if sample.estimated_key:
        key_parts = sample.estimated_key.split()
        if key_parts:
            key_root = key_parts[0]  # First part is the root note

    for chord in sample.chords:
        chord_dict = chord.to_dict()
        # Add Roman numeral if key is known
        if key_root:
            roman = chord_to_roman_numeral(chord.chord_label, key_root)
            chord_dict['roman_numeral'] = roman if roman and roman != '?' else None
        else:
            chord_dict['roman_numeral'] = None
        chords_data.append(chord_dict)

    return {
        'filename': sample.filename,
        'duration_seconds': sample.duration_seconds,
        'estimated_key': sample.estimated_key,
        'estimated_bpm': sample.estimated_bpm,
        'time_signature': list(sample.time_signature),
        'beats_per_bar': sample.beats_per_bar,
        'first_beat_offset': sample.first_beat_offset,
        'chords': chords_data,
        'has_beat_info': sample.has_beat_info,
    }


def encode_audio_base64(filepath: str) -> str:
    """
    Encode audio file as base64 data URL.

    Converts unsupported formats (FLAC, etc.) to WAV for browser compatibility.

    Args:
        filepath: Path to audio file

    Returns:
        Base64 data URL string
    """
    import base64
    from pathlib import Path
    import io

    ext = Path(filepath).suffix.lower()

    # Browser-supported formats (can be used directly)
    browser_supported = {'.wav', '.mp3', '.ogg', '.m4a', '.aac'}

    if ext in browser_supported:
        # Use file directly
        mime_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
        }
        mime_type = mime_types.get(ext, 'audio/wav')

        with open(filepath, 'rb') as f:
            audio_bytes = f.read()
    else:
        # Convert unsupported formats (FLAC, AIFF, etc.) to WAV
        try:
            import soundfile as sf
            import numpy as np

            # Read audio file
            data, samplerate = sf.read(filepath)

            # Write to WAV in memory
            buffer = io.BytesIO()
            sf.write(buffer, data, samplerate, format='WAV', subtype='PCM_16')
            audio_bytes = buffer.getvalue()
            mime_type = 'audio/wav'
        except ImportError:
            # Fallback: try to use file directly (may not work)
            mime_type = 'audio/wav'
            with open(filepath, 'rb') as f:
                audio_bytes = f.read()

    return f"data:{mime_type};base64,{base64.b64encode(audio_bytes).decode('utf-8')}"


def find_audio_file_for_sample(sample) -> Optional[Path]:
    """
    Find the audio file for a sample, handling cases where filepath points to CSV.

    The database may store either:
    1. Direct path to audio file (.wav, .mp3, .flac, etc.)
    2. Path to chord analysis CSV file

    For CSV files, we try to find the corresponding audio file.

    Returns:
        Path to audio file if found, None otherwise
    """
    filepath = Path(sample.filepath)

    # Check if it's an audio file that exists
    audio_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.aif'}
    if filepath.suffix.lower() in audio_extensions and filepath.exists():
        return filepath

    # If it's a CSV file, try to find the corresponding audio file
    if filepath.suffix.lower() == '.csv':
        # CSV filename format: {original_stem}_vamp_nnls-chroma_chordino_simplechord.csv
        # Extract original stem by removing the suffix pattern
        stem = filepath.stem
        suffix_patterns = [
            '_vamp_nnls-chroma_chordino_simplechord',
            '_vamp_nnls-chroma_chordino_chords',
            '_chordino',
        ]
        original_stem = stem
        for pattern in suffix_patterns:
            if stem.endswith(pattern):
                original_stem = stem[:-len(pattern)]
                break

        # Look for audio file in common locations
        search_dirs = [
            filepath.parent,  # Same directory as CSV
            filepath.parent.parent,  # Parent directory
            Path.cwd(),  # Current working directory
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for ext in audio_extensions:
                # Try exact stem match
                audio_file = search_dir / f"{original_stem}{ext}"
                if audio_file.exists():
                    return audio_file
                # Try with different case
                for f in search_dir.glob(f"{original_stem}.*"):
                    if f.suffix.lower() in audio_extensions:
                        return f

    # If filepath doesn't exist but looks like an audio file, check if it exists elsewhere
    if filepath.suffix.lower() in audio_extensions:
        # Try just the filename in current directory
        local_path = Path.cwd() / filepath.name
        if local_path.exists():
            return local_path

    return None


def render_chord_visualizer(sample, height: int = 230, max_bars: int = 16) -> None:
    """
    Render interactive chord visualizer using HTML5/JS with WaveSurfer.js.

    Features:
    - Audio waveform visualization
    - Chord blocks overlay with absolute and Roman numeral labels
    - Smooth playhead animation synchronized with audio
    - Click-to-seek functionality

    Args:
        sample: Sample object with chords and metadata
        height: Height of the component in pixels
        max_bars: Maximum number of bars to display in timeline
    """
    import json
    import streamlit.components.v1 as components
    from pathlib import Path

    # PERFORMANCE: Skip audio embedding if disabled (saves 300+ MB memory)
    if not ENABLE_AUDIO_EMBEDDING:
        # Check if audio file exists
        audio_path = find_audio_file_for_sample(sample)
        has_audio = audio_path and audio_path.exists()

        # Prepare visualization data
        viz_data = prepare_visualization_data(sample)
        if sample.has_beat_info:
            viz_data['chords'] = [c for c in viz_data['chords'] if c.get('bar') and c['bar'] <= max_bars]
            viz_data['max_bars'] = max_bars

        # Render timeline (show "no audio" message only if audio truly unavailable)
        _render_timeline_only(viz_data, height, show_no_audio_message=not has_audio)

        # Show Play button if audio is available
        if has_audio:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("▶️ Play", key=f"play_{sample.id}", use_container_width=True):
                    with col2:
                        st.audio(str(audio_path))
        return

    # Find the audio file (handles CSV paths)
    audio_path = find_audio_file_for_sample(sample)
    if audio_path is None:
        st.warning(f"Audio file not found for: {sample.filepath}")
        # Still show timeline without audio
        viz_data = prepare_visualization_data(sample)
        if sample.has_beat_info:
            viz_data['chords'] = [c for c in viz_data['chords'] if c.get('bar') and c['bar'] <= max_bars]
            viz_data['max_bars'] = max_bars
        _render_timeline_only(viz_data, height, show_no_audio_message=True)
        return

    # Prepare data
    viz_data = prepare_visualization_data(sample)

    # Filter chords to max_bars if beat info is available
    if sample.has_beat_info:
        viz_data['chords'] = [c for c in viz_data['chords'] if c.get('bar') and c['bar'] <= max_bars]
        viz_data['max_bars'] = max_bars

    audio_data_url = encode_audio_base64(str(audio_path))

    # Generate HTML component - Unified visualization with waveform and chord timeline
    html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.min.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: transparent;
            padding: 10px;
        }}
        #unified-player {{
            width: 100%;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }}
        #waveform-layer {{
            width: 100%;
            height: 80px;
            position: relative;
            background: #f8f9fa;
            cursor: pointer;
        }}
        #chord-timeline {{
            width: 100%;
            height: 100px;
            position: relative;
            border-top: 1px solid #e0e0e0;
        }}
        #chord-canvas {{
            width: 100%;
            height: 100%;
        }}
        #controls-overlay {{
            position: absolute;
            top: 8px;
            left: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 6px 12px;
            border-radius: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        #play-btn {{
            background: #4a90d9;
            color: white;
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }}
        #play-btn:hover {{
            background: #357abd;
        }}
        #play-btn:active {{
            transform: scale(0.95);
        }}
        #time-display {{
            font-size: 12px;
            color: #333;
            font-variant-numeric: tabular-nums;
        }}
        #info-overlay {{
            position: absolute;
            top: 8px;
            right: 8px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 6px 12px;
            border-radius: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-size: 12px;
            color: #555;
        }}
        #info-overlay .chord-name {{
            font-weight: bold;
            color: #333;
            font-size: 14px;
        }}
        #info-overlay .roman {{
            color: darkblue;
            font-style: italic;
            margin-left: 4px;
        }}
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 80px;
            color: #666;
        }}
        .error {{
            color: #dc3545;
            padding: 20px;
            text-align: center;
        }}
        #bar-labels {{
            width: 100%;
            height: 18px;
            display: flex;
            border-top: 1px solid #e0e0e0;
            background: #fafafa;
        }}
        .bar-label {{
            flex: 1;
            text-align: center;
            font-size: 10px;
            font-weight: bold;
            color: #666;
            line-height: 18px;
            border-right: 1px solid #e0e0e0;
        }}
        .bar-label:last-child {{
            border-right: none;
        }}
    </style>
</head>
<body>
    <div id="unified-player">
        <!-- Waveform layer with controls overlay -->
        <div id="waveform-layer">
            <div class="loading">Loading waveform...</div>
            <div id="controls-overlay">
                <button id="play-btn" title="Play/Pause">▶</button>
                <span id="time-display">0:00 / 0:00</span>
            </div>
            <div id="info-overlay"></div>
        </div>

        <!-- Chord timeline layer (synchronized with waveform) -->
        <div id="chord-timeline">
            <canvas id="chord-canvas"></canvas>
        </div>

        <!-- Bar labels at bottom -->
        <div id="bar-labels"></div>
    </div>

    <script>
        // Data from Python
        const vizData = {json.dumps(viz_data)};
        const audioUrl = "{audio_data_url}";

        // Pastel colors for chords (matching matplotlib Pastel1)
        const CHORD_COLORS = [
            '#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6',
            '#ffffcc', '#e5d8bd', '#fddaec', '#f2f2f2'
        ];

        // State
        let wavesurfer = null;
        let isPlaying = false;
        let animationFrameId = null;
        const uniqueChordColors = new Map();
        let colorIndex = 0;

        // Preprocess chords to make them continuous (end-to-end)
        function preprocessChords() {{
            const chords = vizData.chords;
            for (let i = 0; i < chords.length; i++) {{
                if (i < chords.length - 1) {{
                    // Extend this chord's end to the next chord's start
                    chords[i].end = chords[i + 1].start;
                    // Update duration_beats if available
                    if (chords[i].duration_beats !== undefined && chords[i + 1].bar !== undefined) {{
                        const beatsPerBar = vizData.beats_per_bar || 4;
                        const thisStartBeat = (chords[i].bar - 1) * beatsPerBar + (chords[i].beat - 1);
                        const nextStartBeat = (chords[i + 1].bar - 1) * beatsPerBar + (chords[i + 1].beat - 1);
                        chords[i].duration_beats = nextStartBeat - thisStartBeat;
                    }}
                }} else {{
                    // Last chord - extend to end of audio duration
                    chords[i].end = vizData.duration_seconds || chords[i].end;
                    // For beat-based: extend to max bars
                    if (chords[i].duration_beats !== undefined && vizData.max_bars) {{
                        const beatsPerBar = vizData.beats_per_bar || 4;
                        const thisStartBeat = (chords[i].bar - 1) * beatsPerBar + (chords[i].beat - 1);
                        const totalBeats = vizData.max_bars * beatsPerBar;
                        chords[i].duration_beats = totalBeats - thisStartBeat;
                    }}
                }}
            }}
        }}

        // Get chord color (consistent across calls)
        function getChordColor(chordLabel) {{
            if (!uniqueChordColors.has(chordLabel)) {{
                uniqueChordColors.set(chordLabel, CHORD_COLORS[colorIndex % CHORD_COLORS.length]);
                colorIndex++;
            }}
            return uniqueChordColors.get(chordLabel);
        }}

        // Format time as m:ss
        function formatTime(seconds) {{
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${{mins}}:${{secs.toString().padStart(2, '0')}}`;
        }}

        // Get chord at current time
        function getChordAtTime(time) {{
            for (const chord of vizData.chords) {{
                if (time >= chord.start && time < chord.end) {{
                    return chord;
                }}
            }}
            return null;
        }}

        // Calculate beat position from time
        function timeToBeat(time) {{
            if (!vizData.estimated_bpm || !vizData.has_beat_info) return null;
            const beatDuration = 60.0 / vizData.estimated_bpm;
            const offset = vizData.first_beat_offset || 0;
            return (time - offset) / beatDuration;
        }}

        // Generate bar labels
        function generateBarLabels() {{
            const container = document.getElementById('bar-labels');
            const hasBeatInfo = vizData.has_beat_info && vizData.estimated_bpm;

            if (hasBeatInfo) {{
                const maxBars = vizData.max_bars || 16;
                for (let bar = 1; bar <= maxBars; bar++) {{
                    const label = document.createElement('div');
                    label.className = 'bar-label';
                    label.textContent = bar;
                    container.appendChild(label);
                }}
            }} else {{
                // Time-based: show seconds
                const duration = vizData.duration_seconds || 30;
                const numSegments = Math.min(Math.ceil(duration / 5), 6);
                for (let i = 0; i < numSegments; i++) {{
                    const label = document.createElement('div');
                    label.className = 'bar-label';
                    label.textContent = `${{i * 5}}s`;
                    container.appendChild(label);
                }}
            }}
        }}

        // Initialize WaveSurfer
        function initWaveSurfer() {{
            wavesurfer = WaveSurfer.create({{
                container: '#waveform-layer',
                waveColor: '#4a90d9',
                progressColor: '#1a5490',
                cursorColor: '#dc3545',
                cursorWidth: 2,
                height: 80,
                barWidth: 2,
                barGap: 1,
                barRadius: 2,
                responsive: true,
            }});

            wavesurfer.load(audioUrl);

            wavesurfer.on('ready', () => {{
                document.querySelector('#waveform-layer .loading')?.remove();
                updateTimeDisplay();
                drawChordTimeline(0);
            }});

            wavesurfer.on('play', () => {{
                isPlaying = true;
                document.getElementById('play-btn').textContent = '⏸';
                animate();
            }});

            wavesurfer.on('pause', () => {{
                isPlaying = false;
                document.getElementById('play-btn').textContent = '▶';
                if (animationFrameId) {{
                    cancelAnimationFrame(animationFrameId);
                }}
            }});

            wavesurfer.on('finish', () => {{
                isPlaying = false;
                document.getElementById('play-btn').textContent = '▶';
            }});

            wavesurfer.on('seek', () => {{
                const currentTime = wavesurfer.getCurrentTime();
                drawChordTimeline(currentTime);
                updateCurrentChordInfo(currentTime);
            }});

            wavesurfer.on('error', (err) => {{
                console.error('WaveSurfer error:', err);
                document.getElementById('waveform-layer').innerHTML =
                    '<div class="error">Could not load audio file</div>';
            }});
        }}

        // Update time display
        function updateTimeDisplay() {{
            const current = wavesurfer.getCurrentTime();
            const duration = wavesurfer.getDuration();
            document.getElementById('time-display').textContent =
                `${{formatTime(current)}} / ${{formatTime(duration)}}`;
        }}

        // Update current chord info display
        function updateCurrentChordInfo(time) {{
            const chord = getChordAtTime(time);
            const infoEl = document.getElementById('info-overlay');

            if (chord) {{
                const chordDisplay = chord.chord.replace(':', '');
                let html = `<span class="chord-name">${{chordDisplay}}</span>`;
                if (chord.roman_numeral) {{
                    html += `<span class="roman">(${{chord.roman_numeral}})</span>`;
                }}

                if (vizData.has_beat_info && chord.bar) {{
                    html = `Bar ${{chord.bar}} | ${{html}}`;
                }}

                infoEl.innerHTML = html;
            }} else {{
                infoEl.innerHTML = '';
            }}
        }}

        // Draw chord timeline on canvas (synchronized with waveform width)
        function drawChordTimeline(currentTime) {{
            const canvas = document.getElementById('chord-canvas');
            const ctx = canvas.getContext('2d');
            const rect = canvas.parentElement.getBoundingClientRect();

            // Set canvas size (high DPI)
            const dpr = window.devicePixelRatio || 1;
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = rect.width + 'px';
            canvas.style.height = rect.height + 'px';
            ctx.scale(dpr, dpr);

            const width = rect.width;
            const height = rect.height;

            // Clear
            ctx.fillStyle = '#fff';
            ctx.fillRect(0, 0, width, height);

            // Determine timeline mode
            const hasBeatInfo = vizData.has_beat_info && vizData.estimated_bpm;

            if (hasBeatInfo) {{
                drawBeatBasedChords(ctx, width, height, currentTime);
            }} else {{
                drawTimeBasedChords(ctx, width, height, currentTime);
            }}
        }}

        // Draw beat-based chord blocks (continuous, no gaps)
        function drawBeatBasedChords(ctx, width, height, currentTime) {{
            const beatsPerBar = vizData.beats_per_bar || 4;
            const maxBars = vizData.max_bars || 16;
            const totalBeats = maxBars * beatsPerBar;
            const beatWidth = width / totalBeats;
            const chordHeight = height - 10;
            const chordY = 5;

            // Draw beat markers (dashed lines)
            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 2]);

            for (let bar = 0; bar < maxBars; bar++) {{
                for (let beat = 1; beat < beatsPerBar; beat++) {{
                    const x = (bar * beatsPerBar + beat) * beatWidth;
                    ctx.beginPath();
                    ctx.moveTo(x, chordY);
                    ctx.lineTo(x, chordY + chordHeight);
                    ctx.stroke();
                }}
            }}
            ctx.setLineDash([]);

            // Draw bar lines (solid)
            ctx.strokeStyle = '#999';
            ctx.lineWidth = 1;

            for (let bar = 0; bar <= maxBars; bar++) {{
                const x = bar * beatsPerBar * beatWidth;
                ctx.beginPath();
                ctx.moveTo(x, chordY);
                ctx.lineTo(x, chordY + chordHeight);
                ctx.stroke();
            }}

            // Draw chord blocks (continuous)
            for (const chord of vizData.chords) {{
                if (!chord.bar || !chord.beat) continue;

                const startBeat = (chord.bar - 1) * beatsPerBar + (chord.beat - 1);
                const durationBeats = chord.duration_beats || 1;

                // Skip if out of visible range
                if (startBeat >= totalBeats) continue;

                const x = startBeat * beatWidth;
                const w = Math.min(durationBeats * beatWidth, width - x);
                const color = getChordColor(chord.chord);

                // Check if current
                const isCurrent = currentTime >= chord.start && currentTime < chord.end;

                // Draw filled rectangle (no gaps - fill entire width)
                ctx.fillStyle = color;
                ctx.fillRect(x, chordY, w, chordHeight);

                // Border
                ctx.strokeStyle = isCurrent ? '#dc3545' : '#888';
                ctx.lineWidth = isCurrent ? 2.5 : 1;
                ctx.strokeRect(x, chordY, w, chordHeight);

                // Labels (only if enough space)
                if (w > 30) {{
                    const centerX = x + w / 2;
                    const chordDisplay = chord.chord.replace(':', '');

                    if (chord.roman_numeral && w > 45) {{
                        // Two labels: chord name on top, Roman numeral below
                        ctx.fillStyle = '#333';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 - 6);

                        ctx.fillStyle = 'darkblue';
                        ctx.font = 'bold italic 12px sans-serif';
                        ctx.fillText(chord.roman_numeral, centerX, chordY + chordHeight / 2 + 10);
                    }} else {{
                        // Single centered label
                        ctx.fillStyle = '#333';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 + 4);
                    }}
                }}
            }}

            // Draw playhead (synchronized with waveform)
            if (vizData.estimated_bpm) {{
                const beatPos = timeToBeat(currentTime);
                if (beatPos !== null && beatPos >= 0 && beatPos <= totalBeats) {{
                    const x = beatPos * beatWidth;

                    ctx.strokeStyle = '#dc3545';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(x, 0);
                    ctx.lineTo(x, height);
                    ctx.stroke();
                }}
            }}
        }}

        // Draw time-based chord blocks (continuous, no gaps)
        function drawTimeBasedChords(ctx, width, height, currentTime) {{
            const duration = vizData.duration_seconds || wavesurfer?.getDuration() || 30;
            const displayDuration = Math.min(duration, 30);
            const pixelsPerSecond = width / displayDuration;
            const chordHeight = height - 10;
            const chordY = 5;

            // Draw time markers
            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 1;

            for (let t = 0; t <= displayDuration; t += 5) {{
                const x = t * pixelsPerSecond;
                ctx.beginPath();
                ctx.moveTo(x, chordY);
                ctx.lineTo(x, chordY + chordHeight);
                ctx.stroke();
            }}

            // Draw chord blocks (continuous)
            for (const chord of vizData.chords) {{
                if (chord.start > displayDuration) continue;

                const x = chord.start * pixelsPerSecond;
                const endX = Math.min(chord.end, displayDuration) * pixelsPerSecond;
                const w = endX - x;
                const color = getChordColor(chord.chord);

                const isCurrent = currentTime >= chord.start && currentTime < chord.end;

                // Rectangle (no gaps)
                ctx.fillStyle = color;
                ctx.fillRect(x, chordY, w, chordHeight);

                ctx.strokeStyle = isCurrent ? '#dc3545' : '#888';
                ctx.lineWidth = isCurrent ? 2.5 : 1;
                ctx.strokeRect(x, chordY, w, chordHeight);

                // Label
                if (w > 30) {{
                    const centerX = x + w / 2;
                    const chordDisplay = chord.chord.replace(':', '');

                    if (chord.roman_numeral && w > 45) {{
                        ctx.fillStyle = '#333';
                        ctx.font = 'bold 10px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 - 6);

                        ctx.fillStyle = 'darkblue';
                        ctx.font = 'bold italic 11px sans-serif';
                        ctx.fillText(chord.roman_numeral, centerX, chordY + chordHeight / 2 + 10);
                    }} else {{
                        ctx.fillStyle = '#333';
                        ctx.font = 'bold 10px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 + 4);
                    }}
                }}
            }}

            // Draw playhead
            if (currentTime >= 0 && currentTime <= displayDuration) {{
                const x = currentTime * pixelsPerSecond;

                ctx.strokeStyle = '#dc3545';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
                ctx.stroke();
            }}
        }}

        // Animation loop
        function animate() {{
            if (!isPlaying) return;

            const currentTime = wavesurfer.getCurrentTime();
            updateTimeDisplay();
            updateCurrentChordInfo(currentTime);
            drawChordTimeline(currentTime);

            animationFrameId = requestAnimationFrame(animate);
        }}

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            // Preprocess chords to make them continuous
            preprocessChords();

            // Generate bar labels
            generateBarLabels();

            // Initialize audio player
            initWaveSurfer();

            // Play/pause button
            document.getElementById('play-btn').addEventListener('click', () => {{
                wavesurfer.playPause();
            }});

            // Keyboard shortcut
            document.addEventListener('keydown', (e) => {{
                if (e.code === 'Space') {{
                    e.preventDefault();
                    wavesurfer.playPause();
                }}
            }});

            // Resize handler
            window.addEventListener('resize', () => {{
                if (wavesurfer) {{
                    const currentTime = wavesurfer.getCurrentTime();
                    drawChordTimeline(currentTime);
                }}
            }});
        }});
    </script>
</body>
</html>
'''

    components.html(html_content, height=height, scrolling=False)


def _render_timeline_only(viz_data: dict, height: int = 200, show_no_audio_message: bool = False) -> None:
    """
    Render a static chord timeline without audio waveform.

    Used as lightweight visualizer when audio embedding is disabled,
    or as fallback when audio file is not available.

    Args:
        viz_data: Visualization data dictionary
        height: Height of the component in pixels
        show_no_audio_message: Whether to show "Audio file not available" message
    """
    import json
    import streamlit.components.v1 as components

    # Conditionally include no-audio message
    no_audio_html = ''
    if show_no_audio_message:
        no_audio_html = '<div class="no-audio">Audio file not available - showing chord timeline only</div>'
        timeline_height = height - 60
    else:
        timeline_height = height - 40  # No message bar, just labels

    html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: transparent;
            padding: 10px;
        }}
        #unified-player {{
            width: 100%;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }}
        .no-audio {{
            padding: 8px 12px;
            background: #f8f9fa;
            color: #666;
            font-size: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        #chord-timeline {{
            width: 100%;
            height: {timeline_height}px;
            position: relative;
        }}
        #chord-canvas {{ width: 100%; height: 100%; }}
        #bar-labels {{
            width: 100%;
            height: 18px;
            display: flex;
            border-top: 1px solid #e0e0e0;
            background: #fafafa;
        }}
        .bar-label {{
            flex: 1;
            text-align: center;
            font-size: 10px;
            font-weight: bold;
            color: #666;
            line-height: 18px;
            border-right: 1px solid #e0e0e0;
        }}
        .bar-label:last-child {{ border-right: none; }}
    </style>
</head>
<body>
    <div id="unified-player">
        {no_audio_html}
        <div id="chord-timeline">
            <canvas id="chord-canvas"></canvas>
        </div>
        <div id="bar-labels"></div>
    </div>

    <script>
        const vizData = {json.dumps(viz_data)};

        const CHORD_COLORS = [
            '#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6',
            '#ffffcc', '#e5d8bd', '#fddaec', '#f2f2f2'
        ];

        const uniqueChordColors = new Map();
        let colorIndex = 0;

        // Preprocess chords to make them continuous (end-to-end)
        function preprocessChords() {{
            const chords = vizData.chords;
            for (let i = 0; i < chords.length; i++) {{
                if (i < chords.length - 1) {{
                    chords[i].end = chords[i + 1].start;
                    if (chords[i].duration_beats !== undefined && chords[i + 1].bar !== undefined) {{
                        const beatsPerBar = vizData.beats_per_bar || 4;
                        const thisStartBeat = (chords[i].bar - 1) * beatsPerBar + (chords[i].beat - 1);
                        const nextStartBeat = (chords[i + 1].bar - 1) * beatsPerBar + (chords[i + 1].beat - 1);
                        chords[i].duration_beats = nextStartBeat - thisStartBeat;
                    }}
                }} else {{
                    chords[i].end = vizData.duration_seconds || chords[i].end;
                    if (chords[i].duration_beats !== undefined && vizData.max_bars) {{
                        const beatsPerBar = vizData.beats_per_bar || 4;
                        const thisStartBeat = (chords[i].bar - 1) * beatsPerBar + (chords[i].beat - 1);
                        const totalBeats = vizData.max_bars * beatsPerBar;
                        chords[i].duration_beats = totalBeats - thisStartBeat;
                    }}
                }}
            }}
        }}

        function getChordColor(chordLabel) {{
            if (!uniqueChordColors.has(chordLabel)) {{
                uniqueChordColors.set(chordLabel, CHORD_COLORS[colorIndex % CHORD_COLORS.length]);
                colorIndex++;
            }}
            return uniqueChordColors.get(chordLabel);
        }}

        function generateBarLabels() {{
            const container = document.getElementById('bar-labels');
            const hasBeatInfo = vizData.has_beat_info && vizData.estimated_bpm;

            if (hasBeatInfo) {{
                const maxBars = vizData.max_bars || 16;
                for (let bar = 1; bar <= maxBars; bar++) {{
                    const label = document.createElement('div');
                    label.className = 'bar-label';
                    label.textContent = bar;
                    container.appendChild(label);
                }}
            }} else {{
                const duration = vizData.duration_seconds || 30;
                const numSegments = Math.min(Math.ceil(duration / 5), 6);
                for (let i = 0; i < numSegments; i++) {{
                    const label = document.createElement('div');
                    label.className = 'bar-label';
                    label.textContent = `${{i * 5}}s`;
                    container.appendChild(label);
                }}
            }}
        }}

        function drawTimeline() {{
            const canvas = document.getElementById('chord-canvas');
            const ctx = canvas.getContext('2d');
            const rect = canvas.parentElement.getBoundingClientRect();

            const dpr = window.devicePixelRatio || 1;
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = rect.width + 'px';
            canvas.style.height = rect.height + 'px';
            ctx.scale(dpr, dpr);

            const width = rect.width;
            const height = rect.height;

            ctx.fillStyle = '#fff';
            ctx.fillRect(0, 0, width, height);

            const hasBeatInfo = vizData.has_beat_info && vizData.estimated_bpm;

            if (hasBeatInfo) {{
                const beatsPerBar = vizData.beats_per_bar || 4;
                const maxBars = vizData.max_bars || 16;
                const totalBeats = maxBars * beatsPerBar;
                const beatWidth = width / totalBeats;
                const chordHeight = height - 10;
                const chordY = 5;

                // Beat markers (dashed)
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 2]);
                for (let bar = 0; bar < maxBars; bar++) {{
                    for (let beat = 1; beat < beatsPerBar; beat++) {{
                        const x = (bar * beatsPerBar + beat) * beatWidth;
                        ctx.beginPath();
                        ctx.moveTo(x, chordY);
                        ctx.lineTo(x, chordY + chordHeight);
                        ctx.stroke();
                    }}
                }}
                ctx.setLineDash([]);

                // Bar lines (solid)
                ctx.strokeStyle = '#999';
                ctx.lineWidth = 1;
                for (let bar = 0; bar <= maxBars; bar++) {{
                    const x = bar * beatsPerBar * beatWidth;
                    ctx.beginPath();
                    ctx.moveTo(x, chordY);
                    ctx.lineTo(x, chordY + chordHeight);
                    ctx.stroke();
                }}

                // Chord blocks (continuous, no gaps)
                for (const chord of vizData.chords) {{
                    if (!chord.bar || !chord.beat) continue;
                    const startBeat = (chord.bar - 1) * beatsPerBar + (chord.beat - 1);
                    const durationBeats = chord.duration_beats || 1;

                    if (startBeat >= totalBeats) continue;

                    const x = startBeat * beatWidth;
                    const w = Math.min(durationBeats * beatWidth, width - x);
                    const color = getChordColor(chord.chord);

                    ctx.fillStyle = color;
                    ctx.fillRect(x, chordY, w, chordHeight);
                    ctx.strokeStyle = '#888';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, chordY, w, chordHeight);

                    if (w > 30) {{
                        const centerX = x + w / 2;
                        const chordDisplay = chord.chord.replace(':', '');

                        if (chord.roman_numeral && w > 45) {{
                            ctx.fillStyle = '#333';
                            ctx.font = 'bold 10px sans-serif';
                            ctx.textAlign = 'center';
                            ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 - 6);
                            ctx.fillStyle = 'darkblue';
                            ctx.font = 'bold italic 11px sans-serif';
                            ctx.fillText(chord.roman_numeral, centerX, chordY + chordHeight / 2 + 10);
                        }} else {{
                            ctx.fillStyle = '#333';
                            ctx.font = 'bold 10px sans-serif';
                            ctx.textAlign = 'center';
                            ctx.fillText(chordDisplay, centerX, chordY + chordHeight / 2 + 4);
                        }}
                    }}
                }}
            }} else {{
                // Time-based fallback (continuous)
                const duration = vizData.duration_seconds || 30;
                const displayDuration = Math.min(duration, 30);
                const pixelsPerSecond = width / displayDuration;
                const chordHeight = height - 10;
                const chordY = 5;

                // Time markers
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                for (let t = 0; t <= displayDuration; t += 5) {{
                    const x = t * pixelsPerSecond;
                    ctx.beginPath();
                    ctx.moveTo(x, chordY);
                    ctx.lineTo(x, chordY + chordHeight);
                    ctx.stroke();
                }}

                // Chord blocks (continuous)
                for (const chord of vizData.chords) {{
                    if (chord.start > displayDuration) continue;
                    const x = chord.start * pixelsPerSecond;
                    const endX = Math.min(chord.end, displayDuration) * pixelsPerSecond;
                    const w = endX - x;
                    const color = getChordColor(chord.chord);

                    ctx.fillStyle = color;
                    ctx.fillRect(x, chordY, w, chordHeight);
                    ctx.strokeStyle = '#888';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, chordY, w, chordHeight);

                    if (w > 30) {{
                        const chordDisplay = chord.chord.replace(':', '');
                        ctx.fillStyle = '#333';
                        ctx.font = 'bold 10px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(chordDisplay, x + w / 2, chordY + chordHeight / 2 + 4);
                    }}
                }}
            }}
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            preprocessChords();
            generateBarLabels();
            drawTimeline();
        }});
        window.addEventListener('resize', drawTimeline);
    </script>
</body>
</html>
'''

    components.html(html_content, height=height, scrolling=False)


def render_sidebar():
    """Render the sidebar settings (database selection only)."""
    st.sidebar.title("🎵 Chord Analyzer")

    # Database selection
    st.sidebar.subheader("Database")

    # Find existing databases
    db_files = list(Path(".").glob("*.db")) + list(Path("output").glob("*.db") if Path("output").exists() else [])
    db_options = [str(f) for f in db_files] if db_files else ["samples.db"]

    db_path = st.sidebar.selectbox("Database", db_options, index=0)

    # Or enter custom path
    custom_db = st.sidebar.text_input("Or enter path")
    if custom_db:
        db_path = custom_db

    if Path(db_path).exists():
        conn = get_db_connection(db_path)
        stats = get_database_stats(conn)
        st.sidebar.success(f"✓ {stats['total_samples']} samples")
    else:
        st.sidebar.warning("Database not found")

    st.sidebar.divider()
    st.sidebar.caption("Chord Analysis & Sample Compatibility Matcher")

    st.sidebar.markdown(
        '<a href="https://github.com/geoffmyers/chord-analysis" '
        'target="_blank" rel="noopener noreferrer" '
        'style="display:inline-flex;align-items:center;gap:6px;'
        'text-decoration:none;">'
        '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" '
        'focusable="false" fill="currentColor">'
        '<path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55'
        '-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65'
        '-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67'
        '-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2'
        '-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06'
        ' 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15'
        '-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 '
        '1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 '
        '1 0 8c0-4.42 3.58-8 8-8Z"></path></svg>'
        "<span>View source on GitHub</span></a>",
        unsafe_allow_html=True,
    )

    return db_path


def render_dashboard(db_path: str):
    """Render the dashboard page with database statistics."""

    if not Path(db_path).exists():
        st.warning("No database found. Use the CLI to analyze samples first:")
        st.code("""# Extract chords from audio files
python -m chord_analyzer analyze \\
    --csv-dir ./chord_data \\
    --db samples.db \\
    --detect-tempo""", language="bash")
        return

    conn = get_db_connection(db_path)
    stats = get_database_stats(conn)

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Samples", stats["total_samples"])

    with col2:
        st.metric("Avg Duration", f"{stats['avg_duration']}s")

    with col3:
        tempo_count = stats.get("samples_with_tempo", 0)
        pct = (tempo_count / stats["total_samples"] * 100) if stats["total_samples"] > 0 else 0
        st.metric("With Tempo", f"{tempo_count} ({pct:.0f}%)")

    with col4:
        st.metric("Cached Scores", stats["cached_comparisons"])

    st.divider()

    # Charts row 1: Key Root and Scale
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔑 Samples by Key")
        key_roots = stats.get("key_roots", {})
        # Filter out zero counts and check if any data remains
        key_roots_filtered = {k: v for k, v in key_roots.items() if v > 0}
        if key_roots_filtered:
            import pandas as pd
            key_roots_df = pd.DataFrame(
                list(key_roots_filtered.items()),
                columns=["Key", "Count"]
            ).head(12)
            st.bar_chart(key_roots_df.set_index("Key"))
        else:
            st.info("No key data available")

    with col2:
        st.subheader("🎵 Samples by Scale")
        scales = stats.get("scales", {})
        # Filter out zero counts and check if any data remains
        scales_filtered = {k: v for k, v in scales.items() if v > 0}
        if scales_filtered:
            import pandas as pd
            scales_df = pd.DataFrame(
                list(scales_filtered.items()),
                columns=["Scale", "Count"]
            )
            st.bar_chart(scales_df.set_index("Scale"))
        else:
            st.info("No scale data available")

    st.divider()

    # Charts row 2: Chord Progressions
    st.subheader("🎼 Top Chord Progressions")
    progressions = stats.get("chord_progressions", {})
    # Filter out zero counts and check if any data remains
    progressions_filtered = {k: v for k, v in progressions.items() if v > 0}
    if progressions_filtered:
        import pandas as pd
        progressions_df = pd.DataFrame(
            list(progressions_filtered.items()),
            columns=["Progression", "Count"]
        ).head(10)
        st.bar_chart(progressions_df.set_index("Progression"))
    else:
        st.info("No chord progression data available")

    # Tempo distribution histogram
    tempo_dist = stats.get("tempo_distribution", {})
    # Filter out zero counts and check if any data remains
    tempo_filtered = {k: v for k, v in tempo_dist.items() if v > 0}
    if tempo_filtered:
        st.divider()
        st.subheader("🎚️ Samples by Tempo")
        import pandas as pd
        tempo_df = pd.DataFrame(
            list(tempo_filtered.items()),
            columns=["BPM Range", "Count"]
        )
        st.bar_chart(tempo_df.set_index("BPM Range"))
    elif stats.get("bpm_min"):
        # Fallback to basic stats if distribution not available
        st.divider()
        st.subheader("🎚️ Tempo Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Min BPM", f"{stats['bpm_min']:.0f}")
        with col2:
            st.metric("Avg BPM", f"{stats['bpm_avg']:.0f}")
        with col3:
            st.metric("Max BPM", f"{stats['bpm_max']:.0f}")


def get_sample_pack_name(filepath: str) -> str:
    """Extract sample pack name from filepath."""
    path = Path(filepath)
    parts = path.parts

    # Look for "Splice - Packs" or similar indicators
    for i, part in enumerate(parts):
        if part == "Splice - Packs" and i + 1 < len(parts):
            return parts[i + 1]
        elif part == "Splice Astra - Sounds" and i + 1 < len(parts):
            return parts[i + 1]
        elif part == "Splice Beatmaker - Presets" and i + 1 < len(parts):
            return parts[i + 1]

    # Fallback: try to find any "Packs", "Samples", or "Loops" folder
    for i, part in enumerate(parts):
        if part.lower() in ["packs", "samples", "loops"] and i + 1 < len(parts):
            return parts[i + 1]

    # Last fallback: return the parent directory of the file
    if len(parts) >= 2:
        return parts[-2]
    return "Unknown"


# Genre keywords mapped to genre categories
GENRE_KEYWORDS = {
    "Hip Hop": ["hip hop", "hip-hop", "hiphop", "boom bap", "trap", "lofi", "lo-fi", "lo fi", "type beat"],
    "House": ["house", "deep house", "tech house", "future house", "tropical house", "progressive house"],
    "Techno": ["techno", "tech house"],
    "R&B": ["r&b", "rnb", "r and b", "soul", "neo soul"],
    "Pop": ["pop", "synth pop", "indie pop"],
    "EDM": ["edm", "electro", "electronic", "dubstep", "drum and bass", "dnb", "d&b", "future bass"],
    "Jazz": ["jazz", "swing"],
    "Ambient": ["ambient", "chill", "chillwave", "chillout", "downtempo", "atmospheric"],
    "Rock": ["rock", "indie rock", "alternative"],
    "Latin": ["latin", "reggaeton", "bossa", "brazilian", "afro", "salsa"],
    "World": ["world", "ethnic", "tribal", "african", "indian", "middle eastern"],
    "Funk": ["funk", "funky", "disco"],
    "Reggae": ["reggae", "dub", "dancehall"],
    "Classical": ["classical", "orchestral", "cinematic", "film", "epic"],
    "Country": ["country", "folk", "acoustic"],
    "Metal": ["metal", "heavy"],
    "Experimental": ["experimental", "abstract", "glitch", "idm"],
}

# Instrument keywords mapped to instrument categories
INSTRUMENT_KEYWORDS = {
    "Piano": ["piano", "keys", "keyboard", "rhodes", "wurlitzer", "ep", "electric piano"],
    "Guitar": ["guitar", "gtr", "acoustic guitar", "electric guitar", "strat", "tele", "les paul"],
    "Synth": ["synth", "synthesizer", "pad", "lead", "arp", "arpegg", "analog", "digital"],
    "Strings": ["strings", "violin", "viola", "cello", "orchestra", "orchestral", "string"],
    "Brass": ["brass", "trumpet", "trombone", "horn", "sax", "saxophone"],
    "Bass": ["bass", "sub", "808", "low end"],
    "Drums": ["drum", "drums", "kick", "snare", "hihat", "hi-hat", "percussion", "perc"],
    "Organ": ["organ", "hammond", "b3", "church organ"],
    "Vocals": ["vocal", "vox", "voice", "choir", "acapella", "singing"],
    "Flute": ["flute", "woodwind", "clarinet", "oboe"],
    "Bells": ["bell", "bells", "chime", "glockenspiel", "vibraphone", "marimba", "xylophone"],
    "Plucks": ["pluck", "pizz", "pizzicato", "harp", "kalimba"],
    "FX": ["fx", "sfx", "effect", "riser", "impact", "sweep", "noise", "texture", "ambient"],
}


def extract_instruments(text: str) -> list[str]:
    """Extract instrument tags from text (pack name or filename)."""
    text_lower = text.lower()
    instruments = set()

    for instrument, keywords in INSTRUMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                instruments.add(instrument)
                break

    return sorted(instruments) if instruments else ["Other"]


def get_sample_instruments(filepath: str) -> list[str]:
    """Extract instruments from sample filepath (pack name + filename)."""
    pack_name = get_sample_pack_name(filepath)
    filename = Path(filepath).stem

    # Combine instruments from pack name and filename
    instruments = set(extract_instruments(pack_name))
    instruments.update(extract_instruments(filename))

    # Remove "Other" if we found real instruments
    if len(instruments) > 1 and "Other" in instruments:
        instruments.discard("Other")

    return sorted(instruments)


def extract_genres(text: str) -> list[str]:
    """Extract genre tags from text (pack name or filename)."""
    text_lower = text.lower()
    genres = set()

    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                genres.add(genre)
                break

    return sorted(genres) if genres else ["Other"]


def get_sample_genres(filepath: str) -> list[str]:
    """Extract genres from sample filepath (pack name + filename)."""
    pack_name = get_sample_pack_name(filepath)
    filename = Path(filepath).stem

    # Combine genres from pack name and filename
    genres = set(extract_genres(pack_name))
    genres.update(extract_genres(filename))

    # Remove "Other" if we found real genres
    if len(genres) > 1 and "Other" in genres:
        genres.discard("Other")

    return sorted(genres)


# Common chord progressions in Roman numeral format
COMMON_PROGRESSIONS = {
    # Classic progressions
    "I-IV-V-I": ["I", "IV", "V", "I"],
    "I-V-vi-IV": ["I", "V", "vi", "IV"],
    "I-vi-IV-V": ["I", "vi", "IV", "V"],
    "ii-V-I": ["ii", "V", "I"],
    "I-V-IV-I": ["I", "V", "IV", "I"],
    "I-IV-I-V": ["I", "IV", "I", "V"],
    "vi-IV-I-V": ["vi", "IV", "I", "V"],
    # Modal/modern progressions
    "I-bVII-IV": ["I", "bVII", "IV"],
    "i-bVII-bVI-V": ["i", "bVII", "bVI", "V"],
    "I-bIII-IV": ["I", "bIII", "IV"],
    # Two-chord vamps
    "I-IV": ["I", "IV"],
    "I-V": ["I", "V"],
    "IV-V": ["IV", "V"],
    "i-iv": ["i", "iv"],
    "I-vi": ["I", "vi"],
    # Patterns found in database
    "V-IV-V-IV": ["V", "IV", "V", "IV"],
    "IV-I-V-IV": ["IV", "I", "V", "IV"],
    "I-V-bIII-IV": ["I", "V", "bIII", "IV"],
    "bIII-IV-I": ["bIII", "IV", "I"],
}


def get_sample_roman_numerals(sample) -> list[str]:
    """Get Roman numeral progression for a sample."""
    if not sample.progression:
        return []
    key = sample.estimated_key
    if key:
        # Extract just the root note from key like "C major" or "C"
        key_root = key.split()[0] if " " in key else key
    else:
        key_root = None
    return progression_to_numerals(sample.progression, key_root)


def normalize_numeral(numeral: str) -> str:
    """Normalize Roman numeral for comparison (strip 7, °, + suffixes)."""
    # Remove common suffixes for matching
    return numeral.rstrip("7°+")


def matches_progression_pattern(sample_numerals: list[str], pattern: list[str]) -> bool:
    """Check if sample's numerals contain the pattern as a subsequence."""
    if not sample_numerals or not pattern:
        return False

    # Normalize both for comparison
    norm_sample = [normalize_numeral(n) for n in sample_numerals]
    norm_pattern = [normalize_numeral(p) for p in pattern]

    # Check if pattern appears as contiguous subsequence
    pattern_len = len(norm_pattern)
    for i in range(len(norm_sample) - pattern_len + 1):
        if norm_sample[i:i + pattern_len] == norm_pattern:
            return True

    return False


def render_sample_browser(db_path: str):
    """Render the sample browser page."""

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if not samples:
        st.info("No samples in database.")
        return

    # Pre-compute counts for filters
    from collections import Counter

    # Sample pack counts
    pack_counts = Counter(get_sample_pack_name(s.filepath) for s in samples)
    pack_options = [f"All Packs ({len(samples)})"] + [
        f"{pack} ({count})" for pack, count in sorted(pack_counts.items())
    ]

    # Genre counts (samples can have multiple genres)
    genre_counts: Counter = Counter()
    for s in samples:
        for genre in get_sample_genres(s.filepath):
            genre_counts[genre] += 1
    genre_options = [f"All Genres ({len(samples)})"] + [
        f"{genre} ({count})" for genre, count in sorted(genre_counts.items())
    ]

    # Instrument counts (samples can have multiple instruments)
    instrument_counts: Counter = Counter()
    for s in samples:
        for instrument in get_sample_instruments(s.filepath):
            instrument_counts[instrument] += 1
    instrument_options = [f"All Instruments ({len(samples)})"] + [
        f"{instrument} ({count})" for instrument, count in sorted(instrument_counts.items())
    ]

    # Split keys into root notes and scales
    # Parse estimated_key (e.g., "C major", "A minor") into components
    key_root_counts = Counter()
    scale_counts = Counter()

    for s in samples:
        if s.estimated_key:
            # Split "C major" -> "C" and "major"
            parts = s.estimated_key.split()
            if len(parts) >= 2:
                key_root = parts[0]  # "C", "A", "F#", etc.
                scale = parts[1].capitalize()  # "Major", "Minor"
                key_root_counts[key_root] += 1
                scale_counts[scale] += 1
            elif len(parts) == 1:
                # Just a root note without quality (rare)
                key_root_counts[parts[0]] += 1

    # Key root options (A, B, C, etc.)
    key_root_options = [f"All Keys ({len(samples)})"] + [
        f"{key_root} ({count})" for key_root, count in sorted(key_root_counts.items())
    ]

    # Scale options (Major, Minor)
    scale_options = [f"All Scales ({len(samples)})"] + [
        f"{scale} ({count})" for scale, count in sorted(scale_counts.items())
    ]

    # Progression counts (pre-compute Roman numerals for efficiency)
    sample_numerals_cache = {s.id: get_sample_roman_numerals(s) for s in samples}
    progression_counts: dict[str, int] = {}
    for prog_name, pattern in COMMON_PROGRESSIONS.items():
        count = sum(
            1 for s in samples
            if matches_progression_pattern(sample_numerals_cache.get(s.id, []), pattern)
        )
        progression_counts[prog_name] = count
    progression_options = [f"All Progressions ({len(samples)})"] + [
        f"{prog} ({count})" for prog, count in progression_counts.items()
    ]

    # Voicing type counts
    voicing_counts = Counter(s.voicing_type for s in samples if s.voicing_type)
    voicing_options = [f"All Voicing ({len(samples)})"] + [
        f"{voicing.title()} ({count})" for voicing, count in sorted(voicing_counts.items())
    ]

    # Filters row 1: Sample Pack, Genre, and Instrument
    col1, col2, col3 = st.columns(3)
    with col1:
        pack_selection = st.selectbox("📦 Sample Pack", pack_options)
    with col2:
        genre_selection = st.selectbox("🎸 Genre", genre_options)
    with col3:
        instrument_selection = st.selectbox("🎹 Instrument", instrument_options)

    # Filters row 2: Key, Scale, Progression, and Voicing
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        key_root_selection = st.selectbox("🔑 Key", key_root_options)
    with col2:
        scale_selection = st.selectbox("🎵 Scale", scale_options)
    with col3:
        progression_selection = st.selectbox("🎼 Progression", progression_options)
    with col4:
        voicing_selection = st.selectbox("🎚️ Voicing", voicing_options)

    # Filters row 3: BPM and Bars
    col1, col2 = st.columns(2)
    with col1:
        bpms = [s.estimated_bpm for s in samples if s.estimated_bpm]
        if bpms:
            min_bpm, max_bpm = int(min(bpms)), int(max(bpms))
            bpm_range = st.slider("🎚️ BPM Range", min_bpm, max_bpm, (min_bpm, max_bpm))
        else:
            bpm_range = None
    with col2:
        bars_list = [s.total_bars for s in samples if s.total_bars]
        if bars_list:
            min_bars, max_bars = int(min(bars_list)), int(max(bars_list))
            bars_range = st.slider("📊 Bars Range", min_bars, max_bars, (min_bars, max_bars))
        else:
            bars_range = None

    # Filters row 4: Search
    search = st.text_input("🔍 Search", placeholder="Filter by filename...")

    # Extract filter values (strip count suffix)
    def extract_filter_value(selection: str) -> str | None:
        """Extract the filter value by removing the count suffix."""
        if selection.startswith("All "):
            return None
        # Remove " (123)" suffix
        idx = selection.rfind(" (")
        return selection[:idx] if idx > 0 else selection

    pack_filter = extract_filter_value(pack_selection)
    genre_filter = extract_filter_value(genre_selection)
    instrument_filter = extract_filter_value(instrument_selection)
    key_root_filter = extract_filter_value(key_root_selection)
    scale_filter = extract_filter_value(scale_selection)
    progression_filter = extract_filter_value(progression_selection)
    voicing_filter = extract_filter_value(voicing_selection)

    # Apply filters
    filtered = samples
    if pack_filter:
        filtered = [s for s in filtered if get_sample_pack_name(s.filepath) == pack_filter]
    if genre_filter:
        filtered = [s for s in filtered if genre_filter in get_sample_genres(s.filepath)]
    if instrument_filter:
        filtered = [s for s in filtered if instrument_filter in get_sample_instruments(s.filepath)]
    if key_root_filter:
        # Filter by key root (e.g., "C", "A", "F#")
        filtered = [s for s in filtered if s.estimated_key and s.estimated_key.split()[0] == key_root_filter]
    if scale_filter:
        # Filter by scale (e.g., "Major", "Minor")
        filtered = [s for s in filtered if s.estimated_key and scale_filter.lower() in s.estimated_key.lower()]
    if progression_filter:
        pattern = COMMON_PROGRESSIONS[progression_filter]
        filtered = [s for s in filtered if matches_progression_pattern(sample_numerals_cache.get(s.id, []), pattern)]
    if voicing_filter:
        filtered = [s for s in filtered if s.voicing_type and s.voicing_type.lower() == voicing_filter.lower()]
    if bpm_range:
        filtered = [s for s in filtered if s.estimated_bpm and bpm_range[0] <= s.estimated_bpm <= bpm_range[1]]
    if bars_range:
        filtered = [s for s in filtered if s.total_bars and bars_range[0] <= s.total_bars <= bars_range[1]]
    if search:
        filtered = [s for s in filtered if search.lower() in s.filename.lower()]

    st.caption(f"Showing {len(filtered)} of {len(samples)} samples")

    # View toggle
    view_mode = st.radio(
        "View Mode",
        ["Card View", "Table View"],
        horizontal=True,
        key="browser_view_mode"
    )

    st.divider()

    # Table View
    if view_mode == "Table View":
        import pandas as pd

        # Prepare data for table
        table_data = []
        for sample in filtered[:100]:  # Show more in table view
            pack_name = get_sample_pack_name(sample.filepath)
            genres = ", ".join(get_sample_genres(sample.filepath))
            instruments = ", ".join(get_sample_instruments(sample.filepath))

            # Truncate progression for table
            prog_str = " → ".join(sample.progression[:4])
            if len(sample.progression) > 4:
                prog_str += "..."

            # Get Roman numerals
            numerals = get_sample_roman_numerals(sample)
            numeral_str = " → ".join(numerals[:4]) if numerals else ""
            if numerals and len(numerals) > 4:
                numeral_str += "..."

            # Format voicing type
            voicing_display = "—"
            if sample.voicing_type:
                voicing_type = sample.voicing_type.lower()
                if voicing_type == "monophonic":
                    voicing_display = "🎤 Mono"
                elif voicing_type == "polyphonic":
                    voicing_display = "🎹 Poly"
                elif voicing_type == "ambiguous":
                    voicing_display = "❓ Mixed"
                else:
                    voicing_display = sample.voicing_type

            # Split key into root and scale
            key_root = "—"
            scale = "—"
            if sample.estimated_key:
                parts = sample.estimated_key.split()
                if len(parts) >= 2:
                    key_root = parts[0]  # "C", "A", "F#"
                    scale = parts[1].capitalize()  # "Major", "Minor"
                elif len(parts) == 1:
                    key_root = parts[0]

            table_data.append({
                "Filename": sample.filename,
                "Pack": pack_name,
                "Genre": genres,
                "Instrument": instruments,
                "Key": key_root,
                "Scale": scale,
                "BPM": f"{sample.estimated_bpm:.0f}" if sample.estimated_bpm else "—",
                "Voicing": voicing_display,
                "Bars": f"{sample.total_bars}" if sample.total_bars else "—",
                "Duration": f"{sample.duration_seconds:.1f}s",
                "Chords": prog_str,
                "Roman": numeral_str,
                "ID": sample.id,
            })

        if table_data:
            df = pd.DataFrame(table_data)

            # Display table with interactive features
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Filename": st.column_config.TextColumn("🎵 Filename", width="large"),
                    "Pack": st.column_config.TextColumn("📦 Pack", width="medium"),
                    "Genre": st.column_config.TextColumn("🎸 Genre", width="medium"),
                    "Instrument": st.column_config.TextColumn("🎹 Instrument", width="medium"),
                    "Key": st.column_config.TextColumn("🔑 Key", width="small"),
                    "Scale": st.column_config.TextColumn("🎵 Scale", width="small"),
                    "BPM": st.column_config.TextColumn("🎚️ BPM", width="small"),
                    "Voicing": st.column_config.TextColumn("Voicing", width="small"),
                    "Bars": st.column_config.TextColumn("📊 Bars", width="small"),
                    "Duration": st.column_config.TextColumn("⏱️ Duration", width="small"),
                    "Chords": st.column_config.TextColumn("🎼 Chords", width="large"),
                    "Roman": st.column_config.TextColumn("Roman", width="medium"),
                    "ID": None,  # Hide ID column
                },
                height=600,
            )

            # Sample selection for actions
            st.divider()
            selected_id = st.number_input(
                "Enter Sample ID to play or find similar:",
                min_value=1,
                max_value=max(s.id for s in filtered),
                step=1,
                key="table_sample_select"
            )

            # Find the selected sample
            selected_sample = next((s for s in filtered if s.id == selected_id), None)

            if selected_sample:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"Selected: **{selected_sample.filename}**")
                    # Audio player
                    audio_path = Path(selected_sample.filepath)
                    if audio_path.exists():
                        try:
                            with open(audio_path, "rb") as f:
                                audio_bytes = f.read()
                            st.audio(audio_bytes, format=f"audio/{audio_path.suffix[1:]}")
                        except Exception:
                            st.caption("⚠️ Could not load audio")
                with col2:
                    if st.button("Find Similar", key=f"table_find_{selected_id}", use_container_width=True):
                        st.session_state.target_filepath = selected_sample.filepath
                        st.session_state.auto_search = True
                        st.session_state.active_tab = "Find Compatible"
                        st.rerun()

    # Card View (original display)
    else:
        for sample in filtered[:50]:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.write(f"**🎵 {sample.filename}**")
                    pack_name = get_sample_pack_name(sample.filepath)
                    genres = get_sample_genres(sample.filepath)
                    instruments = get_sample_instruments(sample.filepath)
                    st.caption(f"📦 {pack_name} · 🎸 {', '.join(genres)} · 🎹 {', '.join(instruments)}")

                with col2:
                    info_parts = []
                    if sample.estimated_key:
                        # Split key into root and scale
                        parts = sample.estimated_key.split()
                        if len(parts) >= 2:
                            info_parts.append(f"Key: {parts[0]} | Scale: {parts[1].capitalize()}")
                        elif len(parts) == 1:
                            info_parts.append(f"Key: {parts[0]}")
                    if sample.estimated_bpm:
                        info_parts.append(f"BPM: {sample.estimated_bpm:.0f}")
                    if sample.total_bars:
                        total_beats = sample.total_bars * sample.beats_per_bar
                        info_parts.append(f"Bars: {sample.total_bars} ({total_beats} beats)")
                    info_parts.append(f"Duration: {sample.duration_seconds:.1f}s")
                    st.caption(" | ".join(info_parts))

                with col3:
                    if st.button("Find Similar", key=f"find_{sample.id}", use_container_width=True):
                        st.session_state.target_filepath = sample.filepath
                        st.session_state.auto_search = True
                        st.session_state.active_tab = "Find Compatible"
                        st.rerun()

                # Interactive chord visualizer with waveform, timeline, and playback sync
                render_chord_visualizer(sample, height=230, max_bars=8)

                st.divider()


def render_find_compatible(db_path: str):
    """Render the compatibility finder page."""

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if not samples:
        st.info("No samples in database.")
        return

    # Target sample selection
    sample_options = {s.filename: s.filepath for s in samples}
    sample_list = list(sample_options.keys())

    # Check for pre-selected target (from "Find Similar" button)
    default_idx = 0
    pre_selected = False
    if "target_filepath" in st.session_state:
        for idx, name in enumerate(sample_list):
            if sample_options[name] == st.session_state.target_filepath:
                default_idx = idx
                pre_selected = True
                break

    # Show info banner if sample was pre-selected
    if pre_selected and st.session_state.get("auto_search"):
        st.info(f"🎯 Sample pre-selected from Sample Browser. Searching for compatible samples...")

    selected_name = st.selectbox(
        "Select Target Sample",
        sample_list,
        index=default_idx,
    )
    target_path = sample_options[selected_name]

    # Show target info
    target = get_sample_by_filepath(conn, target_path)
    if target:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            # Split key into root and scale
            if target.estimated_key:
                parts = target.estimated_key.split()
                if len(parts) >= 2:
                    st.write(f"**Key:** {parts[0]}")
                elif len(parts) == 1:
                    st.write(f"**Key:** {parts[0]}")
            else:
                st.write("**Key:** Unknown")
        with col2:
            # Display scale
            if target.estimated_key:
                parts = target.estimated_key.split()
                if len(parts) >= 2:
                    st.write(f"**Scale:** {parts[1].capitalize()}")
                else:
                    st.write("**Scale:** Unknown")
            else:
                st.write("**Scale:** Unknown")
        with col3:
            st.write(f"**BPM:** {target.estimated_bpm or 'Unknown'}")
        with col4:
            st.write(f"**Chords:** {len(target.progression)}")

        # Interactive chord visualizer with waveform, timeline, and playback sync
        render_chord_visualizer(target, height=230, max_bars=8)

    st.divider()

    # Options
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 50)
    with col2:
        limit = st.slider("Max Results", 5, 50, 20)
    with col3:
        use_rhythm = st.checkbox("Include Rhythm & Tempo",
                                  value=True,
                                  help="Compare beat patterns and tempo compatibility (requires beat/BPM data)")

    # Check if we should auto-search (triggered from Sample Browser "Find Similar" button)
    auto_search = st.session_state.pop("auto_search", False)

    # Clear cached results if search parameters changed
    if "compatible_search_params" in st.session_state:
        params = st.session_state.compatible_search_params
        if (params.get("target_path") != target_path or
            params.get("min_score") != min_score or
            params.get("limit") != limit or
            params.get("use_rhythm") != use_rhythm):
            # Parameters changed - clear cached results
            st.session_state.compatible_results = None

    # Find button
    if st.button("🔍 Find Compatible Samples", type="primary", use_container_width=True) or auto_search:
        with st.spinner("Searching for compatible samples..."):
            results = find_compatible_samples(
                conn,
                target_path,
                min_score=min_score,
                limit=limit,
                use_rhythm=use_rhythm,
            )

        # Store results in session state so they persist across reruns (e.g., when Play button is clicked)
        st.session_state.compatible_results = results
        st.session_state.compatible_search_params = {
            "target_path": target_path,
            "min_score": min_score,
            "limit": limit,
            "use_rhythm": use_rhythm,
        }

    # Retrieve results from session state (if they exist)
    results = st.session_state.get("compatible_results", None)

    # Display results
    if results is not None:
        if not results:
            st.warning(f"No matches found with score >= {st.session_state.compatible_search_params.get('min_score', 50)}")
        else:
            st.success(f"Found {len(results)} compatible samples!")

            # View toggle
            view_mode = st.radio(
                "View Mode",
                ["Card View", "Table View"],
                horizontal=True,
                key="compatible_view_mode"
            )

            st.divider()

            # Table View
            if view_mode == "Table View":
                import pandas as pd

                # Prepare data for table
                table_data = []
                for i, result in enumerate(results, 1):
                    score = result.overall_score

                    # Score emoji
                    if score >= 80:
                        emoji = "🟢"
                    elif score >= 60:
                        emoji = "🟡"
                    else:
                        emoji = "🟠"

                    # Truncate progression
                    prog_str = " → ".join(result.sample.progression[:4])
                    if len(result.sample.progression) > 4:
                        prog_str += "..."

                    # Get main score components
                    components_str = ""
                    if result.components:
                        top_components = sorted(
                            [(k, v) for k, v in result.components.items() if v != 0],
                            key=lambda x: abs(x[1]),
                            reverse=True
                        )[:3]
                        components_str = " | ".join([
                            f"{k.replace('_', ' ').title()}: {v:+.1f}"
                            for k, v in top_components
                        ])

                    # Get first reason
                    reason = result.reasons[0] if result.reasons else "—"

                    # Split key into root and scale
                    key_root = "—"
                    scale = "—"
                    if result.sample.estimated_key:
                        parts = result.sample.estimated_key.split()
                        if len(parts) >= 2:
                            key_root = parts[0]
                            scale = parts[1].capitalize()
                        elif len(parts) == 1:
                            key_root = parts[0]

                    table_data.append({
                        "ID": result.sample.id,
                        "Rank": f"{emoji} #{i}",
                        "Filename": result.sample.filename,
                        "Score": f"{score:.1f}",
                        "Key": key_root,
                        "Scale": scale,
                        "BPM": f"{result.sample.estimated_bpm:.0f}" if result.sample.estimated_bpm else "—",
                        "Duration": f"{result.sample.duration_seconds:.1f}s",
                        "Chords": prog_str,
                        "Components": components_str,
                        "Reason": reason,
                    })

                if table_data:
                    df = pd.DataFrame(table_data)

                    # Display table
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "ID": None,  # Hide ID column
                            "Rank": st.column_config.TextColumn("Rank", width="small"),
                            "Filename": st.column_config.TextColumn("🎵 Filename", width="large"),
                            "Score": st.column_config.TextColumn("💯 Score", width="small"),
                            "Key": st.column_config.TextColumn("🔑 Key", width="small"),
                            "Scale": st.column_config.TextColumn("🎵 Scale", width="small"),
                            "BPM": st.column_config.TextColumn("🎚️ BPM", width="small"),
                            "Duration": st.column_config.TextColumn("⏱️ Duration", width="small"),
                            "Chords": st.column_config.TextColumn("🎼 Chords", width="large"),
                            "Components": st.column_config.TextColumn("📊 Top Components", width="large"),
                            "Reason": st.column_config.TextColumn("💡 Reason", width="large"),
                        },
                        height=600,
                    )

                    # Sample selection for audio playback
                    st.divider()
                    if results:
                        selected_id = st.number_input(
                            "Enter Sample ID to play audio:",
                            min_value=1,
                            max_value=max(r.sample.id for r in results),
                            step=1,
                            key="table_compatible_select"
                        )

                        # Find the selected sample
                        selected_result = next((r for r in results if r.sample.id == selected_id), None)

                        if selected_result:
                            st.caption(f"Selected: **{selected_result.sample.filename}** (Score: {selected_result.overall_score:.1f})")
                            # Audio player
                            audio_path = Path(selected_result.sample.filepath)
                            if audio_path.exists():
                                try:
                                    with open(audio_path, "rb") as f:
                                        audio_bytes = f.read()
                                    st.audio(audio_bytes, format=f"audio/{audio_path.suffix[1:]}")
                                except Exception:
                                    st.caption("⚠️ Could not load audio")

            # Card View (original expander display)
            else:
                for i, result in enumerate(results, 1):
                    score = result.overall_score

                    # Color based on score
                    if score >= 80:
                        emoji = "🟢"
                    elif score >= 60:
                        emoji = "🟡"
                    else:
                        emoji = "🟠"

                    with st.expander(
                        f"{emoji} #{i} {result.sample.filename} — **{score:.1f}**/100",
                        expanded=(i <= 3),
                    ):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            # Score breakdown
                            if result.components:
                                st.write("**Score Components:**")
                                comp_cols = st.columns(3)
                                for idx, (comp, val) in enumerate(result.components.items()):
                                    if val != 0:
                                        with comp_cols[idx % 3]:
                                            label = comp.replace("_", " ").title()
                                            st.write(f"• {label}: {val:+.1f}")

                        with col2:
                            if result.sample.estimated_key:
                                # Split key into root and scale
                                parts = result.sample.estimated_key.split()
                                if len(parts) >= 2:
                                    st.write(f"**Key:** {parts[0]} | **Scale:** {parts[1].capitalize()}")
                                elif len(parts) == 1:
                                    st.write(f"**Key:** {parts[0]}")
                            if result.sample.estimated_bpm:
                                st.write(f"**BPM:** {result.sample.estimated_bpm:.0f}")
                            st.write(f"**Duration:** {result.sample.duration_seconds:.1f}s")

                        if result.reasons:
                            st.info("💡 " + " | ".join(result.reasons[:3]))

                        # Interactive chord visualizer with waveform, timeline, and playback sync
                        render_chord_visualizer(result.sample, height=230, max_bars=8)


def render_compare_samples(db_path: str):
    """Render the sample comparison page."""

    if not Path(db_path).exists():
        st.warning("No database found.")
        return

    conn = get_db_connection(db_path)
    samples = get_all_samples(conn)

    if len(samples) < 2:
        st.info("Need at least 2 samples to compare.")
        return

    sample_options = {s.filename: s for s in samples}
    sample_list = list(sample_options.keys())

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sample A")
        name_a = st.selectbox("Select", sample_list, key="cmp_a")
        sample_a = sample_options[name_a]

        # Split key into root and scale
        if sample_a.estimated_key:
            parts = sample_a.estimated_key.split()
            if len(parts) >= 2:
                st.write(f"**Key:** {parts[0]} | **Scale:** {parts[1].capitalize()}")
            elif len(parts) == 1:
                st.write(f"**Key:** {parts[0]}")
        else:
            st.write("**Key:** Unknown")
        st.write(f"**BPM:** {sample_a.estimated_bpm or 'Unknown'}")
        st.caption(f"{' → '.join(sample_a.progression[:6])}")

    with col2:
        st.subheader("Sample B")
        other_names = [n for n in sample_list if n != name_a]
        name_b = st.selectbox("Select", other_names, key="cmp_b")
        sample_b = sample_options[name_b]

        # Split key into root and scale
        if sample_b.estimated_key:
            parts = sample_b.estimated_key.split()
            if len(parts) >= 2:
                st.write(f"**Key:** {parts[0]} | **Scale:** {parts[1].capitalize()}")
            elif len(parts) == 1:
                st.write(f"**Key:** {parts[0]}")
        else:
            st.write("**Key:** Unknown")
        st.write(f"**BPM:** {sample_b.estimated_bpm or 'Unknown'}")
        st.caption(f"{' → '.join(sample_b.progression[:6])}")

    st.divider()

    if st.button("⚖️ Compare These Samples", type="primary", use_container_width=True):
        result = calculate_compatibility(sample_a.progression, sample_b.progression)

        score = result["overall"]

        # Display score with appropriate styling
        st.divider()

        if score >= 80:
            st.success(f"## Compatibility Score: {score:.1f}/100 🎉")
        elif score >= 60:
            st.warning(f"## Compatibility Score: {score:.1f}/100")
        elif score >= 40:
            st.info(f"## Compatibility Score: {score:.1f}/100")
        else:
            st.error(f"## Compatibility Score: {score:.1f}/100")

        # Transposition info
        if result.get("is_transposition"):
            interval = result.get("transposition_interval", 0)
            note = result.get("transposition_note", "")
            st.success(f"🎹 **Perfect Transposition!** These samples share the same chord pattern, transposed by {interval} semitones ({note})")

        st.divider()

        # Score breakdown
        st.subheader("Score Breakdown")

        components = result.get("components", {})
        cols = st.columns(len(components))

        for col, (comp, val) in zip(cols, components.items()):
            with col:
                label = comp.replace("_", " ").title()
                delta = f"{val:+.1f}" if val != 0 else "0"
                col.metric(label, f"{abs(val):.1f}", delta)

        # Reasons
        if result.get("reasons"):
            st.divider()
            st.subheader("Analysis Notes")
            for reason in result["reasons"]:
                st.write(f"• {reason}")


def main():
    """Main entry point."""
    db_path = render_sidebar()

    # Initialize active tab in session state
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Dashboard"

    # Navigation tabs at top of page
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📊 Dashboard", use_container_width=True, type="primary" if st.session_state.active_tab == "Dashboard" else "secondary"):
            st.session_state.active_tab = "Dashboard"
            st.rerun()

    with col2:
        if st.button("📁 Sample Browser", use_container_width=True, type="primary" if st.session_state.active_tab == "Sample Browser" else "secondary"):
            st.session_state.active_tab = "Sample Browser"
            st.rerun()

    with col3:
        if st.button("🔍 Find Compatible", use_container_width=True, type="primary" if st.session_state.active_tab == "Find Compatible" else "secondary"):
            st.session_state.active_tab = "Find Compatible"
            st.rerun()

    with col4:
        if st.button("⚖️ Compare Samples", use_container_width=True, type="primary" if st.session_state.active_tab == "Compare Samples" else "secondary"):
            st.session_state.active_tab = "Compare Samples"
            st.rerun()

    st.divider()

    # Render active tab content
    if st.session_state.active_tab == "Dashboard":
        render_dashboard(db_path)
    elif st.session_state.active_tab == "Sample Browser":
        render_sample_browser(db_path)
    elif st.session_state.active_tab == "Find Compatible":
        render_find_compatible(db_path)
    elif st.session_state.active_tab == "Compare Samples":
        render_compare_samples(db_path)


if __name__ == "__main__":
    main()

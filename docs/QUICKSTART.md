# Quick Start Guide - Chord Analysis Web UI

## TL;DR - Launch the Web UI

The fastest way to get started:

```bash
cd chord-analysis
./launch-web-ui.sh
```

That's it! The launcher handles everything automatically.

## What the Launcher Does

The launcher script (`launch-web-ui.sh` or `launch_web_ui.py`) performs these steps automatically:

1. **Checks Python version** - Ensures Python 3.9+ is installed
2. **Creates virtual environment** - Sets up isolated Python environment (if needed)
3. **Installs dependencies** - Installs Streamlit, Rich, Pandas, etc. (if needed)
4. **Detects database** - Finds your sample database automatically
5. **Launches web UI** - Opens Streamlit at http://localhost:8501

## Choose Your Launcher

### Option 1: Bash Launcher (Recommended for macOS/Linux)

```bash
# Make it executable (first time only)
chmod +x launch-web-ui.sh

# Launch
./launch-web-ui.sh
```

**Features:**
- Fast and lightweight
- Colored output
- Better error messages
- Native shell integration

### Option 2: Python Launcher (Cross-platform)

```bash
# Make it executable (first time only)
chmod +x launch_web_ui.py

# Launch
./launch_web_ui.py
# or
python launch_web_ui.py
```

**Features:**
- Works on Windows, macOS, Linux
- Python-based (no bash required)
- Same functionality as bash version

## Launcher Options

Both launchers support the same command-line options:

```bash
# Show help
./launch-web-ui.sh --help

# Custom database path
./launch-web-ui.sh --db ./output/my-samples.db

# Custom port
./launch-web-ui.sh --port 8080

# Custom host (for remote access)
./launch-web-ui.sh --host 0.0.0.0

# Don't open browser automatically
./launch-web-ui.sh --no-browser

# Combine options
./launch-web-ui.sh --db ./output/samples.db --port 8080 --no-browser
```

## What if I Don't Have a Database Yet?

The launcher will still work! It will:
1. Create an empty database (`samples.db`)
2. Launch the web UI
3. Show you instructions for analyzing samples

To analyze samples:

```bash
# Extract chords and build database
python -m chord_analyzer analyze \
    --audio-dir ~/Music/Samples \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db \
    --extract \
    --detect-tempo
```

Or if you already have CSV files from Chordino:

```bash
# Build database from existing CSVs
python -m chord_analyzer analyze \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db \
    --detect-tempo
```

## Troubleshooting

### "Python 3 not found"
Install Python 3.9 or higher:
- macOS: `brew install python@3.11`
- Linux: `sudo apt-get install python3.11`

### "Virtual environment creation failed"
Make sure you have `python3-venv` installed:
- Linux: `sudo apt-get install python3-venv`

### "Cannot find database"
Specify the database path explicitly:
```bash
./launch-web-ui.sh --db /path/to/your/database.db
```

### "Port already in use"
Use a different port:
```bash
./launch-web-ui.sh --port 8502
```

### Web UI shows "No samples in database"
You need to analyze some audio files first. See "What if I Don't Have a Database Yet?" above.

## Web UI Features

Once launched, the web UI provides:

### Dashboard
- Total samples count
- Average duration
- Tempo statistics
- Key distribution chart
- Time signature breakdown

### Sample Browser
- Filter by key (C major, A minor, etc.)
- Filter by BPM range
- Search by filename
- View chord progressions
- Quick "Find Compatible" button

### Find Compatible
- Select a target sample
- Set minimum compatibility score (0-100)
- Enable/disable rhythm pattern matching
- View detailed score breakdown
- See transposition information

### Compare Samples
- Side-by-side comparison
- Compatibility score with breakdown
- Transposition detection
- Detailed analysis reasons

## Next Steps

After launching the web UI:

1. **If you have samples**: Use the Sample Browser to explore
2. **Find matches**: Use Find Compatible to discover harmonically compatible samples
3. **Compare specific samples**: Use Compare Samples for detailed analysis
4. **Check the docs**: See README.md for advanced features

## Alternative: Manual Launch

If you prefer not to use the launcher scripts:

```bash
# Activate virtual environment manually
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Launch Streamlit directly
streamlit run chord_analyzer/web_app.py

# Or use the existing run_web.py
streamlit run run_web.py
```

## Getting Help

- **CLI help**: `python -m chord_analyzer --help`
- **Launcher help**: `./launch-web-ui.sh --help`
- **Check dependencies**: `python -m chord_analyzer check`
- **Full documentation**: See README.md and CLAUDE.md

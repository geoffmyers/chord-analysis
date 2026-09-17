# Web UI Launcher - Complete Guide

## What Was Created

Three new files to make launching the web UI effortless:

1. **`launch-web-ui.sh`** - Bash launcher (macOS/Linux)
2. **`launch_web_ui.py`** - Python launcher (cross-platform)
3. **`QUICKSTART.md`** - Quick start guide
4. **`LAUNCHER_COMPARISON.md`** - Detailed comparison of launch methods

Both launchers are **executable** and ready to use!

## One-Line Quick Start

```bash
./launch-web-ui.sh
```

That's it! The launcher handles everything.

## What the Launchers Do

### Automatic Setup (No manual intervention required)

✅ **Step 1: Check Python Version**
- Verifies Python 3.9+ is installed
- Shows friendly error if version too old

✅ **Step 2: Create Virtual Environment**
- Creates `venv/` directory if not present
- Activates the virtual environment
- Ensures isolated package installation

✅ **Step 3: Install Dependencies**
- Checks if packages are already installed
- Installs only what's needed:
  - streamlit (web UI framework)
  - rich (CLI formatting)
  - pandas (data handling)
  - matplotlib (visualizations)
  - librosa (optional, tempo detection)
- Upgrades pip automatically

✅ **Step 4: Detect Database**
- Searches for database files in:
  - `output/splice-samples.db`
  - `samples.db`
  - Any `*.db` file
- Shows sample count if database found
- Creates empty database if none found

✅ **Step 5: Launch Web UI**
- Starts Streamlit server
- Opens browser automatically
- Shows connection URL
- Provides keyboard shortcuts

### Sample Output

```
╔══════════════════════════════════════════════════════════╗
║         🎵  Chord Analysis Web UI Launcher  🎵          ║
╚══════════════════════════════════════════════════════════╝

[1/6] Checking Python version...
✓ Python 3.11 found

[2/6] Setting up virtual environment...
✓ Virtual environment exists

[3/6] Checking pip...
✓ pip up to date

[4/6] Installing dependencies...
✓ Dependencies already satisfied
  • librosa available (tempo detection enabled)

[5/6] Checking database...
✓ Database found: output/splice-samples.db
  • 142 samples loaded

[6/6] Launching web UI...

╔══════════════════════════════════════════════════════════╗
║  ✓ Web UI is starting!                                  ║
║  Open your browser to: http://localhost:8501            ║
║  Press Ctrl+C to stop                                   ║
╚══════════════════════════════════════════════════════════╝

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.0.2.100:8501
```

## Usage Examples

### Basic Launch

```bash
# Bash (recommended for macOS/Linux)
./launch-web-ui.sh

# Python (cross-platform)
python launch_web_ui.py
```

### With Options

```bash
# Custom database
./launch-web-ui.sh --db ./output/my-database.db

# Custom port
./launch-web-ui.sh --port 8080

# Don't open browser
./launch-web-ui.sh --no-browser

# Remote access (accessible from other computers)
./launch-web-ui.sh --host 0.0.0.0

# Combine multiple options
./launch-web-ui.sh --db ./output/samples.db --port 8080 --no-browser
```

### First-Time Setup

If you've never used the project before:

```bash
# 1. Navigate to the project
cd chord-analysis

# 2. Launch (will set up everything automatically)
./launch-web-ui.sh

# That's it! The launcher handles:
# - Virtual environment creation
# - Dependency installation
# - Database detection
# - Web UI startup
```

## Available Options

Both launchers support the same command-line options:

```
--db PATH        Path to database file (default: auto-detect)
                 Examples:
                   --db samples.db
                   --db ./output/splice-samples.db
                   --db /absolute/path/to/database.db

--port PORT      Port to run on (default: 8501)
                 Examples:
                   --port 8080
                   --port 3000

--host HOST      Host to bind to (default: localhost)
                 Examples:
                   --host localhost (local only)
                   --host 0.0.0.0 (accessible from network)

--no-browser     Don't open browser automatically
                 Useful for:
                   - Remote servers
                   - Scripted deployments
                   - Custom browser handling

--help           Show help message
```

## What If I Don't Have a Database?

No problem! The launcher will:
1. Create an empty database (`samples.db`)
2. Launch the web UI
3. Show instructions in the UI for analyzing samples

To create a database with samples:

```bash
# Option 1: Extract chords from audio files
python -m chord_analyzer analyze \
    --audio-dir ~/Music/Samples \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db \
    --extract \
    --detect-tempo \
    --recursive

# Option 2: Use existing Chordino CSV files
python -m chord_analyzer analyze \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db \
    --detect-tempo
```

## File Locations

After running the launcher, you'll have:

```
chord-analysis/
├── launch-web-ui.sh          ← Bash launcher (executable)
├── launch_web_ui.py           ← Python launcher (executable)
├── QUICKSTART.md              ← Quick start guide
├── LAUNCHER_COMPARISON.md     ← Detailed comparison
├── LAUNCHER_README.md         ← This file
│
├── venv/                      ← Virtual environment (auto-created)
│   ├── bin/
│   ├── lib/
│   └── ...
│
├── chord_analyzer/            ← Main package
│   └── web_app.py            ← Streamlit web UI
│
├── output/                    ← Output directory
│   ├── chord_data/           ← CSV chord files
│   └── samples.db            ← SQLite database
│
└── samples.db                 ← Alternative database location
```

## Troubleshooting

### Launcher Won't Start

**Check if file is executable:**
```bash
ls -la launch-web-ui.sh
# Should show: -rwxr-xr-x
```

**Make it executable:**
```bash
chmod +x launch-web-ui.sh
chmod +x launch_web_ui.py
```

**Try with explicit interpreter:**
```bash
bash launch-web-ui.sh
python3 launch_web_ui.py
```

### "Python 3 not found"

Install Python 3.9+:
```bash
# macOS
brew install python@3.11

# Linux (Ubuntu/Debian)
sudo apt-get install python3.11

# Verify
python3 --version
```

### "Cannot create virtual environment"

Install venv module:
```bash
# Linux
sudo apt-get install python3-venv

# macOS (usually included)
# If missing, reinstall Python via Homebrew
```

### Port Already in Use

Use a different port:
```bash
./launch-web-ui.sh --port 8502
```

Or stop the existing process:
```bash
# Find process using port 8501
lsof -i :8501

# Kill the process
kill <PID>
```

### Dependencies Won't Install

Try installing manually:
```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Database Not Found

Specify path explicitly:
```bash
./launch-web-ui.sh --db ./output/splice-samples.db
```

Or check where your database is:
```bash
find . -name "*.db" -type f
```

### Web UI Shows "No Samples"

You need to analyze audio files first:
```bash
# Check if database has samples
sqlite3 output/samples.db "SELECT COUNT(*) FROM samples;"

# If 0, analyze some files
python -m chord_analyzer analyze \
    --csv-dir ./output/chord_data \
    --db ./output/samples.db
```

## Performance Tips

### Speed Up Subsequent Launches

The launcher caches everything after first run:
- Virtual environment persists
- Dependencies don't reinstall
- Database connection is immediate

**First launch:** ~30 seconds (installs dependencies)
**Subsequent launches:** ~3 seconds

### Reduce Startup Time

If you're developing and launching frequently:
```bash
# Activate venv once
source venv/bin/activate

# Launch directly (no launcher overhead)
streamlit run chord_analyzer/web_app.py
```

### Clean Rebuild

If something is broken:
```bash
# Remove virtual environment
rm -rf venv

# Relaunch (will rebuild everything)
./launch-web-ui.sh
```

## Advanced Usage

### Run on Custom Port Range

```bash
# Try ports sequentially
for port in 8501 8502 8503; do
    ./launch-web-ui.sh --port $port && break
done
```

### Background Process

```bash
# Run in background
./launch-web-ui.sh --no-browser &

# Check if running
ps aux | grep streamlit

# Stop background process
pkill -f streamlit
```

### Remote Access Setup

```bash
# Launch on all interfaces
./launch-web-ui.sh --host 0.0.0.0 --port 8501

# Access from other computers
# http://<your-ip>:8501
```

### Integration with Development Workflow

```bash
#!/bin/bash
# start-dev.sh

# Start web UI in background
./launch-web-ui.sh --no-browser --port 8501 &
STREAMLIT_PID=$!

# Start your editor
code .

# Cleanup on exit
trap "kill $STREAMLIT_PID" EXIT
wait
```

## Help Commands

```bash
# Launcher help
./launch-web-ui.sh --help

# CLI tool help
python -m chord_analyzer --help

# Check dependencies
python -m chord_analyzer check

# Database stats
python -m chord_analyzer stats --db ./output/samples.db
```

## Next Steps

After launching the web UI:

1. **Explore the Dashboard** - See database statistics
2. **Browse Samples** - Filter by key, BPM, filename
3. **Find Compatible Samples** - Search for harmonic matches
4. **Compare Samples** - Detailed side-by-side analysis

For more details:
- **QUICKSTART.md** - Basic usage guide
- **LAUNCHER_COMPARISON.md** - Compare launch methods
- **README.md** - Full documentation
- **CLAUDE.md** - Development guidelines

## Support

If you encounter issues:

1. Check this README's Troubleshooting section
2. Verify Python version: `python3 --version`
3. Check dependencies: `python -m chord_analyzer check`
4. Try manual launch to isolate launcher issues
5. Check the main README.md for CLI usage

## Summary

The launcher scripts provide a **zero-configuration** way to start the web UI:

- **No manual setup required**
- **Automatic dependency management**
- **Database auto-detection**
- **Clear progress indicators**
- **Helpful error messages**
- **Cross-platform support**

Just run `./launch-web-ui.sh` and you're ready to go!

# Web UI Launcher Comparison

## Which Launcher Should I Use?

Quick recommendations:

- **macOS/Linux user?** → Use `./launch-web-ui.sh` (fastest)
- **Windows user?** → Use `python launch_web_ui.py`
- **Want maximum compatibility?** → Use `python launch_web_ui.py`
- **Already have environment set up?** → Use `streamlit run chord_analyzer/web_app.py`

## Detailed Comparison

| Feature | launch-web-ui.sh | launch_web_ui.py | Manual Launch |
|---------|-----------------|------------------|---------------|
| **Platform** | macOS, Linux | All platforms | All platforms |
| **Setup Required** | None | None | Virtual env + dependencies |
| **Auto Install Deps** | ✓ Yes | ✓ Yes | ✗ Manual |
| **Auto Detect DB** | ✓ Yes | ✓ Yes | Manual config |
| **Colored Output** | ✓ Yes | ✓ Yes | Basic |
| **Progress Messages** | ✓ Yes | ✓ Yes | Minimal |
| **Error Handling** | Excellent | Excellent | Manual |
| **Speed** | Fast | Fast | Fastest* |
| **Dependencies** | bash, python3 | python3 only | python3 + venv |

*Fastest if already set up

## Command Examples

### Launch with Defaults

**Bash:**
```bash
./launch-web-ui.sh
```

**Python:**
```bash
python launch_web_ui.py
```

**Manual:**
```bash
source venv/bin/activate
streamlit run chord_analyzer/web_app.py
```

### Launch with Custom Database

**Bash:**
```bash
./launch-web-ui.sh --db ./output/my-samples.db
```

**Python:**
```bash
python launch_web_ui.py --db ./output/my-samples.db
```

**Manual:**
```bash
source venv/bin/activate
export STREAMLIT_DB_PATH=./output/my-samples.db
streamlit run chord_analyzer/web_app.py
```

### Launch on Custom Port

**Bash:**
```bash
./launch-web-ui.sh --port 8080
```

**Python:**
```bash
python launch_web_ui.py --port 8080
```

**Manual:**
```bash
source venv/bin/activate
streamlit run chord_analyzer/web_app.py --server.port 8080
```

### Launch Without Opening Browser

**Bash:**
```bash
./launch-web-ui.sh --no-browser
```

**Python:**
```bash
python launch_web_ui.py --no-browser
```

**Manual:**
```bash
source venv/bin/activate
streamlit run chord_analyzer/web_app.py --server.headless=true
```

## What Each Launcher Does

### launch-web-ui.sh (Bash)

1. Validates Python 3.9+ installation
2. Creates/activates virtual environment
3. Upgrades pip
4. Installs missing dependencies
5. Auto-detects database file
6. Shows database statistics
7. Launches Streamlit with optimal settings
8. Opens browser automatically

**Output Example:**
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
```

### launch_web_ui.py (Python)

Identical functionality to bash version, but:
- Pure Python implementation
- Works on Windows
- Slightly slower startup
- More portable

**Output Example:**
```
════════════════════════════════════════════════════════════
       🎵  Chord Analysis Web UI Launcher  🎵
════════════════════════════════════════════════════════════

[1/6] Checking Python version...
✓ Python 3.11 found

[2/6] Setting up virtual environment...
✓ Virtual environment exists

[3/6] Checking pip...
✓ pip up to date

[4/6] Installing dependencies...
✓ Dependencies already satisfied
  ✓ librosa available (tempo detection enabled)

[5/6] Checking database...
✓ Database found: output/splice-samples.db
  ✓ 142 samples loaded

[6/6] Launching web UI...

══════════════════════════════════════════════════════════
  ✓ Web UI is starting!
  Open your browser to: http://localhost:8501
  Press Ctrl+C to stop
══════════════════════════════════════════════════════════
```

### Manual Launch

Requires manual setup:
1. Create virtual environment: `python3 -m venv venv`
2. Activate: `source venv/bin/activate`
3. Install deps: `pip install -r requirements.txt`
4. Run: `streamlit run chord_analyzer/web_app.py`

**Pros:**
- Full control over environment
- No launcher overhead
- Faster if already set up

**Cons:**
- Manual dependency management
- No auto-detection
- More setup steps

## Common Options

All launchers support these options:

| Option | Default | Description |
|--------|---------|-------------|
| `--db PATH` | Auto-detect | Path to SQLite database |
| `--port PORT` | 8501 | HTTP port to bind to |
| `--host HOST` | localhost | Host interface (use 0.0.0.0 for remote access) |
| `--no-browser` | false | Don't open browser automatically |
| `--help` | - | Show help message |

## Environment Variables

The launchers set these automatically:

```bash
STREAMLIT_DB_PATH=<detected-or-specified-db-path>
STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200
```

For manual launch, you can set these yourself:
```bash
export STREAMLIT_DB_PATH=./output/samples.db
export STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200
streamlit run chord_analyzer/web_app.py
```

## First-Time Setup

**Using Launchers (Recommended):**
```bash
cd python-scripts/chord-analysis
./launch-web-ui.sh  # That's it!
```

**Manual Setup:**
```bash
cd python-scripts/chord-analysis
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run chord_analyzer/web_app.py
```

## When to Use Each Method

### Use Automated Launchers When:
- First time using the tool
- Don't want to manage virtual environments
- Want automatic database detection
- Need consistent, reliable setup
- Sharing with others who aren't Python experts

### Use Manual Launch When:
- You're a Python developer
- Already have environment configured
- Want maximum control
- Integrating with CI/CD
- Using in production

## Troubleshooting

### Launcher Won't Run

**Bash launcher:**
```bash
# Make executable
chmod +x launch-web-ui.sh

# Check syntax
bash -n launch-web-ui.sh

# Run with explicit bash
bash launch-web-ui.sh
```

**Python launcher:**
```bash
# Make executable
chmod +x launch_web_ui.py

# Check syntax
python3 -m py_compile launch_web_ui.py

# Run with explicit python
python3 launch_web_ui.py
```

### "Command not found"

Make sure you're in the right directory:
```bash
cd python-scripts/chord-analysis
pwd  # Should show chord-analysis directory
ls -la launch*  # Should show executable files
```

### Virtual Environment Issues

Clean up and rebuild:
```bash
rm -rf venv
./launch-web-ui.sh  # Will recreate venv automatically
```

## Performance Comparison

Typical startup times on macOS M1:

| Method | First Run | Subsequent Runs |
|--------|-----------|-----------------|
| launch-web-ui.sh | ~30s | ~3s |
| launch_web_ui.py | ~35s | ~4s |
| Manual (already set up) | N/A | ~2s |

*First run includes venv creation and dependency installation
*Subsequent runs use existing environment

## Recommendation

For most users: **Start with `./launch-web-ui.sh`** (or `python launch_web_ui.py` on Windows)

It provides the best balance of:
- Ease of use
- Reliability
- Automatic setup
- Clear error messages
- Good performance

Switch to manual launch only if you need advanced customization or are developing on the project itself.

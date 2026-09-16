# Streamlit Configuration

This directory contains Streamlit configuration files.

## config.toml

The `config.toml` file configures Streamlit's behavior and suppresses benign warnings.

### Key Settings

**Logger Level: "error"**
- Suppresses benign Tornado WebSocket warnings
- These warnings occur when browsers disconnect (refresh, navigate away)
- They don't affect functionality - just console noise

**Common WebSocket Warnings (Now Suppressed):**
```
tornado.websocket.WebSocketClosedError
tornado.iostream.StreamClosedError: Stream is closed
Task exception was never retrieved
```

These are **harmless** and occur during normal operation when:
- User refreshes the page
- Browser navigates away
- WebSocket connection is interrupted
- Multiple browser tabs are open

### Other Settings

- `enableWebsocketCompression = true` - Improves performance
- `maxUploadSize = 200` - Allow up to 200MB file uploads
- `showErrorDetails = true` - Show full error details for debugging
- `gatherUsageStats = false` - Privacy: don't send usage data to Streamlit

## Additional Suppression

The `run_web.py` file also includes Python-level warning filters:

```python
# Suppress benign Tornado WebSocket warnings
warnings.filterwarnings("ignore", message=".*WebSocketClosedError.*")
warnings.filterwarnings("ignore", message=".*Stream is closed.*")

# Reduce Tornado logging verbosity
logging.getLogger("tornado.access").setLevel(logging.ERROR)
logging.getLogger("tornado.application").setLevel(logging.ERROR)
logging.getLogger("tornado.general").setLevel(logging.ERROR)
```

## Troubleshooting

If you need to see verbose logs for debugging:

1. **Temporarily enable verbose logging:**
   ```toml
   [logger]
   level = "info"  # or "debug" for maximum detail
   ```

2. **Or run Streamlit with verbose flag:**
   ```bash
   streamlit run run_web.py --logger.level=debug
   ```

3. **Remember to revert to "error" when done:**
   ```toml
   [logger]
   level = "error"
   ```

## Clean Console Output

With these settings, you should see a clean console:

```
✓ Web UI is starting!
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

Instead of the previous noisy output with WebSocket warnings.

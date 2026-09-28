# LanceLoop

LanceLoop is a local prototype for saving the **15 seconds before a button press** from a live camera. Version 2 separates video capture, HTTP routes, and the browser interface. It is a technical demo, not a payment or customer delivery system.

## Run

Requires Python 3.11+ and a webcam. On macOS, allow camera access to the terminal running Python when prompted.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The page shows camera status and buffer progress. Once ready, press **Save last 15 seconds**. Download links appear on the page, and files are stored in the ignored `clips/` directory. Stop the server with `Ctrl+C`.

The first webcam is selected by default. To use another webcam or a camera with an RTSP stream:

```bash
CAMERA_SOURCE=1 uvicorn app:app --host 127.0.0.1 --port 8000
CAMERA_SOURCE='rtsp://user:password@camera-address/stream' uvicorn app:app --host 127.0.0.1 --port 8000
```

`CAMERA_SOURCE` must supply a **continuous** stream. Keep real RTSP credentials outside source control. The app binds to localhost and has no user accounts or access control; do not expose it publicly. `CLIP_DIR` can override the storage directory.

## Structure

- `replay.py`: camera connection, rolling memory buffer, MP4 creation.
- `app.py`: local HTTP routes and application lifecycle.
- `web/`: browser interface.
- `tests/`: focused checks for the buffer and saved video.

Run the checks with:

```bash
python -m unittest discover -s tests -v
```

## Next validation

Keep the capture running for a full match and save replays at different moments. Check timing, framing, sustained frame rate, reconnection after a network interruption, and disk use. A court pilot also needs a camera with a documented continuous stream and a stable power source. Payment, private storage, email delivery, and a physical button are later steps.

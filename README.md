# LanceLoop

Prototype for saving the last 15 seconds of a live camera feed when someone presses a button. This is a local technical proof, not a payment or customer delivery system.

## Run locally

Requires Python 3.11+ and a webcam. On macOS, allow Terminal/Python camera access when prompted.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Wait at least 15 seconds, then press **Save replay**. MP4 clips appear in `clips/` and can be downloaded from the page.

`CAMERA_SOURCE` defaults to `0` (the first webcam). Set it to another device number or an RTSP URL to test a compatible network camera:

```bash
CAMERA_SOURCE='rtsp://user:password@camera-address/stream' uvicorn app:app --host 127.0.0.1 --port 8000
```

Keep RTSP credentials in the environment, never in source control. This prototype binds to localhost, has no authentication, and should not be exposed to the internet.

## What this proves

One local process reads the camera continuously and holds about 15 seconds of JPEG frames in memory. A button freezes the current frames and writes an MP4 without stopping capture. Before installing at a court, test frame rate, sustained capture, reconnection, disk use, camera positioning, and replay quality over a whole match. Payment, private storage, email delivery, and a physical court button are later steps.

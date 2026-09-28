"""Local webcam/RTSP replay proof of concept."""

from collections import deque
from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock, Thread
import time
from uuid import uuid4

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse


SECONDS = 15
TARGET_FPS = 15
CLIP_DIR = Path("clips")
CLIP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LanceLoop prototype")
frames: deque[tuple[float, bytes]] = deque()
frame_lock = Lock()
camera_error = "Camera is starting"
running = True


def source_value() -> int | str:
    source = os.getenv("CAMERA_SOURCE", "0")
    return int(source) if source.isdecimal() else source


def capture_loop() -> None:
    global camera_error
    source = source_value()
    while running:
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            camera_error = "Cannot open camera; check CAMERA_SOURCE and permissions"
            capture.release()
            time.sleep(2)
            continue

        camera_error = ""
        next_frame_at = time.monotonic()
        while running:
            ok, frame = capture.read()
            if not ok:
                camera_error = "Camera stream disconnected; reconnecting"
                break
            now = time.monotonic()
            if now < next_frame_at:
                continue
            next_frame_at = now + 1 / TARGET_FPS
            frame = cv2.resize(frame, (1280, 720))
            encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not encoded:
                continue
            with frame_lock:
                frames.append((now, jpeg.tobytes()))
                while frames and frames[0][0] < now - SECONDS:
                    frames.popleft()
        capture.release()
        time.sleep(1)


@app.on_event("startup")
def start_capture() -> None:
    Thread(target=capture_loop, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LanceLoop</title><style>body{font:18px system-ui;max-width:860px;margin:3rem auto;padding:0 1rem}
img{display:block;width:100%;background:#222}button{font:inherit;padding:.7rem 1rem;margin-top:1rem}
</style></head><body><h1>LanceLoop</h1><p>Local 15-second replay prototype</p>
<img src="/live" alt="Live camera"><button id="save">Save replay</button><p id="status"></p>
<script>document.querySelector('#save').onclick=async()=>{const status=document.querySelector('#status');
status.textContent='Saving…';try{const res=await fetch('/replays',{method:'POST'});
const data=await res.json();if(!res.ok)throw Error(data.detail);
status.innerHTML='Saved: ';const link=document.createElement('a');link.href=data.url;
link.textContent='Download replay';status.append(link)}catch(err){status.textContent=err.message}}</script></body></html>"""


@app.get("/health")
def health() -> dict:
    with frame_lock:
        buffered = len(frames)
        duration = frames[-1][0] - frames[0][0] if buffered > 1 else 0
    return {"camera_error": camera_error, "buffered_frames": buffered, "buffered_seconds": round(duration, 1)}


def live_frames():
    last_frame = None
    while True:
        with frame_lock:
            latest = frames[-1][1] if frames else None
        if latest and latest is not last_frame:
            last_frame = latest
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + latest + b"\r\n"
        time.sleep(1 / TARGET_FPS)


@app.get("/live")
def live() -> StreamingResponse:
    return StreamingResponse(live_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


def write_clip(snapshot: list[tuple[float, bytes]], destination: Path) -> None:
    duration = snapshot[-1][0] - snapshot[0][0]
    fps = min(TARGET_FPS, max(1, (len(snapshot) - 1) / duration))
    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
    if not writer.isOpened():
        raise RuntimeError("Cannot create MP4; check OpenCV video codec support")
    try:
        for _, jpeg in snapshot:
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            writer.write(image)
    finally:
        writer.release()


@app.post("/replays")
def save_replay() -> dict:
    with frame_lock:
        snapshot = list(frames)
    if len(snapshot) < 2 or snapshot[-1][0] - snapshot[0][0] < SECONDS - 1:
        raise HTTPException(409, "Wait 15 seconds for the replay buffer to fill")

    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8] + ".mp4"
    destination = CLIP_DIR / name
    try:
        write_clip(snapshot, destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(500, str(exc)) from exc
    return {"url": f"/replays/{name}", "seconds": round(snapshot[-1][0] - snapshot[0][0], 1)}


@app.get("/replays/{name}")
def download_replay(name: str) -> FileResponse:
    if "/" in name or "\\" in name or not name.endswith(".mp4"):
        raise HTTPException(404)
    path = CLIP_DIR / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4", filename=name)

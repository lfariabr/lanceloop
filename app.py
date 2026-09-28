"""HTTP interface for the local LanceLoop replay prototype."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from replay import CameraCapture, ClipStore, ReplayNotReady


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
camera = CameraCapture(os.getenv("CAMERA_SOURCE", "0"))
clips = ClipStore(Path(os.getenv("CLIP_DIR", ROOT / "clips")))


@asynccontextmanager
async def lifespan(_: FastAPI):
    camera.start()
    try:
        yield
    finally:
        camera.stop()


app = FastAPI(title="LanceLoop", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB / "index.html", media_type="text/html")


@app.get("/health")
def health() -> dict:
    return camera.status()


@app.get("/live")
def live() -> StreamingResponse:
    return StreamingResponse(
        camera.live_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.post("/replays")
def save_replay() -> dict:
    try:
        snapshot = camera.snapshot()
    except ReplayNotReady as exc:
        raise HTTPException(409, str(exc)) from exc

    try:
        filename = clips.save(snapshot)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"url": f"/replays/{filename}", "seconds": round(snapshot[-1][0] - snapshot[0][0], 1)}


@app.get("/replays/{filename}")
def download_replay(filename: str) -> FileResponse:
    path = clips.find(filename)
    if path is None:
        raise HTTPException(404, "Replay not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)

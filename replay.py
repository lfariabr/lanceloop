"""Capture a live camera and keep only its most recent frames in memory."""

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
import time
from uuid import uuid4

import cv2
import numpy as np


REPLAY_SECONDS = 15
TARGET_FPS = 15
FRAME_SIZE = (1280, 720)
MIN_READY_SECONDS = 14

Frame = tuple[float, bytes]


class ReplayNotReady(Exception):
    """The camera has not supplied a full replay window yet."""


def normalise_source(source: str) -> int | str:
    return int(source) if source.isdecimal() else source


def fit_frame(frame: np.ndarray) -> np.ndarray:
    """Letterbox wide or tall cameras without distorting the picture."""
    target_width, target_height = FRAME_SIZE
    height, width = frame.shape[:2]
    scale = min(target_width / width, target_height / height)
    resized = cv2.resize(frame, (round(width * scale), round(height * scale)))
    canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    left = (target_width - resized.shape[1]) // 2
    top = (target_height - resized.shape[0]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return canvas


class CameraCapture:
    def __init__(self, source: str):
        self.source = normalise_source(source)
        self._frames: deque[Frame] = deque()
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._error = "Connecting to camera"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._capture_loop, name="camera-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
            self._frames.clear()

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            capture = cv2.VideoCapture(self.source)
            if not capture.isOpened():
                self._set_error("Camera unavailable. Check its connection and permissions.")
                capture.release()
                self._stop.wait(2)
                continue

            with self._lock:
                self._error = ""
            next_frame_at = time.monotonic()
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    self._set_error("Camera disconnected. Reconnecting…")
                    break
                now = time.monotonic()
                if now < next_frame_at:
                    continue
                next_frame_at = now + 1 / TARGET_FPS
                encoded, jpeg = cv2.imencode(
                    ".jpg", fit_frame(frame), [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                if not encoded:
                    continue
                with self._lock:
                    self._frames.append((now, jpeg.tobytes()))
                    while self._frames and self._frames[0][0] < now - REPLAY_SECONDS:
                        self._frames.popleft()
            capture.release()
            self._stop.wait(1)

    def status(self) -> dict:
        with self._lock:
            count = len(self._frames)
            duration = self._frames[-1][0] - self._frames[0][0] if count > 1 else 0
            fresh = count > 0 and time.monotonic() - self._frames[-1][0] < 2
            connected = not self._error and fresh
            return {
                "connected": connected,
                "ready": connected and duration >= MIN_READY_SECONDS,
                "buffered_seconds": round(duration, 1),
                "replay_seconds": REPLAY_SECONDS,
                "error": self._error,
            }

    def snapshot(self) -> list[Frame]:
        with self._lock:
            if self._error or not self._frames or time.monotonic() - self._frames[-1][0] >= 2:
                raise ReplayNotReady("Camera is not connected")
            snapshot = list(self._frames)
        if snapshot[-1][0] - snapshot[0][0] < MIN_READY_SECONDS:
            raise ReplayNotReady("Wait for the 15-second replay buffer to fill")
        return snapshot

    def live_frames(self):
        previous = None
        while not self._stop.is_set():
            with self._lock:
                latest = self._frames[-1][1] if self._frames else None
            if latest is not None and latest is not previous:
                previous = latest
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + latest + b"\r\n"
            self._stop.wait(1 / TARGET_FPS)


class ClipStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, frames: list[Frame]) -> str:
        duration = frames[-1][0] - frames[0][0]
        fps = min(TARGET_FPS, max(1, (len(frames) - 1) / duration))
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}.mp4"
        path = self.directory / name
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, FRAME_SIZE
        )
        if not writer.isOpened():
            raise RuntimeError("Could not create MP4. Check video codec support.")
        try:
            for _, jpeg in frames:
                image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise RuntimeError("A camera frame could not be decoded")
                writer.write(image)
        except Exception:
            writer.release()
            path.unlink(missing_ok=True)
            raise
        writer.release()
        return name

    def find(self, name: str) -> Path | None:
        if Path(name).name != name or not name.endswith(".mp4"):
            return None
        path = self.directory / name
        return path if path.is_file() else None

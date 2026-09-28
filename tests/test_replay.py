import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

from replay import CameraCapture, ClipStore, ReplayNotReady, fit_frame


class ReplayTests(unittest.TestCase):
    def setUp(self):
        image = np.full((90, 160, 3), 120, dtype=np.uint8)
        _, encoded = cv2.imencode(".jpg", fit_frame(image))
        self.jpeg = encoded.tobytes()

    def test_buffer_requires_recent_full_window(self):
        camera = CameraCapture("0")
        with self.assertRaises(ReplayNotReady):
            camera.snapshot()

        now = time.monotonic()
        with camera._lock:
            camera._error = ""
            camera._frames.extend((now - 15 + offset, self.jpeg) for offset in range(16))
        self.assertTrue(camera.status()["ready"])
        self.assertEqual(len(camera.snapshot()), 16)

        with camera._lock:
            camera._frames.clear()
            camera._frames.extend((now - 30 + offset, self.jpeg) for offset in range(16))
        self.assertFalse(camera.status()["ready"])
        with self.assertRaises(ReplayNotReady):
            camera.snapshot()

    def test_saved_clip_is_readable(self):
        now = time.monotonic()
        frames = [(now - 15 + offset, self.jpeg) for offset in range(16)]
        with tempfile.TemporaryDirectory() as directory:
            store = ClipStore(Path(directory))
            name = store.save(frames)
            path = store.find(name)
            self.assertIsNotNone(path)
            capture = cv2.VideoCapture(str(path))
            self.assertTrue(capture.isOpened())
            self.assertEqual(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 16)
            self.assertEqual(int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), 1280)
            capture.release()
            self.assertIsNone(store.find("../" + name))


if __name__ == "__main__":
    unittest.main()

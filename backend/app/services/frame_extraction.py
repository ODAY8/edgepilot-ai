"""Pulls a single representative frame out of an uploaded video file.

Kept separate from vision.py on purpose: this module's only job is "get
a real image out of a video," so vision.py only ever has to deal with
"analyze an image" regardless of whether the original upload was a
photo or a video.
"""

import logging
import os
import tempfile

import cv2

logger = logging.getLogger("edgepilot.frame_extraction")


class FrameExtractionError(Exception):
    """Raised when a frame cannot be pulled from the given video bytes."""


def extract_frame(video_bytes: bytes, suffix: str = ".mp4") -> bytes:
    """Returns JPEG-encoded bytes of a representative (middle) frame.

    cv2.VideoCapture only reads from a file path, not an in-memory
    buffer, so the video is briefly written to a temp file.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        capture = cv2.VideoCapture(tmp_path)
        try:
            if not capture.isOpened():
                raise FrameExtractionError("Could not open uploaded video.")

            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame = max(frame_count // 2, 0)
            capture.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)

            ok, frame = capture.read()
            if not ok:
                # Some containers misreport frame count; fall back to the first frame.
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = capture.read()
            if not ok:
                raise FrameExtractionError("Could not read any frame from uploaded video.")

            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise FrameExtractionError("Could not encode extracted frame as JPEG.")

            return encoded.tobytes()
        finally:
            capture.release()
    except FrameExtractionError:
        raise
    except Exception as exc:
        logger.exception("Frame extraction failed.")
        raise FrameExtractionError(f"Frame extraction failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

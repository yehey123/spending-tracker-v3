"""OpenCV image preprocessing pipeline for OCR.

Stage 1 of the OCR pipeline (ocr-pipeline.md §Stage 1):
    PIL → grayscale → denoise → adaptive threshold → deskew → PIL
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

from PIL import Image


def preprocess(image: Image.Image) -> Image.Image:
    """OpenCV pipeline: RGB→grayscale → denoise → threshold → deskew.

    Args:
        image: Input PIL image in any mode.

    Returns:
        PIL image in grayscale mode ("L"), thresholded and deskewed.
    """
    if cv2 is None:  # pragma: no cover
        raise RuntimeError(
            "opencv-python-headless is required for image preprocessing. "
            "Install it with: pip install opencv-python-headless"
        )

    # Step 1: PIL → numpy; ensure RGB; convert to grayscale
    img_rgb = image.convert("RGB")
    arr = np.array(img_rgb)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Step 2: Upscale if the image is small — Tesseract needs ~300 DPI equivalent.
    # Screenshots from mobile banking apps are typically 72–96 DPI; 2× upscale
    # meaningfully improves character recognition without blowing up memory.
    h, w = gray.shape[:2]
    if max(h, w) < 2000:
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # Step 3: Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Step 4: Adaptive threshold — use a larger blockSize after upscaling so the
    # neighbourhood covers a similar physical area as before.
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=21,
        C=5,
    )

    # Step 4: Deskew
    deskewed = _deskew(thresholded)

    # Return numpy → PIL (mode "L")
    return Image.fromarray(deskewed, mode="L")


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Rotate the image to correct skew if angle is > 0.5 degrees."""
    # Find coordinates of non-zero (foreground) pixels
    coords = np.column_stack(np.where(gray > 0))

    if coords.shape[0] == 0:
        return gray

    # Fit a minimum area rectangle around the foreground pixels
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # minAreaRect returns angles in [-90, 0); convert to a meaningful skew
    # angle relative to horizontal
    if angle < -45:
        angle = 90 + angle

    # Only rotate if skew is significant
    if abs(angle) <= 0.5:
        return gray

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray,
        rotation_matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated

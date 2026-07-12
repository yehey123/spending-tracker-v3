import pytest
from PIL import Image
from unittest.mock import patch
import numpy as np


def test_preprocess_returns_pil_image():
    from src.domain.services.preprocessor import preprocess
    img = Image.new("RGB", (100, 100), color="white")
    result = preprocess(img)
    assert isinstance(result, Image.Image)


def test_preprocess_small_image_no_crash():
    from src.domain.services.preprocessor import preprocess
    img = Image.new("RGB", (10, 10), color="white")
    result = preprocess(img)
    assert isinstance(result, Image.Image)


def test_preprocess_grayscale_output():
    from src.domain.services.preprocessor import preprocess
    img = Image.new("RGB", (50, 50), color=(128, 128, 128))
    result = preprocess(img)
    assert result.mode == "L"


def test_deskew_skipped_if_angle_small():
    from src.domain.services.preprocessor import preprocess
    import cv2
    img = Image.new("RGB", (100, 100), color="white")
    # Patch minAreaRect to return near-zero angle — no rotation should occur
    fake_rect = ((50, 50), (80, 20), 0.3)
    with patch("cv2.minAreaRect", return_value=fake_rect), \
         patch("cv2.warpAffine") as mock_warp:
        preprocess(img)
    mock_warp.assert_not_called()

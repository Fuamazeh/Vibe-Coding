"""
vision_service.py
-----------------
Custom PyTorch CNN for parsing handwritten market lists and printed receipts.

Classes
-------
ReceiptParsingCNN
    Lightweight CNN that ingests a greyscale 224×224 image and outputs a
    structured 5-element regression vector:
        [commodity_class_logits(2), quantity(1), unit_price(1), confidence(1)]

    In a production training run the commodity_class_logits head would be
    replaced with a larger softmax over the full commodity catalogue; the
    quantity and price heads would regress to normalised FCFA/unit values.
    This scaffold exposes the correct architecture and inference path.

Exceptions
----------
VisionProcessingError
    Raised when an image payload is unreadable, blurred, or corrupt.

Functions
---------
parse_market_image(image_bytes: bytes) -> dict
    End-to-end inference wrapper.  Returns a pre-populated form-field dict or
    raises ``VisionProcessingError``.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import torch
import torch.nn as nn
from PIL import Image, UnidentifiedImageError
import torchvision.transforms as T

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence threshold below which a parse result is rejected
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class VisionProcessingError(Exception):
    """Raised when the CNN cannot reliably parse the supplied image."""
    pass


# ---------------------------------------------------------------------------
# CNN architecture
# ---------------------------------------------------------------------------

class ReceiptParsingCNN(nn.Module):
    """
    Convolutional feature extractor for receipt / market-list parsing.

    Input  : (batch, 1, 224, 224) greyscale tensor, values in [0, 1]
    Output : (batch, 5) — see module docstring for field mapping
    """

    def __init__(self) -> None:
        super().__init__()

        # -------------------------------------------------------------------
        # Feature extraction backbone
        # 3 conv blocks, each followed by BatchNorm → ReLU → MaxPool
        # -------------------------------------------------------------------
        self.features = nn.Sequential(
            # Block 1: 1 → 32 channels, 224→112
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 2: 32 → 64 channels, 112→56
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 3: 64 → 128 channels, 56→28
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
        )

        # -------------------------------------------------------------------
        # Global average pooling collapses spatial dims to (batch, 128)
        # -------------------------------------------------------------------
        self.global_avg_pool = nn.AdaptiveAvgPool2d((1, 1))

        # -------------------------------------------------------------------
        # Regression / classification head
        # -------------------------------------------------------------------
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(64, 5),   # [cls_logit_0, cls_logit_1, quantity, price, confidence]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        x = self.features(x)
        x = self.global_avg_pool(x)
        return self.classifier(x)


# ---------------------------------------------------------------------------
# Pre-processing pipeline
# ---------------------------------------------------------------------------

_TRANSFORM = T.Compose(
    [
        T.Grayscale(num_output_channels=1),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.5], std=[0.5]),
    ]
)

# ---------------------------------------------------------------------------
# Singleton model instance (lazy-loaded; weights not trained in this scaffold)
# ---------------------------------------------------------------------------

_model: ReceiptParsingCNN | None = None


def _get_model() -> ReceiptParsingCNN:
    global _model
    if _model is None:
        _model = ReceiptParsingCNN()
        _model.eval()
    return _model


# ---------------------------------------------------------------------------
# Public inference function
# ---------------------------------------------------------------------------

def parse_market_image(image_bytes: bytes) -> dict[str, Any]:
    """
    Run CNN inference on raw image bytes and return pre-populated form fields.

    Parameters
    ----------
    image_bytes : bytes
        Raw binary content of the uploaded image file (JPEG, PNG, etc.).

    Returns
    -------
    dict
        Keys: ``commodity_name``, ``quantity``, ``submitted_unit_price_fcfa``,
        ``neighborhood_name``, ``confidence``.  Values may be ``None`` when the
        model is uncertain about a specific field.

    Raises
    ------
    VisionProcessingError
        If the image is unreadable, corrupt, or the model's confidence falls
        below :data:`CONFIDENCE_THRESHOLD`.
    """
    # -----------------------------------------------------------------------
    # 1. Decode and pre-process the image
    # -----------------------------------------------------------------------
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning("Image decode failure: %s", exc)
        raise VisionProcessingError(
            "Could not parse image clearly. Please verify or enter fields manually."
        ) from exc

    try:
        tensor = _TRANSFORM(pil_image).unsqueeze(0)   # Add batch dim → (1,1,224,224)
    except Exception as exc:
        logger.warning("Image transform failure: %s", exc)
        raise VisionProcessingError(
            "Could not parse image clearly. Please verify or enter fields manually."
        ) from exc

    # -----------------------------------------------------------------------
    # 2. Forward pass (no gradient required at inference time)
    # -----------------------------------------------------------------------
    model = _get_model()
    try:
        with torch.no_grad():
            output = model(tensor)          # shape: (1, 5)
    except Exception as exc:
        logger.error("CNN forward-pass error: %s", exc)
        raise VisionProcessingError(
            "Could not parse image clearly. Please verify or enter fields manually."
        ) from exc

    # -----------------------------------------------------------------------
    # 3. Decode raw output vector
    # -----------------------------------------------------------------------
    raw        = output.squeeze(0)                       # shape: (5,)
    confidence = float(torch.sigmoid(raw[4]).item())     # normalise to [0,1]

    if confidence < CONFIDENCE_THRESHOLD:
        raise VisionProcessingError(
            "Could not parse image clearly. Please verify or enter fields manually."
        )

    # Commodity: argmax over first two logits
    commodity_idx  = int(torch.argmax(raw[:2]).item())
    commodity_name = ["Garri", "Spaghetti"][commodity_idx]

    # Quantity: clamp to a positive integer
    quantity = max(1, int(abs(raw[2].item())))

    # Price: clamp to a positive integer (de-normalised from model output)
    price = max(1, round(abs(float(raw[3].item())) * 1000))

    return {
        "commodity_name":            commodity_name,
        "quantity":                  quantity,
        "submitted_unit_price_fcfa": price,
        "neighborhood_name":         None,   # Spatial info not inferred by this model
        "confidence":                round(confidence, 4),
    }

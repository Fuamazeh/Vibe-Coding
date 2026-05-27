"""
test_vision_pipeline.py
-----------------------
TDD tests for Milestone 4:
  - ReceiptParsingCNN architecture
  - parse_market_image happy path + corrupt inputs
  - HTTP 422 from /api/submissions/upload-image
"""

import io
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from app.vision_service import (
    CONFIDENCE_THRESHOLD,
    ReceiptParsingCNN,
    VisionProcessingError,
    parse_market_image,
)


def _make_valid_png_bytes(width: int = 64, height: int = 64) -> bytes:
    img = Image.new("L", (width, height), color=128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# CNN architecture
# ---------------------------------------------------------------------------

class TestReceiptParsingCNNArchitecture:
    def test_model_instantiates(self):
        assert ReceiptParsingCNN() is not None

    def test_forward_output_shape(self):
        model = ReceiptParsingCNN()
        model.eval()
        with torch.no_grad():
            output = model(torch.zeros(1, 1, 224, 224))
        assert output.shape == (1, 5)

    def test_model_is_nn_module(self):
        assert isinstance(ReceiptParsingCNN(), torch.nn.Module)

    def test_batch_forward(self):
        model = ReceiptParsingCNN()
        model.eval()
        with torch.no_grad():
            output = model(torch.randn(4, 1, 224, 224))
        assert output.shape == (4, 5)


# ---------------------------------------------------------------------------
# Corrupt inputs
# ---------------------------------------------------------------------------

class TestVisionCorruptInput:
    def test_random_bytes_raises_vision_error(self):
        with pytest.raises(VisionProcessingError):
            parse_market_image(b"this is not an image at all")

    def test_empty_bytes_raises_vision_error(self):
        with pytest.raises(VisionProcessingError):
            parse_market_image(b"")

    def test_truncated_jpeg_raises_vision_error(self):
        with pytest.raises(VisionProcessingError):
            parse_market_image(b"\xff\xd8\xff\xe0" + b"\x00" * 20)


# ---------------------------------------------------------------------------
# Happy path (mocked high-confidence output)
# ---------------------------------------------------------------------------

class TestVisionHappyPath:
    def _high_conf(self):
        return torch.tensor([[1.0, 0.0, 3.0, 0.5, 10.0]])

    def test_valid_image_with_mocked_model_returns_dict(self):
        with patch("app.vision_service._get_model") as m:
            m.return_value = MagicMock(return_value=self._high_conf())
            result = parse_market_image(_make_valid_png_bytes())
        assert all(k in result for k in ("commodity_name", "quantity", "submitted_unit_price_fcfa", "confidence"))

    def test_result_commodity_name_is_valid(self):
        with patch("app.vision_service._get_model") as m:
            m.return_value = MagicMock(return_value=self._high_conf())
            result = parse_market_image(_make_valid_png_bytes())
        assert result["commodity_name"] in ("Garri", "Spaghetti")

    def test_result_quantity_is_positive(self):
        with patch("app.vision_service._get_model") as m:
            m.return_value = MagicMock(return_value=self._high_conf())
            result = parse_market_image(_make_valid_png_bytes())
        assert isinstance(result["quantity"], int) and result["quantity"] >= 1

    def test_low_confidence_output_raises_vision_error(self):
        low_conf = torch.tensor([[1.0, 0.0, 3.0, 0.5, -10.0]])
        with patch("app.vision_service._get_model") as m:
            m.return_value = MagicMock(return_value=low_conf)
            with pytest.raises(VisionProcessingError):
                parse_market_image(_make_valid_png_bytes())


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

class TestVisionHTTPLayer:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.database import Base, get_db
        from app.main import app
        from app.seed import seed_initial_data

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine)

        def override_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        db = TestSession()
        seed_initial_data(db)
        db.close()

        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    def test_corrupt_image_upload_returns_422(self, client):
        r = client.post("/api/submissions/upload-image",
                        files={"file": ("test.jpg", b"garbage_data_!!!", "image/jpeg")})
        assert r.status_code == 422

    def test_422_error_message_matches_spec(self, client):
        r = client.post("/api/submissions/upload-image",
                        files={"file": ("test.jpg", b"bad", "image/jpeg")})
        assert r.status_code == 422
        assert "Could not parse image clearly" in r.json()["detail"]
        assert "manually" in r.json()["detail"]

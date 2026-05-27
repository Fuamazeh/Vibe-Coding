"""
test_submissions_api.py
-----------------------
Integration tests for Milestone 2:
  POST /api/submissions  — happy path + error cases
  POST /api/submissions/upload-image — vision endpoint
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_initial_data
from app.models import Commodity, Neighborhood


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def test_db_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def seeded_client(test_db_engine):
    TestingSession = sessionmaker(bind=test_db_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSession()
    seed_initial_data(session)
    session.close()

    with TestClient(app) as client:
        yield client, TestingSession

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_garri_id(Session):
    db = Session()
    garri = db.query(Commodity).filter_by(name="Garri").first()
    db.close()
    return garri.id


def get_molyko_id(Session):
    db = Session()
    molyko = db.query(Neighborhood).filter_by(name="Molyko").first()
    db.close()
    return molyko.id


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestSubmissionHappyPath:
    def test_fair_price_returns_green(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": 100, "neighborhood_id": get_molyko_id(Session),
        })
        assert response.status_code == 201
        body = response.json()
        assert body["ui_color_code"] == "GREEN"
        assert body["is_anomaly"] is False
        assert body["calculated_threshold"] == 110

    def test_gouged_price_returns_red(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": 150, "neighborhood_id": get_molyko_id(Session),
        })
        assert response.status_code == 201
        assert response.json()["ui_color_code"] == "RED"

    def test_threshold_boundary_at_exact_threshold(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": 110, "neighborhood_id": get_molyko_id(Session),
        })
        assert response.status_code == 201
        assert response.json()["ui_color_code"] == "GREEN"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestSubmissionValidation:
    def test_unknown_commodity_returns_400(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": 99999, "quantity": 1,
            "submitted_unit_price_fcfa": 100, "neighborhood_id": get_molyko_id(Session),
        })
        assert response.status_code == 400
        assert "not listed in the system" in response.json()["detail"]

    def test_missing_neighborhood_raises_validation_error(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": 100,
        })
        assert response.status_code == 422

    def test_negative_price_rejected(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": -50, "neighborhood_id": get_molyko_id(Session),
        })
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# "Other" neighbourhood triage
# ---------------------------------------------------------------------------

class TestCustomNeighborhood:
    def test_custom_neighborhood_saved_as_unapproved(self, seeded_client):
        client, Session = seeded_client
        response = client.post("/api/submissions", json={
            "commodity_id": get_garri_id(Session), "quantity": 1,
            "submitted_unit_price_fcfa": 100, "custom_neighborhood_name": "Bomaka",
        })
        assert response.status_code == 201
        body = response.json()
        assert body["neighborhood_name"] == "Bomaka"
        assert body["neighborhood_is_approved"] is False

    def test_custom_neighborhood_dedup(self, seeded_client):
        client, Session = seeded_client
        for _ in range(2):
            client.post("/api/submissions", json={
                "commodity_id": get_garri_id(Session), "quantity": 1,
                "submitted_unit_price_fcfa": 100, "custom_neighborhood_name": "Mile 16",
            })
        db = Session()
        count = db.query(Neighborhood).filter_by(name="Mile 16").count()
        db.close()
        assert count == 1


# ---------------------------------------------------------------------------
# Multi-user coexistence
# ---------------------------------------------------------------------------

class TestMultiUserCoexistence:
    def test_two_users_both_records_saved(self, seeded_client):
        client, Session = seeded_client
        from app.models import PriceSubmission
        db = Session()
        before = db.query(PriceSubmission).count()
        db.close()
        for price in [100, 170]:
            r = client.post("/api/submissions", json={
                "commodity_id": get_garri_id(Session), "quantity": 1,
                "submitted_unit_price_fcfa": price, "neighborhood_id": get_molyko_id(Session),
            })
            assert r.status_code == 201
        db = Session()
        after = db.query(PriceSubmission).count()
        db.close()
        assert after - before == 2


# ---------------------------------------------------------------------------
# Vision upload route
# ---------------------------------------------------------------------------

class TestVisionUploadRoute:
    def test_corrupt_bytes_returns_422(self, seeded_client):
        client, _ = seeded_client
        r = client.post("/api/submissions/upload-image",
                        files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")})
        assert r.status_code == 422
        assert "parse image" in r.json()["detail"].lower()

    def test_empty_bytes_returns_422(self, seeded_client):
        client, _ = seeded_client
        r = client.post("/api/submissions/upload-image",
                        files={"file": ("empty.jpg", b"", "image/jpeg")})
        assert r.status_code == 422

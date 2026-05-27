"""
test_analytics_engine.py
------------------------
TDD tests for Milestone 3:
  - 24-hour aggregation grouping
  - ±2 σ outlier pruning
  - GET /api/analytics/heatmap endpoint
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.aggregation_service import _prune_outliers, aggregate_daily_heatmap_data
from app.database import Base, get_db
from app.main import app
from app.models import Commodity, Neighborhood, PriceSubmission
from app.seed import seed_initial_data

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def Session(test_engine):
    return sessionmaker(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def seeded_session(Session):
    db = Session()
    seed_initial_data(db)
    yield db
    db.close()


@pytest.fixture(scope="module")
def http_client(test_engine, Session, seeded_session):
    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def get_entity_ids(Session):
    db = Session()
    garri  = db.query(Commodity).filter_by(name="Garri").first()
    molyko = db.query(Neighborhood).filter_by(name="Molyko").first()
    db.close()
    return garri.id, molyko.id


# ---------------------------------------------------------------------------
# Outlier pruning unit tests
# ---------------------------------------------------------------------------

class TestOutlierPruning:
    def test_obvious_outlier_removed(self):
        prices = [100, 105, 98, 102, 101, 99, 100, 103, 97, 104, 2500]
        assert 2500 not in _prune_outliers(prices)

    def test_normal_cluster_unchanged(self):
        prices = [100, 101, 99, 100, 102]
        assert sorted(_prune_outliers(prices)) == sorted(prices)

    def test_single_entry_returned_as_is(self):
        assert _prune_outliers([150]) == [150]

    def test_two_identical_entries_unchanged(self):
        assert _prune_outliers([100, 100]) == [100, 100]

    def test_all_entries_equal_unchanged(self):
        assert _prune_outliers([200, 200, 200, 200]) == [200, 200, 200, 200]


# ---------------------------------------------------------------------------
# Aggregation pipeline tests
# ---------------------------------------------------------------------------

class TestAggregateDailyHeatmap:
    def _seed_submissions(self, db, commodity_id, neighborhood_id, prices):
        for price in prices:
            db.add(PriceSubmission(
                commodity_id=commodity_id,
                neighborhood_id=neighborhood_id,
                quantity=1,
                submitted_unit_price_fcfa=price,
                calculated_threshold_fcfa=110,
                is_anomaly=price > 110,
                created_at=datetime.utcnow() - timedelta(minutes=30),
            ))
        db.commit()

    def test_aggregate_returns_entries(self, Session):
        db = Session()
        garri_id, molyko_id = get_entity_ids(Session)
        self._seed_submissions(db, garri_id, molyko_id, [100, 105, 102])
        results = aggregate_daily_heatmap_data(db)
        db.close()
        assert len(results) >= 1

    def test_outlier_excluded_from_mean(self, Session):
        db = Session()
        garri_id, molyko_id = get_entity_ids(Session)
        self._seed_submissions(db, garri_id, molyko_id,
                               [100, 105, 98, 102, 101, 99, 100, 103, 97, 104, 2500])
        results = aggregate_daily_heatmap_data(db)
        db.close()
        cluster = next(
            (r for r in results if r["commodity_id"] == garri_id and r["neighborhood_id"] == molyko_id),
            None,
        )
        assert cluster is not None
        assert cluster["mean_price_fcfa"] < 200

    def test_underlying_records_not_deleted(self, Session):
        db = Session()
        before = db.query(PriceSubmission).count()
        aggregate_daily_heatmap_data(db)
        after = db.query(PriceSubmission).count()
        db.close()
        assert after == before

    def test_old_submissions_excluded(self, Session):
        db = Session()
        garri_id, molyko_id = get_entity_ids(Session)
        db.add(PriceSubmission(
            commodity_id=garri_id, neighborhood_id=molyko_id,
            quantity=1, submitted_unit_price_fcfa=9999,
            calculated_threshold_fcfa=110, is_anomaly=True,
            created_at=datetime.utcnow() - timedelta(hours=25),
        ))
        db.commit()
        results = aggregate_daily_heatmap_data(db)
        db.close()
        for entry in results:
            assert entry["mean_price_fcfa"] < 500


# ---------------------------------------------------------------------------
# Heatmap endpoint
# ---------------------------------------------------------------------------

class TestHeatmapEndpoint:
    def test_heatmap_endpoint_returns_200(self, http_client):
        response = http_client.get("/api/analytics/heatmap")
        assert response.status_code == 200
        assert "entries" in response.json()

    def test_heatmap_response_schema(self, http_client):
        for entry in http_client.get("/api/analytics/heatmap").json()["entries"]:
            for field in ("neighborhood_id", "commodity_id", "mean_price_fcfa",
                          "threshold_fcfa", "markup_pct", "submission_count"):
                assert field in entry

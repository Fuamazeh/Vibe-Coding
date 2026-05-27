"""
test_core.py
------------
TDD test suite for Milestone 1:
  - Database schema integrity (in-memory SQLite)
  - Price engine formula correctness
  - Anomaly evaluation rules
  - Zero-unit division guard
  - Seeding idempotency
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Commodity, InsWholesalePrice, Neighborhood, PriceSubmission
from app.price_engine import calculate_fair_threshold, evaluate_submission, get_ui_color_code
from app.seed import seed_initial_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Schema integrity
# ---------------------------------------------------------------------------

class TestSchemaIntegrity:
    def test_commodity_table_exists(self, db_session):
        c = Commodity(
            name="TestGood",
            category="loose_local",
            ins_bulk_package_type="50kg_bag",
            base_units_per_bulk=300,
        )
        db_session.add(c)
        db_session.commit()
        assert db_session.query(Commodity).count() == 1

    def test_neighborhood_default_approved(self, db_session):
        n = Neighborhood(name="TestZone")
        db_session.add(n)
        db_session.commit()
        stored = db_session.query(Neighborhood).filter_by(name="TestZone").first()
        assert stored.is_approved is True

    def test_ins_wholesale_price_cascade_delete(self, db_session):
        commodity = Commodity(
            name="Beans",
            category="loose_local",
            ins_bulk_package_type="50kg_bag",
            base_units_per_bulk=250,
        )
        db_session.add(commodity)
        db_session.flush()

        price = InsWholesalePrice(
            commodity_id=commodity.id,
            bulk_price_fcfa=25_000,
            effective_date=date(2024, 1, 1),
        )
        db_session.add(price)
        db_session.commit()

        db_session.delete(commodity)
        db_session.commit()

        assert db_session.query(InsWholesalePrice).count() == 0

    def test_price_submission_multi_user_no_overwrite(self, db_session):
        commodity    = Commodity(name="Garri", category="loose_local", ins_bulk_package_type="50kg_bag", base_units_per_bulk=300)
        neighborhood = Neighborhood(name="Molyko")
        db_session.add_all([commodity, neighborhood])
        db_session.flush()

        sub_a = PriceSubmission(commodity_id=commodity.id, neighborhood_id=neighborhood.id, quantity=1, submitted_unit_price_fcfa=100,  calculated_threshold_fcfa=110, is_anomaly=False)
        sub_b = PriceSubmission(commodity_id=commodity.id, neighborhood_id=neighborhood.id, quantity=1, submitted_unit_price_fcfa=170,  calculated_threshold_fcfa=110, is_anomaly=True)
        db_session.add_all([sub_a, sub_b])
        db_session.commit()

        assert db_session.query(PriceSubmission).count() == 2


# ---------------------------------------------------------------------------
# Threshold calculation
# ---------------------------------------------------------------------------

class TestThresholdCalculation:
    def test_garri_reference_case(self):
        assert calculate_fair_threshold(30_000, 300) == 110

    def test_spaghetti_reference_case(self):
        assert calculate_fair_threshold(20_000, 40) == 550

    def test_threshold_rounding(self):
        assert isinstance(calculate_fair_threshold(10_000, 300), int)

    def test_zero_units_raises_value_error(self):
        with pytest.raises(ValueError, match="Units per bulk cannot be zero"):
            calculate_fair_threshold(30_000, 0)

    def test_large_bulk_price(self):
        assert calculate_fair_threshold(500_000, 1000) == 550


class TestAnomalyEvaluation:
    def test_price_above_threshold_is_anomaly(self):
        assert evaluate_submission(111, 110) is True

    def test_price_equal_threshold_is_not_anomaly(self):
        assert evaluate_submission(110, 110) is False

    def test_price_below_threshold_is_not_anomaly(self):
        assert evaluate_submission(105, 110) is False

    def test_ui_color_code_red(self):
        assert get_ui_color_code(True) == "RED"

    def test_ui_color_code_green(self):
        assert get_ui_color_code(False) == "GREEN"


# ---------------------------------------------------------------------------
# Seeding idempotency
# ---------------------------------------------------------------------------

class TestSeedIdempotency:
    def test_seed_creates_neighborhoods(self, db_session):
        seed_initial_data(db_session)
        assert db_session.query(Neighborhood).count() == 3

    def test_seed_creates_commodities(self, db_session):
        seed_initial_data(db_session)
        assert db_session.query(Commodity).count() == 2

    def test_seed_is_idempotent(self, db_session):
        seed_initial_data(db_session)
        seed_initial_data(db_session)
        assert db_session.query(Neighborhood).count() == 3
        assert db_session.query(Commodity).count() == 2

    def test_garri_has_wholesale_price(self, db_session):
        seed_initial_data(db_session)
        garri = db_session.query(Commodity).filter_by(name="Garri").first()
        assert len(garri.wholesale_prices) == 1
        assert garri.wholesale_prices[0].bulk_price_fcfa == 30_000

    def test_molyko_is_approved(self, db_session):
        seed_initial_data(db_session)
        molyko = db_session.query(Neighborhood).filter_by(name="Molyko").first()
        assert molyko.is_approved is True

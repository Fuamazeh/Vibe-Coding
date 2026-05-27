"""
seed.py
-------
Idempotent seeding module for Buea Market Watch.

Call ``seed_initial_data(db_session)`` to populate the database with the
canonical initial neighborhoods and commodities (including an active INS
wholesale price entry for Garri). Running it multiple times is safe — it
checks for existing records before inserting.
"""

from datetime import date

from sqlalchemy.orm import Session

from .models import Commodity, InsWholesalePrice, Neighborhood


# ---------------------------------------------------------------------------
# Reference data constants
# ---------------------------------------------------------------------------

INITIAL_NEIGHBORHOODS = [
    "Molyko",
    "Ndongo",
    "Great Soppo",
]

INITIAL_COMMODITIES = [
    {
        "name":                  "Garri",
        "category":              "loose_local",
        "ins_bulk_package_type": "50kg_bag",
        "base_units_per_bulk":   300,
        "wholesale_price_fcfa":  30_000,
    },
    {
        "name":                  "Spaghetti",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "carton",
        "base_units_per_bulk":   40,
        "wholesale_price_fcfa":  None,
    },
]


# ---------------------------------------------------------------------------
# Public seeding function
# ---------------------------------------------------------------------------

def seed_initial_data(db: Session) -> None:
    """
    Idempotently populate the database with initial neighborhoods and commodities.
    """
    _seed_neighborhoods(db)
    _seed_commodities(db)
    db.commit()
    print("[seed] Initial data seeded successfully.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _seed_neighborhoods(db: Session) -> None:
    for name in INITIAL_NEIGHBORHOODS:
        existing = db.query(Neighborhood).filter_by(name=name).first()
        if not existing:
            db.add(Neighborhood(name=name, is_approved=True))
            print(f"[seed] Inserting neighborhood: {name!r}")
        else:
            print(f"[seed] Neighborhood already exists, skipping: {name!r}")


def _seed_commodities(db: Session) -> None:
    for item in INITIAL_COMMODITIES:
        existing = db.query(Commodity).filter_by(name=item["name"]).first()

        if existing:
            print(f"[seed] Commodity already exists, skipping: {item['name']!r}")
            commodity = existing
        else:
            commodity = Commodity(
                name=item["name"],
                category=item["category"],
                ins_bulk_package_type=item["ins_bulk_package_type"],
                base_units_per_bulk=item["base_units_per_bulk"],
            )
            db.add(commodity)
            db.flush()
            print(f"[seed] Inserting commodity: {item['name']!r}")

        if item["wholesale_price_fcfa"] is not None:
            price_exists = (
                db.query(InsWholesalePrice)
                .filter_by(
                    commodity_id=commodity.id,
                    effective_date=date(2024, 1, 1),
                )
                .first()
            )
            if not price_exists:
                db.add(
                    InsWholesalePrice(
                        commodity_id=commodity.id,
                        bulk_price_fcfa=item["wholesale_price_fcfa"],
                        effective_date=date(2024, 1, 1),
                    )
                )
                print(f"[seed] Inserting INS wholesale price for: {item['name']!r}")

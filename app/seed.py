"""
seed.py
-------
Idempotent seeding module for Buea Market Watch.

Call ``seed_initial_data(db_session)`` to populate the database with the
canonical initial neighborhoods and commodities (including active INS
wholesale price entries). Running it multiple times is safe — every insert
is guarded by a filter_by existence check before writing.

Seeded neighborhoods
--------------------
Molyko · Ndongo · Great Soppo · Dirty South

Seeded commodities (with INS wholesale prices)
-----------------------------------------------
Garri · Spaghetti · Noodles · Maggi · Mayor · Salt · Groundnuts
"""

from datetime import date

from sqlalchemy.orm import Session

from .models import Commodity, InsWholesalePrice, Neighborhood


# ---------------------------------------------------------------------------
# Reference data constants
# ---------------------------------------------------------------------------

INITIAL_NEIGHBORHOODS = [
    # name, is_approved
    ("Molyko",      True),
    ("Ndongo",      True),
    ("Great Soppo", True),
    ("Dirty South", True),
]

INITIAL_COMMODITIES = [
    # --------------- original staples ----------------------------------------
    {
        "name":                  "Garri",
        "category":              "loose_local",
        "ins_bulk_package_type": "50kg_bag",
        "base_units_per_bulk":   300,
        "wholesale_price_fcfa":  30_000,   # threshold → 110 FCFA
    },
    {
        "name":                  "Spaghetti",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "carton",
        "base_units_per_bulk":   40,
        "wholesale_price_fcfa":  None,     # no INS price yet
    },
    # --------------- new student staples -------------------------------------
    {
        "name":                  "Noodles",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "carton",
        "base_units_per_bulk":   40,
        "wholesale_price_fcfa":  10_000,   # threshold → 250 FCFA (10000/40*1.10)
    },
    {
        "name":                  "Maggi",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "carton",
        "base_units_per_bulk":   60,
        "wholesale_price_fcfa":  3_000,    # threshold → 55 FCFA (3000/60*1.10)
    },
    {
        "name":                  "Mayor",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "crate",
        "base_units_per_bulk":   12,
        "wholesale_price_fcfa":  18_000,   # threshold → 1650 FCFA (18000/12*1.10)
    },
    {
        "name":                  "Salt",
        "category":              "packaged_factory",
        "ins_bulk_package_type": "packet_bundle",
        "base_units_per_bulk":   50,
        "wholesale_price_fcfa":  2_500,    # threshold → 55 FCFA (2500/50*1.10)
    },
    {
        "name":                  "Groundnuts",
        "category":              "loose_local",
        "ins_bulk_package_type": "50kg_bag",
        "base_units_per_bulk":   150,
        "wholesale_price_fcfa":  37_500,   # threshold → 275 FCFA (37500/150*1.10)
    },
]


# ---------------------------------------------------------------------------
# Public seeding function
# ---------------------------------------------------------------------------

def seed_initial_data(db: Session) -> None:
    """
    Idempotently populate the database with initial neighborhoods and commodities.

    Each helper checks for an existing record before inserting, so this
    function is safe to call on every application startup.

    A final ``db.commit()`` is issued here to guarantee all rows are flushed
    to the remote PostgreSQL instance before any request is handled.  The
    caller (``app/main.py``) issues a second commit for defence-in-depth; the
    extra commit is a no-op when there are no pending changes.
    """
    _seed_neighborhoods(db)
    _seed_commodities(db)
    # CRITICAL: explicit commit ensures every seeded row is persisted to
    # Postgres before Render's health-check probe hits the dropdown endpoints.
    db.commit()
    print("[seed] Initial data seeded successfully.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _seed_neighborhoods(db: Session) -> None:
    for name, is_approved in INITIAL_NEIGHBORHOODS:
        existing = db.query(Neighborhood).filter_by(name=name).first()
        if not existing:
            db.add(Neighborhood(name=name, is_approved=is_approved))
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

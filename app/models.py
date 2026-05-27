"""
models.py
---------
SQLAlchemy ORM table definitions for Buea Market Watch.

Tables
------
  Commodity           – Reference catalogue of tracked goods
  InsWholesalePrice   – INS bulk price time-series per commodity
  Neighborhood        – Known locality entries (approved + unapproved triage)
  PriceSubmission     – Crowdsourced student price submissions (audit log)
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


# ---------------------------------------------------------------------------
# Commodity
# ---------------------------------------------------------------------------

class Commodity(Base):
    __tablename__ = "commodities"

    id                  = Column(Integer, primary_key=True, index=True)
    name                = Column(String(100), unique=True, nullable=False)
    category            = Column(
        String(50),
        CheckConstraint("category IN ('loose_local', 'packaged_factory')", name="ck_commodity_category"),
        nullable=False,
    )
    ins_bulk_package_type = Column(String(50), nullable=False)
    base_units_per_bulk   = Column(Integer, nullable=False)

    wholesale_prices  = relationship("InsWholesalePrice", back_populates="commodity", cascade="all, delete-orphan")
    submissions       = relationship("PriceSubmission",   back_populates="commodity")

    def __repr__(self) -> str:
        return f"<Commodity id={self.id} name={self.name!r} category={self.category!r}>"


# ---------------------------------------------------------------------------
# InsWholesalePrice
# ---------------------------------------------------------------------------

class InsWholesalePrice(Base):
    __tablename__ = "ins_wholesale_prices"

    id             = Column(Integer, primary_key=True, index=True)
    commodity_id   = Column(Integer, ForeignKey("commodities.id", ondelete="CASCADE"), nullable=False)
    bulk_price_fcfa = Column(Integer, nullable=False)
    effective_date = Column(Date, nullable=False)

    commodity = relationship("Commodity", back_populates="wholesale_prices")

    def __repr__(self) -> str:
        return (
            f"<InsWholesalePrice id={self.id} commodity_id={self.commodity_id} "
            f"price={self.bulk_price_fcfa} date={self.effective_date}>"
        )


# ---------------------------------------------------------------------------
# Neighborhood
# ---------------------------------------------------------------------------

class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), unique=True, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)

    submissions = relationship("PriceSubmission", back_populates="neighborhood")

    def __repr__(self) -> str:
        return f"<Neighborhood id={self.id} name={self.name!r} approved={self.is_approved}>"


# ---------------------------------------------------------------------------
# PriceSubmission
# ---------------------------------------------------------------------------

class PriceSubmission(Base):
    __tablename__ = "price_submissions"

    id                       = Column(Integer, primary_key=True, index=True)
    commodity_id             = Column(Integer, ForeignKey("commodities.id",   ondelete="RESTRICT"), nullable=False)
    neighborhood_id          = Column(Integer, ForeignKey("neighborhoods.id", ondelete="RESTRICT"), nullable=False)
    quantity                 = Column(Integer, nullable=False)
    submitted_unit_price_fcfa = Column(Integer, nullable=False)
    calculated_threshold_fcfa = Column(Integer, nullable=False)
    is_anomaly               = Column(Boolean, nullable=False)
    image_path               = Column(String(255), nullable=True)
    created_at               = Column(DateTime, default=func.now(), nullable=False)

    commodity    = relationship("Commodity",    back_populates="submissions")
    neighborhood = relationship("Neighborhood", back_populates="submissions")

    def __repr__(self) -> str:
        return (
            f"<PriceSubmission id={self.id} commodity_id={self.commodity_id} "
            f"neighborhood_id={self.neighborhood_id} price={self.submitted_unit_price_fcfa} "
            f"anomaly={self.is_anomaly}>"
        )


# ---------------------------------------------------------------------------
# Explicit compound indexes on FK lookup columns of PriceSubmission
# ---------------------------------------------------------------------------

Index("ix_price_submissions_commodity_id",    PriceSubmission.commodity_id)
Index("ix_price_submissions_neighborhood_id", PriceSubmission.neighborhood_id)

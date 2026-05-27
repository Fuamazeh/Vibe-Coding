"""
aggregation_service.py
----------------------
24-hour batch heatmap aggregation pipeline for Buea Market Watch.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from .models import Commodity, InsWholesalePrice, Neighborhood, PriceSubmission
from .price_engine import calculate_fair_threshold


def aggregate_daily_heatmap_data(db: Session) -> list[dict[str, Any]]:
    """
    Run the 24-hour aggregation pipeline.

    Returns a list of dicts matching the ``NeighborhoodHeatmapEntry`` schema.
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)

    raw_rows = (
        db.query(PriceSubmission)
        .filter(PriceSubmission.created_at >= cutoff)
        .all()
    )

    if not raw_rows:
        return []

    clusters: dict[tuple[int, int], list[PriceSubmission]] = {}
    for row in raw_rows:
        key = (row.neighborhood_id, row.commodity_id)
        clusters.setdefault(key, []).append(row)

    results: list[dict[str, Any]] = []

    for (neighborhood_id, commodity_id), submissions in clusters.items():
        commodity    = db.get(Commodity, commodity_id)
        neighborhood = db.get(Neighborhood, neighborhood_id)

        if commodity is None or neighborhood is None:
            continue

        threshold = _get_threshold(db, commodity)
        if threshold is None:
            continue

        prices = [s.submitted_unit_price_fcfa for s in submissions]
        clean_prices = _prune_outliers(prices)

        if not clean_prices:
            continue

        mean_price = sum(clean_prices) / len(clean_prices)
        markup_pct = ((mean_price / threshold) - 1.0) * 100.0

        results.append(
            {
                "neighborhood_id":   neighborhood_id,
                "neighborhood_name": neighborhood.name,
                "commodity_id":      commodity_id,
                "commodity_name":    commodity.name,
                "submission_count":  len(clean_prices),
                "mean_price_fcfa":   round(mean_price, 2),
                "threshold_fcfa":    threshold,
                "markup_pct":        round(markup_pct, 2),
            }
        )

    return results


def _get_threshold(db: Session, commodity: Commodity) -> int | None:
    latest_price = (
        db.query(InsWholesalePrice)
        .filter_by(commodity_id=commodity.id)
        .order_by(InsWholesalePrice.effective_date.desc())
        .first()
    )
    if latest_price is None:
        return None
    try:
        return calculate_fair_threshold(
            latest_price.bulk_price_fcfa,
            commodity.base_units_per_bulk,
        )
    except ValueError:
        return None


def _prune_outliers(prices: list[int]) -> list[int]:
    """Remove entries deviating more than 2 standard deviations from the mean."""
    if len(prices) < 2:
        return prices[:]

    mu    = statistics.mean(prices)
    sigma = statistics.stdev(prices)

    if sigma == 0.0:
        return prices[:]

    return [p for p in prices if abs(p - mu) <= 2 * sigma]

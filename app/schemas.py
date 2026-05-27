"""
schemas.py
----------
Pydantic request and response models for Buea Market Watch API.

All monetary values are integers (FCFA).
"""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Submission request
# ---------------------------------------------------------------------------

class SubmissionRequest(BaseModel):
    """
    Payload sent by the student frontend when reporting an observed price.

    Fields
    ------
    commodity_id
        Primary key of the tracked commodity in the ``commodities`` table.
    quantity
        Number of base units purchased (must be ≥ 1).
    submitted_unit_price_fcfa
        Price the student saw at the point of sale, per base unit (FCFA).
    neighborhood_id
        Optional FK to an existing ``neighborhoods`` row.  Either this OR
        ``custom_neighborhood_name`` must be supplied — not both, not neither.
    custom_neighborhood_name
        Free-text neighborhood name provided when the student selects "Other".
        Triggers the unapproved-triage path.
    """

    commodity_id:               int           = Field(..., gt=0)
    quantity:                   int           = Field(..., gt=0)
    submitted_unit_price_fcfa:  int           = Field(..., gt=0)
    neighborhood_id:            Optional[int] = Field(None, gt=0)
    custom_neighborhood_name:   Optional[str] = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_neighborhood_supplied(self) -> "SubmissionRequest":
        has_id     = self.neighborhood_id is not None
        has_custom = (
            self.custom_neighborhood_name is not None
            and self.custom_neighborhood_name.strip() != ""
        )
        if not has_id and not has_custom:
            raise ValueError(
                "Either 'neighborhood_id' or 'custom_neighborhood_name' must be provided."
            )
        if has_id and has_custom:
            raise ValueError(
                "Provide only one of 'neighborhood_id' or 'custom_neighborhood_name', not both."
            )
        return self


# ---------------------------------------------------------------------------
# Submission response
# ---------------------------------------------------------------------------

class SubmissionResponse(BaseModel):
    """
    Instant bargaining-feedback payload returned to the student after submission.
    """

    id:                       int
    submitted_price:          int
    calculated_threshold:     int
    is_anomaly:               bool
    ui_color_code:            str    # "RED" | "GREEN"
    neighborhood_id:          int
    neighborhood_name:        str
    neighborhood_is_approved: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Heatmap analytics response
# ---------------------------------------------------------------------------

class NeighborhoodHeatmapEntry(BaseModel):
    """
    Per-neighborhood aggregated statistics returned by the heatmap endpoint.
    """

    neighborhood_id:      int
    neighborhood_name:    str
    commodity_id:         int
    commodity_name:       str
    submission_count:     int          # number of records used (after outlier pruning)
    mean_price_fcfa:      float        # outlier-pruned arithmetic mean
    threshold_fcfa:       int          # Fair Trade Threshold for this commodity
    markup_pct:           float        # ((mean_price / threshold) - 1) * 100

    model_config = {"from_attributes": True}


class HeatmapResponse(BaseModel):
    """Top-level response wrapper for GET /api/analytics/heatmap."""

    entries: list[NeighborhoodHeatmapEntry]


# ---------------------------------------------------------------------------
# Vision upload response
# ---------------------------------------------------------------------------

class VisionParseResponse(BaseModel):
    """
    Pre-populated form fields extracted from the uploaded market-list image.
    """

    commodity_name:            Optional[str]  = None
    quantity:                  Optional[int]  = None
    submitted_unit_price_fcfa: Optional[int]  = None
    neighborhood_name:         Optional[str]  = None
    confidence:                Optional[float] = None

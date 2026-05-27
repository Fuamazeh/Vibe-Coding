"""
main.py
-------
FastAPI application entry-point for Buea Market Watch.

Routes
------
POST  /api/submissions               – Student price submission + bargaining feedback
GET   /api/analytics/heatmap         – 24-hour aggregated neighbourhood price heatmap
POST  /api/submissions/upload-image  – CNN receipt / market-list image parser

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .aggregation_service import aggregate_daily_heatmap_data
from .database import Base, SessionLocal, engine, get_db
from .models import Commodity, InsWholesalePrice, Neighborhood, PriceSubmission
from .price_engine import calculate_fair_threshold, evaluate_submission, get_ui_color_code
from .schemas import (
    HeatmapResponse,
    NeighborhoodHeatmapEntry,
    SubmissionRequest,
    SubmissionResponse,
    VisionParseResponse,
)
from .vision_service import VisionProcessingError, parse_market_image
from .seed import seed_initial_data
from . import models  # noqa: F401 — ensures all ORM models are registered before create_all

_STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Global Database Initialization & Explicit Seeding
# ---------------------------------------------------------------------------
# Force table creation synchronously on module import
Base.metadata.create_all(bind=engine)

# Open a synchronous initialization session to seed lookup values permanently
db = SessionLocal()
try:
    seed_initial_data(db)
    db.commit()  # <-- CRITICAL: Forces SQLAlchemy to commit the seeded rows to Postgres
    print("Database schema built and lookup data committed successfully.")
except Exception as e:
    db.rollback()
    print(f"Database initialization encountered an exception: {e}")
finally:
    db.close()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Buea Market Watch API",
    description=(
        "Crowdsourced student data-mining platform for price transparency "
        "in Buea, Cameroon."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve CSS/JS/images from /static/*
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# GET / — serve the single-page frontend
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# GET /api/commodities  — dropdown helper
# ---------------------------------------------------------------------------

@app.get("/api/commodities", summary="List all tracked commodities", tags=["Reference"])
def list_commodities(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(Commodity).order_by(Commodity.name).all()
    return [{"id": c.id, "name": c.name, "category": c.category} for c in rows]


# ---------------------------------------------------------------------------
# GET /api/neighborhoods  — dropdown helper (approved only)
# ---------------------------------------------------------------------------

@app.get("/api/neighborhoods", summary="List approved neighborhoods", tags=["Reference"])
def list_neighborhoods(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Neighborhood)
        .filter_by(is_approved=True)
        .order_by(Neighborhood.name)
        .all()
    )
    return [{"id": n.id, "name": n.name} for n in rows]


# ---------------------------------------------------------------------------
# POST /api/submissions
# ---------------------------------------------------------------------------

@app.post(
    "/api/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an observed retail price",
    tags=["Submissions"],
)
def create_submission(
    payload: SubmissionRequest,
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    # 1. Validate commodity exists
    commodity = db.get(models.Commodity, payload.commodity_id)
    if commodity is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The given item is not listed in the system.",
        )

    # 2. Fetch most-recent INS wholesale price
    latest_price: InsWholesalePrice | None = (
        db.query(InsWholesalePrice)
        .filter_by(commodity_id=commodity.id)
        .order_by(InsWholesalePrice.effective_date.desc())
        .first()
    )
    if latest_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No INS wholesale price available for this commodity.",
        )

    # 3. Compute threshold
    try:
        threshold = calculate_fair_threshold(
            latest_price.bulk_price_fcfa,
            commodity.base_units_per_bulk,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    # 4. Resolve neighbourhood
    if payload.neighborhood_id is not None:
        neighborhood: Neighborhood | None = db.get(Neighborhood, payload.neighborhood_id)
        if neighborhood is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Neighbourhood not found.",
            )
    else:
        custom_name = payload.custom_neighborhood_name.strip()  # type: ignore[union-attr]
        neighborhood = db.query(Neighborhood).filter_by(name=custom_name).first()
        if neighborhood is None:
            neighborhood = Neighborhood(name=custom_name, is_approved=False)
            db.add(neighborhood)
            db.flush()

    # 5. Evaluate anomaly
    is_anomaly    = evaluate_submission(payload.submitted_unit_price_fcfa, threshold)
    ui_color_code = get_ui_color_code(is_anomaly)

    # 6. Persist submission
    submission = PriceSubmission(
        commodity_id=commodity.id,
        neighborhood_id=neighborhood.id,
        quantity=payload.quantity,
        submitted_unit_price_fcfa=payload.submitted_unit_price_fcfa,
        calculated_threshold_fcfa=threshold,
        is_anomaly=is_anomaly,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return SubmissionResponse(
        id=submission.id,
        submitted_price=submission.submitted_unit_price_fcfa,
        calculated_threshold=threshold,
        is_anomaly=is_anomaly,
        ui_color_code=ui_color_code,
        neighborhood_id=neighborhood.id,
        neighborhood_name=neighborhood.name,
        neighborhood_is_approved=neighborhood.is_approved,
    )


# ---------------------------------------------------------------------------
# GET /api/analytics/heatmap
# ---------------------------------------------------------------------------

@app.get(
    "/api/analytics/heatmap",
    response_model=HeatmapResponse,
    summary="24-hour neighbourhood price heatmap",
    tags=["Analytics"],
)
def get_heatmap(db: Session = Depends(get_db)) -> HeatmapResponse:
    raw_entries = aggregate_daily_heatmap_data(db)
    entries = [NeighborhoodHeatmapEntry(**entry) for entry in raw_entries]
    return HeatmapResponse(entries=entries)


# ---------------------------------------------------------------------------
# POST /api/submissions/upload-image
# ---------------------------------------------------------------------------

@app.post(
    "/api/submissions/upload-image",
    response_model=VisionParseResponse,
    summary="Parse a market-list or receipt image via CNN",
    tags=["Submissions"],
)
async def upload_market_image(file: UploadFile = File(...)) -> VisionParseResponse:
    image_bytes = await file.read()

    try:
        result = parse_market_image(image_bytes)
    except VisionProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse image clearly. Please verify or enter fields manually.",
        ) from exc

    return VisionParseResponse(**result)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Buea Market Watch** is a crowdsourced data mining platform for student advocacy in Buea, Cameroon. It combines student-submitted retail prices with official National Institute of Statistics (INS) wholesale benchmarks to compute a **Fair Trade Threshold** — the maximum fair retail price per unit — and outputs color-coded Red/Green bargaining feedback plus a public neighborhood-level heatmap of price anomalies.

## Tech Stack

- **Language:** Python 3.11
- **API Framework:** FastAPI (ASGI, async)
- **ORM:** SQLAlchemy; SQLite (`sqlite:///./market_watch.db`) for dev, PostgreSQL for production
- **ML Integration:** PyTorch (custom CNN for receipt/market-list image parsing)
- **Testing:** pytest + FastAPI `TestClient`
- **Containerization:** Docker (`python:3.11-slim`)
- **CI/CD:** Jenkins → Sonatype Nexus/JFrog Artifactory → Python Fabric SSH deploy

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest --maxfail=1 --disable-warnings

# Run a single test file
pytest test_core.py -v

# Run a single test function
pytest test_core.py::test_threshold_calculation -v

# Seed the database
python -c "from database import SessionLocal; from seed import seed_initial_data; db = SessionLocal(); seed_initial_data(db); db.close()"
```

## Module Architecture

Build in this order — each milestone depends on the previous:

| File | Purpose |
|------|---------|
| `database.py` | SQLAlchemy engine (`sqlite:///./market_watch.db`), `SessionLocal`, `get_db()` dependency |
| `models.py` | ORM table definitions (see schema below) |
| `price_engine.py` | Pure calculation functions — no DB access |
| `seed.py` | Idempotent `seed_initial_data(db_session)` for initial neighborhoods and commodities |
| `schemas.py` | Pydantic request/response models |
| `main.py` | FastAPI app instance + all route definitions |
| `aggregation_service.py` | 24-hour batch heatmap aggregation pipeline |
| `vision_service.py` | PyTorch CNN (`ReceiptParsingCNN`) + `parse_market_image()` |

**DevOps files** (repo root): `Dockerfile`, `Jenkinsfile`, `fabfile.py`

**Test files**: `test_core.py`, `test_submissions_api.py`, `test_analytics_engine.py`, `test_vision_pipeline.py`

## Core Business Logic

### Threshold Formula
```
Threshold (FCFA) = round((INS_bulk_price / base_units_per_bulk) * 1.10)
```
- Example: 30,000 FCFA / 300 cups × 1.10 = **110 FCFA**
- Raises `ValueError("Units per bulk cannot be zero")` if `base_units_per_bulk == 0`

### Anomaly Evaluation
```python
is_anomaly = submitted_price > threshold  # True → RED, False → GREEN
```

### API Response Color Codes
- `submitted_price > threshold` → `"RED"` (price gouging alert)
- `submitted_price <= threshold` → `"GREEN"` (fair vendor)

## Key API Endpoints

| Method | Path | Behaviour |
|--------|------|-----------|
| `POST` | `/api/submissions` | Validates commodity, handles "Other" neighborhood triage, computes threshold, saves `PriceSubmission`, returns `{submitted_price, calculated_threshold, is_anomaly, ui_color_code}` |
| `GET` | `/api/analytics/heatmap` | Returns 24-hour aggregated neighborhood stats with outlier-pruned price means |
| `POST` | `/api/submissions/upload-image` | Accepts `UploadFile`, runs CNN inference, pre-populates form fields or returns HTTP 422 on parse failure |

## Database Schema (Key Constraints)

- `Commodity.category` is constrained to `'loose_local'` or `'packaged_factory'`
- `Neighborhood.is_approved` defaults to `True`; custom "Other" entries are saved with `is_approved=False` for admin moderation
- `PriceSubmission` has explicit DB indexes on both `commodity_id` and `neighborhood_id`
- Multiple users submitting different prices for the same commodity in the same neighborhood **both persist** — no overwrite (audit trail requirement)

## Error Handling Requirements

| Scenario | Response |
|----------|----------|
| Commodity not in `commodities` table | HTTP 400: `"The given item is not listed in the system."` |
| CNN parse failure (blurry/corrupt image) | HTTP 422: `"Could not parse image clearly. Please verify or enter fields manually."` |
| `base_units_per_bulk == 0` | `ValueError("Units per bulk cannot be zero")` — never let this crash the API |

## Statistical Outlier Pruning (Heatmap Aggregation)

For each `(neighborhood_id, commodity_id)` cluster in the trailing 24-hour window:
1. Compute mean (μ) and standard deviation (σ) of submitted prices
2. Drop any entry where `|price - μ| > 2σ`
3. Compute clean arithmetic mean and markup % vs. INS threshold on remaining entries
4. Underlying transaction records are **never deleted** — only excluded from heatmap computation

## Seeded Reference Data

| Commodity | Category | Bulk Package | Base Units | Initial Wholesale |
|-----------|----------|--------------|------------|-------------------|
| Garri | `loose_local` | `50kg_bag` | 300 cups | 30,000 FCFA |
| Spaghetti | `packaged_factory` | `carton` | 40 packets | — |

Initial neighborhoods: `"Molyko"`, `"Ndongo"`, `"Great Soppo"`

## CI/CD Pipeline Stages

Jenkins executes five sequential stages: `Repository Pull` → `Test Execution Matrix` → `Immutable Docker Assembly` → `Artifact Registration` (Nexus registry `nexus.bueamarketwatch.internal:8082`) → `Automated Infrastructure Fabric Release` (`fab deploy --image-tag=${BUILD_NUMBER}`).

The Fabric `deploy(c, image_tag)` task: logs into registry, pulls image, stops/removes container `live_market_watch_api` (with `|| true` guards), then runs new container on port 8000 with `--restart always` and `$PROD_DB_URL` injected.

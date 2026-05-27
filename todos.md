# Buea Market Watch - Comprehensive Technical Implementation Checklist

## Milestone 1: Storage Tier & Pure Computational Foundations
- [x] **Task 1.1: Database Engine Assembly & Session Factory Setup**
  - [x] Implement `database.py` utilizing SQLAlchemy.
  - [x] Configure a local transactional database engine (`sqlite:///./market_watch.db`) and force SQLite to strictly enforce foreign key constraints (`PRAGMA foreign_keys = ON`).
  - [x] Implement a thread-safe `SessionLocal` maker and expose a clean context-manager dependency generator function `get_db()`.
- [x] **Task 1.2: Relational Schema Mapping Declarations**
  - [x] Implement `models.py` referencing the declarative base class.
  - [x] Build the `Commodity` table (`id`, `name` [Unique], `category` [constrained to 'loose_local' or 'packaged_factory'], `ins_bulk_package_type`, `base_units_per_bulk`).
  - [x] Build the `InsWholesalePrice` table (`id`, `commodity_id` [FK to commodities with CASCADE delete], `bulk_price_fcfa`, `effective_date`).
  - [x] Build the `Neighborhood` table (`id`, `name` [Unique], `is_approved` [Boolean, default True]).
  - [x] Build the `PriceSubmission` table (`id`, `commodity_id` [FK], `neighborhood_id` [FK], `quantity`, `submitted_unit_price_fcfa`, `calculated_threshold_fcfa`, `is_anomaly` [Boolean], `image_path` [Nullable], `created_at`).
  - [x] Apply database indexes explicitly across the foreign key lookup columns (`neighborhood_id`, `commodity_id`) in `PriceSubmission`.
- [x] **Task 1.3: Idempotent Seeding Module Configuration**
  - [x] Create `seed.py` exposing a `seed_initial_data(db_session)` execution method.
  - [x] Populate core neighborhoods: `"Molyko"`, `"Ndongo"`, `"Great Soppo"`.
  - [x] Populate foundational baseline items: `"Garri"` (loose_local, bulk package: 50kg_bag, 300 base cups) and `"Spaghetti"` (packaged_factory, bulk package: carton, 40 base packets), with relevant matching active `ins_wholesale_prices` metrics.
- [x] **Task 1.4: Pure Pricing Rules Core Engine**
  - [x] Create `price_engine.py` to handle structural calculation algorithms.
  - [x] Implement `calculate_fair_threshold(bulk_price: int, units_per_bulk: int) -> int` mapping the core logic formula: `Threshold = (bulk_price / units_per_bulk) * 1.10`.
  - [x] Apply explicit mathematical rounding parameters to guarantee clean integer outputs in FCFA currency bounds.
  - [x] Implement zero-unit intercept exceptions checking if `units_per_bulk` is 0, raising an explicit `ValueError("Units per bulk cannot be zero")`.
  - [x] Implement `evaluate_submission(submitted_price: int, threshold: int) -> bool` returning `True` (Anomaly) if the unit price exceeds bounds, and `False` otherwise.
- [x] **Task 1.5: Core Persistence & Math TDD Test Suites**
  - [x] Create `test_core.py` to assert relational definitions on an in-memory SQLite configuration.
  - [x] Write unit tests confirming a 30,000 FCFA wholesale list with 300 base units accurately resolves to a 110 FCFA threshold.
  - [x] Assert that a simulated input of 111 FCFA triggers an anomaly status (`True`), while 105 FCFA evaluates to safe (`False`).
  - [x] Write unit tests confirming the zero-unit safety error triggers correctly on bad inputs.

## Milestone 2: Structured Submission Intake & Real-Time API Layer
- [x] **Task 2.1: FastAPI Server Setup & Pydantic Contracts**
  - [x] Create `main.py` initializing a FastAPI framework instance along with broad global CORS permissions.
  - [x] Create `schemas.py` and implement the student incoming submission payload Pydantic model (`commodity_id`, `quantity`, `submitted_unit_price_fcfa`, `neighborhood_id`, `custom_neighborhood_name`).
- [x] **Task 2.2: Transaction Submission Route Orchestration**
  - [x] Construct the core data intake path route at `POST /api/submissions` inside `main.py`.
  - [x] Wire the route to pull corresponding reference metrics directly from active database sessions using the incoming `commodity_id`.
- [x] **Task 2.3: Untracked Commodity Validation Trap**
  - [x] Implement a strict data evaluation checkpoint raising an `HTTP 400 Bad Request` displaying the exact validation message string if a commodity lookup returns null: `"The given item is not listed in the system."`
- [x] **Task 2.4: Unapproved Neighborhood Triage Queue Integration**
  - [x] Add evaluation logic handling instances where a student writes a custom string selection using the "Other" option parameter.
  - [x] Automate checking for pre-existing strings before inserting a new row in the `Neighborhood` table flagged cleanly with `is_approved = False`.
  - [x] Swap the target relational execution parameters dynamically to point to this newly created unapproved zone location index.
- [x] **Task 2.5: Student Real-Time Color Negotiation Feedback Generator**
  - [x] Complete transactional commits saving logs directly into `PriceSubmission` entities.
  - [x] Formulate client response payloads containing calculation steps alongside the explicit negotiation token: return `"RED"` for active anomalies, and `"GREEN"` for fair vendor transactions.
- [x] **Task 2.6: API Core Route Integration Testing**
  - [x] Create `test_submissions_api.py` leveraging FastAPI's native `TestClient`.
  - [x] Test the pipeline end-to-end to verify that fair prices return `GREEN` indicators, gouged prices output `RED` color tokens, and missing item indexes throw the exact required `HTTP 400` error text.

## Milestone 3: Analytical 24-Hour Statistical Aggregation Engine
- [x] **Task 3.1: 24-Hour Grouping & Multi-User Coexistence Engine**
  - [x] Implement `aggregation_service.py` exposing the core routine `aggregate_daily_heatmap_data(db_session)`.
  - [x] Query all items captured within a trailing 24-hour runtime window, grouping records concurrently by both `neighborhood_id` and `commodity_id`.
  - [x] Ensure that multiple user prices for the same items in the same location are safely preserved independently in the transactional log history without overwriting each other.
- [x] **Task 3.2: Statistical Outlier Pruning Loop Module**
  - [x] Implement a trimming filter iterating through localized neighborhood data blocks.
  - [x] Compute current sample means and standard deviations, automatically dropping any individual user transaction with an extreme pricing value deviating beyond $\pm 2$ standard deviations from that neighborhood's group running average.
- [x] **Task 3.3: Map Visualization Analytical Exposer Route**
  - [x] Implement an optimized analytics data endpoint path at `GET /api/analytics/heatmap` inside `main.py`.
  - [x] Configure the route to output spatial analytics payloads mapping active submission sizes, clean statistical price averages, and relative markup percentages per region zone indicator.
- [x] **Task 3.4: Aggregation Aggregators & Multi-User Integration Tests**
  - [x] Create `test_analytics_engine.py` using pytest.
  - [x] Seed a neighborhood partition with 10 typical inputs and 1 massive topographical typing error (e.g., 2,500 FCFA instead of 100 FCFA).
  - [x] Execute the batch pipeline algorithm and assert that the statistical outlier gets dropped from the map display calculation layer, while the underlying transactions remain fully intact for audit tracking.

## Milestone 4: Custom CNN Document Parsing Service
- [x] **Task 4.1: PyTorch Machine Learning Engine Layout Structure**
  - [x] Construct a computer vision modeling module named `vision_service.py` introducing a custom `ReceiptParsingCNN` inheriting from `torch.nn.Module`.
  - [x] Scaffold convolutional feature engineering pipelines down to linear estimation output blocks.
- [x] **Task 4.2: Faulty Input Catch Exception Handling Wrapper**
  - [x] Implement a processing function `parse_market_image(image_bytes: bytes) -> dict`.
  - [x] Incorporate safe catch parameters inside the wrapper to throw a dedicated domain exception named `VisionProcessingError` if image data is unreadable, blurred, or corrupt.
- [x] **Task 4.3: Binary Multipart Data Streaming Upload Route**
  - [x] Integrate a dedicated binary file parser route inside `main.py` at `POST /api/submissions/upload-image` accepting an `UploadFile` entity.
  - [x] Intercept execution runtime environments inside a try-except layer catching `VisionProcessingError`.
  - [x] If execution fails, abort and return an `HTTP 422 Unprocessable Entity` containing the exact error mitigation instructions: `"Could not parse image clearly. Please verify or enter fields manually."`
- [x] **Task 4.4: Image Parsing End-to-End TDD Test Matrix**
  - [x] Create `test_vision_pipeline.py` writing verification tests using mock image file byte streams.
  - [x] Assert that mock file binaries parse into clean dictionary blocks, and that bad streams drop down smoothly to the manual fallback instructions payload with an HTTP 422 error.

## Milestone 5: Production DevOps & Infrastructure CI/CD Pipeline
- [x] **Task 5.1: Layer-Optimized Multi-Stage Production Containerization**
  - [x] Create a production-grade `Dockerfile` in the repository root using a `python:3.11-slim` runtime base layer.
  - [x] Install native dependencies (`build-essential`) via `apt-get`, clearing temporary execution cache lists afterward to maintain small disk footprint rules.
  - [x] Handle layer caching optimizations by isolating python package installations via `requirements.txt` independently with `--no-cache-dir`.
  - [x] Expose network port 8000 and mount the main ASGI uvicorn worker runtime engine loop.
- [x] **Task 5.2: Remote SSH Infrastructure Automation Pipeline**
  - [x] Build a production delivery engine file named `fabfile.py` utilizing Python Fabric task structures.
  - [x] Write the `deploy(c, image_tag)` method to connect via SSH, authenticate securely against private artifact registries (`nexus.bueamarketwatch.internal:8082`), ingest target immutable images, and cycle old containers safely without throwing errors if the stack is spinning up fresh.
- [x] **Task 5.3: Orchestrated Continuous Integration Blueprint Execution**
  - [x] Author a declarative pipeline script in a file named `Jenkinsfile` residing in the project root directory.
  - [x] Enforce consecutive multi-phase execution gates: 'Repository Pull', 'Test Execution Matrix' (running all python unit and integration tests), 'Immutable Docker Assembly', 'Artifact Registration' (registering container targets with unique build number hashes and 'latest' tags to Sonatype Nexus or JFrog Artifactory), and 'Automated Infrastructure Fabric Release'.

Here is the comprehensive development strategy and step-by-step code-generation prompt matrix for building **Buea Market Watch**.

---

## Part 1: Architecture Blueprint & Phased Breakdown

To build this application without creating unintegrated ("orphaned") code components, we will structure the implementation into **5 Progressive Milestones**. Each milestone introduces a single functional slice, fully verified by matching Test-Driven Development (TDD) execution scripts before expanding to the next layer.

### Phase 1: Storage Tier & Pure Core Computation

* **Step 1.1:** Build the SQLAlchemy models and automated schema initialization engine.
* **Step 1.2:** Build an idempotent seeding interface for core neighborhoods and National Institute of Statistics (INS) commodity baselines.
* **Step 1.3:** Build the core pricing business engine implementing the structural conversion logic and the $+10\%$ wholesale margin rule.

### Phase 2: Ingestion & Verification REST API

* **Step 2.1:** Implement the FastAPI application runner and define structured request/response payload schemas.
* **Step 2.2:** Build the operational submission router (`POST /api/submissions`) with error traps for untracked commodities.
* **Step 2.3:** Integrate the "Other" neighborhood triage mechanism to handle dynamic student inputs cleanly.

### Phase 3: Analytical 24-Hour Statistical Aggregation

* **Step 3.1:** Build the asynchronous daily aggregation pipeline mapping multi-user localized transaction variants.
* **Step 3.2:** Implement the $\pm2$ standard deviation outlier pruning module to sanitize public dashboard datasets.
* **Step 3.3:** Expose the analytical delivery route (`GET /api/analytics/heatmap`) returning computed spatial weights.

### Phase 4: Custom CNN Document Parsing Layer

* **Step 4.1:** Build a custom PyTorch structural CNN architecture to process image payloads.
* **Step 4.2:** Build the multipart binary entry route (`POST /api/submissions/upload-image`) with robust fallback error handling for corrupted image assets.

### Phase 5: Production Deployment & Infrastructure DevOps Configuration

* **Step 5.1:** Author the multi-stage, containerized `Dockerfile`.
* **Step 5.2:** Build the remote SSH automation pipeline via `fabfile.py`.
* **Step 5.3:** Build the orchestrating `Jenkinsfile` tying validation, linting, image construction, asset registration, and live deployment execution into a cohesive sequence.

---

## Part 2: Standalone Code-Generation Prompts

### Prompt 1: Database Layer & Pure Computational Domain Engine

```text
You are an expert principal backend engineer specializing in Python 3.11, SQLAlchemy ORM, and test-driven domain-driven design. Your task is to implement the persistence layer and the mathematical evaluation engine for the "Buea Market Watch" application.

1. Create a module named `database.py` that configures a standard SQLAlchemy engine using an SQLite connection string (`sqlite:///./market_watch.db`) configured to enforce foreign key constraints, along with a `SessionLocal` thread-safe session maker.

2. Create a module named `models.py` that defines the following declarative tables:
   - `Commodity`: id (PK), name (String, Unique), category (String: constrained to 'loose_local' or 'packaged_factory'), ins_bulk_package_type (String), base_units_per_bulk (Integer).
   - `InsWholesalePrice`: id (PK), commodity_id (FK to commodities), bulk_price_fcfa (Integer), effective_date (Date).
   - `Neighborhood`: id (PK), name (String, Unique), is_approved (Boolean, default=True).
   - `PriceSubmission`: id (PK), commodity_id (FK to commodities), neighborhood_id (FK to neighborhoods), quantity (Integer), submitted_unit_price_fcfa (Integer), calculated_threshold_fcfa (Integer), is_anomaly (Boolean), image_path (String, Nullable), created_at (DateTime, default=now). Make sure to add indexing across neighborhood_id and commodity_id.

3. Create a module named `price_engine.py` that contains pure functional calculation logic:
   - `calculate_fair_threshold(bulk_price: int, units_per_bulk: int) -> int`: Computes the threshold using the exact formula: Threshold = (bulk_price / units_per_bulk) * 1.10. Round the final result to the nearest integer. If `units_per_bulk` is 0, explicitly raise a ValueError with the message: "Units per bulk cannot be zero".
   - `evaluate_submission(submitted_price: int, threshold: int) -> bool`: Returns True if `submitted_price` is strictly greater than `threshold`, and False otherwise.

4. Create a module named `seed.py` that provides an idempotent function `seed_initial_data(db_session)` to seed three neighborhoods ("Molyko", "Ndongo", "Great Soppo") and two commodities: "Garri" (loose_local, bulk_package: '50kg_bag', 300 base units) and "Spaghetti" (packaged_factory, bulk_package: 'carton', 40 base units), alongside matching baseline wholesale rows in `ins_wholesale_prices`.

5. Write a comprehensive pytest module named `test_core.py` that initializes an in-memory database configuration, builds the schema tables, runs the seed script, and verifies:
   - An INS wholesale price of 30,000 FCFA for Garri with 300 units per bag yields a calculated threshold of exactly 110 FCFA.
   - A submission of 111 FCFA is marked as an anomaly (True), while 105 FCFA evaluates to safe (False).
   - Passing 0 into `units_per_bulk` throws the requested ValueError.

Provide the complete code for all four files. Do not include partial snippets, shortcuts, placeholders, or omit any details.

```

### Prompt 2: FastAPI Submissions Router Layer & Triage Exception Handling

```text
You are an expert API architect building endpoints using Python 3.11 and FastAPI. Your task is to implement the real-time student verification and point-of-sale submission intake router.

Import your existing database session factory, SQLAlchemy models, and computational logic from your previous workspace modules (`database.py`, `models.py`, `price_engine.py`). 

1. Create a module named `main.py` that bootstraps a FastAPI application instance. 

2. Implement a Pydantic schema file named `schemas.py` that defines the input payload constraint for a transaction entry:
   - `commodity_id`: int
   - `quantity`: int
   - `submitted_unit_price_fcfa`: int
   - `neighborhood_id`: int
   - `custom_neighborhood_name`: Optional[str] = None

3. Inside `main.py`, construct a POST router endpoint at `/api/submissions`. The logic must execute the following sequential steps:
   - Fetch the specified commodity record from the database. If it does not exist, immediately raise an HTTP 400 Bad Request exception with the exact error message string: "The given item is not listed in the system."
   - Handle the "Other" neighborhood triage exception: If `neighborhood_id` matches a placeholder ID indicating "Other" (or if `custom_neighborhood_name` is populated), check if that neighborhood string already exists in the table. If it does not, create and persist a new `Neighborhood` row with `name=custom_neighborhood_name` and `is_approved=False`. Use the new or existing unapproved neighborhood record's ID moving forward.
   - Query the most recent `InsWholesalePrice` entry associated with the chosen commodity. Run your `calculate_fair_threshold` and `evaluate_submission` functions to compute the active pricing metrics.
   - Persist the transactional tracking log as a new `PriceSubmission` record.
   - Return a JSON response payload structured with these keys:
     - `submitted_price`: int
     - `calculated_threshold`: int
     - `is_anomaly`: bool
     - `ui_color_code`: Return "RED" if `is_anomaly` evaluates to True, or "GREEN" if it evaluates to False.

4. Write an exhaustive test file named `test_submissions_api.py` leveraging FastAPI's `TestClient` and pytest. Ensure your test suite mocks or configures the underlying relational data states to fully verify:
   - A valid, non-anomalous submission saves down cleanly and outputs a "GREEN" color token.
   - An inflated price submission returns a "RED" token along with the accurate side-by-side threshold calculations.
   - Querying an unregistered commodity ID safely aborts processing, throwing the expected HTTP 400 validation error message string.
   - Submitting an unlisted neighborhood through `custom_neighborhood_name` creates a triage record set to `is_approved=False`.

Provide the complete code for all three files. Do not use shortcuts, placeholders, or omit implementation details.

```

### Prompt 3: Analytical 24-Hour Statistical Aggregation Engine & Outlier Filter

```text
You are an expert data engineer specialized in statistical processing pipelines and background analytics using Python 3.11, SQLAlchemy, and FastAPI. Your task is to implement the 24-hour asynchronous analytical aggregation engine.

1. Inside a new module named `aggregation_service.py`, implement a function named `aggregate_daily_heatmap_data(db_session)`. This engine must resolve multi-user price variances using the following multi-step statistical pipeline:
   - Query all transactional logs from the `PriceSubmission` table recorded over the trailing 24 hours.
   - Group the active transaction rows concurrently by both `neighborhood_id` and `commodity_id`. Ensure that multiple entries for the same food stuff in the same sector coexist cleanly in the database without overwriting each other.
   - For each localized neighborhood commodity cluster, compute the statistical mean and standard deviation of the submitted prices.
   - Apply the $\pm2$ standard deviation outlier pruning filter rule: Loop through the cluster and drop any transaction entry with a unit price that falls outside two standard deviations from that neighborhood group's average. This strips out typographical errors or bad-faith inputs.
   - For all remaining valid submissions, calculate the clean arithmetic mean price and compute its combined markup percentage relative to the commodity's official INS reference threshold.

2. Inside your `main.py` application layer, expose a new GET endpoint at `/api/analytics/heatmap`. This route must fetch the processed summary results from your aggregation loop and return a structured JSON response mapping neighborhood metrics. Each neighborhood node must output an array of tracked commodities, their valid submission counts, the clean averaged price, and the computed aggregate markup tier.

3. Write a comprehensive integration test file named `test_analytics_engine.py` using pytest. Seed a target neighborhood with 10 normal pricing entries (e.g., around 100 FCFA to 120 FCFA) and 1 highly inflated typographical error entry (e.g., 2,500 FCFA). Trigger your `aggregate_daily_heatmap_data` function and explicitly assert that:
   - The statistical outlier entry is successfully detected and dropped from the map calculation array.
   - The resulting data payload returned by hitting your GET endpoint accurately reflects the clean statistical mean of the 10 valid submissions.
   - The multi-user transaction records remain perfectly intact in the transaction table for auditing.

Provide the complete code for both files. Do not include placeholders or omit implementation code.

```

### Prompt 4: Deep Learning PyTorch Image-Parsing Ingestion Module

```text
You are an expert machine learning engineer specialized in computer vision pipelines using PyTorch, FastAPI, and asynchronous file handlers. Your task is to implement the image document processing layer that pre-populates form data from uploaded photos.

1. Inside a new module named `vision_service.py`, build a clean image processing pipeline layer:
   - Declare a lightweight convolutional neural network class named `ReceiptParsingCNN` inheriting from `torch.nn.Module`. Set up standard structural feature layers (`Conv2d`, `MaxPool2d`, `Linear`) capable of structural layout analysis.
   - Implement a functional wrapper method `parse_market_image(image_bytes: bytes) -> dict`. For the operational scope of this standalone module, write a robust mock inference sequence inside this function that parses readable image inputs and extracts a dictionary mapping structured form targets: `{"commodity_name": str, "quantity": int, "unit_price": int}`.
   - If the image byte array stream is corrupted, unreadable, or fails confidence checks, explicitly throw a custom defined domain exception named `VisionProcessingError`.

2. Open your core FastAPI application runner file (`main.py`) and add a new multipart routing endpoint at `POST /api/submissions/upload-image`. This route must capture file streams using FastAPI's `UploadFile`.
   - Wrap the execution logic inside an explicit try-except block intercepting `VisionProcessingError`.
   - If a processing error occurs, halt execution and instantly return an HTTP 422 Unprocessable Entity status payload containing the exact instruction string: "Could not parse image clearly. Please verify or enter fields manually."
   - If successful, return the parsed data dictionary back to the client web layout so it can pre-populate the student form fields automatically.

3. Create an automated testing module named `test_vision_pipeline.py` using pytest. Write test flows that send valid mock byte streams to verify successful data dictionary outputs, and send bad or empty byte sequences to confirm that the pipeline drops down gracefully to the manual-input message with an HTTP 422 error status.

Provide the complete code for all modules. Do not use shortcuts, omissions, or partial implementations.

```

### Prompt 5: Production Containerization & DevOps Infrastructure Automation

```text
You are an expert site reliability and DevOps engineer specializing in multi-stage Docker builds, Jenkins pipeline scripting, and Python Fabric orchestration. Your task is to implement the production CI/CD infrastructure workspace that packages, registers, and deploys the "Buea Market Watch" application.

Configure and output the following three infrastructure automation configuration files to reside in your repository root:

1. Create a multi-stage `Dockerfile`:
   - Utilize a base runtime image layer of `python:3.11-slim`.
   - Install minimal native dependencies (`build-essential`) via `apt-get`, clearing packaging lists afterward to preserve small disk footprints.
   - Establish `/app` as the active working directory, handle Python dependency caching by copying `requirements.txt` independently, install pip modules cleanly via `--no-cache-dir`, expose server network port 8000, and launch the application using `uvicorn main:app --host 0.0.0.0 --port 8000`.

2. Create an automated `fabfile.py` script leveraging Python Fabric modules:
   - Implement a configuration execution task command `deploy(c, image_tag)` designed to coordinate updates via remote SSH handshakes.
   - The task must call remote shell executions using `c.run()` commands to log securely into a private container registry URL (`nexus.bueamarketwatch.internal:8082`), pull the freshly compiled image identifier tag, gracefully terminate and clear stale running application runtimes matching the container namespace `live_market_watch_api` without crashing if no container exists, and spin up the new versioned container mapped to network port 8000.

3. Create a declarative `Jenkinsfile` pipeline script:
   - Run across any execution agent node, establishing environment tokens for registry paths, image identities, and safe authentication IDs.
   - Define five explicit production deployment phases: 'Repository Pull' (git fetch), 'Test Execution Matrix' (running pip installations and executing pytest suites), 'Immutable Docker Assembly' (building the versioned container asset via `docker.build`), 'Artifact Registration' (logging into the registry and pushing both the build number and 'latest' tags to Sonatype Nexus/JFrog Artifactory), and 'Automated Infrastructure Fabric Release' (loading SSH agent keys and executing the Fabric command line string: `fab deploy --image-tag=${BUILD_NUMBER}`).

Ensure all scripts are fully configured, grammatically accurate across Groovy, Python, and Docker engines, and wire together seamlessly. Do not use placeholders or unconfigured parameter strings.

```
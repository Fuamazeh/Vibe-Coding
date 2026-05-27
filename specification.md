# Technical Specification Document: Buea Market Watch (Comprehensive Implementation & DevOps Blueprint)

This document serves as the comprehensive, production-grade functional, technical, and deployment specification for **Buea Market Watch**. It integrates the core system architecture, data mining engines, real-time bargaining feedback loops, and an automated continuous integration/continuous deployment (CI/CD) infrastructure.

---

## 1. System Overview & Core Objectives

University students in Buea face sudden, unpredictable retail food price increases due to a lack of structured pricing mechanisms in student-heavy neighborhoods.

**Buea Market Watch** is a data mining platform designed for student advocacy. It combines crowdsourced retail data with official wholesale benchmarks to calculate a **"Fair Trade Threshold"** (Wholesale Price + a 10% Margin). The platform provides two core outputs:

1. **Point-of-Sale Bargaining Tool:** Instant, color-coded visual validation (Red/Green feedback) that empowers students to negotiate prices with vendors using empirical data.
2. **Price Transparency Heatmap:** A public web dashboard that aggregates neighborhood-level pricing anomalies over a 24-hour window to pinpoint regional price-gouging hotspots.

---

## 2. Functional Requirements

### 2.1 Student Data Submission & Image Ingestion Pipeline

The frontend provides a responsive, validated input form supported by a machine learning module for automated data extraction.

* **Structured Fields:**
* **Good:** Auto-completing text input linked to tracked commodities (e.g., Garri, Beans, Rice, Spaghetti, Noodles).
* **Quantity & Unit:** A positive numeric input mapped to a strict unit selector (`Cup`, `Sachet`, `Packet`).
* **Unit Price:** A positive integer representing the pricing structure in Central African CFA francs (FCFA).
* **Neighborhood:** A predefined dropdown configuration containing localized sectors (`Molyko`, `Ndongo`, `Great Soppo`, `Mile 14`).


* **The "Other" Neighborhood Triage Exception:**
* If a student's neighborhood is missing, selecting **"Other"** displays a text input field.
* The submission is processed immediately, but the new location string is saved with a database flag of `is_approved = False`. This flags the record for an administrative moderation queue to protect the global dropdown options from duplicate strings or noise.


* **Custom CNN Document Processing:**
* Students can take a photo of a handwritten market list or a receipt.
* The backend routes the file stream to a custom **Convolutional Neural Network (CNN)** optimized for text-localization and layout extraction. The network parses the image structures and pre-populates the form fields to streamline manual data entry.



### 2.2 Core Processing Engine & Multi-User Variance Resolution

1. **Reference Alignment:** The system matches submissions against official bulk metrics from the National Institute of Statistics (INS). If an unmapped or untracked commodity is passed, the pipeline halts execution and returns an on-screen validation error: *"The given item is not listed in the system."*
2. **Unit Standardization:** To bridge loose market measurements with formal bulk metrics, the backend converts quantities using category-specific baselines:
* *Locally Produced Loose Goods (Garri, Beans, Rice):* Evaluated using a standard average conversion factor where **1 Cup** serves as the universal base unit.
* *Factory Packaged Goods (Spaghetti, Noodles):* Evaluated using **1 Sachet** or **1 Packet** as the base unit.


3. **Threshold Calculation:** The core engine computes the absolute maximum fair retail price per unit using the exact formula:

$$\text{Threshold} = \left( \frac{\text{INS Wholesale Bulk Package Price}}{\text{Total Base Units Per Bulk Package}} \right) \times 1.10$$

4. **Multi-User Variance Handling:** If two different users input different prices for the exact same commodity inside the same neighborhood concurrently, **both individual records are preserved** in the database to maintain audit trails and historical depth.

### 2.3 Real-Time Student Response UI

Upon form submission, the system returns an instantaneous verification block:

* **Fair Price (Green UI State):** If `Unit Price <= Threshold`, the interface renders an emerald green card badge displaying: **"FAIR PRICE VENDOR"**.
* **Pricing Anomaly (Red UI State):** If `Unit Price > Threshold`, the record is flagged as an anomaly. The application UI turns deep crimson red, flashing a warning that displays the calculated fair threshold and the markup percentage side-by-side to assist the student in negotiating with the vendor.

### 2.4 Analytical Heatmap Engine

* **Visual Element:** A Map overlay of Buea divided into neighborhood boundary polygons.
* **24-Hour Batch Window (Cron-Job):** The public map updates once every 24 hours via an asynchronous aggregation script.
* **Statistical Pruning Filter:** During aggregation, the engine calculates the running mean and standard deviation for each item cluster per neighborhood. Any individual entry deviating by more than $\pm2$ standard deviations from the localized group mean is discarded from the map computation layer. This removes typos and bad-faith entries while preserving real local pricing variance on the public map dashboard.

---

## 3. Architecture & Data Handling Blueprint

### 3.1 Tech Stack Standard

* **Language Ecosystem:** Python 3.11
* **API Framework:** FastAPI (Asynchronous ASGI execution layer)
* **Data Persistence Layer:** PostgreSQL + SQLAlchemy ORM
* **Machine Learning Integration:** PyTorch (Lightweight tensor processing backend)
* **Task Automation / Orchestration:** Native Linux Crontab or Async Background Worker Loops

### 3.2 Relational Database Schema Schema Definitions

The persistent tier handles transactional logs, reference indices, and aggregation tables:

```sql
CREATE TABLE commodities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'loose_local' or 'packaged_factory'
    ins_bulk_package_type VARCHAR(50) NOT NULL, -- e.g., '50kg_bag', 'carton'
    base_units_per_bulk INT NOT NULL
);

CREATE TABLE ins_wholesale_prices (
    id SERIAL PRIMARY KEY,
    commodity_id INT REFERENCES commodities(id) ON DELETE CASCADE,
    bulk_price_fcfa INT NOT NULL,
    effective_date DATE NOT NULL
);

CREATE TABLE neighborhoods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    is_approved BOOLEAN DEFAULT TRUE
);

CREATE TABLE price_submissions (
    id SERIAL PRIMARY KEY,
    commodity_id INT REFERENCES commodities(id) ON DELETE RESTRICT,
    neighborhood_id INT REFERENCES neighborhoods(id) ON DELETE RESTRICT,
    quantity INT NOT NULL,
    submitted_unit_price_fcfa INT NOT NULL,
    calculated_threshold_fcfa INT NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

---

## 4. DevOps & Deployment Infrastructure Blueprint

The deployment topology replaces legacy environments with an immutable, isolated, containerized lifecycle driven by **Docker**, orchestrated by **Jenkins**, registered securely within **Sonatype Nexus/JFrog Artifactory**, and shipped via **Python Fabric**.

### 4.1 Production Core Containerization (`Dockerfile`)

The application infrastructure must build into clean, isolated layers. Put this in the repository root:

```dockerfile
FROM python:3.11-slim

# Install system dependencies needed for native C extensions or ML runtimes
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

```

### 4.2 Automated Continuous Integration Pipeline (`Jenkinsfile`)

Jenkins serves as the central orchestration controller, handling test execution, containerization packaging, asset registration, and triggering remote delivery commands.

```groovy
pipeline {
    agent any
    environment {
        REGISTRY = 'nexus.bueamarketwatch.internal:8082'
        IMAGE_NAME = 'market-watch-backend'
        REGISTRY_CREDENTIALS_ID = 'nexus-registry-auth-token'
        SSH_CREDENTIALS_ID = 'production-server-ssh-key'
    }
    stages {
        stage('Repository Pull') {
            steps {
                checkout scm
            }
        }
        stage('Test Execution Matrix') {
            steps {
                sh '''
                pip install -r requirements.txt
                pytest --maxfail=1 --disable-warnings
                '''
            }
        }
        stage('Immutable Docker Assembly') {
            steps {
                script {
                    appImage = docker.build("${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}")
                }
            }
        }
        stage('Artifact Registration') {
            steps {
                script {
                    docker.withRegistry("https://${REGISTRY}", REGISTRY_CREDENTIALS_ID) {
                        appImage.push()
                        appImage.push("latest")
                    }
                }
            }
        }
        stage('Automated Infrastructure Fabric Release') {
            steps {
                sshagent([SSH_CREDENTIALS_ID]) {
                    sh """
                    pip install fabric
                    fab deploy --image-tag=${BUILD_NUMBER}
                    """
                }
            }
        }
    }
}

```

### 4.3 Automated Delivery Script (`fabfile.py`)

Python Fabric connects directly to the deployment host environments via SSH, log managers, pulls down versioned docker assets, and safely cycles target resources.

```python
from fabric import task
import os

@task
def deploy(c, image_tag):
    """
    SSH remote invocation handler. Authenticates against the private Nexus/JFrog registry,
    pulls down target immutable images, terminates stale runtimes, and hot-swaps active routes.
    """
    registry_url = "nexus.bueamarketwatch.internal:8082"
    container_name = "live_market_watch_api"
    
    # Extract credentials piped securely through Jenkins environmental injections
    reg_user = os.getenv("REGISTRY_USER", "default_deployer")
    reg_pass = os.getenv("REGISTRY_PASS")
    
    print(f"Beginning delivery process on host {c.host} for build tag: {image_tag}")

    # Secure login directly inside target instance environment
    c.run(f"docker login {registry_url} -u {reg_user} -p {reg_pass}")

    # Ingest the targeted immutable artifact image
    c.run(f"docker pull {registry_url}/market-watch-backend:{image_tag}")

    # Gracefully remove running containers without crashing pipelines if instances do not exist yet
    c.run(f"docker stop {container_name} || true")
    c.run(f"docker rm {container_name} || true")

    # Run the production container
    c.run(
        f"docker run -d --name {container_name} "
        f"-p 8000:8000 "
        f"--restart always "
        f"-e DATABASE_URL=\$PROD_DB_URL "
        f"{registry_url}/market-watch-backend:{image_tag}"
    )
    
    print("Remote execution complete. Health checks successfully transferred.")

```

---

## 5. Error Handling & Operational Resiliency

| Exception Scenario | Root Detection | System/Application Handling Strategy |
| --- | --- | --- |
| **Unlisted Commodity Query** | Incoming entity lookup returns null from `commodities` metadata reference table. | Terminate API request execution early. Throw an `HTTP 400 Bad Request` with the message: `"The given item is not listed in the system."` |
| **CNN Inference Fault** | Document upload features low contrast, extreme motion blur, or unreadable handwriting vectors. | Catch standard exceptions inside `vision_service.py`. Fall back to an empty manual entry form layout. Return an `HTTP 422 Unprocessable Entity` containing the string: `"Could not parse image clearly. Please verify or enter fields manually."` |
| **Division-by-Zero Protection** | Target calculation maps a new reference entry configured with a 0 value for `base_units_per_bulk`. | Add check statements before running equations. If base units count matches `0`, log a critical error alert notification, gracefully reject the active entry pipeline, and avoid application runtime failure. |
| **Batch Aggregation Outliers** | Typographical inputs (e.g., typing 10,000 FCFA instead of 1,000 FCFA) or bad-faith data entries enter logs. | The 24-hour batch processing engine calculates sample variance and strips out any entry with a price deviation beyond $\pm 2$ standard deviations from that neighborhood's running average. This keeps the public dashboard reliable. |

---

## 6. Test-Driven Development (TDD) Plan

### 6.1 Unit & Machine Learning Testing Suite (`test_price_engine.py`)

* **Formula Verification:** Assert that passing an INS reference wholesale baseline of 30,000 FCFA for a commodity configured with 300 base units inside a bulk package computes a strict retail threshold limit score of exactly 110 FCFA ($[30000 / 300] \times 1.10 = 110$).
* **Visual State Switching Rules:** Assert that a mock user unit price execution entry of 111 FCFA triggers an active anomaly boolean indicator (`True`), throwing a **RED** UI color state token. Assert that a unit score of 105 FCFA evaluates to safe (`False`), triggering a **GREEN** UI token.
* **Inference Safety Proofs:** Pass corrupt file streams into vision parsing modules to assert that the `VisionProcessingError` catch architecture activates, forcing the system to return the standard manual-entry message.

### 6.2 Integration & Multi-User Coexistence Tests (`test_aggregation.py`)

* **Data Preservation Check:** Simulate two distinct users uploading different prices for the exact same commodity inside the same neighborhood concurrently (e.g., User A submits 100 FCFA, User B submits 170 FCFA for Garri in Molyko). Verify that both records persist safely in the database without overwriting each other.
* **Outlier Removal Check:** Seed a test dataset database table partition containing 10 normal pricing entries alongside 1 extreme anomaly. Run the asynchronous aggregation job and confirm that the extreme outlier is dropped, ensuring that the resulting `GET /api/analytics/heatmap` endpoint accurately reflects the mathematical mean of the clean submissions.
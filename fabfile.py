"""
fabfile.py
----------
Python Fabric 3 remote deployment automation for Buea Market Watch.

Invocation (from CI or developer workstation):
    fab deploy --image-tag=<BUILD_NUMBER>

Requires
--------
- Fabric ≥ 3.2  (``pip install fabric``)
- Environment variables injected by Jenkins credential bindings:
    REGISTRY_USER   – Nexus / JFrog registry username
    REGISTRY_PASS   – Nexus / JFrog registry password
    PROD_DB_URL     – PostgreSQL connection string for the live database
- SSH connectivity to the production host (key forwarded by sshagent in Jenkins)
"""

import os

from fabric import task

# ---------------------------------------------------------------------------
# Registry and container configuration constants
# ---------------------------------------------------------------------------

REGISTRY_URL    = "nexus.bueamarketwatch.internal:8082"
IMAGE_NAME      = "market-watch-backend"
CONTAINER_NAME  = "live_market_watch_api"
HOST_PORT       = 8000
CONTAINER_PORT  = 8000


@task
def deploy(c, image_tag):
    """
    SSH remote invocation handler for the Buea Market Watch deployment pipeline.

    Steps
    -----
    1. Authenticate against the private Nexus / JFrog Docker registry.
    2. Pull the immutable, build-numbered image artefact.
    3. Gracefully stop and remove the currently running container (if any).
    4. Launch the new container with the production database URL injected.

    Parameters
    ----------
    c : fabric.Connection
        SSH connection provided by Fabric (configured via fabfile hosts or CLI).
    image_tag : str
        Jenkins ``BUILD_NUMBER`` used to identify the immutable artefact.
    """
    # Pull credentials from the Jenkins-injected environment
    reg_user = os.getenv("REGISTRY_USER", "default_deployer")
    reg_pass = os.getenv("REGISTRY_PASS")
    prod_db  = os.getenv("PROD_DB_URL", "")

    full_image = f"{REGISTRY_URL}/{IMAGE_NAME}:{image_tag}"

    print(f"[deploy] Starting deployment on host '{c.host}' — build tag: {image_tag}")

    # -----------------------------------------------------------------------
    # 1. Registry authentication
    # -----------------------------------------------------------------------
    c.run(f"docker login {REGISTRY_URL} -u {reg_user} -p {reg_pass}", hide=True)
    print(f"[deploy] Authenticated against {REGISTRY_URL}")

    # -----------------------------------------------------------------------
    # 2. Pull the immutable image artefact
    # -----------------------------------------------------------------------
    c.run(f"docker pull {full_image}")
    print(f"[deploy] Image pulled: {full_image}")

    # -----------------------------------------------------------------------
    # 3. Stop and remove the currently running container (|| true = no-op if
    #    the container does not exist yet — safe for first-ever deploy)
    # -----------------------------------------------------------------------
    c.run(f"docker stop {CONTAINER_NAME} || true")
    c.run(f"docker rm   {CONTAINER_NAME} || true")
    print(f"[deploy] Stale container '{CONTAINER_NAME}' removed (if it existed)")

    # -----------------------------------------------------------------------
    # 4. Launch the new production container
    # -----------------------------------------------------------------------
    c.run(
        f"docker run -d "
        f"--name {CONTAINER_NAME} "
        f"-p {HOST_PORT}:{CONTAINER_PORT} "
        f"--restart always "
        f"-e DATABASE_URL={prod_db} "
        f"{full_image}"
    )
    print(
        f"[deploy] Container '{CONTAINER_NAME}' launched on port {HOST_PORT}. "
        f"Deployment complete for build {image_tag}."
    )

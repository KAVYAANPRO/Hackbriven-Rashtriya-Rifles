"""Start the API from any working directory.

    python run_api.py            # uses .env exactly as configured (MongoDB if MONGODB_URI is set)
    python run_api.py --local    # ignores MONGODB_URI: jobs live in memory, accounts/credits in
                                 # SQLite under storage/local - handy for trying things without
                                 # touching a shared database

The backend reads `.env` and `storage/` relative to its own folder, so this
script switches there first. Port: BACKEND_PORT (default 8000).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))

    if "--local" in sys.argv[1:]:
        # Environment variables win over .env in pydantic-settings.
        os.environ["MONGODB_URI"] = ""
        os.environ["STORAGE_DIR"] = "storage/local"

    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()

"""Write the API's OpenAPI schema as JSON, the contract the frontend's types come from.

    uv run python scripts/export_openapi.py ../frontend/openapi.json

Building the schema needs no database, network or secrets: the app is created with
placeholder settings and never started.
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import HttpUrl, SecretStr

from giftai.core.config import Settings
from giftai.main import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="where to write the schema")
    arguments = parser.parse_args()

    # Only the shape of the API matters, so these placeholders are never used to connect.
    settings = Settings(
        _env_file=None,
        database_url=SecretStr("postgresql://unused:unused@localhost:5432/unused"),
        supabase_url=HttpUrl("https://unused.supabase.co"),
    )
    schema = create_app(settings).openapi()
    arguments.output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

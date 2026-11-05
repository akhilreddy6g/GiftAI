"""Sign in to Supabase with an email and password and print the access token.

To call the API by hand, outside the app:

    SUPABASE_URL=https://<project>.supabase.co SUPABASE_ANON_KEY=<publishable key> \
        uv run python scripts/get_access_token.py you@example.com

    curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/me

The user must already exist (create one under Authentication > Users in the Supabase
dashboard). The anon / publishable key is meant to be public; it is not a secret.
"""

import argparse
import getpass
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    arguments = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not anon_key:
        print("Set SUPABASE_URL and SUPABASE_ANON_KEY first.", file=sys.stderr)
        return 2

    password = getpass.getpass(f"Password for {arguments.email}: ")
    try:
        response = httpx.post(
            f"{supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": anon_key},
            json={"email": arguments.email, "password": password},
            timeout=10,
        )
    except httpx.HTTPError as error:
        print(f"Could not reach Supabase: {error}", file=sys.stderr)
        return 1

    if response.status_code != httpx.codes.OK:
        detail = response.json().get("error_description") or response.text
        print(f"Sign-in failed ({response.status_code}): {detail}", file=sys.stderr)
        return 1

    print(response.json()["access_token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

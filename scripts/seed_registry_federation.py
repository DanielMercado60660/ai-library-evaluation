#!/usr/bin/env python3
"""Seed registry with spoke catalog URLs for federated resolution.

Reads the network seed manifest and registers each spoke library's
catalog_url in the registry service so ILL can resolve holdings.

Usage:
    python scripts/seed_registry_federation.py                    # local URLs
    python scripts/seed_registry_federation.py --docker           # docker container names
    python scripts/seed_registry_federation.py --registry-url http://localhost:8004
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "network_seed_manifest.json"

# Default port assignments for spoke catalogs
DEFAULT_PORTS = {
    "mastodon-institute": 8011,
    "mammoth-valley": 8012,
    "ivory-university": 8013,
    "tusk-conservatory": 8014,
}


def load_manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def build_catalog_url(library_code: str, docker: bool = False) -> str:
    """Build the catalog URL for a spoke library."""
    if docker:
        return f"http://catalog-{library_code.replace('-', '')}:8000"
    port = DEFAULT_PORTS.get(library_code)
    if port is None:
        raise ValueError(f"No default port for library '{library_code}'")
    return f"http://localhost:{port}"


def seed_registry(registry_url: str, manifest: dict, docker: bool = False) -> list[dict]:
    """Register spoke libraries with their catalog_url in the registry."""
    results = []

    for spoke in manifest.get("spokes", []):
        code = spoke["code"]
        catalog_url = build_catalog_url(code, docker)

        # Try PATCH first (update existing), fall back to POST (create new)
        payload_update = {"catalog_url": catalog_url}
        payload_create = {
            "code": code,
            "name": spoke["name"],
            "display_name": spoke["name"],
            "catalog_url": catalog_url,
            "specializations": spoke.get("specializations", []),
            "lending_enabled": True,
            "borrowing_enabled": True,
        }

        try:
            r = httpx.patch(f"{registry_url}/libraries/{code}", json=payload_update, timeout=5)
            if r.status_code == 200:
                results.append({"code": code, "catalog_url": catalog_url, "action": "updated"})
                continue
            elif r.status_code == 404:
                # Library doesn't exist yet — create it
                r = httpx.post(f"{registry_url}/libraries", json=payload_create, timeout=5)
                r.raise_for_status()
                results.append({"code": code, "catalog_url": catalog_url, "action": "created"})
            else:
                r.raise_for_status()
        except httpx.HTTPError as e:
            results.append({"code": code, "catalog_url": catalog_url, "action": "error", "error": str(e)})

    return results


def main():
    parser = argparse.ArgumentParser(description="Seed registry with spoke catalog URLs.")
    parser.add_argument("--registry-url", default="http://localhost:8004", help="Registry service URL")
    parser.add_argument("--docker", action="store_true", help="Use Docker container names instead of localhost")
    args = parser.parse_args()

    manifest = load_manifest()
    print(f"Seeding registry at {args.registry_url} with spoke catalog URLs")
    print("-" * 50)

    results = seed_registry(args.registry_url, manifest, args.docker)
    for r in results:
        status = r["action"]
        if status == "error":
            print(f"  {r['code']:25s} ERROR: {r['error']}")
        else:
            print(f"  {r['code']:25s} {r['catalog_url']:40s} [{status}]")

    errors = [r for r in results if r["action"] == "error"]
    if errors:
        print(f"\n{len(errors)} error(s) encountered.")
        return 1

    print(f"\nAll {len(results)} spokes registered successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

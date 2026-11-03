#!/bin/sh
# All Dutch source data for the AOI (scripts/aoi.py) into data/raw, cached: rerunning only fetches what is missing.
# AHN5 point clouds are opt-in (LAZ=1), ~4 GB; the AHN4 rasters from the WCS are enough to start.
set -e
cd "$(dirname "$0")/.."
sh scripts/fetch_osm.sh
PYTHONPATH=scripts uv run python scripts/fetch_ahn.py
[ -n "$LAZ" ] && PYTHONPATH=scripts uv run python scripts/fetch_ahn.py --laz
PYTHONPATH=scripts uv run python scripts/fetch_ortho.py
PYTHONPATH=scripts uv run python scripts/fetch_bgt.py
PYTHONPATH=scripts uv run --with pyogrio python scripts/fetch_3dbag.py
PYTHONPATH=scripts uv run python scripts/fetch_bomen.py

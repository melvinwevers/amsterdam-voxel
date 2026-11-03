#!/bin/sh
# Full data pipeline for Amsterdam: download (cached) -> mosaic -> voxelize -> web/public/data
# (~1.7 GB of downloads on first run plus ~20 MB of historical map tiles and ~50 MB of 20 cm DSM sheets; then about
# 10 min and ~4 GB RAM)
set -e
cd "$(dirname "$0")/.."
sh scripts/fetch_nl.sh
PYTHONPATH=scripts uv run python scripts/prep.py
PYTHONPATH=scripts uv run python scripts/notable.py      # Wikidata places + page views, for the labels
PYTHONPATH=scripts uv run python scripts/climate.py
PYTHONPATH=scripts uv run --with pyogrio --with geopandas python scripts/bgt_water.py   # surveyed water where OSM has none
PYTHONPATH=scripts uv run python scripts/voxelize.py
for s in terrain zones windows places phenology; do PYTHONPATH=scripts uv run python scripts/$s.py; done
# the historical layer (the year slider)
PYTHONPATH=scripts uv run python scripts/fetch_maps.py   # six town plans 1625-1985, on the grid
PYTHONPATH=scripts uv run python scripts/dempingen.py    # canals filled in since: water before their year
PYTHONPATH=scripts uv run python scripts/photos.py       # the city archive's copyright-free pictures per place
PYTHONPATH=scripts uv run --with "laspy[lazrs]" python scripts/insets.py  # landmarks at 0.5 m from the 20 cm DSM
rm -f web/public/data/flood.bin web/public/data/flood.json  # the Vistula's; Amsterdam's canals sit at a fixed level

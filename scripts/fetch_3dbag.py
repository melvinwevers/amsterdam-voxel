"""3D BAG (TU Delft 3D geoinformation group, CC BY 4.0) over the AOI -> data/raw/3dbag/<z>-<x>-<y>.city.json.gz

Every building of the BAG register as LoD1.2, LoD1.3 and LoD2.2 solids (real roof shapes, reconstructed from AHN5 in
Amsterdam), with attributes such as ridge and eave heights, roof type and the BAG construction year. Tiles are
CityJSON; the tile index is a FlatGeobuf read with a bbox filter, and every tile is checked against its SHA-256.

usage: uv run --with pyogrio python scripts/fetch_3dbag.py
"""
import hashlib

import pyogrio.raw

from nl_fetch import aoi_box, get, raw

VERSION = "v20250903"  # latest release on 3dbag.nl/en/download (Nov 2026)
# the object store behind data.3dbag.nl/<version>/ (the tile index's own download links point there)
STORE = "https://3dbag.fsn1.your-objectstorage.com"
index = get(f"{STORE}/{VERSION}/tile_index.fgb", raw("3dbag", f"tile_index_{VERSION}.fgb"))
_, _, _, (ids, sha, url) = pyogrio.raw.read(index, bbox=aoi_box(margin=20), read_geometry=False)
print(len(ids), "3D BAG tiles")
for tid, h, u in zip(ids, sha, url):
    p = raw("3dbag", tid.replace("/", "-") + ".city.json.gz")
    fresh = not p.exists()
    if not get(u, p, decode=False):
        print("FAILED", tid)
        continue
    if fresh and hashlib.sha256(p.read_bytes()).hexdigest() != h:
        p.unlink()
        print("BAD CHECKSUM", tid)
        continue
    print(p)

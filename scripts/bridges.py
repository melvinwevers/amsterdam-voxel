"""Amsterdam's bridges by material on the AOI grid -> data/bridges.npy (uint8 [D, W]: 0 none, 1 brick, 2 wood,
3 steel, 4 concrete)

From the city's register of civil structures (api.data.amsterdam.nl, civieleconstructies / brug, 1837 bridges with
footprint, material and fixed or movable): voxelize.py colours each deck's underside and sides by it (the masonry
arches' brick, the wooden bridges' timber, painted steel, concrete), makes brick ones a voxel deeper and gives every
deck a parapet where it faces the water.

usage: uv run python scripts/bridges.py
"""
import sys
from pathlib import Path

import numpy as np
import rasterio.features
import requests
from affine import Affine
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).parent))
from aoi import CX, CY, D, I0, J0, THETA, W  # noqa: E402
from nl_fetch import UA, aoi_wkt  # noqa: E402

assert THETA == 0
URL = "https://api.data.amsterdam.nl/v1/civieleconstructies/brug/"
MAT = {"Metselwerk": 1, "Hout": 2, "Staal": 3, "Gewapend beton": 4, "Beton": 4, "Composiet": 4}
feats, page = [], 1
while True:
    r = requests.get(URL, headers={**UA, "Accept-Crs": "EPSG:28992", "Content-Crs": "EPSG:28992"}, timeout=300,
                     params={"geometrie[intersects]": aoi_wkt(margin=0), "_format": "geojson", "_pageSize": 1000, "page": page})
    r.raise_for_status()
    got = r.json()["features"]
    feats += got
    if len(got) < 1000:
        break
    page += 1
T = Affine(1, 0, CX - I0, 0, -1, CY + J0)
shapes = [(shape(f["geometry"]), MAT.get(f["properties"].get("materiaal"), 4)) for f in feats if f.get("geometry")]
grid = rasterio.features.rasterize(shapes, out_shape=(D, W), transform=T, dtype=np.uint8) if shapes else np.zeros((D, W), np.uint8)
np.save("data/bridges.npy", grid)
print(len(feats), "bridges in the map;", {k: int((grid == v).sum()) for k, v in (("brick", 1), ("wood", 2), ("steel", 3), ("concrete", 4))}, "cells")

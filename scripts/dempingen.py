"""Canals and harbours since filled in, for the viewer's year slider -> web/public/data/dempingen.bin + .json

From the city's historical soil information (api.data.amsterdam.nl, historische_bodeminformatie /
dempingen_en_ophogingen, after HisGIS and the city archive): every filling ("Demping") with the years it was done.
Before its year, the viewer shows the filled ground as water again (Rozengracht, Elandsgracht, Nieuwezijds Voorburgwal,
Damrak's inner part ...).

Output: dempingen.bin = gzip of uint8[ceil(D/2), ceil(W/2)], per 2 m cell the year it was filled in as
(year - 1500) / 2 (1..255, i.e. 1502-2010; 0 = never filled; the earliest year given, so the water shows until the work
began); dempingen.json: the list of fillings (year, area, note) for reference.

usage: uv run python scripts/dempingen.py
"""
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio.features
import requests
from affine import Affine
from shapely.geometry import shape
import shapely

sys.path.insert(0, str(Path(__file__).parent))
from aoi import D, W, to_grid  # noqa: E402
from nl_fetch import UA, aoi_wkt  # noqa: E402

URL = "https://api.data.amsterdam.nl/v1/historische_bodeminformatie/dempingen_en_ophogingen/"
CRS = {"Accept-Crs": "EPSG:28992", "Content-Crs": "EPSG:28992"}
OUT = Path("web/public/data")
C = 2  # metres per cell

feats, page = [], 1
while True:
    r = requests.get(URL, headers={**UA, **CRS}, timeout=300,
                     params={"geometrie[intersects]": aoi_wkt(margin=0), "_format": "geojson", "_pageSize": 1000, "page": page})
    r.raise_for_status()
    got = r.json()["features"]
    feats += got
    if len(got) < 1000:
        break
    page += 1
fills = []
for f in feats:
    p = f["properties"]
    y = p.get("vanMinimaalJaar") or p.get("vanMaximaalJaar")
    if p.get("categorie") != "Demping" or not y or not f.get("geometry"):
        continue
    g = shapely.transform(shape(f["geometry"]), lambda xy: np.stack(to_grid(xy[:, 0], xy[:, 1]), 1))
    if g.is_empty or g.area < 20:
        continue
    fills.append((int(y), g, p.get("opmerking") or p.get("beschrijving") or ""))
fills.sort(key=lambda t: t[0])  # earliest first, so the latest filling (the one that made it land as it is now) wins
code = lambda y: int(np.clip(round((y - 1500) / 2), 1, 255))
idx = rasterio.features.rasterize([(g, code(y)) for y, g, n in fills],
                                  out_shape=(math.ceil(D / C), math.ceil(W / C)), transform=Affine(C, 0, 0, 0, C, 0), dtype=np.uint8)
(OUT / "dempingen.bin").write_bytes(gzip.compress(idx.tobytes(), 9, mtime=0))
json.dump({"cell": C, "fillings": [[y, round(g.area), n] for y, g, n in sorted(fills, key=lambda t: t[0])],
           "source": "Gemeente Amsterdam, historische bodeminformatie: dempingen (HisGIS, Stadsarchief)"},
          open(OUT / "dempingen.json", "w"), ensure_ascii=False)
print(len(feats), "features in the AOI,", len(fills), "fillings;", int((idx > 0).sum()) * C * C, "m2 filled")
for y, g, n in sorted(fills, key=lambda t: -t[1].area)[:25]:
    print(" ", y, round(g.area), "m2", n[:70])

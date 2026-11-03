"""The city of 1832 where it has gone since: buildings of the 1832 cadastre that no building of today stands in for,
for the viewer's year slider -> web/public/data/hist/

Source: the HisGIS Amsterdam 1832 cadastre's building layer as published by the UvA ("Amsterdam huurwaarden 1832",
Zenodo 10.5281/zenodo.6949127, CC BY 4.0; after Feikens, Fryske Akademy, HISGIS Amsterdam 2013): 36 745 buildings
with owner, profession, use and rental value.

Each 1832 building is shown from 1700 (the city's extent, and much of its fabric, was that of 1832 by then: an
approximation) until the year the building of today on its footprint went up; where nothing stands now (cleared for a
street or square) until 1880. Where a building of today predates 1832 and covers most of the footprint, the 1832 one
is left out: that building is shown already. Height: the median height of the surviving pre-1850 buildings within
40 m (the cadastre has none). Colour: the old centre's brick, a few plastered, as in voxelize.py's palette by era.

Output (hist/): {tx}_{ty}.bin level-1 tiles (scripts/tiles.py format) holding only these buildings; ids.bin = gzip of
uint16[D, W], the 1832 building per column (1-based, 0 none); index.json = per building [from, until, height, use],
the tiles, and the palette ids used.

usage: uv run --with pyogrio --with geopandas python scripts/hist1832.py   (after voxelize.py and zones.py)
"""
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
import pyogrio
import rasterio.features
from affine import Affine

sys.path.insert(0, str(Path(__file__).parent))
from aoi import CX, CY, D, I0, J0, THETA, W  # noqa: E402

assert THETA == 0
OUT = Path("web/public/data/hist")
N = 128
FROM, CLEARED = 1700, 1880

meta = json.load(open("web/public/data/meta.json"))
pal = np.array(meta["palette"])
gz = np.load("data/ground.npz")
g, bh = gz["g"].astype(np.int32), gz["b"].astype(np.int32)
zones = json.load(open("web/public/data/zones.json"))
zyears = np.array([0] + zones["years"])
zbld = np.frombuffer(gzip.decompress(Path("web/public/data/zones.bin").read_bytes()), np.uint16)[W * D:].reshape(D, W)
cur_year = zyears[zbld]  # year of today's building per column (0: none or unknown)


def nearest(hexes, mat):
    """palette ids nearest to the colours, among entries of a material"""
    ids = np.nonzero(pal[:, 3] == mat)[0]
    out = []
    for h in hexes:
        c = np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)])
        out.append(int(ids[np.argmin(np.abs(pal[ids, :3] - c).sum(1))]))
    return out


WALLS = nearest(["#5e3127", "#6a392b", "#75402f", "#4f3129", "#623a2e", "#7e4734", "#3f302b", "#5a3f33",
                 "#e6dfd0", "#d8d0bf"], 1)
ROOFS = nearest(["#55504c", "#6b4a3c", "#4a4b50", "#7a5a48"], 12)

gdf = pyogrio.read_dataframe("data/raw/hisgis1832/b.shp")
T = Affine(1, 0, CX - I0, 0, -1, CY + J0)
hid = rasterio.features.rasterize(((geom, i + 1) for i, geom in enumerate(gdf.geometry) if geom is not None),
                                  out_shape=(D, W), transform=T, dtype=np.int32)
n = len(gdf)
idx = np.flatnonzero(hid.ravel())
hb = hid.ravel()[idx]
area = np.bincount(hb, minlength=n + 1)
# coverage by today's buildings: those from before 1832 (survivors) and the rest
cy = cur_year.ravel()[idx]
covered = np.bincount(hb, weights=(zbld.ravel()[idx] > 0), minlength=n + 1)
surv = np.bincount(hb, weights=(cy > 0) & (cy <= 1832), minlength=n + 1)
first_new = np.full(n + 1, 9999)
newer = (cy > 1832)
np.minimum.at(first_new, hb[newer], cy[newer])
until = np.where(covered >= 0.3 * area, np.where(first_new < 9999, first_new, CLEARED), CLEARED)
keep = (area > 4) & (surv < 0.5 * area)
keep[0] = False
# heights from the surviving pre-1850 buildings round each one (40 m box), 12 m where there are none
old = (cur_year > 0) & (cur_year <= 1850) & (bh > 3)
rows, cols = np.divmod(idx, W)
cr = np.bincount(hb, weights=rows, minlength=n + 1) / np.maximum(area, 1)
cc = np.bincount(hb, weights=cols, minlength=n + 1) / np.maximum(area, 1)
height = np.zeros(n + 1, np.int32)
for k in np.nonzero(keep)[0]:
    r0, c0 = int(cr[k]), int(cc[k])
    box = bh[max(0, r0 - 40):r0 + 40, max(0, c0 - 40):c0 + 40][old[max(0, r0 - 40):r0 + 40, max(0, c0 - 40):c0 + 40]]
    height[k] = int(np.clip(np.median(box), 6, 22)) if box.size > 50 else 12
use = gdf["Soort_ei_1"].fillna("").tolist()
# small outbuildings (sheds, back-houses) lower
for k in np.nonzero(keep)[0]:
    u = use[k - 1].lower()
    if any(w in u for w in ("schuur", "stal", "loods", "koetshuis", "achterhuis")):
        height[k] = min(height[k], 7)
# columns: kept 1832 buildings, not where a building from before 1832 stands today
col_ok = (hid > 0) & keep[hid] & ~((cur_year > 0) & (cur_year <= 1832))
ids = np.where(col_ok, hid, 0).astype(np.int32)
# renumber the kept ones 1..m
kept = np.nonzero(keep & (np.bincount(ids.ravel(), minlength=n + 1) > 0))[0]
remap = np.zeros(n + 1, np.int32)
remap[kept] = np.arange(1, len(kept) + 1)
ids = remap[ids].astype(np.uint16)
wall = np.array([0] + [WALLS[(int(k) * 2654435761) % len(WALLS)] for k in kept])
roof = np.array([0] + [ROOFS[(int(k) * 40503) % len(ROOFS)] for k in kept])
hgt = np.array([0] + [int(height[k]) for k in kept])

OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.bin"):
    f.unlink()
tiles = []
S = N + 2
for ty in range(math.ceil(D / N)):
    for tx in range(math.ceil(W / N)):
        r0, c0 = ty * N - 1, tx * N - 1  # apron
        sub = np.zeros((S, S), np.int32)
        gsub = np.zeros((S, S), np.int32)
        rr0, rr1, cc0, cc1 = max(0, r0), min(D, r0 + S), max(0, c0), min(W, c0 + S)
        sub[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = ids[rr0:rr1, cc0:cc1]
        gsub[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = g[rr0:rr1, cc0:cc1]
        if not sub[1:-1, 1:-1].any():
            continue
        counts = np.zeros(S * S, np.uint16)
        runs = []
        for i, k in enumerate(sub.ravel()):
            if not k:
                continue
            z0, h = int(gsub.ravel()[i]), int(hgt[k])
            runs += [(z0, h - 1, int(wall[k])), (z0 + h - 1, 1, int(roof[k]))]
            counts[i] = 2
        blob = counts.tobytes() + np.clip(gsub, 0, 255).astype(np.uint8).ravel().tobytes() + np.array(runs, np.uint16).tobytes()
        (OUT / f"{tx}_{ty}.bin").write_bytes(gzip.compress(blob, 9, mtime=0))
        tiles.append([tx, ty])
(OUT / "ids.bin").write_bytes(gzip.compress(ids.tobytes(), 9, mtime=0))
info = [[FROM, int(until[k]), int(height[k]), use[k - 1]] for k in kept]
json.dump(dict(source="HisGIS Amsterdam 1832 cadastre, building layer (UvA, Zenodo 10.5281/zenodo.6949127, CC BY 4.0)",
               N=N, tiles=tiles, buildings=info), open(OUT / "index.json", "w"), ensure_ascii=False)
u = np.array([b[1] for b in info])
print(f"{n} buildings in the 1832 cadastre; {len(kept)} gone since and drawn ({int(col_ok.sum()) / 1e6:.2f} km2),",
      f"{len(tiles)} tiles; replaced by 1880: {(u <= 1880).sum()}, by 1920: {(u <= 1920).sum()}, after: {(u > 1920).sum()}")

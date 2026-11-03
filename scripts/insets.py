"""Landmarks at 0.5 m: finer voxel models of the best-known buildings, shown in place of their 1 m versions.

Shape: Kadaster's 3D Basisvoorziening DSM 20 cm (2025, a regular point grid from the aerial photos, PDOK; fetched
per 250 m sheet into data/raw/dsm20), the highest point in each 0.5 m cell, inside the landmark's OSM outline and
parts, standing on the model's ground. Spires, pinnacles, gables and the cupola come out at twice the resolution.
Colour: from the finished 1 m model (web/public/data/tiles/1, so the curation in overrides_amsterdam.json carries
over): each 0.5 m voxel takes the 1 m voxel it lies in, else the nearest one at that height round it, else its
column's top (the roof).

Output web/public/data/insets/<key>.bin in the tile format (scripts/tiles.py: counts, ground, runs, no detail) with
N = the larger side in cells, z in 0.5 m cells above the model base, ground in metres; and index.json: per landmark
the grid corner (x0, y0 m), N, the zones building ids it replaces (scripts/zones.py) and its year. The viewer meshes
them at unit scale and scales the mesh by 0.5 (web/src/insets.ts).

usage: uv run python scripts/insets.py   (after voxelize.py and zones.py)
"""
import gzip
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import rasterio.features
from affine import Affine
from scipy import ndimage
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
from aoi import to_grid, to_world  # noqa: E402
from nl_fetch import get, raw  # noqa: E402
from osm import OSM  # noqa: E402
from landmarks import OVERRIDES  # noqa: E402

R = 0.5  # metres per inset voxel
OUT = Path("web/public/data/insets")
TILES = Path("web/public/data/tiles/1")
DSM = "https://download.pdok.nl/kadaster/basisvoorziening-3d/v1_0/2025/dsm20/laz/DSM_{}.laz"
# key -> OSM ids or names of the outlines (and their parts) that make up the landmark
LANDMARKS = {
    "westertoren": ["99203577"],
    "westerkerk": ["Westerkerk"],
    "zuiderkerk": ["114120359"],
    "munttoren": ["57862728"],
    "montelbaanstoren": ["57864086"],
    "schreierstoren": ["Schreierstoren"],
    "oudekerk": ["57857592"],
    "nieuwekerk": ["220749328"],
    "paleis": ["Koninklijk Paleis"],
    "rijksmuseum": ["431070185"],
    "beurs": ["Beurs van Berlage"],
    "waag": ["Waag"],
    "portugese_synagoge": ["Portugese Synagoge"],
    "concertgebouw": ["Concertgebouw"],
}

meta = json.load(open("web/public/data/meta.json"))
BASE = meta["base"]
gz = np.load("data/ground.npz")
g, bosm = gz["g"].astype(np.int32), gz["osm"]
D, W = g.shape
zones = json.load(open("web/public/data/zones.json"))
zbin = np.frombuffer(gzip.decompress(Path("web/public/data/zones.bin").read_bytes()), np.uint16)
zbld = zbin[W * D:].reshape(D, W)
osm = OSM()


# ---- the finished 1 m model, column by column, from its level-1 tiles
def tile_cols(tx, ty, _cache={}):
    if (tx, ty) not in _cache:
        p = TILES / f"{tx}_{ty}.bin"
        if not p.exists():
            _cache[(tx, ty)] = None
        else:
            b = gzip.decompress(p.read_bytes()); n2 = 130 * 130
            counts = np.frombuffer(b, np.uint16, n2)
            runs = np.frombuffer(b, np.uint16, int(counts.sum()) * 3, n2 * 3).reshape(-1, 3)
            off = np.concatenate([[0], np.cumsum(counts, dtype=np.int64)])
            _cache[(tx, ty)] = (counts, runs, off)
    return _cache[(tx, ty)]


def column(c, r):
    """palette id per 1 m z of the model column (c, r): an array, 0 = empty"""
    t = tile_cols(c // 128, r // 128)
    if t is None or not (0 <= c < W and 0 <= r < D):
        return np.zeros(0, np.uint16)
    counts, runs, off = t
    i = (r % 128 + 1) * 130 + (c % 128 + 1)
    rr = runs[int(off[i]):int(off[i + 1])]
    col = np.zeros(int((rr[:, 0] + rr[:, 1]).max()) if len(rr) else 0, np.uint16)
    for z0, n, p in rr:
        col[z0:z0 + n] = p
    return col


# ---- the 20 cm surface model
def dsm_points(x0, y0, x1, y1):
    import laspy
    xs, ys, zs = [], [], []
    for sx in range(int(x0 // 250) * 250, int(x1) + 1, 250):
        for sy in range(int(y0 // 250) * 250, int(y1) + 1, 250):
            name = f"{sx // 100}_{sy // 100}"
            p = get(DSM.format(name), raw("dsm20", f"DSM_{name}.laz"))
            if p is None:
                print("  no DSM sheet", name)
                continue
            f = laspy.read(p)
            x, y = np.asarray(f.x), np.asarray(f.y)
            k = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
            xs.append(x[k]); ys.append(y[k]); zs.append(np.asarray(f.z)[k])
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(zs)


def geoms_for(keys):
    gs, ids = [], set()
    for oid, typ, t, gm in osm.areas:
        name = t.get("name")
        if str(oid) in keys or (name in keys and "building" in t):
            gs.append(gm); ids.add(oid)
    # its parts (building:part inside the outline)
    if gs:
        outline = unary_union(gs)
        for oid, typ, t, gm in osm.areas:
            if "building:part" in t and outline.contains(gm.representative_point()):
                gs.append(gm)
    return unary_union(gs) if gs else None, ids


OUT.mkdir(parents=True, exist_ok=True)
index = []
for key, keys in LANDMARKS.items():
    geom, ids = geoms_for(set(keys))
    if geom is None:
        print(key, "not found in OSM"); continue
    minx, miny, maxx, maxy = geom.bounds  # grid metres (col, row)
    gx0, gy0 = math.floor(minx) - 2, math.floor(miny) - 2
    nx, ny = int(math.ceil((maxx + 2 - gx0) / R)), int(math.ceil((maxy + 2 - gy0) / R))
    N = max(nx, ny)
    # footprint at 0.5 m
    mask = rasterio.features.rasterize([(geom, 1)], out_shape=(N, N), transform=Affine(R, 0, gx0, 0, R, gy0), dtype=np.uint8) > 0
    # cell centres -> world (RD) for the DSM
    jj, ii = np.mgrid[0:N, 0:N]
    cx, cy = gx0 + (ii + 0.5) * R, gy0 + (jj + 0.5) * R
    wx, wy = to_world(cx, cy)
    px, py, pz = dsm_points(wx[mask].min() - 1, wy[mask].min() - 1, wx[mask].max() + 1, wy[mask].max() + 1)
    # each point -> inset cell (the grid is axis-aligned with RD: THETA = 0)
    gi, gj = to_grid(px, py)
    ci, cj = np.floor((gi - gx0) / R).astype(int), np.floor((gj - gy0) / R).astype(int)
    ok = (ci >= 0) & (ci < N) & (cj >= 0) & (cj < N)
    top = np.full((N, N), -1e9)
    np.maximum.at(top, (cj[ok], ci[ok]), pz[ok] - BASE)
    have = top > -1e8
    if not have[mask].any():
        print(key, "no DSM points"); continue
    _, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
    top = top[ir, ic]
    # 1 m model columns under each cell; its ground and (for colour) its voxels
    mc, mr = np.clip(np.floor(cx).astype(int), 0, W - 1), np.clip(np.floor(cy).astype(int), 0, D - 1)
    ground = g[mr, mc]
    model_top = max((len(column(c, r)) for c, r in set(zip(mc[mask].tolist(), mr[mask].tolist()))), default=0)
    top = np.minimum(top, model_top + 3)  # no cranes or noise above the landmark
    cols = {}
    def colz(c, r):
        if (c, r) not in cols:
            cols[(c, r)] = column(c, r)
        return cols[(c, r)]
    counts = np.zeros((N + 2) * (N + 2), np.uint16)
    gw = np.zeros((N + 2) * (N + 2), np.uint8)
    runs = []
    nvox = 0
    for j in range(N):
        for i in range(N):
            k = (j + 1) * (N + 2) + (i + 1)
            gw[k] = min(255, max(0, int(ground[j, i])))
            if not mask[j, i]:
                continue
            z0, z1 = int(round(ground[j, i] / R)), int(math.floor(top[j, i] / R))
            if z1 <= z0:
                continue
            c, r = int(mc[j, i]), int(mr[j, i])
            col = colz(c, r)
            nbr = [colz(c + dc, r + dr) for dc in (-1, 0, 1) for dr in (-1, 0, 1) if dc or dr]
            roof = int(col[np.nonzero(col)[0][-1]]) if col.any() else next((int(n_[np.nonzero(n_)[0][-1]]) for n_ in nbr if n_.any()), 0)
            pals = []
            for z in range(z0, z1):
                m = int(z * R)
                p = int(col[m]) if m < len(col) else 0
                if not p:
                    p = next((int(n_[m]) for n_ in nbr if m < len(n_) and n_[m]), 0)
                pals.append(p or roof)
            if not roof and not any(pals):
                continue
            # runs of equal palette
            start = 0
            for z in range(1, len(pals) + 1):
                if z == len(pals) or pals[z] != pals[start]:
                    runs.append((z0 + start, z - start, pals[start])); counts[k] += 1; start = z
            nvox += z1 - z0
    blob = counts.tobytes() + gw.tobytes() + np.array(runs, np.uint16).reshape(-1, 3).tobytes()
    (OUT / f"{key}.bin").write_bytes(gzip.compress(blob, 9, mtime=0))
    # the zones buildings it replaces: those whose columns lie mostly inside the footprint
    sub = zbld[max(0, int(miny)):int(maxy) + 1, max(0, int(minx)):int(maxx) + 1]
    bl = [int(b) for b in np.unique(sub) if b]
    fp = rasterio.features.rasterize([(geom, 1)], out_shape=sub.shape, transform=Affine(1, 0, max(0, int(minx)), 0, 1, max(0, int(miny))), dtype=np.uint8) > 0
    bl = [b for b in bl if (fp & (sub == b)).sum() > 0.5 * (sub == b).sum()]
    years = [zones["years"][b - 1] for b in bl if zones["years"][b - 1]]
    index.append(dict(key=key, x0=gx0, y0=gy0, N=N, r=R, bld=bl, year=min(years) if years else 0, file=f"insets/{key}.bin"))
    print(f"{key}: {N}x{N} cells, {nvox} voxels at {R} m, top {top[mask].max():.1f} m above base, replaces buildings {bl}")
json.dump(dict(source="Kadaster 3D Basisvoorziening DSM 20 cm (2025), PDOK; colours from the 1 m model", insets=index),
          open(OUT / "index.json", "w"), indent=1)

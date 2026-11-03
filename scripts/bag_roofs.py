"""Roof heights from 3D BAG's LoD2.2 models on the AOI grid -> data/bag_roof.npy (float32 [D, W], m NAP; NaN none)

The LiDAR DSM gives every roof, but as a cloud: ragged steps, chimneys and noise, and the flattening in voxelize.py
terraces pitched roofs. 3D BAG (TU Delft, CC BY 4.0, data/raw/3dbag from fetch_3dbag.py) reconstructs each roof as
planar faces from AHN, so a canal house's gable comes out as clean symmetric steps. Every RoofSurface of the LoD2.2
solids is fitted with a plane (least squares over its outer ring), its 2D outline burnt into the grid with the highest
faces last (they win where faces overlap in plan), and each cell takes its face's plane at the cell centre.
voxelize.py uses it where it agrees with the LiDAR to within 6 m (towers and spires keep the LiDAR's).

usage: uv run python scripts/bag_roofs.py
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import rasterio.features
from affine import Affine
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).parent))
from aoi import CX, CY, D, I0, J0, THETA, W  # noqa: E402

assert THETA == 0
T = Affine(1, 0, CX - I0, 0, -1, CY + J0)  # RD -> grid
faces = []  # (polygon in RD, a, b, c, zmax)
for p in sorted(Path("data/raw/3dbag").glob("*.city.json.gz")):
    cj = json.loads(gzip.decompress(p.read_bytes()))
    tr = cj["transform"]
    V = np.array(cj["vertices"], np.float64) * tr["scale"] + tr["translate"]
    for obj in cj["CityObjects"].values():
        for geom in obj.get("geometry", []):
            if str(geom.get("lod")) != "2.2" or "semantics" not in geom:
                continue
            sem, vals = geom["semantics"]["surfaces"], geom["semantics"]["values"]
            shells = geom["boundaries"] if geom["type"] == "Solid" else [geom["boundaries"]]
            svals = vals if geom["type"] == "Solid" else [vals]
            for shell, sv in zip(shells, svals):
                for surf, s in zip(shell, sv):
                    if s is None or sem[s]["type"] != "RoofSurface":
                        continue
                    ring = V[surf[0]]
                    if len(ring) < 3:
                        continue
                    A = np.c_[ring[:, 0] - ring[0, 0], ring[:, 1] - ring[0, 1], np.ones(len(ring))]
                    (a, b, c), *_ = np.linalg.lstsq(A, ring[:, 2], rcond=None)
                    poly = Polygon(ring[:, :2])
                    if not poly.is_valid or poly.area < 0.5:
                        continue
                    faces.append((poly, a, b, c - a * ring[0, 0] - b * ring[0, 1], float(ring[:, 2].max())))
print(len(faces), "roof faces")
faces.sort(key=lambda f: f[4])  # highest last: wins where faces overlap in plan
fid = rasterio.features.rasterize(((f[0], i + 1) for i, f in enumerate(faces)), out_shape=(D, W), transform=T,
                                  dtype=np.int32)
abc = np.array([[0, 0, np.nan]] + [[f[1], f[2], f[3]] for f in faces])
rr, cc = np.mgrid[0:D, 0:W]
x, y = CX + (cc + 0.5 - I0), CY - (rr + 0.5 - J0)  # cell centres in RD
roof = (abc[fid, 0] * x + abc[fid, 1] * y + abc[fid, 2]).astype(np.float32)
np.save("data/bag_roof.npy", roof)
print(f"roof cells: {int(np.isfinite(roof).sum()) / 1e6:.2f} km2, height {np.nanmin(roof):.1f}-{np.nanmax(roof):.1f} m NAP")

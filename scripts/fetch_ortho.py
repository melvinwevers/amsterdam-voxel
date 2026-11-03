"""PDOK aerial orthophoto (Beeldmateriaal Nederland, CC BY 4.0) over the AOI -> data/raw/ortho/<layer>_<x0>_<y0>.tif

The national 8 cm RGB ortho, read through the PDOK WMS in 200 m windows (2500 px: the WMS refuses much more) and
written as JPEG-compressed GeoTIFFs in EPSG:28992. Layers: 2026_orthoHR (default, this spring's flight),
2025_orthoHR, Actueel_orthoHR, ... (GetCapabilities on the WMTS lists them).

usage: uv run python scripts/fetch_ortho.py [--layer 2026_orthoHR] [--res 0.08]
"""
import argparse
import io

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds

from nl_fetch import aoi_box, chunks, get, raw

WMS = "https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0"
TILE = 200  # m

ap = argparse.ArgumentParser()
ap.add_argument("--layer", default="2026_orthoHR")
ap.add_argument("--res", type=float, default=0.08)
a = ap.parse_args()
px = round(TILE / a.res)
assert px <= 2500, "WMS GetMap is capped near 2500 px; use a coarser --res"

for x0, y0, x1, y1 in chunks(aoi_box(margin=20, snap=TILE), TILE):
    out = raw("ortho", f"{a.layer}_{x0}_{y0}.tif")
    if out.exists():
        continue
    jpg = get(WMS, raw("ortho", "tmp", f"{x0}_{y0}.jpg"),
              params=dict(SERVICE="WMS", VERSION="1.3.0", REQUEST="GetMap", LAYERS=a.layer, STYLES="",
                          CRS="EPSG:28992", BBOX=f"{x0},{y0},{x1},{y1}", WIDTH=px, HEIGHT=px, FORMAT="image/jpeg"),
              ok=lambda r: r.headers.get("content-type", "").startswith("image/"))
    if not jpg:
        print("FAILED", x0, y0)
        continue
    rgb = np.asarray(Image.open(io.BytesIO(jpg.read_bytes())).convert("RGB")).transpose(2, 0, 1)
    with rasterio.open(out, "w", driver="GTiff", width=px, height=px, count=3, dtype="uint8", crs="EPSG:28992",
                       transform=from_bounds(x0, y0, x1, y1, px, px), compress="JPEG", photometric="YCBCR",
                       tiled=True, jpeg_quality=92) as f:
        f.write(rgb)
    jpg.unlink()
    print(out)

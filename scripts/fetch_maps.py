"""Historical maps of Amsterdam on the AOI grid, for the viewer's year slider -> web/public/data/maps/<year>.webp

The six town plans the Amsterdam Time Machine serves as web map tiles (tiles.amsterdamtimemachine.nl; georeferenced
and stitched by Webmapper and Jan Hartmann, UvA; scans from the Stadsarchief and the Allard Pierson):
  1625 Balthasar Florisz. van Berckenrode   1724 Gerrit de Broen   1876 Loman's Buurtatlas
  1909, 1943, 1985 Dienst der Publieke Werken, 1:1000
Each is fetched in Web Mercator tiles at its deepest zoom up to Z (cached in data/raw/maps), mosaicked, and resampled
onto the AOI grid (scripts/aoi.py) at 1 m per pixel, row 0 = grid row 0: the same frame as the voxels, so the viewer
looks a pixel up by grid column and row. Where a map has no data the pixel is transparent (WebP with alpha).

The 1625-1909 maps are long out of copyright; the 1943 and 1985 municipal maps carry no licence statement on the
Time Machine's page.

usage: uv run python scripts/fetch_maps.py
"""
import io
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from aoi import CRS, D, W, to_world  # noqa: E402
from nl_fetch import UA, get, raw  # noqa: E402

HOST = "https://images.huygens.knaw.nl/webmapper/maps"
MAPS = [  # year, layer, extension, title
    (1625, "berckenrode", "png", "Balthasar Florisz. van Berckenrode, 1625"),
    (1724, "debroen", "png", "Gerrit de Broen, 1724"),
    (1876, "loman", "jpeg", "Loman's Buurtatlas, 1876"),
    (1909, "pw-1909", "png", "Publieke Werken, 1909"),
    (1943, "pw-1943", "png", "Publieke Werken, 1943"),
    (1985, "pw-1985", "png", "Publieke Werken, 1985"),
]
Z = 17  # ~0.73 m per pixel at Amsterdam's latitude: finer than the 1 m grid
OUT = Path("web/public/data/maps")

T = Transformer.from_crs(CRS, 4326, always_xy=True)
jj, ii = np.mgrid[0:D, 0:W].astype(np.float64) + 0.5
lon, lat = T.transform(*to_world(ii, jj))
del ii, jj
n = 2 ** Z
mx = (lon + 180) / 360 * n  # Web Mercator tile coordinates at zoom Z, per grid pixel
my = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n
del lon, lat
tx0, tx1, ty0, ty1 = int(mx.min()), int(mx.max()), int(my.min()), int(my.max())
print(f"zoom {Z}: tiles x {tx0}-{tx1}, y {ty0}-{ty1} ({(tx1 - tx0 + 1) * (ty1 - ty0 + 1)} per map)")


def tile(layer, ext, x, y):
    p = get(f"{HOST}/{layer}/{Z}/{x}/{y}.{ext}", raw("maps", layer, f"{Z}_{x}_{y}.{ext}"), headers=UA, tries=3,
            ok=lambda r: r.headers.get("content-type", "").startswith("image/"))
    if p is None:
        return x, y, None
    try:
        return x, y, Image.open(p).convert("RGBA")
    except Exception:  # noqa: BLE001  (an empty or broken tile: no data there)
        return x, y, None


OUT.mkdir(parents=True, exist_ok=True)
index = []
for year, layer, ext, title in MAPS:
    nx, ny = tx1 - tx0 + 1, ty1 - ty0 + 1
    mosaic = np.zeros((ny * 256, nx * 256, 4), np.uint8)
    with ThreadPoolExecutor(4) as pool:  # polite: four at a time
        jobs = [pool.submit(tile, layer, ext, x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
        got = 0
        for j in jobs:
            x, y, im = j.result()
            if im is not None:
                mosaic[(y - ty0) * 256:(y - ty0 + 1) * 256, (x - tx0) * 256:(x - tx0 + 1) * 256] = np.asarray(im)
                got += 1
    # bilinear resample onto the grid (pixel centres)
    rows, cols = (my - ty0) * 256 - 0.5, (mx - tx0) * 256 - 0.5
    grid = np.stack([ndimage.map_coordinates(mosaic[..., k], [rows, cols], order=1, mode="constant", cval=0)
                     for k in range(4)], -1).astype(np.uint8)
    grid[..., 3] = np.where(grid[..., 3] > 200, 255, 0)  # hard edge where the map ends
    cover = float((grid[..., 3] > 0).mean())
    Image.fromarray(grid, "RGBA").save(OUT / f"{year}.webp", quality=82, method=6)
    size = (OUT / f"{year}.webp").stat().st_size // 1024
    print(f"{year} {layer}: {got} tiles, covers {cover:.0%} of the map, {size} KB")
    if got:
        index.append(dict(year=year, title=title, file=f"maps/{year}.webp", cover=round(cover, 3)))
json.dump(dict(source="Amsterdam Time Machine (tiles.amsterdamtimemachine.nl)", maps=index),
          open(OUT / "index.json", "w"), indent=1)

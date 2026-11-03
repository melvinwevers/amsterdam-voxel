"""When each tree was planted, for the viewer's year slider -> web/public/data/treeyears.bin

Amsterdam's tree register gives most trees a planting year (jaarVanAanleg, in web/public/data/trees.json as "date").
Every 2 m cell takes the year of the nearest tree within 8 m (its crown), so a crown goes as one; trees without a year
(the LiDAR-only ones, OSM's, undated register trees) give 0 and always stand.

Output: gzip of uint8[ceil(D/2), ceil(W/2)], (year - 1500) / 2 as in dempingen.bin (1..255, 0 = unknown).

usage: uv run python scripts/tree_years.py   (after voxelize.py)
"""
import gzip
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
from aoi import D, W  # noqa: E402

C = 2
trees = json.load(open("web/public/data/trees.json"))["trees"]
xy = np.array([(t["x"], t["y"]) for t in trees])
year = np.array([int(m.group()) if (m := re.match(r"\d{4}", str(t.get("date") or ""))) else 0 for t in trees])
year[year < 1700] = 0  # placeholders (1000 ...): no street tree here is that old
code = np.where(year > 0, np.clip(np.round((year - 1500) / 2), 1, 255), 0).astype(np.uint8)
h, w = math.ceil(D / C), math.ceil(W / C)
jj, ii = np.mgrid[0:h, 0:w]
dist, k = cKDTree(xy).query(np.stack([(ii.ravel() + 0.5) * C, (jj.ravel() + 0.5) * C], 1), distance_upper_bound=8)
out = np.zeros(h * w, np.uint8)
ok = np.isfinite(dist)
out[ok] = code[k[ok]]
Path("web/public/data/treeyears.bin").write_bytes(gzip.compress(out.tobytes(), 9, mtime=0))
dated = year[year > 0]
print(f"{len(trees)} trees, {len(dated)} with a planting year ({dated.min()}-{dated.max()}, median {int(np.median(dated))});",
      f"{int((out > 0).sum()) * C * C} m2 of crowns dated")

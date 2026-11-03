"""Shared bits of the Dutch fetchers (fetch_ahn.py, fetch_ortho.py, fetch_bgt.py, fetch_3dbag.py, fetch_bomen.py):
the AOI box in RD New and a polite, cached, retrying download."""
import math
import time
from pathlib import Path

import requests

from aoi import RAW, world_bounds

UA = {"User-Agent": "amsterdam-voxel/0.1 (+https://github.com/stared/warsaw-vibe-voxel)"}


def aoi_box(margin=20, snap=1):
    """AOI bounds in EPSG:28992 plus a margin, snapped outwards to multiples of `snap` metres."""
    x0, y0, x1, y1 = world_bounds(margin)
    return (math.floor(x0 / snap) * snap, math.floor(y0 / snap) * snap,
            math.ceil(x1 / snap) * snap, math.ceil(y1 / snap) * snap)


def aoi_wkt(margin=20):
    x0, y0, x1, y1 = aoi_box(margin)
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def chunks(box, size):
    """size x size m windows covering box, west to east, north to south."""
    x0, y0, x1, y1 = box
    for y in range(int(y1), int(y0), -size):
        for x in range(int(x0), int(x1), size):
            yield x, y - size, x + size, y


def raw(*parts):
    p = Path(RAW, *parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get(url, path, params=None, headers=None, ok=lambda r: True, tries=5, decode=True):
    """Download url to path unless it is already there; .part until complete. Returns the path, or None on failure.
    decode=False keeps the bytes as served even under Content-Encoding: gzip (3D BAG's .city.json.gz tiles are
    served that way, and their checksums are of the gzip)."""
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        return path
    part = path.with_name(path.name + ".part")
    for attempt in range(tries):
        try:
            with requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=600, stream=True) as r:
                r.raise_for_status()
                if not ok(r):
                    raise RuntimeError(f"unexpected {r.headers.get('content-type')}: {r.text[:200]}")
                blocks = r.iter_content(1 << 20) if decode else \
                    iter(lambda: r.raw.read(1 << 20, decode_content=False), b"")
                with open(part, "wb") as f:
                    for block in blocks:
                        f.write(block)
            part.rename(path)
            return path
        except Exception as e:  # noqa: BLE001
            print("  retry", path.name, e)
            time.sleep(5 * (attempt + 1))
    return None

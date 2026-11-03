"""AHN (Actueel Hoogtebestand Nederland) heights over the AOI -> data/raw/ahn*/

Default: the 0.5 m DSM and DTM rasters from the PDOK WCS (AHN4, flown 2020-22), cut to the AOI in 500 m GeoTIFFs:
  data/raw/ahn/dsm_<x0>_<y0>.tif, dtm_<x0>_<y0>.tif   (float32, EPSG:28992, nodata 3.4e38 over water in the DSM)
The DSM is "everything but water", the DTM is ground only (both squared-IDW gridded by RWS).

--laz: the AHN5 point clouds (flown 2023 over Amsterdam) from TU Delft's GeoTiles, as 1000 x 1250 m sub-tiles of the
5 x 6.25 km AHN map sheets -> data/raw/ahn5/<sheet>_<nn>.LAZ (~250-500 MB each). Newer than AHN4 and classified
(ground, building, water, bridge), but needs gridding (PDAL / laspy) before prep. 3D BAG's roofs already use AHN5.

usage: uv run python scripts/fetch_ahn.py [--laz]
"""
import sys

from nl_fetch import aoi_box, chunks, get, raw

WCS = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
GEOTILES = "https://geotiles.citg.tudelft.nl/AHN5_T"
# AHN map sheets around central Amsterdam: name -> (west x, north y) in RD; each is 5000 x 6250 m, split into 5 x 5
# sub-tiles numbered 01..25 row by row from the north-west corner. Read off the LAZ headers (bounds include a 20 m
# overlap). Add sheets here if the AOI grows.
SHEETS = {
    "25BZ2": (115000, 493750), "25EZ1": (120000, 493750), "25EZ2": (125000, 493750),
    "25DN2": (115000, 487500), "25GN1": (120000, 487500), "25GN2": (125000, 487500),
    "25DZ2": (115000, 481250), "25GZ1": (120000, 481250), "25GZ2": (125000, 481250),
}


def wcs():
    box = aoi_box(margin=20, snap=500)
    for x0, y0, x1, y1 in chunks(box, 500):
        for cov in ("dsm", "dtm"):
            p = get(WCS, raw("ahn", f"{cov}_{x0}_{y0}.tif"),
                    params=[("SERVICE", "WCS"), ("VERSION", "2.0.1"), ("REQUEST", "GetCoverage"),
                            ("COVERAGEID", f"{cov}_05m"), ("FORMAT", "image/tiff"),
                            ("SUBSET", f"x({x0},{x1})"), ("SUBSET", f"y({y0},{y1})")],
                    ok=lambda r: "tiff" in r.headers.get("content-type", ""))
            print(p or f"FAILED {cov} {x0} {y0}")


def subtiles(box):
    x0, y0, x1, y1 = box
    for name, (sx, sy) in SHEETS.items():
        for k in range(25):
            r, c = divmod(k, 5)
            tx0, ty1 = sx + c * 1000, sy - r * 1250
            if tx0 < x1 and tx0 + 1000 > x0 and ty1 - 1250 < y1 and ty1 > y0:
                yield f"{name}_{k + 1:02d}"


def laz():
    box = aoi_box(margin=20)
    tiles = list(subtiles(box))
    if box[0] < min(x for x, _ in SHEETS.values()) or box[2] > max(x for x, _ in SHEETS.values()) + 5000 or \
            box[1] < min(y for _, y in SHEETS.values()) - 6250 or box[3] > max(y for _, y in SHEETS.values()):
        sys.exit("AOI runs off the SHEETS table; add the neighbouring AHN sheets")
    print(len(tiles), "AHN5 sub-tiles:", " ".join(tiles))
    for t in tiles:
        print(get(f"{GEOTILES}/{t}.LAZ", raw("ahn5", f"{t}.LAZ")) or f"FAILED {t}")


if __name__ == "__main__":
    laz() if "--laz" in sys.argv else wcs()

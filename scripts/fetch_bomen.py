"""Amsterdam's tree register (gemeente Amsterdam, Bomen / stamgegevens) over the AOI -> data/raw/trees/bomen.geojson

~326 k trees city-wide, one point each with the Latin and Dutch species (soortnaam, soortnaamTop), height class
(boomhoogteklasseActueel, e.g. "d. 12 tot 15 m."), trunk-diameter class, planting year (jaarVanAanleg), owner and
the kind of ground it stands in. Read from the DSO API (api.data.amsterdam.nl) with a polygon filter in RD New.

usage: uv run python scripts/fetch_bomen.py
"""
import json

import requests

from nl_fetch import UA, aoi_wkt, raw

URL = "https://api.data.amsterdam.nl/v1/bomen/stamgegevens/"
CRS = {"Accept-Crs": "EPSG:28992", "Content-Crs": "EPSG:28992"}
PAGE = 5000

out = raw("trees", "bomen.geojson")
feats, page = [], 1
while True:
    r = requests.get(URL, headers={**UA, **CRS}, timeout=300,
                     params={"geometrie[intersects]": aoi_wkt(margin=20), "_format": "geojson",
                             "_pageSize": PAGE, "page": page})
    r.raise_for_status()
    got = r.json()["features"]
    feats += got
    print(f"  page {page}: {len(got)} trees ({r.headers.get('x-total-count')} in the AOI)")
    if len(got) < PAGE:
        break
    page += 1
json.dump({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:28992"}},
           "features": feats}, open(out, "w"))
print(out, len(feats), "trees")

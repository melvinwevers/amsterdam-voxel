"""BGT (Basisregistratie Grootschalige Topografie, CC0) over the AOI -> data/raw/bgt/bgt_<featuretype>.gml

The survey-grade base map the municipality keeps (updated nightly): every water, road, pavement and green surface as
a polygon, bridge decks (overbruggingsdeel), quay walls and other structures (kunstwerkdeel, scheiding), poles and
street lights (paal), street furniture, rails. Where OSM and BGT disagree on a surface, BGT is the measured one.

The PDOK download API is asynchronous: POST the request, poll its status, fetch the zip. Format: GML light
(plain GML 3.2, one file per feature type, current objects only).

usage: uv run python scripts/fetch_bgt.py
"""
import time
import zipfile

import requests

from nl_fetch import UA, aoi_wkt, get, raw

API = "https://api.pdok.nl/lv/bgt/download/v1_0"
TYPES = ["waterdeel", "ondersteunendwaterdeel", "waterinrichtingselement",
         "wegdeel", "ondersteunendwegdeel", "weginrichtingselement", "spoor",
         "begroeidterreindeel", "onbegroeidterreindeel", "vegetatieobject",
         "overbruggingsdeel", "kunstwerkdeel", "tunneldeel", "overigbouwwerk", "pand",
         "scheiding", "overigescheiding", "paal", "straatmeubilair", "bord", "kast", "bak", "put", "mast"]

zp = raw("bgt", "extract.zip")
if not zp.exists():
    r = requests.post(f"{API}/full/custom", headers=UA, timeout=60,
                      json={"featuretypes": TYPES, "format": "gmllight", "geofilter": aoi_wkt(margin=20)})
    r.raise_for_status()
    rid = r.json()["downloadRequestId"]
    print("BGT request", rid)
    while True:
        s = requests.get(f"{API}/full/custom/{rid}/status", headers=UA, timeout=60).json()
        print("  ", s.get("status"), s.get("progress"))
        if s.get("status") == "COMPLETED":
            break
        if s.get("status") not in ("PENDING", "RUNNING"):
            raise SystemExit(f"BGT request failed: {s}")
        time.sleep(10)
    href = s["_links"]["download"]["href"]
    get("https://api.pdok.nl" + href if href.startswith("/") else href, zp)
with zipfile.ZipFile(zp) as z:
    z.extractall(zp.parent)
    for n in z.namelist():
        print(zp.parent / n, z.getinfo(n).file_size)

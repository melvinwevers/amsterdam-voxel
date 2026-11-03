"""The BGT's water (surveyed by the city, data/raw/bgt/bgt_waterdeel.gml from fetch_bgt.py) on the AOI grid -> data/bgt_water.npy

OSM misses some of Amsterdam's water (the Rokin's open stretch, the Amstel south of the Munt, parts of the IJ:
mapped as relations the water step does not read): measured against the BGT, the model held 84 % of the water. The
BGT's waterdeel polygons (waterloop, watervlakte, ...) are the city's survey, so voxelize.py burns them as water on
top of OSM's.

usage: uv run --with pyogrio --with geopandas python scripts/bgt_water.py
"""
import sys
from pathlib import Path

import numpy as np
import pyogrio
import rasterio.features
from affine import Affine

sys.path.insert(0, str(Path(__file__).parent))
from aoi import CX, CY, D, I0, J0, THETA, W  # noqa: E402

assert THETA == 0, "the grid is assumed axis-aligned with RD here"
gdf = pyogrio.read_dataframe("data/raw/bgt/bgt_waterdeel.gml")
T = Affine(1, 0, CX - I0, 0, -1, CY + J0)  # grid col = I0 + (x - CX), row = J0 - (y - CY)
mask = rasterio.features.rasterize(((g, 1) for g in gdf.geometry if g is not None), out_shape=(D, W), transform=T,
                                   dtype=np.uint8) > 0
np.save("data/bgt_water.npy", mask)
print(len(gdf), "BGT water polygons,", round(mask.sum() / 1e6, 3), "km2 of water on the grid")

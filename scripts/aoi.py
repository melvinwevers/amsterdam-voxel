"""Area of interest shared by all pipeline steps.

Amsterdam's canal belt is a horseshoe, so there is no single street axis to rotate the grid to (Warsaw's 21.5° trick):
the grid stays on the RD axes (THETA = 0). Walls on the Herengracht/Keizersgracht/Prinsengracht arcs will staircase.

World coords: EPSG:28992 (RD New, Rijksdriehoek), x = easting, y = northing.
Grid coords: (i, j) continuous, i = column (east), j = row (growing south); cell (c, r) spans [c, c+1) x [r, r+1).
"""
import math

import numpy as np

CITY = "amsterdam"  # selects the curated landmarks, labels and camera presets (scripts/landmarks.py)
CRS = 28992
LEAF_OFF = True  # AHN and the PDOK ortho are flown in winter/early spring: bare crowns, no green (voxelize.py)
CX, CY = 121419.0, 487331.0  # Nationaal Monument op de Dam (read off the 2026 PDOK orthophoto), EPSG:28992
THETA = math.radians(0.0)
# 3400 x 3300 m: west past the Westerkerk and the Jordaan, east to Artis and the Plantage, north over Centraal Station
# onto the IJ, south past the Rijksmuseum to the Vondelpark's edge.
W, D = 3400, 3300
I0, J0 = 1700, 1300  # grid position of the Dam monument
RAW = "data/raw"

EU = np.array([math.cos(THETA), math.sin(THETA)])   # grid +i in world
EV = np.array([math.sin(THETA), -math.cos(THETA)])  # grid +j in world


def to_grid(x, y):
    dx, dy = np.asarray(x) - CX, np.asarray(y) - CY
    return I0 + dx * EU[0] + dy * EU[1], J0 + dx * EV[0] + dy * EV[1]


def to_world(i, j):
    u, v = np.asarray(i) - I0, np.asarray(j) - J0
    return CX + u * EU[0] + v * EV[0], CY + u * EU[1] + v * EV[1]


def world_bounds(margin=0):
    xs, ys = to_world(np.array([0, W, W, 0]), np.array([0, 0, D, D]))
    return xs.min() - margin, ys.min() - margin, xs.max() + margin, ys.max() + margin

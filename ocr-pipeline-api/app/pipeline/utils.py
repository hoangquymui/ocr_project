import os
import json


def ensure_dirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def polygon_to_bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]

    return {
        "x_min": float(min(xs)),
        "y_min": float(min(ys)),
        "x_max": float(max(xs)),
        "y_max": float(max(ys)),
        "width": float(max(xs) - min(xs)),
        "height": float(max(ys) - min(ys)),
    }

import os
import json


def ensure_dirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def find_first_pdf(input_dir):
    for name in os.listdir(input_dir):
        if name.lower().endswith(".pdf"):
            return os.path.join(input_dir, name)

    raise FileNotFoundError("Không tìm thấy file PDF trong thư mục input/")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


def block_bbox(lines):
    x_min = min(l["bbox"]["x_min"] for l in lines)
    y_min = min(l["bbox"]["y_min"] for l in lines)
    x_max = max(l["bbox"]["x_max"] for l in lines)
    y_max = max(l["bbox"]["y_max"] for l in lines)

    return {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "width": x_max - x_min,
        "height": y_max - y_min,
    }
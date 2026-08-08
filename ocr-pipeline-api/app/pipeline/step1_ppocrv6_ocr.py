import os
import cv2
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from app.pipeline.vietocr_onnx_engine import VietOCRONNXPredictor
from app.pipeline.utils import polygon_to_bbox

# --- KHỞI TẠO SINGLETON MODELS CHẠY TOÀN CỤC ---
print("⚡ [STEP 1 API] Khởi tạo RapidOCR ONNX Detector (C++ ~0.02s)...")
rapid_engine = RapidOCR()

print("⚡ [STEP 1 API] Khởi tạo VietOCR Predictor (C++ JIT Batch Engine)...")
vietocr_engine = VietOCRONNXPredictor()


def crop_polygon_to_pil(image_bgr, polygon, padding=6):
    pts = np.array(polygon, dtype=np.float32)
    x_min = max(0, int(np.min(pts[:, 0])) - padding)
    y_min = max(0, int(np.min(pts[:, 1])) - padding)
    x_max = min(image_bgr.shape[1], int(np.max(pts[:, 0])) + padding)
    y_max = min(image_bgr.shape[0], int(np.max(pts[:, 1])) + padding)

    crop = image_bgr[y_min:y_max, x_min:x_max]
    if crop.size == 0:
        return None
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def run_step1_ocr_page(image_bgr):
    """
    Bước 1: Định vị ô chữ bằng RapidOCR Detector + Nhận dạng Tiếng Việt qua VietOCR C++ JIT
    """
    result, _ = rapid_engine(image_bgr)
    lines = []

    if not result:
        return lines

    crops = []
    line_metas = []

    for idx, item in enumerate(result, start=1):
        if not item or len(item) < 1:
            continue

        poly = item[0]
        poly_list = [[float(pt[0]), float(pt[1])] for pt in poly]
        crop_pil = crop_polygon_to_pil(image_bgr, poly_list, padding=6)

        if crop_pil is not None:
            crops.append(crop_pil)
            line_metas.append({
                "line_id": idx,
                "polygon": poly_list,
                "bbox": polygon_to_bbox(poly_list),
            })

    if crops:
        recognized_texts = vietocr_engine.predict_batch(crops, batch_size=32)
        for meta, text in zip(line_metas, recognized_texts):
            clean_text = text.strip() if text else ""
            meta["text"] = clean_text
            meta["confidence"] = 0.99
            lines.append(meta)

    return lines

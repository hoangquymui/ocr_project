import collections
if not hasattr(collections, 'Mapping'):
    import collections.abc
    collections.Mapping = collections.abc.Mapping
    
import os
import shutil
import uuid
import cv2
import fitz
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from app.pipeline import (
    VietOCRONNXPredictor,
    process_layout_alignment,
    create_docx_document,
    detect_table_regions_api
)

app = FastAPI(title="End-to-End Pipeline OCR API", version="4.0")

TEMP_DIR = "/tmp/ocr_pipeline"
os.makedirs(TEMP_DIR, exist_ok=True)

print(">>> [API LOG] Khởi tạo RapidOCR ONNX Runtime Engine (Detector)...")
rapid_engine = RapidOCR()

print(">>> [API LOG] Khởi tạo VietOCR Predictor (Recognizer)...")
vietocr_engine = VietOCRONNXPredictor()


def crop_polygon_to_pil(image_bgr, poly, padding=6):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x_min = max(0, int(min(xs)) - padding)
    y_min = max(0, int(min(ys)) - padding)
    x_max = min(image_bgr.shape[1], int(max(xs)) + padding)
    y_max = min(image_bgr.shape[0], int(max(ys)) + padding)

    crop = image_bgr[y_min:y_max, x_min:x_max]
    if crop.size == 0:
        return None
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def run_ocr_on_cv2_image(img):
    """ RapidOCR ONNX Detector + VietOCR Recognizer """
    result, _ = rapid_engine(img)
    lines_output = []

    if not result:
        return lines_output

    crops = []
    line_metas = []

    for item in result:
        if not item or len(item) < 1:
            continue

        poly = item[0]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]

        crop_pil = crop_polygon_to_pil(img, poly, padding=6)
        if crop_pil is not None:
            crops.append(crop_pil)
            line_metas.append({
                "bbox": {
                    "x_min": float(min(xs)),
                    "y_min": float(min(ys)),
                    "x_max": float(max(xs)),
                    "y_max": float(max(ys))
                }
            })

    if crops:
        recognized_texts = vietocr_engine.predict_batch(crops, batch_size=32)
        for meta, text in zip(line_metas, recognized_texts):
            meta["text"] = text.strip() if text else ""
            lines_output.append(meta)

    return lines_output


@app.post("/api/v1/pipeline/ocr")
async def execute_full_pipeline(file: UploadFile = File(...)):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ['.pdf', '.jpg', '.jpeg', '.png']:
        raise HTTPException(status_code=400, detail="Hệ thống chỉ hỗ trợ xử lý file PDF hoặc Ảnh (JPG, PNG).")
        
    session_id = str(uuid.uuid4())
    upload_path = os.path.join(TEMP_DIR, f"{session_id}{ext}")
    output_docx_path = os.path.join(TEMP_DIR, f"{session_id}_final.docx")
    
    try:
        print(f">>> [API LOG] Nhận file từ Client: {filename} (Định dạng: {ext})")
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        pages_extracted_data = []

        if ext == '.pdf':
            doc = fitz.open(upload_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                img = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)
                
                raw_lines = run_ocr_on_cv2_image(img)
                tables, cover_frames = detect_table_and_cover_regions_api(img)
                structured_lines = process_layout_alignment(raw_lines, img.shape[1])
                pages_extracted_data.append({
                    "lines": structured_lines,
                    "tables": tables,
                    "cover_frames": cover_frames,
                    "width": img.shape[1]
                })
            doc.close()
        else:
            img = cv2.imread(upload_path)
            if img is None:
                raise HTTPException(status_code=400, detail="Không thể giải mã file ảnh.")
            raw_lines = run_ocr_on_cv2_image(img)
            tables, cover_frames = detect_table_and_cover_regions_api(img)
            structured_lines = process_layout_alignment(raw_lines, img.shape[1])
            pages_extracted_data.append({
                "lines": structured_lines,
                "tables": tables,
                "cover_frames": cover_frames,
                "width": img.shape[1]
            })

        print(f">>> [API LOG] Kết xuất file Word Flow Native + Đường Kẻ Bảng (Table Grid)...")
        create_docx_document(pages_extracted_data, output_docx_path)
        
        export_filename = f"OCR_{os.path.splitext(filename)[0]}.docx"
        return FileResponse(
            path=output_docx_path, 
            filename=export_filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống trong quá trình OCR: {str(e)}")
        
    finally:
        if os.path.exists(upload_path):
            os.remove(upload_path)
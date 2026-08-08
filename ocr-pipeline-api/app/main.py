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

from app.pipeline.document import create_document, add_page
from app.pipeline.step1_ppocrv6_ocr import run_step1_ocr_page
from app.pipeline.step2_layout_analysis import run_step2_layout_page
from app.pipeline.step3_reading_order import run_step3_reading_order_page
from app.pipeline.step4_docx_builder import run_step4_docx_builder

app = FastAPI(title="End-to-End Modular Pipeline OCR API", version="6.0")

TEMP_DIR = "/tmp/ocr_pipeline"
os.makedirs(TEMP_DIR, exist_ok=True)


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
            
        rendered_images = []

        if ext == '.pdf':
            doc = fitz.open(upload_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                img = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)
                rendered_images.append(img)
            doc.close()
        else:
            img = cv2.imread(upload_path)
            if img is None:
                raise HTTPException(status_code=400, detail="Không thể giải mã file ảnh.")
            rendered_images.append(img)

        document = create_document(source_name=filename, total_pages=len(rendered_images))

        # --- CHẠY TUẦN TỰ 4 BƯỚC MODULAR PIPELINE ---
        for page_idx, img in enumerate(rendered_images, start=1):
            print(f">>> [API LOG Trang {page_idx}] 1. Fast OCR (RapidOCR Det + VietOCR Rec)...")
            raw_lines = run_step1_ocr_page(img)

            page_data = add_page(
                document=document,
                page_number=page_idx,
                width=img.shape[1],
                height=img.shape[0],
                image_path=upload_path,
                lines=raw_lines
            )

            print(f">>> [API LOG Trang {page_idx}] 2. Layout, Style, Image, Table & Cover Frame Analysis...")
            page_data = run_step2_layout_page(page_data, img)

            print(f">>> [API LOG Trang {page_idx}] 3. Reading Order & Multi-Column Sorting...")
            page_data = run_step3_reading_order_page(page_data)

        print(">>> [API LOG] 4. Dựng File Word Reflowable Flow Native + Kẻ Bảng (Table Grid)...")
        run_step4_docx_builder(document, output_docx_path)

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
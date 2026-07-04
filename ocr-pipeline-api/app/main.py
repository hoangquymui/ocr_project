import collections
# Tự vá lỗi cấu trúc Mapping bị thiếu trên Python mới cho thư viện attrdict của PaddleOCR
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
from paddleocr import PaddleOCR
from PIL import Image

from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg
from app.pipeline import merge_neighbor_boxes, process_layout_alignment, create_docx_document

app = FastAPI(title="End-to-End Pipeline OCR API", version="3.0")

TEMP_DIR = "/tmp/ocr_pipeline"
os.makedirs(TEMP_DIR, exist_ok=True)

# --- KHỞI TẠO MODEL LÚC BẬT DỊCH VỤ ---
print(">>> [AI LOG] Khởi tạo mô hình định vị biên chữ (PaddleOCR Detector)...")
ocr_det = PaddleOCR(
    lang="vi", det=True, rec=False, show_log=False, use_gpu=False,
    det_db_thresh=0.25, det_db_box_thresh=0.55, det_db_unclip_ratio=1.4
)

print(">>> [AI LOG] Khởi tạo mô hình nhận dạng chữ quốc ngữ (VietOCR Predictor)...")
config = Cfg.load_config_from_name('vgg_transformer')
config['predictor']['beamsearch'] = False
config['device'] = 'cpu'
detector = Predictor(config)

def run_ocr_on_cv2_image(img):
    """ Quy trình xử lý nhận dạng chữ trên ảnh đơn lẻ """
    raw_result = ocr_det.ocr(img, cls=False)
    optimized_lines = merge_neighbor_boxes(raw_result)
    
    lines_output = []
    for line in optimized_lines:
        x_min, y_min = max(0, int(line["x_min"])), max(0, int(line["y_min"]))
        x_max, y_max = min(img.shape[1], int(line["x_max"])), min(img.shape[0], int(line["y_max"]))

        pad_y = 2
        crop_y_min = max(0, y_min - pad_y)
        crop_y_max = min(img.shape[0], y_max + pad_y)
        
        cropped_img = img[crop_y_min:crop_y_max, x_min:x_max]
        if cropped_img.size > 0:
            cropped_pil = Image.fromarray(cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB))
            text = detector.predict(cropped_pil).strip()
        else:
            text = ""

        lines_output.append({
            "text": text,
            "bbox": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}
        })
    return lines_output

@app.post("/api/v1/pipeline/ocr")
async def execute_full_pipeline(file: UploadFile = File(...)):
    print(">>> [API LOG] Endpoint nhận diện và tự động trả về file Word (.docx) hoàn chỉnh """)
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ['.pdf', '.jpg', '.jpeg', '.png']:
        raise HTTPException(status_code=400, detail="Hệ thống chỉ hỗ trợ xử lý file PDF hoặc Ảnh (JPG, PNG).")
        
    session_id = str(uuid.uuid4())
    upload_path = os.path.join(TEMP_DIR, f"{session_id}{ext}")
    output_docx_path = os.path.join(TEMP_DIR, f"{session_id}_final.docx")
    
    try:
        print(f">>> [API LOG] Nhận file từ Client: {filename} (Định dạng: {ext})")
        # 1. Ghi file tạm nhận được từ Client
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        pages_extracted_data = []

        print(f">>> [API LOG] Tiến hành xử lý OCR và dựng cấu trúc dữ liệu từ file {filename}...")
        # 2. Rẽ nhánh tiền xử lý dữ liệu dựa trên định dạng đầu vào
        if ext == '.pdf':
            doc = fitz.open(upload_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                img = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)
                
                raw_lines = run_ocr_on_cv2_image(img)
                structured_lines = process_layout_alignment(raw_lines, img.shape[1])
                pages_extracted_data.append({"lines": structured_lines, "width": img.shape[1]})
            doc.close()
        else:
            img = cv2.imread(upload_path)
            if img is None:
                raise HTTPException(status_code=400, detail="Không thể giải mã file ảnh.")
            raw_lines = run_ocr_on_cv2_image(img)
            structured_lines = process_layout_alignment(raw_lines, img.shape[1])
            pages_extracted_data.append({"lines": structured_lines, "width": img.shape[1]})

        # 3. Dựng cấu trúc và kết xuất file Word
        print(f">>> [API LOG] Tiến hành dựng cấu trúc và kết xuất file Word từ dữ liệu đã xử lý...")
        create_docx_document(pages_extracted_data, output_docx_path)
        
        # 4. Trả file Word về cho Client tải trực tiếp
        export_filename = f"OCR_{os.path.splitext(filename)[0]}.docx"
        print(f">>> [API LOG] Trả file Word về cho Client: {export_filename}")
        return FileResponse(
            path=output_docx_path, 
            filename=export_filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống trong quá trình OCR: {str(e)}")
        
    finally:
        # Giải phóng dung lượng ổ cứng - Xóa bỏ các tệp tin tạm sau khi xử lý xong
        if os.path.exists(upload_path):
            os.remove(upload_path)
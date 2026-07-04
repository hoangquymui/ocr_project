import os
import json
import cv2
import fitz
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image

# Vá lỗi Pillow 10+ cho VietOCR 0.3.11
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE_DIR, "sfile_12.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_scan_ocr")
DEBUG_CROP_DIR = os.path.join(OUTPUT_DIR, "debug_crops")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_CROP_DIR, exist_ok=True)

# 1. KHỞI TẠO PADDLEOCR VỚI BỘ THAM SỐ TINH CHỈNH BIÊN BOX CHUẨN XÁC
ocr_det = PaddleOCR(
    lang="vi",
    det=True,
    rec=False, 
    show_log=False,
    use_gpu=False,
    det_db_thresh=0.25,        # Nhận diện cả nét chữ mảnh/mờ
    det_db_box_thresh=0.55,    # Ngưỡng liên kết pixel tạo khối text
    det_db_unclip_ratio=1.4,   # Khống chế box ôm sát vừa vặn, chặn liếm chữ hàng xóm
)

# 2. KHỞI TẠO VIETOCR (Bản vgg_transformer ổn định)
config = Cfg.load_config_from_name('vgg_transformer')
config['predictor']['beamsearch'] = False
config['device'] = 'cpu' 
detector = Predictor(config)

def merge_neighbor_boxes(ocr_results, x_threshold=45, y_threshold=12):
    """
    Thuật toán hậu xử lý: Tự động gộp các box rời rạc nằm song song sát cạnh nhau
    trên cùng một hàng ngang thành một dòng duy nhất.
    """
    if not ocr_results or not ocr_results[0]:
        return []
        
    raw_lines = []
    for line in ocr_results[0]:
        poly = line[0]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        raw_lines.append({
            "x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys)
        })
        
    # Sắp xếp các box từ trên xuống dưới, từ trái sang phải để duyệt tuần tự
    raw_lines.sort(key=lambda l: (l["y_min"], l["x_min"]))
    
    merged_lines = []
    for line in raw_lines:
        if not merged_lines:
            merged_lines.append(line)
            continue
            
        prev = merged_lines[-1]
        
        # Kiểm tra điều kiện gộp:
        # 1. Hai box phải nằm suýt soát cùng độ cao trục Y (Trùng hàng ngang)
        is_same_row = abs(line["y_min"] - prev["y_min"]) < y_threshold or abs(line["y_max"] - prev["y_max"]) < y_threshold
        # 2. Khoảng cách lề phải của box trước và lề trái của box sau phải nhỏ hơn ngưỡng x_threshold
        is_close_x = (line["x_min"] - prev["x_max"]) < x_threshold
        
        # Không gộp nếu khoảng cách X âm quá lớn (trường hợp chia cột dọc rõ ràng)
        if is_same_row and is_close_x and (line["x_min"] >= prev["x_min"]):
            # Tiến hành hợp nhất biên tọa độ 2 box thành 1 box lớn dài hơn
            prev["x_max"] = max(prev["x_max"], line["x_max"])
            prev["y_min"] = min(prev["y_min"], line["y_min"])
            prev["y_max"] = max(prev["y_max"], line["y_max"])
        else:
            merged_lines.append(line)
            
    return merged_lines

doc = fitz.open(PDF_PATH)
print("Tổng số trang:", len(doc))

all_pages_data = []

for page_idx in range(len(doc)):
    page = doc[page_idx]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.h, pix.w, pix.n
    )

    if pix.n == 4:
        img = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
    else:
        img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

    image_path = os.path.join(OUTPUT_DIR, f"page_{page_idx + 1}.jpg")
    cv2.imwrite(image_path, img)

    # Chạy phát hiện box thô từ PaddleOCR
    raw_result = ocr_det.ocr(image_path, cls=False)

    print(f"\n--- Trang {page_idx + 1} ---")

    page_data = {
        "page": page_idx + 1,
        "width": img.shape[1],
        "height": img.shape[0],
        "lines": []
    }

    # Thực hiện thuật toán tự động gộp box thông minh
    optimized_lines = merge_neighbor_boxes(raw_result)

    if not optimized_lines:
        print("Không nhận diện được cấu trúc text")
        all_pages_data.append(page_data)
        continue

    img_canvas = img.copy()

    for i, line in enumerate(optimized_lines, start=1):
        x_min, y_min = max(0, int(line["x_min"])), max(0, int(line["y_min"]))
        x_max, y_max = min(img.shape[1], int(line["x_max"])), min(img.shape[0], int(line["y_max"]))

        # --- BƯỚC CẮT ẢNH AN TOÀN ---
        pad_y = 2
        pad_x = 0  # Tuyệt đối không nới lề X để triệt tiêu lỗi liếm chữ
        
        crop_y_min = max(0, y_min - pad_y)
        crop_y_max = min(img.shape[0], y_max + pad_y)
        crop_x_min = max(0, x_min - pad_x)
        crop_x_max = min(img.shape[1], x_max + pad_x)
        
        cropped_img = img[crop_y_min:crop_y_max, crop_x_min:crop_x_max]
        
        if cropped_img.size > 0:
            # Lưu ảnh để phục vụ việc debug lỗi
            crop_filename = f"page_{page_idx + 1}_line_{i}.jpg"
            cv2.imwrite(os.path.join(DEBUG_CROP_DIR, crop_filename), cropped_img)
            
            # Đưa vào nhận diện chữ tiếng Việt có dấu
            cropped_pil = Image.fromarray(cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB))
            text = detector.predict(cropped_pil)
            text = text.strip()
        else:
            text = ""

        score = 1.0

        # Lưu thông tin tọa độ hoàn chỉnh cho Step 2 sử dụng làm mốc phân tích layout
        line_data = {
            "line_id": i,
            "text": text,
            "score": score,
            "polygon": [
                [float(x_min), float(y_min)],
                [float(x_max), float(y_min)],
                [float(x_max), float(y_max)],
                [float(x_min), float(y_max)]
            ],
            "bbox": {
                "x_min": float(x_min),
                "y_min": float(y_min),
                "x_max": float(x_max),
                "y_max": float(y_max)
            }
        }

        page_data["lines"].append(line_data)
        print(f"Dòng {i}: {text}")

        # Vẽ hình chữ nhật bao quanh dòng chữ đã được tối ưu hóa
        cv2.rectangle(img_canvas, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        cv2.putText(
            img_canvas,
            str(i),
            (x_min, y_min - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

    all_pages_data.append(page_data)

    output_img = os.path.join(OUTPUT_DIR, f"page_{page_idx + 1}_boxed.jpg")
    cv2.imwrite(output_img, img_canvas)

json_path = os.path.join(OUTPUT_DIR, "ocr_result.json")

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "source_pdf": os.path.basename(PDF_PATH),
            "total_pages": len(doc),
            "pages": all_pages_data
        },
        f,
        ensure_ascii=False,
        indent=2
    )

doc.close()
print(f"\nXong Step 1: Đã tối ưu hóa và tự động gộp Box thành công!")
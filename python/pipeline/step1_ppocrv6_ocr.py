import os
import cv2
import fitz
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

from config import (
    INPUT_DIR,
    OUTPUT_DIR,
    PAGES_DIR,
    DEBUG_DIR,
    DOCUMENT_JSON,
    OCR_LANG,
    RENDER_ZOOM,
)

from utils import (
    ensure_dirs,
    find_first_pdf,
    polygon_to_bbox,
    save_json,
)

from document import create_document, add_page


def init_vietocr():
    config = Cfg.load_config_from_name("vgg_transformer")
    config["cnn"]["pretrained"] = False
    config["device"] = "cpu"
    config["predictor"]["beamsearch"] = False
    return Predictor(config)


def render_pdf_to_images(pdf_path):
    doc = fitz.open(pdf_path)
    rendered_pages = []

    print("Đang chuyển PDF thành ảnh...")

    for page_index in range(len(doc)):
        page_number = page_index + 1
        page = doc[page_index]

        pix = page.get_pixmap(
            matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM),
            alpha=False
        )

        img_data = np.frombuffer(
            pix.samples,
            dtype=np.uint8
        ).reshape(
            pix.h,
            pix.w,
            pix.n
        )

        img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

        page_img_path = os.path.join(
            PAGES_DIR,
            f"page_{page_number}.jpg"
        )

        cv2.imwrite(page_img_path, img)

        rendered_pages.append({
            "page": page_number,
            "image_path": page_img_path,
            "width": img.shape[1],
            "height": img.shape[0],
        })

        print(f"Đã tạo ảnh trang {page_number}: {page_img_path}")

    doc.close()
    return rendered_pages


def normalize_ocr_result(result):
    """
    PaddleOCR 3.x trả về OCRResult.
    Hàm này lấy bbox/polygon từ PaddleOCR.
    Text ban đầu có thể không dùng, vì sẽ được VietOCR nhận diện lại.
    """
    lines = []

    if not result:
        return lines

    res = result[0]

    if hasattr(res, "json"):
        if callable(res.json):
            res = res.json()
        else:
            res = res.json

    if isinstance(res, dict) and "res" in res:
        res = res["res"]

    if not isinstance(res, dict):
        print("Không đọc được OCR result type:", type(res))
        return lines

    texts = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])

    if "rec_polys" in res:
        polys = res["rec_polys"]
    elif "dt_polys" in res:
        polys = res["dt_polys"]
    else:
        polys = []

    for i, poly in enumerate(polys):
        paddle_text = texts[i] if i < len(texts) else ""
        score = float(scores[i]) if i < len(scores) else 0.0

        poly = [
            [float(point[0]), float(point[1])]
            for point in poly
        ]

        lines.append({
            "line_id": i + 1,
            "text": paddle_text,
            "paddle_text": paddle_text,
            "confidence": score,
            "recognizer": "paddleocr",
            "polygon": poly,
            "bbox": polygon_to_bbox(poly),
        })

    return lines


def crop_polygon_to_pil(image_bgr, polygon, padding=4):
    pts = np.array(polygon, dtype=np.float32)

    x_min = max(0, int(np.min(pts[:, 0])) - padding)
    y_min = max(0, int(np.min(pts[:, 1])) - padding)
    x_max = min(image_bgr.shape[1], int(np.max(pts[:, 0])) + padding)
    y_max = min(image_bgr.shape[0], int(np.max(pts[:, 1])) + padding)

    crop = image_bgr[y_min:y_max, x_min:x_max]

    if crop.size == 0:
        return None

    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(crop_rgb)


def recognize_lines_with_vietocr(vietocr, image_path, lines):
    image_bgr = cv2.imread(image_path)

    if image_bgr is None:
        print("Không đọc được ảnh:", image_path)
        return lines

    for line in lines:
        crop_img = crop_polygon_to_pil(
            image_bgr,
            line["polygon"],
            padding=6
        )

        if crop_img is None:
            continue

        try:
            viet_text = vietocr.predict(crop_img)

            line["text"] = viet_text
            line["vietocr_text"] = viet_text
            line["recognizer"] = "vietocr"

        except Exception as e:
            print(f"Lỗi VietOCR line {line['line_id']}:", e)
            line["vietocr_text"] = ""
            line["recognizer"] = "paddleocr_fallback"

    return lines


def draw_debug_boxes(image_path, lines, output_path):
    img = cv2.imread(image_path)

    if img is None:
        return

    for line in lines:
        poly = np.array(line["polygon"], dtype=np.int32)

        cv2.polylines(
            img,
            [poly],
            True,
            (0, 255, 0),
            2
        )

        x = int(line["bbox"]["x_min"])
        y = int(line["bbox"]["y_min"])

        label = str(line["line_id"])

        cv2.putText(
            img,
            label,
            (x, max(20, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

    cv2.imwrite(output_path, img)


def main():
    ensure_dirs(
        OUTPUT_DIR,
        PAGES_DIR,
        DEBUG_DIR
    )

    pdf_path = find_first_pdf(INPUT_DIR)

    print("PDF:", pdf_path)

    rendered_pages = render_pdf_to_images(pdf_path)

    print("Đang khởi tạo PaddleOCR để detect box...")
    paddle_ocr = PaddleOCR(
        lang=OCR_LANG,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True
    )

    print("Đang khởi tạo VietOCR để nhận diện tiếng Việt...")
    vietocr = init_vietocr()

    document = create_document(
        source_pdf=os.path.basename(pdf_path),
        total_pages=len(rendered_pages)
    )

    for page_info in rendered_pages:
        page_number = page_info["page"]
        image_path = page_info["image_path"]

        print(f"Đang detect box trang {page_number} bằng PaddleOCR...")

        result = paddle_ocr.predict(image_path)
        lines = normalize_ocr_result(result)

        print(f"Trang {page_number}: detect được {len(lines)} box")

        print(f"Đang nhận diện tiếng Việt trang {page_number} bằng VietOCR...")
        lines = recognize_lines_with_vietocr(
            vietocr=vietocr,
            image_path=image_path,
            lines=lines
        )

        debug_img_path = os.path.join(
            DEBUG_DIR,
            f"page_{page_number}_boxes.jpg"
        )

        draw_debug_boxes(
            image_path=image_path,
            lines=lines,
            output_path=debug_img_path
        )

        add_page(
            document=document,
            page_number=page_number,
            width=page_info["width"],
            height=page_info["height"],
            image_path=image_path,
            debug_image_path=debug_img_path,
            lines=lines
        )

        print(f"Trang {page_number}: lưu {len(lines)} dòng")

    save_json(DOCUMENT_JSON, document)

    print("Saved:", DOCUMENT_JSON)


if __name__ == "__main__":
    main()
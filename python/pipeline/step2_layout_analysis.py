import os
import cv2
import numpy as np

from config import IMAGES_DIR, DEBUG_DIR
from document import load_document, save_document
from utils import ensure_dirs


DEFAULT_FONT = "Times New Roman"


def upper_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def detect_alignment(line, page_width):
    bbox = line["bbox"]
    center_x = page_width / 2
    line_center_x = (bbox["x_min"] + bbox["x_max"]) / 2
    line_width = bbox["width"]

    if abs(line_center_x - center_x) < page_width * 0.06 and line_width < page_width * 0.75:
        return "CENTER"

    if bbox["x_min"] > center_x * 1.1 and line_width < page_width * 0.45:
        return "RIGHT"

    return "LEFT"


def classify_text_box(line, page_width, page_height):
    text = line.get("text", "").strip()
    bbox = line["bbox"]

    if not text:
        return "empty"

    y_min = bbox["y_min"]
    center_x = (bbox["x_min"] + bbox["x_max"]) / 2
    page_center_x = page_width / 2
    word_count = len(text.split())
    ratio = upper_ratio(text)

    if text.isdigit() and word_count == 1 and y_min > page_height * 0.85:
        return "page_number"

    is_centered = abs(center_x - page_center_x) < page_width * 0.13
    is_short = word_count <= 18
    mostly_upper = ratio > 0.55

    if is_centered and is_short and mostly_upper:
        return "title"

    prefix = text[:14]

    if any(ch.isdigit() for ch in prefix) and "." in prefix and word_count <= 25:
        # Tránh đánh nhầm danh sách sinh viên thành heading ở trang bìa
        if page_height and y_min > page_height * 0.55 and page_height * 0.55 < y_min < page_height * 0.85:
            return "text_box"
        return "heading"

    if text.startswith(("-", "•", "*", "+")):
        return "list_item"

    if ":" in text and word_count <= 10:
        return "field"

    digit_count = sum(1 for c in text if c.isdigit())
    if digit_count >= 2 and word_count <= 8:
        return "table_cell_candidate"

    return "text_box"


def compute_page_style(page):
    # Hiện tại dùng size ổn định theo trang, tránh mỗi bbox một cỡ chữ.
    # Sau này có thể nâng cấp bằng median height theo vùng nội dung.
    return {
        "font_family": DEFAULT_FONT,
        "body_font_size": 11,
        "title_font_size": 14,
        "heading_font_size": 12,
        "small_font_size": 9,
    }


def apply_style_to_line(line, page_style):
    layout_type = line.get("layout_type", "text_box")
    text = line.get("text", "")

    if layout_type == "title":
        font_size = page_style["title_font_size"]
    elif layout_type == "heading":
        font_size = page_style["heading_font_size"]
    elif layout_type in ["header", "footer", "page_number"]:
        font_size = page_style["small_font_size"]
    else:
        font_size = page_style["body_font_size"]

    bold = layout_type in ["title", "heading"] or (
        upper_ratio(text) > 0.6 and len(text.split()) <= 18
    )

    # Field như GVHD, Lớp không nên auto bold/to quá
    if layout_type == "field":
        bold = False
        font_size = page_style["body_font_size"]

    line["style"] = {
        "font_family": page_style["font_family"],
        "font_size": font_size,
        "bold": bold,
        "italic": False,
        "underline": False,
        "color": "000000",
    }

    return line


def remove_text_regions(binary, page, padding=10):
    for line in page.get("lines", []):
        bbox = line["bbox"]

        x1 = max(0, int(bbox["x_min"]) - padding)
        y1 = max(0, int(bbox["y_min"]) - padding)
        x2 = min(binary.shape[1], int(bbox["x_max"]) + padding)
        y2 = min(binary.shape[0], int(bbox["y_max"]) + padding)

        cv2.rectangle(binary, (x1, y1), (x2, y2), 0, -1)

    return binary


def remove_border_regions(binary, page):
    h, w = binary.shape[:2]

    # Xóa viền ngoài trang để không bị detect nhầm là ảnh/logo.
    margin_x = int(w * 0.08)
    margin_y = int(h * 0.05)

    cv2.rectangle(binary, (0, 0), (w, margin_y), 0, -1)
    cv2.rectangle(binary, (0, h - margin_y), (w, h), 0, -1)
    cv2.rectangle(binary, (0, 0), (margin_x, h), 0, -1)
    cv2.rectangle(binary, (w - margin_x, 0), (w, h), 0, -1)

    return binary


def remove_table_lines(binary):
    """ Loại bỏ toàn bộ kẻ bảng ngang và kẻ bảng dọc """
    # Tìm các đường kẻ ngang dài (> 40px)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    lines_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)

    # Tìm các đường kẻ dọc dài (> 40px)
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    lines_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

    # Xóa toàn bộ đường kẻ ngang & dọc khỏi ảnh nhị phân
    table_lines = cv2.add(lines_h, lines_v)
    binary = cv2.subtract(binary, table_lines)
    return binary


def detect_image_regions(page):
    ensure_dirs(IMAGES_DIR)

    image_path = page["image_path"]
    img = cv2.imread(image_path)

    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Lấy vùng không trắng
    _, binary = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)

    binary = remove_text_regions(binary, page, padding=12)
    binary = remove_border_regions(binary, page)
    binary = remove_table_lines(binary)

    # Gom các nét đen của logo/hình thực sự thành vùng lớn
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    images = []
    lines_in_page = page.get("lines", [])

    for idx, cnt in enumerate(contours, start=1):
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        # Loại bỏ các vết nhiễu hoặc đường viền mỏng nhỏ
        if area < 8000:
            continue

        if w < 70 or h < 70:
            continue

        # Loại bỏ mảnh đường kẻ ngang/dọc sót lại (Aspect Ratio quá lệch)
        aspect_ratio = w / float(h)
        if aspect_ratio > 4.5 or aspect_ratio < 0.22:
            continue

        # Loại bỏ các vùng nằm sát viền hoặc chiếm hầu hết chiều rộng trang
        if w > page["width"] * 0.7 or h > page["height"] * 0.6:
            continue

        # Lọc bỏ các vùng chứa nhiều hơn 1 dòng văn bản (bảng chứa chữ)
        overlapping_text_lines = 0
        for l in lines_in_page:
            lb = l["bbox"]
            # Kiểm tra xem dòng chữ có nằm trong bounding box này không
            if not (lb["x_max"] < x or lb["x_min"] > x + w or lb["y_max"] < y or lb["y_min"] > y + h):
                overlapping_text_lines += 1

        if overlapping_text_lines >= 2:
            continue

        pad = 8
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img.shape[1], x + w + pad)
        y2 = min(img.shape[0], y + h + pad)

        crop = img[y1:y2, x1:x2]

        # Kiểm tra độ lệch chuẩn màu sắc (Ảnh/Logo thật có màu sắc đa dạng)
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        std_dev = np.std(crop_gray)
        if std_dev < 18:  # Nếu vùng bị phẳng màu (khung ô trắng), bỏ qua
            continue

        crop_path = os.path.join(
            IMAGES_DIR,
            f"page_{page['page']}_image_{len(images) + 1}.png"
        )

        cv2.imwrite(crop_path, crop)

        images.append({
            "image_id": len(images) + 1,
            "type": "logo_or_image",
            "path": crop_path,
            "bbox": {
                "x_min": float(x1),
                "y_min": float(y1),
                "x_max": float(x2),
                "y_max": float(y2),
                "width": float(x2 - x1),
                "height": float(y2 - y1),
            }
        })

    return images


def draw_layout_debug(page):
    image_path = page["image_path"]
    img = cv2.imread(image_path)

    if img is None:
        return

    # Text boxes xanh
    for line in page.get("lines", []):
        bbox = line["bbox"]
        x1 = int(bbox["x_min"])
        y1 = int(bbox["y_min"])
        x2 = int(bbox["x_max"])
        y2 = int(bbox["y_max"])

        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.putText(
            img,
            str(line.get("line_id", "")),
            (x1, max(20, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2
        )

    # Logo/image boxes xanh dương
    for image in page.get("images", []):
        bbox = image["bbox"]
        x1 = int(bbox["x_min"])
        y1 = int(bbox["y_min"])
        x2 = int(bbox["x_max"])
        y2 = int(bbox["y_max"])

        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 3)

        cv2.putText(
            img,
            f"IMG{image['image_id']}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2
        )

    debug_path = os.path.join(
        DEBUG_DIR,
        f"page_{page['page']}_layout.jpg"
    )

    cv2.imwrite(debug_path, img)
    page["layout_debug_image_path"] = debug_path


def analyze_page(page):
    page_width = page["width"]
    page_height = page["height"]

    lines = sorted(
        page.get("lines", []),
        key=lambda line: (
            line["bbox"]["y_min"],
            line["bbox"]["x_min"]
        )
    )

    analyzed_lines = []

    for idx, line in enumerate(lines, start=1):
        line["line_id"] = idx
        line["order"] = idx
        line["layout_type"] = classify_text_box(line, page_width, page_height)
        line["alignment"] = detect_alignment(line, page_width)
        analyzed_lines.append(line)

    page["page_style"] = compute_page_style(page)

    final_lines = []
    for line in analyzed_lines:
        final_lines.append(apply_style_to_line(line, page["page_style"]))

    page["lines"] = final_lines
    page["images"] = detect_image_regions(page)

    page["blocks"] = []

    for idx, line in enumerate(final_lines, start=1):
        page["blocks"].append({
            "block_id": idx,
            "type": line["layout_type"],
            "order": line["order"],
            "alignment": line["alignment"],
            "text": line.get("text", ""),
            "bbox": line["bbox"],
            "style": line["style"],
            "lines": [line],
        })

    for image in page["images"]:
        page["blocks"].append({
            "block_id": len(page["blocks"]) + 1,
            "type": image["type"],
            "order": len(page["blocks"]) + 1,
            "bbox": image["bbox"],
            "image_path": image["path"],
            "lines": [],
        })

    draw_layout_debug(page)

    return page


def main():
    ensure_dirs(IMAGES_DIR, DEBUG_DIR)

    document = load_document()

    for page in document["pages"]:
        analyze_page(page)

        print(
            f"Trang {page['page']}: "
            f"{len(page.get('lines', []))} text boxes | "
            f"{len(page.get('images', []))} images/logos"
        )

    save_document(document)
    print("Updated document.json with Layout + Style + Image Analysis")


if __name__ == "__main__":
    main()
import os
import cv2
import numpy as np

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


def compute_page_style(page_data):
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


def remove_text_regions(binary, lines, padding=8):
    for line in lines:
        bbox = line["bbox"]
        x1 = max(0, int(bbox["x_min"]) - padding)
        y1 = max(0, int(bbox["y_min"]) - padding)
        x2 = min(binary.shape[1], int(bbox["x_max"]) + padding)
        y2 = min(binary.shape[0], int(bbox["y_max"]) + padding)
        cv2.rectangle(binary, (x1, y1), (x2, y2), 0, -1)
    return binary


def remove_table_lines(binary):
    """ Loại bỏ đường kẻ ngang & dọc của bảng biểu """
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    lines_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    lines_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

    table_lines = cv2.add(lines_h, lines_v)
    return cv2.subtract(binary, table_lines)


def detect_image_regions(img_bgr, page_w, page_h, lines, temp_dir="/tmp/ocr_pipeline"):
    """ Tách trích xuất Logo và Hình ảnh đồ họa chuẩn xác """
    os.makedirs(temp_dir, exist_ok=True)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)

    binary = remove_text_regions(binary, lines, padding=8)
    binary = remove_table_lines(binary)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 12))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    images = []

    for idx, cnt in enumerate(contours, start=1):
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        if area < 2000 or w < 40 or h < 40:
            continue

        aspect_ratio = w / float(h)
        if aspect_ratio > 6.0 or aspect_ratio < 0.15:
            continue

        if w > page_w * 0.85 or h > page_h * 0.75:
            continue

        overlapping_text_lines = 0
        for l in lines:
            lb = l["bbox"]
            if not (lb["x_max"] < x or lb["x_min"] > x + w or lb["y_max"] < y or lb["y_min"] > y + h):
                overlapping_text_lines += 1

        if overlapping_text_lines >= 3:
            continue

        pad = 6
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_bgr.shape[1], x + w + pad)
        y2 = min(img_bgr.shape[0], y + h + pad)

        crop = img_bgr[y1:y2, x1:x2]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if np.std(crop_gray) < 8:
            continue

        img_filename = f"crop_img_{idx}_{x1}_{y1}.png"
        img_save_path = os.path.join(temp_dir, img_filename)
        cv2.imwrite(img_save_path, crop)

        images.append({
            "image_id": len(images) + 1,
            "type": "logo_or_image",
            "image_path": img_save_path,
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


def detect_table_and_cover_regions(img_bgr, page_w, page_h):
    """ Tách biệt Khung Bìa Trang (Cover Frame) và Bảng Biểu (Tables) """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    lines_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    lines_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)

    table_grid = cv2.add(lines_h, lines_v)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    table_mask = cv2.morphologyEx(table_grid, cv2.MORPH_CLOSE, kernel_close, iterations=2)

    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables = []
    cover_frames = []

    for idx, cnt in enumerate(contours, start=1):
        x, y, w, h = cv2.boundingRect(cnt)
        if w > page_w * 0.75 and h > page_h * 0.75:
            cover_frames.append({
                "frame_id": len(cover_frames) + 1,
                "type": "cover_frame",
                "bbox": {"x_min": float(x), "y_min": float(y), "x_max": float(x + w), "y_max": float(y + h)}
            })
        elif w >= 160 and h >= 60:
            tables.append({
                "table_id": len(tables) + 1,
                "type": "table_region",
                "bbox": {"x_min": float(x), "y_min": float(y), "x_max": float(x + w), "y_max": float(y + h)}
            })

    return tables, cover_frames


def run_step2_layout_page(page_data, image_bgr):
    """ Bước 2: Phân tích bố cục, căn lề, kiểu chữ, trích xuất ảnh, bảng biểu & khung bìa """
    page_w = page_data["width"]
    page_h = page_data["height"]
    lines = page_data.get("lines", [])

    lines_sorted = sorted(lines, key=lambda l: (l["bbox"]["y_min"], l["bbox"]["x_min"]))

    analyzed_lines = []
    for idx, line in enumerate(lines_sorted, start=1):
        line["line_id"] = idx
        line["order"] = idx
        line["layout_type"] = classify_text_box(line, page_w, page_h)
        line["alignment"] = detect_alignment(line, page_w)
        analyzed_lines.append(line)

    page_style = compute_page_style(page_data)
    final_lines = [apply_style_to_line(l, page_style) for l in analyzed_lines]

    page_data["page_style"] = page_style
    page_data["lines"] = final_lines
    page_data["images"] = detect_image_regions(image_bgr, page_w, page_h, final_lines)
    
    tables, cover_frames = detect_table_and_cover_regions(image_bgr, page_w, page_h)
    page_data["tables"] = tables
    page_data["cover_frames"] = cover_frames
    return page_data

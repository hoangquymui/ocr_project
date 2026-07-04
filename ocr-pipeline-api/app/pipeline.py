import os
import cv2
import fitz
import numpy as np
from PIL import Image
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Vá lỗi Pillow 10+ cho VietOCR 0.3.11
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

def merge_neighbor_boxes(ocr_results, x_threshold=45, y_threshold=12):
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
        
    raw_lines.sort(key=lambda l: (l["y_min"], l["x_min"]))
    
    merged_lines = []
    for line in raw_lines:
        if not merged_lines:
            merged_lines.append(line)
            continue
            
        prev = merged_lines[-1]
        is_same_row = abs(line["y_min"] - prev["y_min"]) < y_threshold or abs(line["y_max"] - prev["y_max"]) < y_threshold
        is_close_x = (line["x_min"] - prev["x_max"]) < x_threshold
        
        if is_same_row and is_close_x and (line["x_min"] >= prev["x_min"]):
            prev["x_max"] = max(prev["x_max"], line["x_max"])
            prev["y_min"] = min(prev["y_min"], line["y_min"])
            prev["y_max"] = max(prev["y_max"], line["y_max"])
        else:
            merged_lines.append(line)
            
    return merged_lines

def process_layout_alignment(lines, width):
    if not lines:
        return []
    
    CENTER_X = width / 2
    lines.sort(key=lambda l: l["bbox"]["y_min"])
    
    final_ordered_lines = []
    current_row = []
    
    # Gom cụm hàng ngang (Row Clustering)
    for line in lines:
        if not current_row:
            current_row.append(line)
        else:
            prev_line = current_row[-1]
            avg_height = ((prev_line["bbox"]["y_max"] - prev_line["bbox"]["y_min"]) + 
                          (line["bbox"]["y_max"] - line["bbox"]["y_min"])) / 2
            y_distance = abs(line["bbox"]["y_min"] - prev_line["bbox"]["y_min"])
            
            if y_distance < (avg_height * 0.4):
                current_row.append(line)
            else:
                if len(current_row) > 1:
                    current_row.sort(key=lambda l: l["bbox"]["x_min"])
                final_ordered_lines.extend(current_row)
                current_row = [line]
                
    if current_row:
        if len(current_row) > 1:
            current_row.sort(key=lambda l: l["bbox"]["x_min"])
        final_ordered_lines.extend(current_row)

    # Phân loại căn lề động (Dynamic Alignment)
    processed_lines = []
    for idx, line in enumerate(final_ordered_lines, start=1):
        bbox = line["bbox"]
        line_width = bbox["x_max"] - bbox["x_min"]
        line_center_x = (bbox["x_min"] + bbox["x_max"]) / 2
        
        alignment = "LEFT"
        if abs(line_center_x - CENTER_X) < (width * 0.06) and line_width < (width * 0.7):
            alignment = "CENTER"
        elif bbox["x_min"] > (CENTER_X * 1.1) and line_width < (width * 0.45):
            alignment = "RIGHT"
            
        line["alignment"] = alignment
        processed_lines.append(line)
        
    return processed_lines

def group_lines_into_paragraphs(lines):
    paragraphs = []
    current_para = []

    for line in lines:
        if line["alignment"] in ["CENTER", "RIGHT"]:
            if current_para:
                paragraphs.append({"alignment": "LEFT", "text": " ".join(current_para)})
                current_para = []
            paragraphs.append({"alignment": line["alignment"], "text": line["text"]})
        else:
            current_para.append(line["text"])

    if current_para:
        paragraphs.append({"alignment": "LEFT", "text": " ".join(current_para)})

    return paragraphs

def create_docx_document(pages_data, output_path):
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(13)

    for idx, page in enumerate(pages_data):
        paragraphs_data = group_lines_into_paragraphs(page["lines"])
        
        for p_data in paragraphs_data:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.3
            
            if p_data["alignment"] == "CENTER":
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif p_data["alignment"] == "RIGHT":
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
            run = p.add_run(p_data["text"])
            if p_data["alignment"] == "CENTER" and p_data["text"].isupper():
                run.bold = True

        if idx < len(pages_data) - 1:
            doc.add_page_break()

    doc.save(output_path)
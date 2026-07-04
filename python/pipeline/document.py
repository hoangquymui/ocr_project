from config import DOCUMENT_JSON
from utils import load_json, save_json


def create_document(source_pdf, total_pages):
    return {
        "source_pdf": source_pdf,
        "total_pages": total_pages,
        "pages": []
    }


def load_document():
    return load_json(DOCUMENT_JSON)


def save_document(document):
    save_json(DOCUMENT_JSON, document)


def add_page(
    document,
    page_number,
    width,
    height,
    image_path,
    debug_image_path,
    lines
):
    document["pages"].append({
        "page": page_number,
        "width": width,
        "height": height,
        "image_path": image_path,
        "debug_image_path": debug_image_path,
        "lines": lines,
        "blocks": []
    })
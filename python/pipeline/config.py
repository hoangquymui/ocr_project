import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_DIR = os.path.join(ROOT_DIR, "input")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

PAGES_DIR = os.path.join(OUTPUT_DIR, "pages")
DEBUG_DIR = os.path.join(OUTPUT_DIR, "debug")
DOCX_DIR = os.path.join(OUTPUT_DIR, "docx")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

DOCUMENT_JSON = os.path.join(OUTPUT_DIR, "document.json")
OUTPUT_DOCX = os.path.join(DOCX_DIR, "output.docx")

OCR_LANG = "vi"
RENDER_ZOOM = 2
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODELS_DIR = os.path.join(ROOT_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_PT_PATH = os.path.join(MODELS_DIR, "vietocr_vgg_cnn.pt")
OCR_LANG = "vi"
RENDER_ZOOM = 2

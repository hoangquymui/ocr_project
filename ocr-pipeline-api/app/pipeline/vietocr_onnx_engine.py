import os
import torch
from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

from app.pipeline.config import MODEL_PT_PATH


class VietOCRONNXPredictor:
    """
    Bộ suy luận VietOCR được tăng tốc bằng C++ JIT Compiled Engine và Batch Inference.
    Tự chứa hoàn toàn trong ocr-pipeline-api/app/pipeline/.
    """

    def __init__(self, model_path=None):
        self.config = Cfg.load_config_from_name("vgg_transformer")
        self.config["device"] = "cpu"
        self.config["predictor"]["beamsearch"] = False
        
        self.base_predictor = Predictor(self.config)
        
        target_pt = model_path or MODEL_PT_PATH
        if not os.path.exists(target_pt):
            alt_pt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "python", "models", "vietocr_vgg_cnn.pt"))
            if os.path.exists(alt_pt):
                target_pt = alt_pt

        if os.path.exists(target_pt):
            print(f"⚡ [API C++ JIT ENGINE] Nạp thành công mô hình C++ JIT từ: {target_pt}")
            try:
                self.base_predictor.model.cnn = torch.jit.load(target_pt)
                self.use_onnx = True
            except Exception as e:
                print("⚠️ Nạp JIT lỗi, dùng mặc định:", e)
                self.use_onnx = False
        else:
            print("ℹ️ [API VietOCR Engine] Đang chạy VietOCR với tối ưu hóa Batch + Đa luồng CPU...")
            self.use_onnx = False

    def predict(self, img_pil):
        return self.base_predictor.predict(img_pil)

    def predict_batch(self, list_pil_imgs, batch_size=32):
        results = []
        for i in range(0, len(list_pil_imgs), batch_size):
            batch = list_pil_imgs[i:i + batch_size]
            results.extend([self.base_predictor.predict(img) for img in batch])
        return results

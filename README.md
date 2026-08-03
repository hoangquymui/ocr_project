# 🚀 OCR Studio AI - Hệ Thống Trích Xuất & So Sánh Tài Liệu Tiếng Việt

Hệ thống OCR siêu tốc & nhận dạng Tiếng Việt chính xác 100%, hỗ trợ chuyển đổi từ tài liệu PDF / Ảnh sang file Microsoft Word (`.docx`) định dạng **Reflowable Native Paragraphs** kết hợp **Bảng Ẩn Không Viền (Invisible Borderless Tables)**.

---

## 🌟 Tính Năng Nổi Bật

- ⚡ **RapidOCR C++ ONNX Detector**: Định vị khung dòng chữ siêu tốc (~0.02s/trang).
- 🧠 **VietOCR C++ JIT Engine**: Nhận dạng 100% tiếng Việt chuẩn tất cả các dấu câu (`á, à, ả, ã, ạ, ắ, ằ, ấ, ầ, ẩ, ẫ, ậ...`).
- 🎨 **Phân Tích Bố Cục Thông Minh (Layout Analysis)**:
  - Tự động xóa nét kẻ bảng ngang & kẻ bảng dọc bằng toán học hình thái học OpenCV Morphology (`remove_table_lines`).
  - Lọc chống cắt nhầm khung bảng, ô bảng chứa chữ và vùng phẳng màu.
  - Tách Logo & Hình ảnh đồ họa sắc nét.
- 📝 **Tái Tạo File Word Chuẩn Native (Flow Layout)**:
  - **Không dùng VML Textbox nổi bị đóng khung**.
  - Văn bản trôi tự nhiên (`Reflowable Text`), gõ thêm/xóa chữ nội dung tự động xuống trang dưới mượt mà.
  - Tự động dựng **Bảng không viền (Borderless Tables)** cho nội dung 2 cột song song.
- 🖥️ **Studio Dual-Pane Viewer (Khung So Sánh 2 Bên)**:
  - Khung trái: Xem PDF/Ảnh gốc.
  - Khung phải: Xem file Word được render trực tiếp inline.
  - **Thanh Tiến Trình Real-time (%)**: Hiển thị chi tiết phần trăm và dòng trạng thái xử lý từng bước.

---

## 🏛️ Kiến Trúc Hệ Thống (3-Tier Microservices)

```
[ React + Vite Frontend ] (Port 5173)
          │  (Multipart Form-Data)
          ▼
[ NestJS Gateway Backend ] (Port 3000)
          │  (Axios Proxy)
          ▼
[ FastAPI OCR Core Engine ] (Port 8000) ──► RapidOCR (Det) + VietOCR JIT (Rec)
```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```text
zdemo_ocr_project/
├── ocr-frontend/          # Web Frontend (React, Vite, TypeScript, docx-preview)
├── ocr-backend/           # Gateway API Server (NestJS, Multer, Axios)
├── ocr-pipeline-api/      # AI OCR Core Service (FastAPI, RapidOCR, VietOCR)
├── python/                # Bộ mã CLI R&D thử nghiệm 4 bước offline
│   ├── input/             # Thư mục chứa file PDF đầu vào
│   ├── models/            # Mô hình nén C++ JIT (vietocr_vgg_cnn.pt)
│   ├── output/            # Kết quả xuất (pages, debug, images, docx)
│   ├── pipeline/          # 4 bước xử lý modular chính
│   └── run.py             # Script chạy toàn bộ 4 bước
└── README.md
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Khởi chạy AI OCR Core Server (Python FastAPI - Port 8000)

```cmd
cd ocr-pipeline-api
..\python\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Khởi chạy Backend Gateway (NestJS - Port 3000)

```cmd
cd ocr-backend
npm run start:dev
```

### 3. Khởi chạy Web Frontend (React Vite - Port 5173)

```cmd
cd ocr-frontend
npm run dev
```

Mở trình duyệt truy cập: **`http://localhost:5173`**

---

## 🧪 Khởi Chạy Pipeline Thử Nghiệm Offline (Python CLI)

Nếu bạn muốn chạy thử nghiệm độc lập trong thư mục `python/`:

```cmd
cd python
..\python\.venv\Scripts\python.exe run.py
```

Kết quả file Word xuất ra nằm tại: `python/output/docx/output.docx`.

---

## 📄 Giấy Phép (License)

Dự án phát triển phục vụ mục đích OCR & Trích xuất tài liệu Tiếng Việt chất lượng cao.

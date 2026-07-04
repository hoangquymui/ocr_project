FROM python:3.11-slim

# 1. Cài đặt các gói hệ thống bắt buộc cho g++ compiler, OpenMP và nhân OpenCV (libGL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# 2. Khởi tạo Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 3. Cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Tạo sẵn thư mục lưu cache model AI
RUN mkdir -p /root/.paddleocr /root/.vietocr

# 5. Sao chép mã nguồn vào container
COPY ./app /workspace/app

EXPOSE 8000

# 6. Khởi chạy bằng python trong môi trường ảo
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
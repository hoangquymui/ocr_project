import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "output_scan_ocr", "ocr_result.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "output_scan_ocr", "layout_processed_result.json")

def process_layout_page_generic(page_data):
    width = page_data["width"]
    height = page_data["height"]
    lines = page_data["lines"]
    
    if not lines:
        return page_data

    CENTER_X = width / 2
    
    # --- BƯỚC 1: SẮP XẾP THÔ THEO TRỤC Y (TỪ TRÊN XUỐNG DƯỚI) ---
    lines.sort(key=lambda l: l["bbox"]["y_min"])
    
    final_ordered_lines = []
    current_row = []
    
    # --- BƯỚC 2: THUẬT TOÁN GOM CỤM DÒNG NGANG (ROW CLUSTERING) ---
    # Mục đích: Phát hiện các dòng nằm song song nhau (chia cột/bảng/header)
    for line in lines:
        if not current_row:
            current_row.append(line)
        else:
            # Tính toán độ giao thoa (overlap) hoặc khoảng cách Y giữa dòng hiện tại và dòng trước đó
            prev_line = current_row[-1]
            prev_y_min = prev_line["bbox"]["y_min"]
            prev_y_max = prev_line["bbox"]["y_max"]
            curr_y_min = line["bbox"]["y_min"]
            curr_y_max = line["bbox"]["y_max"]
            
            # Tính chiều cao trung bình của dòng để làm ngưỡng (threshold) động
            avg_height = ((prev_y_max - prev_y_min) + (curr_y_max - curr_y_min)) / 2
            y_distance = abs(curr_y_min - prev_y_min)
            
            # Nếu 2 dòng nằm gần như song song trên một trục ngang (lệch nhau không quá 40% chiều cao dòng)
            if y_distance < (avg_height * 0.4):
                current_row.append(line)
            else:
                # Trước khi đóng hàng cũ, sắp xếp các phần tử trong hàng từ TRÁI SANG PHẢI
                if len(current_row) > 1:
                    current_row.sort(key=lambda l: l["bbox"]["x_min"])
                
                final_ordered_lines.extend(current_row)
                # Khởi tạo hàng ngang mới
                current_row = [line]
                
    # Đóng hàng cuối cùng nếu còn sót
    if current_row:
        if len(current_row) > 1:
            current_row.sort(key=lambda l: l["bbox"]["x_min"])
        final_ordered_lines.extend(current_row)

    # --- BƯỚC 3: PHÂN LOẠI CĂN LỀ ĐỘNG (DYNAMIC ALIGNMENT DETECTION) ---
    processed_lines = []
    for idx, line in enumerate(final_ordered_lines, start=1):
        bbox = line["bbox"]
        line_width = bbox["x_max"] - bbox["x_min"]
        line_center_x = (bbox["x_min"] + bbox["x_max"]) / 2
        
        # Thiết lập mặc định là căn lề trái (LEFT) cho văn bản thông thường
        alignment = "LEFT"
        
        # 3.1 Nhận diện căn giữa (CENTER): 
        # Nếu tâm dòng trùng với tâm trang (sai số 6% chiều rộng) và dòng không chiếm quá 70% bề ngang trang
        if abs(line_center_x - CENTER_X) < (width * 0.06) and line_width < (width * 0.7):
            alignment = "CENTER"
            
        # 3.2 Nhận diện căn phải (RIGHT):
        # Nếu dòng nằm hẳn về bên phải và có độ dài ngắn (Thường là ngày tháng, địa danh, hoặc tên người ký)
        elif bbox["x_min"] > (CENTER_X * 1.1) and line_width < (width * 0.45):
            alignment = "RIGHT"
            
        # Cập nhật thông tin cấu trúc mới vào dictionary
        line["new_sequence_id"] = idx
        line["alignment"] = alignment
        processed_lines.append(line)
        
    page_data["lines"] = processed_lines
    return page_data

def main():
    if not os.path.exists(INPUT_JSON):
        print(f"LỖI: Không tìm thấy file {INPUT_JSON}.")
        print("Vui lòng chạy file 'step1_paddleocr_pdf.py' trước để trích xuất dữ liệu thô!")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Bắt đầu phân tích layout linh hoạt cho: {data['source_pdf']}")
    
    processed_pages = []
    for page_data in data["pages"]:
        print(f"-> Đang cấu trúc lại Trang {page_data['page']}...")
        new_page_data = process_layout_page_generic(page_data)
        processed_pages.append(new_page_data)
        
    data["pages"] = processed_pages
    
    # Ghi đè hoặc lưu ra file mới tùy bạn, ở đây lưu ra file riêng biệt để dễ đối chiếu
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("\n--- HOÀN THÀNH STEP 2 ---")
    print(f"Kết quả phân tích bố cục đa năng đã được lưu tại:\n{OUTPUT_JSON}")

if __name__ == "__main__":
    main()
def run_step3_reading_order_page(page_data):
    """
    Bước 3: Sắp xếp thứ tự đọc văn bản (Reading Order Sorting)
    """
    lines = page_data.get("lines", [])
    if not lines:
        return page_data

    grouped_rows = []
    current_row = []

    lines_sorted = sorted(lines, key=lambda l: l["bbox"]["y_min"])

    for line in lines_sorted:
        if not current_row:
            current_row.append(line)
        else:
            last_y = current_row[-1]["bbox"]["y_min"]
            curr_y = line["bbox"]["y_min"]
            if abs(curr_y - last_y) < 18:
                current_row.append(line)
            else:
                grouped_rows.append(current_row)
                current_row = [line]

    if current_row:
        grouped_rows.append(current_row)

    ordered_lines = []
    order_counter = 1

    for row in grouped_rows:
        row_sorted = sorted(row, key=lambda l: l["bbox"]["x_min"])
        for line in row_sorted:
            line["order"] = order_counter
            order_counter += 1
            ordered_lines.append(line)

    page_data["lines"] = ordered_lines
    return page_data

def create_document(source_name, total_pages):
    return {
        "source_pdf": source_name,
        "total_pages": total_pages,
        "pages": []
    }


def add_page(document, page_number, width, height, image_path, lines):
    page_data = {
        "page": page_number,
        "width": width,
        "height": height,
        "image_path": image_path,
        "lines": lines,
        "blocks": [],
        "images": [],
        "tables": [],
        "cover_frames": []
    }
    document["pages"].append(page_data)
    return page_data

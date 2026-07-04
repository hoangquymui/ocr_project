from document import load_document, save_document


def is_full_width(block, page_width):
    return block["bbox"]["width"] > page_width * 0.65


def split_columns(blocks, page_width):
    left = []
    right = []
    full = []

    for block in blocks:
        bbox = block["bbox"]
        center_x = (bbox["x_min"] + bbox["x_max"]) / 2

        if is_full_width(block, page_width):
            full.append(block)
        elif center_x < page_width / 2:
            left.append(block)
        else:
            right.append(block)

    if len(left) >= 2 and len(right) >= 2:
        return full, left, right

    return blocks, [], []


def sort_top_to_bottom(blocks):
    return sorted(
        blocks,
        key=lambda block: (
            block["bbox"]["y_min"],
            block["bbox"]["x_min"]
        )
    )


def assign_order(blocks):
    for i, block in enumerate(blocks, start=1):
        block["order"] = i

    return blocks


def main():
    document = load_document()

    for page in document["pages"]:
        blocks = page.get("blocks", [])

        if not blocks:
            continue

        full, left, right = split_columns(
            blocks,
            page["width"]
        )

        if left and right:
            ordered = (
                sort_top_to_bottom(full)
                + sort_top_to_bottom(left)
                + sort_top_to_bottom(right)
            )
        else:
            ordered = sort_top_to_bottom(full)

        page["blocks"] = assign_order(ordered)

        print(
            f"Trang {page['page']}: "
            f"{len(page['blocks'])} blocks ordered"
        )

    save_document(document)

    print("Updated document.json")


if __name__ == "__main__":
    main()
import html
import os
from docx import Document
from docx.shared import Inches
from docx.oxml import parse_xml

from config import DOCX_DIR, OUTPUT_DOCX
from utils import ensure_dirs
from document import load_document


BASE_PAGE_WIDTH_IN = 8.5


def get_page_size_in(page):
    ratio = page["height"] / page["width"]
    page_width_in = BASE_PAGE_WIDTH_IN
    page_height_in = page_width_in * ratio
    return page_width_in, page_height_in


def bbox_to_inches(bbox, img_width, img_height, page_width_in, page_height_in):
    x_scale = page_width_in / img_width
    y_scale = page_height_in / img_height

    return (
        bbox["x_min"] * x_scale,
        bbox["y_min"] * y_scale,
        bbox["width"] * x_scale,
        bbox["height"] * y_scale,
    )


def setup_page(section, page_width_in, page_height_in):
    section.page_width = Inches(page_width_in)
    section.page_height = Inches(page_height_in)
    section.top_margin = Inches(0)
    section.bottom_margin = Inches(0)
    section.left_margin = Inches(0)
    section.right_margin = Inches(0)


def prepare_anchor_paragraph(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = 0
    p.paragraph_format.space_after = 0
    p.paragraph_format.line_spacing = 1
    return p


def add_textbox(
    paragraph,
    text,
    x_in,
    y_in,
    w_in,
    h_in,
    font_family="Times New Roman",
    font_size=11,
    bold=False,
    italic=False,
    underline=False,
    color="000000",
    alignment="LEFT",
):
    text = html.escape(text)
    font_family = html.escape(font_family)

    bold_xml = "<w:b/>" if bold else ""
    italic_xml = "<w:i/>" if italic else ""
    underline_xml = '<w:u w:val="single"/>' if underline else ""

    align_map = {
        "LEFT": "left",
        "CENTER": "center",
        "RIGHT": "right",
        "JUSTIFY": "both",
    }

    jc_val = align_map.get(alignment, "left")

    xml = f"""
    <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
         xmlns:v="urn:schemas-microsoft-com:vml"
         xmlns:o="urn:schemas-microsoft-com:office:office">
      <w:pict>
        <v:shape id="TextBox"
          type="#_x0000_t202"
          style="position:absolute;
                 margin-left:{x_in}in;
                 margin-top:{y_in}in;
                 width:{w_in}in;
                 height:{h_in}in;
                 z-index:2;
                 mso-position-horizontal-relative:page;
                 mso-position-vertical-relative:page;
                 mso-position-horizontal:absolute;
                 mso-position-vertical:absolute"
          stroked="f"
          filled="f">
          <v:textbox inset="0,0,0,0" style="mso-fit-shape-to-text:true">
            <w:txbxContent>
              <w:p>
                <w:pPr>
                  <w:jc w:val="{jc_val}"/>
                  <w:spacing w:before="0" w:after="0" w:line="220" w:lineRule="auto"/>
                </w:pPr>
                <w:r>
                  <w:rPr>
                    <w:rFonts w:ascii="{font_family}" w:hAnsi="{font_family}" w:eastAsia="{font_family}"/>
                    <w:sz w:val="{int(font_size * 2)}"/>
                    <w:color w:val="{color}"/>
                    {bold_xml}
                    {italic_xml}
                    {underline_xml}
                  </w:rPr>
                  <w:t>{text}</w:t>
                </w:r>
              </w:p>
            </w:txbxContent>
          </v:textbox>
        </v:shape>
      </w:pict>
    </w:r>
    """

    paragraph._p.append(parse_xml(xml))


def add_inline_image(paragraph, image_path, w_in, h_in):
    if not image_path or not os.path.exists(image_path):
        return

    run = paragraph.add_run()
    run.add_picture(
        image_path,
        width=Inches(w_in),
        height=Inches(h_in)
    )


def get_style(line, page_style):
    style = line.get("style", {})

    return {
        "font_family": style.get("font_family", page_style.get("font_family", "Times New Roman")),
        "font_size": style.get("font_size", page_style.get("body_font_size", 11)),
        "bold": style.get("bold", False),
        "italic": style.get("italic", False),
        "underline": style.get("underline", False),
        "color": style.get("color", "000000"),
    }


def textbox_expand_by_type(line):
    layout_type = line.get("layout_type", "text_box")

    if layout_type == "title":
        return 1.25, 1.75

    if layout_type in ["header", "footer", "page_number"]:
        return 1.25, 1.65

    if layout_type in ["table_cell_candidate", "field"]:
        return 1.35, 1.75

    return 1.3, 1.75


def main():
    ensure_dirs(DOCX_DIR)

    data = load_document()
    doc = Document()

    for page_index, page in enumerate(data["pages"]):
        page_width_in, page_height_in = get_page_size_in(page)

        if page_index == 0:
            setup_page(doc.sections[0], page_width_in, page_height_in)
        else:
            doc.add_page_break()
            section = doc.sections[-1]
            setup_page(section, page_width_in, page_height_in)

        paragraph = prepare_anchor_paragraph(doc)

        page_style = page.get("page_style", {
            "font_family": "Times New Roman",
            "body_font_size": 11,
            "title_font_size": 14,
            "heading_font_size": 12,
            "small_font_size": 9,
        })

        # Logo/image: trước mắt nhúng inline để tránh lỗi relationship.
        # Vị trí tuyệt đối ảnh sẽ xử lý ở bước sau.
        for image in page.get("images", []):
            _, _, w, h = bbox_to_inches(
                image["bbox"],
                page["width"],
                page["height"],
                page_width_in,
                page_height_in,
            )

            add_inline_image(
                paragraph,
                image.get("path") or image.get("image_path"),
                round(w, 3),
                round(h, 3),
            )

        lines = sorted(
            page.get("lines", []),
            key=lambda line: line.get("order") or line.get("line_id") or 999999
        )

        for line in lines:
            text = line.get("text", "").strip()

            if not text:
                continue

            x, y, w, h = bbox_to_inches(
                line["bbox"],
                page["width"],
                page["height"],
                page_width_in,
                page_height_in,
            )

            style = get_style(line, page_style)
            w_expand, h_expand = textbox_expand_by_type(line)

            w = max(w * w_expand, 0.35)
            h = max(h * h_expand, 0.16)

            add_textbox(
                paragraph=paragraph,
                text=text,
                x_in=round(x, 3),
                y_in=round(y, 3),
                w_in=round(w, 3),
                h_in=round(h, 3),
                font_family=style["font_family"],
                font_size=style["font_size"],
                bold=style["bold"],
                italic=style["italic"],
                underline=style["underline"],
                color=style["color"],
                alignment=line.get("alignment", "LEFT"),
            )

    doc.save(OUTPUT_DOCX)
    print("Saved:", OUTPUT_DOCX)


if __name__ == "__main__":
    main()



"""
将 .docx 文件转换为 Markdown 文件。
用法: python convert_docx_to_md.py <输入文件.docx> [输出文件.md]
"""

import sys
import os
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_paragraph_text(para: Paragraph) -> str:
    """提取段落文本，处理加粗、斜体等内联格式。"""
    runs_text = []
    for run in para.runs:
        text = run.text
        if not text:
            continue
        bold = run.bold
        italic = run.italic
        if bold and italic:
            text = f"***{text}***"
        elif bold:
            text = f"**{text}**"
        elif italic:
            text = f"*{text}*"
        runs_text.append(text)
    return "".join(runs_text)


def get_heading_level(para: Paragraph) -> int:
    """判断段落的标题级别（1-6），非标题返回 0。"""
    style_name = para.style.name if para.style else ""
    if style_name.startswith("Heading"):
        try:
            return int(style_name.replace("Heading", "").strip())
        except ValueError:
            return 0
    if style_name.startswith("标题"):
        try:
            return int(style_name.replace("标题", "").strip())
        except ValueError:
            return 0
    return 0


def para_has_numbering(para: Paragraph) -> bool:
    """判断段落是否带有序号/项目符号。"""
    numPr = para._element.find(qn("w:pPr"))
    if numPr is not None:
        numPrElem = numPr.find(qn("w:numPr"))
        if numPrElem is not None:
            return True
    return False


def extend_paragraph_text(para):
    """扩展段落结束的文本，如果end不为空，则将其添加到texts中"""
    return


def convert_table_to_md(table: Table) -> list[str]:
    """将 docx 表格转换为 Markdown 表格行列表。"""
    rows = []
    for row_idx, row in enumerate(table.rows):
        cells = []
        for cell in row.cells:
            cell_text = cell.text.replace("\n", "<br>").replace("|", "\\|")
            cells.append(cell_text)
        rows.append("| " + " | ".join(cells) + " |")
        if row_idx == 0:
            rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return rows


def convert_docx_to_md(docx_path: str, md_path: str) -> None:
    """将 docx 文件转换为 Markdown 文件。

    Args:
        docx_path: 输入的 .docx 文件路径
        md_path: 输出的 .md 文件路径
    """
    doc = Document(docx_path)
    lines: list[str] = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]  # 去掉命名空间前缀（带花括号 {} 包裹的 URI）

        if tag == "p":
            # ---- 段落 ----
            para = Paragraph(block, doc)
            text = extract_paragraph_text(para).strip()
            level = get_heading_level(para)
            is_numbered = para_has_numbering(para)

            if not text and not para._element.findall(qn("w:drawing")):
                # 空段落（无图片）
                lines.append("")
                continue

            # 检查是否含有图片
            drawings = para._element.findall(qn("w:drawing"))
            for drawing in drawings:
                # 提取图片的 rId 并尝试获取文件名
                blip = drawing.find(f".//{qn('a:blip')}")
                if blip is not None:
                    embed_id = blip.get(qn("r:embed"))
                    if embed_id:
                        try:
                            image_part = doc.part.related_parts[embed_id]
                            img_filename = os.path.basename(image_part.partname)
                            # 保存图片到与 md 同级的 images 目录
                            img_dir = os.path.join(os.path.dirname(md_path) or ".", "images")
                            os.makedirs(img_dir, exist_ok=True)
                            img_save_path = os.path.join(img_dir, img_filename)
                            with open(img_save_path, "wb") as f:
                                f.write(image_part.blob)
                            lines.append(f"![{img_filename}](images/{img_filename})")
                        except Exception:
                            lines.append("![图片]()")
                    else:
                        lines.append("![图片]()")
                else:
                    lines.append("![图片]()")

            if not text:
                continue

            if level > 0:
                # 标题
                lines.append(f"{'#' * level} {text}")
            elif is_numbered:
                # 列表项
                lines.append(f"- {text}")
            else:
                lines.append(text)

        elif tag == "tbl":
            # ---- 表格 ----
            table = Table(block, doc)
            lines.extend(convert_table_to_md(table))
            lines.append("")

        elif tag == "sdt":
            # 结构化文档标签（目录等），递归处理内部内容
            for child in block:
                child_tag = child.tag.split("}")[-1]
                if child_tag == "sdtContent":
                    for inner in child:
                        inner_tag = inner.tag.split("}")[-1]
                        if inner_tag == "p":
                            para = Paragraph(inner, doc)
                            text = extract_paragraph_text(para).strip()
                            if text:
                                lines.append(text)

    # 清理连续空行（最多保留 1 个）
    cleaned = []
    prev_empty = False
    for line in lines:
        if line == "":
            if not prev_empty:
                cleaned.append(line)
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + "\n")

    print(f"转换完成: {docx_path} → {md_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".md"

    if not os.path.exists(input_path):
        print(f"错误: 文件不存在 - {input_path}")
        sys.exit(1)

    convert_docx_to_md(input_path, output_path)

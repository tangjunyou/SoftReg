#!/usr/bin/env python3
"""Build the user-manual (documentation) identification PDF from polished Markdown.

Input: 草稿/操作手册.md (human-polished), 截图/ images.
Output: single text PDF with the same header convention as the code PDF
(software name + version left, 第 N 页 right).

Markdown subset supported (manuals don't need more):
  # / ## / ### headings, paragraphs, - bullets, 1. numbered items,
  > blockquote, | tables |, ![alt](relative-image-name), horizontal rules.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

PAGE_W, PAGE_H = A4
MARGIN_L = 2.5 * cm
MARGIN_R = 2.5 * cm
MARGIN_T = 2.4 * cm
MARGIN_B = 2.0 * cm
BODY_W = PAGE_W - MARGIN_L - MARGIN_R

FONT_CANDIDATES = {
    "cjk": [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
}


def find_cjk() -> str:
    for p in FONT_CANDIDATES["cjk"]:
        if Path(p).exists():
            return p
    raise SystemExit("STOP_FOR_USER\nNEXT_ACTION: 找不到 CJK 字体，请安装任一中文字体后重试。")


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t: str) -> str:
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<font face='CodeMono'>\1</font>", t)
    return t


def parse_md(md_text: str):
    """Yield flowable-spec tuples: (kind, payload)."""
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            yield ("h" + str(len(m.group(1))), m.group(2).strip())
            i += 1
            continue
        m = re.match(r"^!\[[^\]]*\]\(([^)]+)\)\s*$", ln.strip())
        if m:
            yield ("img", m.group(1).strip())
            i += 1
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            yield ("table", [header] + rows)
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            text = re.sub(r"^\s*[-*]\s+", "", ln)
            yield ("li", text)
            i += 1
            continue
        if re.match(r"^\s*\d+[.、]\s*", ln):
            text = re.sub(r"^\s*\d+[.、]\s*", "", ln)
            yield ("nli", text)
            i += 1
            continue
        if ln.strip().startswith(">"):
            yield ("quote", ln.strip().lstrip(">").strip())
            i += 1
            continue
        if re.match(r"^\s*([-*_])\1{2,}\s*$", ln):
            yield ("hr", None)
            i += 1
            continue
        # paragraph: absorb following lines until blank / special
        buf = [ln.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if (not nxt.strip() or nxt.strip().startswith(("#", "|", ">", "!["))
                    or re.match(r"^\s*[-*]\s+", nxt) or re.match(r"^\s*\d+[.、]\s*", nxt)):
                break
            buf.append(nxt.strip())
            i += 1
        yield ("p", "".join(buf))


def make_styles(font: str) -> dict:
    base = dict(fontName=font, wordWrap="CJK", textColor="black")
    return {
        "h1": ParagraphStyle("h1", fontSize=16, leading=24, spaceBefore=14, spaceAfter=10, **base),
        "h2": ParagraphStyle("h2", fontSize=13, leading=20, spaceBefore=12, spaceAfter=8, **base),
        "h3": ParagraphStyle("h3", fontSize=11.5, leading=18, spaceBefore=10, spaceAfter=6, **base),
        "p": ParagraphStyle("p", fontSize=10.5, leading=17, firstLineIndent=21, spaceAfter=6, **base),
        "li": ParagraphStyle("li", fontSize=10.5, leading=17, leftIndent=21, spaceAfter=4, **base),
        "quote": ParagraphStyle("quote", fontSize=10, leading=16, leftIndent=21, **base),
        "cell": ParagraphStyle("cell", fontSize=9.5, leading=14, **base),
    }


def image_flow(spec: str, images_dir: Path | None, used: list, font: str) -> KeepTogether | Paragraph:
    name = spec.split("/")[-1].split("?")[0]
    p = (images_dir / name) if images_dir else None
    if not p or not p.exists():
        # keep a visible placeholder so the slot survives into the final PDF
        used.append({"requested": spec, "found": False})
        return Paragraph(f"【截图预留：请在此处插入 {esc(name)} 对应的界面截图。】",
                         ParagraphStyle("ph", fontName=font, wordWrap="CJK", fontSize=10.5,
                                        leading=17, textColor="black", backColor="#f0f0f0",
                                        borderPadding=6, spaceAfter=8))
    used.append({"requested": spec, "found": True, "path": str(p)})
    with PILImage.open(p) as im:
        w, h = im.size
    tw = BODY_W
    th = tw * h / w
    max_h = PAGE_H * 0.55
    if th > max_h:
        th = max_h
        tw = th * w / h
    img = Image(str(p), width=tw, height=th)
    return KeepTogether([img, Spacer(1, 8)])


def build(out_path: Path, md_path: Path, images_dir: Path | None, software_name: str, version: str) -> dict:
    font_name = "DocCJK"
    mono = None
    from build_code_pdf import find_font  # reuse font discovery
    try:
        mono = find_font("mono")
        pdfmetrics.registerFont(TTFont("CodeMono", mono))
    except SystemExit:
        pass
    cjk = find_cjk()
    pdfmetrics.registerFont(TTFont(font_name, cjk))
    styles = make_styles(font_name)

    story = []
    used_images: list[dict] = []
    table_count = 0
    heading_seq: list[str] = []

    for kind, payload in parse_md(md_path.read_text(encoding="utf-8")):
        if kind in ("h1", "h2", "h3"):
            heading_seq.append(payload)
            story.append(Paragraph(inline(payload), styles[kind]))
        elif kind == "p":
            story.append(Paragraph(inline(payload), styles["p"]))
        elif kind in ("li", "nli"):
            bullet = "• " if kind == "li" else ""
            story.append(Paragraph(bullet + inline(payload), styles["li"]))
        elif kind == "quote":
            story.append(Paragraph(inline(payload), styles["quote"]))
        elif kind == "hr":
            story.append(Spacer(1, 6))
        elif kind == "img":
            story.append(image_flow(payload, images_dir, used_images, font_name))
        elif kind == "table":
            table_count += 1
            data = [[Paragraph(inline(c), styles["cell"]) for c in row] for row in payload]
            t = Table(data, colWidths=[BODY_W / len(data[0])] * len(data[0]))
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, "#999999"),
                ("BACKGROUND", (0, 0), (-1, 0), "#eeeeee"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        y = PAGE_H - 40
        canvas.drawString(MARGIN_L, y, f"{software_name} {version}")
        label = f"第 {doc.page} 页"
        w = pdfmetrics.stringWidth(label, font_name, 8)
        canvas.drawString(PAGE_W - MARGIN_R - w, y, label)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_L, y - 6, PAGE_W - MARGIN_R, y - 6)
        canvas.restoreState()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(out_path), pagesize=A4,
                          leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                          topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                          title=f"{software_name} {version} 用户操作手册")
    frame = Frame(MARGIN_L, MARGIN_B, BODY_W, PAGE_H - MARGIN_T - MARGIN_B, id="body")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=on_page)])
    doc.build(story)

    return {"images": used_images, "tables": table_count,
            "headings": len(heading_seq),
            "images_missing": sum(1 for u in used_images if not u["found"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", required=True)
    ap.add_argument("--images-dir", default=None)
    ap.add_argument("--software-name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from common import final_confirmation_issue
    manual_path = Path(args.manual).resolve()
    workdir = manual_path.parent.parent if manual_path.parent.name == "草稿" else manual_path.parent
    issue = final_confirmation_issue(workdir)
    if issue:
        raise SystemExit("STOP_FOR_USER\nNEXT_ACTION: " + issue)

    out = Path(args.out)
    info = build(out, Path(args.manual),
                 Path(args.images_dir) if args.images_dir else None,
                 args.software_name, args.version)

    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(out))
    n = len(pdf)
    sample = pdf[0].get_textpage().get_text_range()
    pdf.close()
    result = {"pages": n, "has_text_layer": bool(sample and sample.strip()), **info}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if info["images_missing"]:
        print(f"NOTE: {info['images_missing']} 张截图缺失，已在 PDF 中保留可见预留位。", file=sys.stderr)


if __name__ == "__main__":
    main()

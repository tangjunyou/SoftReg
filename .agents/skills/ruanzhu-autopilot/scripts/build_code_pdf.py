#!/usr/bin/env python3
"""Build the single source-code identification PDF for software copyright registration.

Fixes over the upstream docx pipeline (issues #26/#27/#28):
- One single PDF (official upload slot accepts exactly one file).
- Exact physical page count (front 30 + back 30 = 60 sheets), because we render
  lines ourselves with reportlab instead of trusting Word pagination.
- No Word theme fonts; embedded Courier New (ASCII) + Arial Unicode (CJK).
- Mixed-width measurement per line, soft-wrap simulation, per-page source-line
  floor of 50, adaptive font-size/spacing combos.

Usage:
  python3 build_code_pdf.py \
    --project <project-dir> \
    --selection <草稿/代码文件选择.json> \
    --software-name "某某管理系统" \
    --version "V1.0" \
    --out 软件著作权申请资料/正式资料/代码鉴别材料.pdf
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
MARGIN_L = 45.0
MARGIN_R = 45.0
MARGIN_T = 68.0  # header lives inside the top margin
MARGIN_B = 42.0
BODY_W = PAGE_W - MARGIN_L - MARGIN_R
BODY_TOP = PAGE_H - MARGIN_T
BODY_BOTTOM = MARGIN_B
BODY_H = BODY_TOP - BODY_BOTTOM

PAGE_SOURCE_LINES = 52          # rows per page incl. File markers -> >=50 real code lines
FRONT_PAGES = 30
BACK_PAGES = 30
# (font_size, line_spacing) combos from comfortable to cramped; first fit wins.
LAYOUT_CANDIDATES = [
    (7.0, 11.0), (7.0, 10.5), (7.0, 10.0), (7.0, 9.5), (7.0, 9.0),
    (6.5, 9.0), (6.5, 8.5), (6.0, 8.0),
]
WRAP_INDENT = "    "            # continuation indent for soft-wrapped display rows

FONT_CANDIDATES = {
    "mono": [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/courier/Courier_New.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    ],
    "cjk": [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
}

COMMENT_PREFIX = {
    ".py": "#", ".rb": "#", ".sh": "#", ".yaml": "#", ".yml": "#", ".toml": "#",
    ".ini": "#", ".conf": "#", ".sql": "--",
}


def find_font(kind: str) -> str:
    for candidate in FONT_CANDIDATES[kind]:
        if Path(candidate).exists():
            return candidate
    raise SystemExit(f"STOP_FOR_USER\nNEXT_ACTION: 找不到可用字体（{kind}）。请安装 Courier New / 任一 CJK 字体后重试。")


def register_fonts() -> tuple[str, str]:
    mono = find_font("mono")
    cjk = find_font("cjk")
    pdfmetrics.registerFont(TTFont("CodeMono", mono))
    pdfmetrics.registerFont(TTFont("CodeCJK", cjk))
    return "CodeMono", "CodeCJK"


def is_ascii(ch: str) -> bool:
    return ord(ch) < 128


def visual_width(ch: str, size: float) -> float:
    if is_ascii(ch):
        return pdfmetrics.stringWidth(ch, "CodeMono", size)
    return pdfmetrics.stringWidth(ch, "CodeCJK", size)


def measure(text: str, size: float) -> float:
    if all(is_ascii(c) for c in text):
        return pdfmetrics.stringWidth(text, "CodeMono", size)
    return sum(visual_width(c, size) for c in text)


def wrap_line(text: str, max_w: float, size: float) -> list[str]:
    """Soft-wrap one source line into display rows that each fit max_w."""
    if measure(text, size) <= max_w or not text:
        return [text]
    rows: list[str] = []
    cur = ""
    cur_w = 0.0
    for ch in text:
        w = visual_width(ch, size)
        if cur_w + w > max_w and cur:
            rows.append(cur)
            cur = WRAP_INDENT
            cur_w = measure(WRAP_INDENT, size)
        cur += ch
        cur_w += w
    if cur.strip():
        rows.append(cur)
    return rows


def comment_prefix_for(path: Path) -> str:
    return COMMENT_PREFIX.get(path.suffix.lower(), "//")


def read_selection(selection_path: Path) -> list[dict]:
    data = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("selection_required") and not data.get("user_confirmed"):
        raise SystemExit(
            "STOP_FOR_USER\nNEXT_ACTION: 代码文件选择尚未确认。请先在 草稿/代码文件选择.json 中确认，"
            "并运行 confirm_stage.py --stage code-selection。"
        )
    items = data.get("files") if isinstance(data, dict) else data
    selected = [it for it in items if isinstance(it, dict) and it.get("selected") and it.get("path")]
    if not selected:
        raise SystemExit("STOP_FOR_USER\nNEXT_ACTION: 代码文件选择.json 中没有任何 selected=true 的文件。")
    return selected


def collect_lines(project: Path, selection_path: Path) -> tuple[list[str], list[dict]]:
    """Return (stream of material lines, per-file manifest). Pure blank lines dropped."""
    stream: list[str] = []
    manifest: list[dict] = []
    for item in read_selection(selection_path):
        rel_path = item["path"]
        f = (project / rel_path).resolve()
        try:
            f.relative_to(project.resolve())
        except ValueError:
            raise SystemExit(f"Selected file is outside project: {f}")
        if not f.is_file():
            continue
        raw_lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        start_line = int(item.get("start_line") or 1)
        end_line = int(item.get("end_line") or len(raw_lines))
        seg = raw_lines[start_line - 1 : end_line]
        keep = [ln.rstrip() for ln in seg if ln.strip()]
        if not keep:
            continue
        marker = f"{comment_prefix_for(f)} File: {rel_path}"
        mat_start = len(stream) + 1
        stream.append(marker)
        stream.extend(keep)
        manifest.append(
            {
                "path": rel_path,
                "source_lines": len(raw_lines),
                "blank_dropped": len(seg) - len(keep),
                "segment": [start_line, end_line],
                "material_line_range": [mat_start, len(stream)],
            }
        )
    return stream, manifest


def plan_pages(stream: list[str]) -> tuple[list[list[str]], dict]:
    """Try layout combos comfortable->cramped; return page chunks + chosen layout."""
    chunks = [stream[i : i + PAGE_SOURCE_LINES] for i in range(0, len(stream), PAGE_SOURCE_LINES)]
    report = {"worst_page_display_rows": None, "font_size": None, "spacing_pt": None,
              "capacity": None, "ok": False}
    for size, sp in LAYOUT_CANDIDATES:
        worst = max(sum(len(wrap_line(ln, BODY_W, size)) for ln in ch) for ch in chunks)
        cap = math.floor(BODY_H / sp)
        report.update(worst_page_display_rows=worst, font_size=size, spacing_pt=sp, capacity=cap)
        if worst <= cap:
            report["ok"] = True
            break
    return chunks, report


def header_footer(c: canvas.Canvas, page_no: int, software_name: str, version: str) -> None:
    c.setFont("CodeCJK", 8)
    y = PAGE_H - 40
    c.drawString(MARGIN_L, y, f"{software_name} {version}")
    label = f"第 {page_no} 页"
    w = pdfmetrics.stringWidth(label, "CodeCJK", 8)
    c.drawString(PAGE_W - MARGIN_R - w, y, label)
    c.setLineWidth(0.4)
    c.line(MARGIN_L, y - 6, PAGE_W - MARGIN_R, y - 6)


def draw_mixed(c: canvas.Canvas, x: float, y: float, text: str, size: float) -> None:
    """Draw a display row switching fonts between ASCII and non-ASCII runs."""
    cur = ""
    cur_ascii = is_ascii(text[0]) if text else True
    cx = x
    for ch in text:
        a = is_ascii(ch)
        if a != cur_ascii and cur:
            c.setFont("CodeMono" if cur_ascii else "CodeCJK", size)
            c.drawString(cx, y, cur)
            cx += pdfmetrics.stringWidth(cur, "CodeMono" if cur_ascii else "CodeCJK", size)
            cur = ""
            cur_ascii = a
        cur += ch
    if cur:
        c.setFont("CodeMono" if cur_ascii else "CodeCJK", size)
        c.drawString(cx, y, cur)


def render_pdf(out_path: Path, pages: list[list[str]], font_size: float, spacing: float,
               software_name: str, version: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=A4)
    c.setTitle(f"{software_name} {version} 源程序")
    for idx, page in enumerate(pages, start=1):
        header_footer(c, idx, software_name, version)
        y = BODY_TOP - spacing
        for ln in page:
            for row in wrap_line(ln, BODY_W, font_size):
                if y < BODY_BOTTOM - spacing:
                    raise SystemExit("FATAL: 页面溢出（自适应布局失败），拒绝生成不合格 PDF。")
                draw_mixed(c, MARGIN_L, y, row, font_size)
                y -= spacing
        c.showPage()
    c.save()


def self_check(out_path: Path, expected_pages: int) -> dict:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(out_path))
    n = len(pdf)
    sample = pdf[min(1, n - 1)].get_textpage().get_text_range()
    text_ok = bool(sample and sample.strip())
    pdf.close()
    return {"pages": n, "expected": expected_pages, "pages_match": n == expected_pages,
            "has_text_layer": text_ok}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--selection", required=True)
    ap.add_argument("--software-name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest-out", default=None)
    ap.add_argument("--front-pages", type=int, default=FRONT_PAGES)
    ap.add_argument("--back-pages", type=int, default=BACK_PAGES)
    args = ap.parse_args()

    register_fonts()
    project = Path(args.project).resolve()
    stream, manifest = collect_lines(project, Path(args.selection))

    front_n = args.front_pages * PAGE_SOURCE_LINES
    back_n = args.back_pages * PAGE_SOURCE_LINES
    total_needed = front_n + back_n

    mode = "full"
    if len(stream) >= total_needed:
        mode = "front_back"
        pages_src = stream[:front_n] + stream[-back_n:]
    else:
        pages_src = stream

    chunks, report = plan_pages(pages_src)
    if not report["ok"]:
        print(
            f"WARN: 所有字号/行距组合都无法容纳最差页 "
            f"({report['worst_page_display_rows']} 显示行 > 容量 {report['capacity']})。"
            "建议在 代码文件选择.json 中剔除超长行文件（如内联 SVG / 超长 className），"
            "或对文件使用 start_line/end_line 截段。",
            file=sys.stderr,
        )

    out = Path(args.out)
    render_pdf(out, chunks, report["font_size"], report["spacing_pt"],
               args.software_name, args.version)

    result = {
        "mode": mode,
        "material_lines_total": len(stream),
        "source_line_count": sum(m["source_lines"] for m in manifest),
        "selected_source_line_count": len(stream),
        "total_pages": len(chunks),
        "source_lines_needed_for_front_back": total_needed,
        "pages": len(chunks),
        "rows_per_page": PAGE_SOURCE_LINES,
        "font_size": report["font_size"],
        "spacing_pt": report["spacing_pt"],
        "layout_report": report,
        "files": manifest,
        "last_line": pages_src[-1][:120] if pages_src else "",
    }
    result["self_check"] = self_check(out, len(chunks))

    manifest_out = Path(args.manifest_out) if args.manifest_out else out.with_suffix(".manifest.json")
    manifest_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: result[k] for k in ("mode", "pages", "font_size", "spacing_pt", "self_check")},
                     ensure_ascii=False, indent=2))
    if not result["self_check"]["pages_match"]:
        raise SystemExit("FATAL: 渲染页数与计划页数不一致，请勿提交该文件。")
    if mode == "full":
        print(f"NOTE: 源码不足 {total_needed} 行，按全部提交模式生成 {len(chunks)} 页。", file=sys.stderr)


if __name__ == "__main__":
    main()

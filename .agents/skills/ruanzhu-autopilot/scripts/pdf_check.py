#!/usr/bin/env python3
"""Pre-upload health check for identification-material PDFs.

Run this on every PDF right before uploading to register.ccopyright.com.cn.
Doc types:
  code   - 源程序鉴别材料: >=50 rows/page hard requirement
  manual - 文档鉴别材料(操作手册): 30-row rule is advisory for pages that
           carry screenshots/tables, so density issues are warnings, not blockers

Checks:
  1. valid PDF, sane file size
  2. exact page count (front30+back30 must equal 60)
  3. text layer on every page (official wants readable text PDFs)
  4. header on every page: "<software-name> <version>" + "第 N 页",
     page numbers continuous 1..N
  5. per-page density (hard for code, advisory for manual)
  6. no blank pages (render-sample pixel variance)

Usage:
  python3 pdf_check.py --pdf 代码鉴别材料.pdf \
    --software-name "某某管理系统" --version "V1.0" \
    --doc-type code [--expect-pages 60]
Exit code 0 = pass; 1 = fail (do NOT upload); 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

MIN_ROWS_CODE = 50
MIN_ROWS_MANUAL = 30
SIZE_WARN_BYTES = 10 * 1024 * 1024


def page_rows(text: str) -> list[str]:
    return [ln for ln in re.split(r"[\r\n]+", text) if ln.strip()]


def render_is_blank(page) -> bool:
    img = page.render(scale=0.5).to_pil().convert("L")
    hist = img.histogram()
    dark = sum(hist[:200])
    return dark < img.width * img.height * 0.001  # <0.1% dark pixels


def check(pdf_path: Path, software_name: str, version: str,
          expect_pages: int | None, doc_type: str) -> dict:
    problems: list[str] = []
    warnings: list[str] = []
    result: dict = {"pdf": str(pdf_path), "doc_type": doc_type,
                    "problems": problems, "warnings": warnings}

    if not pdf_path.is_file():
        problems.append(f"文件不存在: {pdf_path}")
        return result
    size = pdf_path.stat().st_size
    result["size_mb"] = round(size / 1024 / 1024, 2)
    if size < 1024:
        problems.append("文件过小（<1KB），疑似损坏。")
    if size > SIZE_WARN_BYTES:
        warnings.append(f"文件 {result['size_mb']}MB 偏大，官网大文件上传易超时，建议压缩图片。")

    pdf = pdfium.PdfDocument(str(pdf_path))
    n = len(pdf)
    result["pages"] = n
    if n < 1:
        problems.append("PDF 无页面。")
        pdf.close()
        return result
    if expect_pages is not None and n != expect_pages:
        problems.append(f"页数 {n} != 预期 {expect_pages}。前30+后30 必须正好 60 页；全部提交模式应为实际全部页。")

    header_needle = f"{software_name} {version}"
    for i in range(n):
        page = pdf[i]
        text = page.get_textpage().get_text_range()
        rows = page_rows(text)
        page_no = i + 1
        flat = text.replace("\r", "").replace("\n", " ")
        if not text.strip():
            problems.append(f"第 {page_no} 页无文本层（疑似纯图片页）。官网要求可读文本。")
            continue
        if header_needle not in flat:
            problems.append(f"第 {page_no} 页页眉缺少「{header_needle}」。")
        if f"第 {page_no} 页" not in flat:
            problems.append(f"第 {page_no} 页页码不是「第 {page_no} 页」（页码须连续且与实际张数一致）。")
        body_rows = len(rows) - 1  # header line itself doesn't count
        if doc_type == "code":
            if body_rows < MIN_ROWS_CODE and page_no != n:
                problems.append(f"第 {page_no} 页仅 {body_rows} 行（含折行），低于每页 {MIN_ROWS_CODE} 行要求。")
            if page_no == n and expect_pages == 60 and body_rows < 30:
                problems.append(f"末页仅 {body_rows} 行，疑似内容被截断。")
        else:  # manual
            if body_rows < MIN_ROWS_MANUAL:
                warnings.append(
                    f"第 {page_no} 页正文行数 {body_rows} 低于 {MIN_ROWS_MANUAL}"
                    "（含截图/表格的页面属正常，请人工确认该页有实质内容）。")
        if render_is_blank(page):
            problems.append(f"第 {page_no} 页渲染后近乎空白。")
    pdf.close()

    result["pass"] = not problems
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--software-name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--doc-type", choices=["code", "manual"], default="code")
    ap.add_argument("--expect-pages", type=int, default=None,
                    help="60 for front30+back30; omit to only validate consistency")
    args = ap.parse_args()

    result = check(Path(args.pdf), args.software_name, args.version,
                   args.expect_pages, args.doc_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["problems"]:
        print("RESULT: FAIL — 请勿上传该文件。", file=sys.stderr)
        sys.exit(1)
    print("RESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()

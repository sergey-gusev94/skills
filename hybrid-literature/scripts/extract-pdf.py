#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf4llm==1.28.2"]
# ///
"""Extract a PDF to page-marked Markdown with a pdftotext fallback."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def write_pages(output: Path, pages: list[str]) -> None:
    if not any(page.strip() for page in pages):
        raise ValueError("extractor returned no usable text")
    chunks = []
    for number, page in enumerate(pages, 1):
        chunks.append(f"<!-- page {number} -->\n\n{page.strip()}\n")
    output.write_text("\n".join(chunks), encoding="utf-8")


def with_pymupdf(source: Path, output: Path) -> bool:
    try:
        import pymupdf4llm  # type: ignore[import-not-found]

        chunks = pymupdf4llm.to_markdown(str(source), page_chunks=True, use_ocr=False)
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("pymupdf4llm returned no page chunks")
        pages = []
        for chunk in chunks:
            if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
                raise ValueError("invalid pymupdf4llm page chunk")
            pages.append(chunk["text"])
        write_pages(output, pages)
        return True
    except Exception as exc:  # The fallback must cover import and extraction errors.
        print(f"pymupdf4llm unavailable or failed: {exc}", file=sys.stderr)
        return False


def with_pdftotext(source: Path, output: Path) -> bool:
    executable = shutil.which("pdftotext")
    if executable is None:
        print("pdftotext not found", file=sys.stderr)
        return False
    try:
        result = subprocess.run(
            [executable, str(source), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        pages = text.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        if not pages:
            raise ValueError("pdftotext returned no pages")
        write_pages(output, pages)
        return True
    except Exception as exc:
        print(f"pdftotext failed: {exc}", file=sys.stderr)
        return False


def remove_output(output: Path) -> None:
    try:
        if output.is_file() or output.is_symlink():
            output.unlink()
    except OSError as exc:
        print(f"could not remove failed extraction output: {exc}", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract-pdf.py <input.pdf> <output.md>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    if not source.is_file():
        remove_output(output)
        print(f"input PDF not found: {source}", file=sys.stderr)
        print("EXTRACTION=failed")
        return 1
    same_file = source.resolve() == output.resolve()
    if output.exists():
        try:
            same_file = same_file or source.samefile(output)
        except OSError:
            pass
    if same_file:
        print("input and output must be different files", file=sys.stderr)
        print("EXTRACTION=failed")
        return 1
    if with_pymupdf(source, output):
        print("EXTRACTION=pymupdf4llm")
        return 0
    if with_pdftotext(source, output):
        print("EXTRACTION=pdftotext")
        return 0
    remove_output(output)
    print("EXTRACTION=failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

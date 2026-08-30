#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf==1.26.4", "pyyaml==6.0.2"]
# ///
"""Create, ingest, validate, and index a literature knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


class QuotedString(str):
    pass


class FrontmatterDumper(yaml.SafeDumper):
    pass


FrontmatterDumper.add_representer(
    QuotedString,
    lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"'),
)


TYPES = {
    "article", "preprint", "chapter", "book", "thesis", "proceedings",
    "report", "dataset", "software", "standard", "other",
}
ACCESSES = {"open", "user-supplied", "none"}
FULLTEXTS = {"pymupdf", "pdftotext", "none"}
STATUSES = {"unread", "read"}
REQUIRED_PRESENT = {
    "slug", "title", "authors", "year", "venue", "type", "access",
    "fulltext", "status", "added", "candidate_id", "relevance",
}
REQUIRED_NONEMPTY = {
    "slug", "title", "type", "access", "fulltext", "status", "added",
    "candidate_id", "relevance",
}
PAGE_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
REF_RE = re.compile(r"\[\[([^]\n]+)\]\](?:\s+p\.(\d+))?")


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " and ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def normalize_doi(value: Any) -> str:
    raw = text(value).lower()
    raw = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", raw)
    normalized = raw.rstrip(" \t\r\n.,;:'\"")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while normalized.endswith(closing) and normalized.count(closing) > normalized.count(opening):
            normalized = normalized[:-1].rstrip(" \t\r\n.,;:'\"")
    return normalized


def normalize_arxiv(value: Any) -> str:
    raw = re.sub(r"^arxiv:\s*", "", text(value).lower())
    return re.sub(r"v\d+$", "", raw.strip().rstrip(".,;:'\""))


def ascii_words(value: Any) -> list[str]:
    folded = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", folded.lower())


def normalize_title(value: Any) -> str:
    return "".join(ascii_words(value))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{number}: malformed JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{number}: candidate must be a JSON object")
            continue
        records.append(record)
    if errors:
        raise ValueError("\n".join(errors))
    return records


def frontmatter(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\s*\Z)", content, re.DOTALL)
    if not match:
        raise ValueError("missing YAML frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def note_body(content: str) -> str:
    match = re.match(r"\A---\s*\n.*?\n---(?:\s*\n|\s*\Z)", content, re.DOTALL)
    return content[match.end():] if match else content


def kb_papers(kb: Path) -> dict[str, dict[str, Any]]:
    papers: dict[str, dict[str, Any]] = {}
    root = kb / "papers"
    if not root.is_dir():
        return papers
    for note in sorted(root.glob("*/paper.md")):
        if note.is_symlink():
            continue
        try:
            papers[note.parent.name] = frontmatter(note)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError):
            continue
    return papers


def identity_maps(papers: dict[str, dict[str, Any]]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    dois: dict[str, str] = {}
    arxivs: dict[str, str] = {}
    titles: dict[str, str] = {}
    for slug, data in papers.items():
        doi = normalize_doi(data.get("doi"))
        arxiv = normalize_arxiv(data.get("arxiv"))
        title_key = normalize_title(data.get("title"))
        if doi:
            dois.setdefault(doi, slug)
        if arxiv:
            arxivs.setdefault(arxiv, slug)
        if title_key:
            titles.setdefault(title_key, slug)
    return dois, arxivs, titles


def kb_structure_errors(kb: Path) -> list[str]:
    if os.path.islink(kb):
        return [f"{kb}: knowledge-base root is a symlink"]
    if not kb.is_dir():
        return [f"{kb}: knowledge-base directory is missing"]
    papers = kb / "papers"
    if os.path.islink(papers):
        return [f"{papers}: papers directory is a symlink"]
    if not papers.is_dir():
        return [f"{papers}: papers directory is missing"]
    staging = kb / ".staging"
    if os.path.islink(staging):
        return [f"{staging}: staging directory is a symlink"]
    return []


def command_init(args: argparse.Namespace) -> int:
    project = args.project.absolute()
    kb = project / "literature"
    if kb.is_symlink():
        print(f"ERROR: knowledge-base path is a symlink: {kb}", file=sys.stderr)
        return 1
    if kb.exists():
        print(f"ERROR: knowledge base already exists: {kb}", file=sys.stderr)
        return 1
    if not project.is_dir():
        print(f"ERROR: project directory does not exist: {project}", file=sys.stderr)
        return 1
    template = Path(__file__).resolve().parent.parent / "assets" / "kb-template"
    shutil.copytree(template, kb, symlinks=True)
    gitignore = kb / "gitignore"
    gitignore.rename(kb / ".gitignore")
    generate_derived(kb, {})
    print(f"INITIALIZED={kb}")
    return 0


def merge_group(records: list[dict[str, Any]], indexes: list[int]) -> dict[str, Any]:
    merged = dict(records[indexes[0]])
    lanes: list[str] = []
    urls: list[str] = []
    oa_urls: list[str] = []
    for index in indexes:
        record = records[index]
        for key, value in record.items():
            if key not in merged or merged[key] in (None, "", []):
                merged[key] = value
        lane_values = record.get("lanes", record.get("lane", []))
        if not isinstance(lane_values, list):
            lane_values = [lane_values]
        for lane in lane_values:
            if text(lane) and text(lane) not in lanes:
                lanes.append(text(lane))
        for key, target in (("url", urls), ("oa_url", oa_urls)):
            values = record.get(f"{key}s", record.get(key, []))
            if not isinstance(values, list):
                values = [values]
            for url in values:
                if text(url) and text(url) not in target:
                    target.append(text(url))
        if len(text(record.get("relevance"))) > len(text(merged.get("relevance"))):
            merged["relevance"] = text(record.get("relevance"))
    if lanes:
        merged["lane"] = lanes[0]
        merged["lanes"] = lanes
    if urls:
        merged["url"] = urls[0]
        merged["urls"] = urls
    if oa_urls:
        merged["oa_url"] = oa_urls[0]
        merged["oa_urls"] = oa_urls
    doi = normalize_doi(merged.get("doi"))
    arxiv = normalize_arxiv(merged.get("arxiv"))
    if doi:
        merged["doi"] = doi
    if arxiv:
        merged["arxiv"] = arxiv
    return merged


def compact_candidate_line(candidate: dict[str, Any]) -> str:
    author = text(candidate.get("authors"))
    first_author = re.split(r"\s+and\s+|,", author, maxsplit=1, flags=re.I)[0] or "-"
    title_value = text(candidate.get("title"))
    short_title = title_value if len(title_value) <= 52 else title_value[:49] + "..."
    access = "file" if candidate.get("file") else ("open" if candidate.get("oa_url") else "none")
    return f"{candidate['id']:<12} {text(candidate.get('in_kb')) or '-':<24} {text(candidate.get('year')) or '-':<6} {first_author[:18]:<18} {short_title:<52} {access}"


def command_dedup(args: argparse.Namespace) -> int:
    structure_errors = kb_structure_errors(args.kb)
    if structure_errors:
        for error in structure_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    records: list[dict[str, Any]] = []
    try:
        for lane in args.lanes:
            records.extend(read_jsonl(lane))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root if left_root < right_root else right_root
            parent[left_root] = min(left_root, right_root)

    seen_doi: dict[str, int] = {}
    seen_arxiv: dict[str, int] = {}
    for index, record in enumerate(records):
        for normalized, seen in (
            (normalize_doi(record.get("doi")), seen_doi),
            (normalize_arxiv(record.get("arxiv")), seen_arxiv),
        ):
            if normalized:
                if normalized in seen:
                    union(index, seen[normalized])
                else:
                    seen[normalized] = index

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        groups[find(index)].append(index)
    candidates = [merge_group(records, indexes) for _, indexes in sorted(groups.items(), key=lambda item: min(item[1]))]

    papers = kb_papers(args.kb)
    kb_dois, kb_arxivs, kb_titles = identity_maps(papers)
    for number, candidate in enumerate(candidates, 1):
        candidate["id"] = f"{args.prefix}-N{number:03d}"
        doi = normalize_doi(candidate.get("doi"))
        arxiv = normalize_arxiv(candidate.get("arxiv"))
        title_key = normalize_title(candidate.get("title"))
        owner = (kb_dois.get(doi) if doi else None) or (kb_arxivs.get(arxiv) if arxiv else None) or (kb_titles.get(title_key) if title_key else None)
        if owner:
            candidate["in_kb"] = owner

    title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        title_key = normalize_title(candidate.get("title"))
        if title_key:
            title_groups[title_key].append(candidate)
    for matches in title_groups.values():
        if len(matches) > 1:
            for candidate in matches:
                candidate["possible_duplicate_of"] = [other["id"] for other in matches if other is not candidate]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    print(f"{'ID':<12} {'IN_KB':<24} {'YEAR':<6} {'FIRST AUTHOR':<18} {'TITLE':<52} ACCESS")
    for candidate in candidates:
        print(compact_candidate_line(candidate))
    print(f"INPUT={len(records)} CANDIDATES={len(candidates)} COLLAPSED={len(records) - len(candidates)} IN_KB={sum('in_kb' in item for item in candidates)}")
    return 0


def source_extension(data: bytes, content_type: str = "", url: str = "") -> str:
    lowered = data[:512]
    if lowered.startswith(b"\xef\xbb\xbf"):
        lowered = lowered[3:]
    lowered = lowered.lstrip()
    if lowered.lower().startswith(b"<?xml"):
        end = lowered.find(b"?>")
        if end >= 0:
            lowered = lowered[end + 2:].lstrip()
    lowered = lowered.lower()
    ctype = content_type.lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    if data.startswith(b"%PDF-"):
        return "pdf"
    if lowered.startswith((b"<!doctype html", b"<html")) or "html" in ctype:
        return "html"
    if "spreadsheetml" in ctype or suffix == ".xlsx":
        return "xlsx"
    if data.startswith(b"PK\x03\x04") or "zip" in ctype:
        return "zip"
    if lowered.startswith((b"{", b"[")) or "json" in ctype:
        return "json"
    if "markdown" in ctype or suffix in {".md", ".markdown"}:
        return "md"
    if ctype.startswith("text/") or suffix == ".txt":
        return "txt"
    return "bin"


def read_prefix(path: Path, limit: int = 512) -> bytes:
    with path.open("rb") as handle:
        return handle.read(limit)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_pages(path: Path, pages: Iterable[str]) -> None:
    page_list = list(pages)
    if not page_list:
        raise ValueError("extractor returned no pages")
    chunks = []
    for number, page in enumerate(page_list, 1):
        safe_page = PAGE_RE.sub(lambda match: match.group(0).replace("<!--", "<!- -", 1), page)
        chunks.append(f"<!-- page {number} -->\n\n{safe_page.strip()}\n")
    path.write_text("\n".join(chunks), encoding="utf-8")


def pymupdf_worker(source: Path, output: Path) -> int:
    delay = os.environ.get("LIT_TEST_PYMUPDF_DELAY")
    if delay:
        time.sleep(float(delay))
    import pymupdf

    document = pymupdf.open(source)
    try:
        write_pages(output, [page.get_text() for page in document])
    finally:
        document.close()
    return 0


def extract_pdf(source: Path, output: Path, timeout: float | None = None) -> str:
    if timeout is None:
        timeout = float(os.environ.get("LIT_PYMUPDF_TIMEOUT", "120"))
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "_extract-pymupdf", str(source), str(output)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return "pymupdf"
    except (OSError, subprocess.SubprocessError, ValueError):
        output.unlink(missing_ok=True)
    executable = shutil.which("pdftotext")
    if not executable:
        return "none"
    try:
        result = subprocess.run(
            [executable, str(source), "-"], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        )
        pages = result.stdout.decode("utf-8", errors="replace").split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        write_pages(output, pages)
        return "pdftotext"
    except (OSError, subprocess.SubprocessError, ValueError):
        output.unlink(missing_ok=True)
        return "none"


def surname_for(authors: Any, title_value: Any) -> str:
    author_text = text(authors)
    if author_text:
        first = re.split(r"\s+and\s+", author_text, maxsplit=1, flags=re.I)[0].strip()
        if " and " in author_text.lower() and "," in first:
            words = ascii_words(first.split(",", 1)[0])
        else:
            first = first.split(",", 1)[0]
            words = ascii_words(first)
        if words and words[-1] != "unknown":
            return words[-1]
    title_words = [word for word in ascii_words(title_value) if word != "unknown"]
    return title_words[0] if title_words else "paper"


def make_slug(candidate: dict[str, Any], occupied: set[str]) -> str:
    surname = surname_for(candidate.get("authors"), candidate.get("title"))
    year_match = re.search(r"\d{4}", text(candidate.get("year")))
    year = year_match.group(0) if year_match else "0000"
    title_words = [word for word in ascii_words(candidate.get("title")) if word != "unknown"][:5] or ["paper"]
    base = "-".join([f"{surname}{year}", *title_words])
    base = "-".join(re.findall(r"[a-z0-9]+", base)) or "paper0000-paper"
    slug = base
    suffix = 2
    while slug in occupied:
        slug = f"{base}-{suffix}"
        suffix += 1
    occupied.add(slug)
    return slug


def mapped_type(value: Any) -> str:
    raw = text(value).lower()
    if raw in TYPES:
        return raw
    mappings = (
        ("preprint", "preprint"), ("arxiv", "preprint"),
        ("conference", "proceedings"), ("proceeding", "proceedings"),
        ("journal", "article"), ("article", "article"),
        ("chapter", "chapter"), ("book", "book"), ("thesis", "thesis"),
        ("dissertation", "thesis"), ("report", "report"),
        ("dataset", "dataset"), ("software", "software"),
        ("standard", "standard"),
    )
    return next((result for token, result in mappings if token in raw), "other")


def yaml_document(data: dict[str, Any]) -> str:
    quoted = {
        key: QuotedString(value) if isinstance(value, str) else value
        for key, value in data.items()
    }
    return yaml.dump(
        quoted, Dumper=FrontmatterDumper, allow_unicode=True,
        sort_keys=False, width=10**6,
    ).strip()


def paper_note(data: dict[str, Any]) -> str:
    return (
        f"---\n{yaml_document(data)}\n---\n\n"
        "This package is unread. A reader must replace this body with source-grounded notes "
        f"and cite claims with `[[{data['slug']}]] p.N` locators.\n\n"
        "## Summary\n\nUnread.\n\n"
        "## Findings and locators\n\nUnread.\n"
    )


def fetch(url: str, destination: Path) -> tuple[bool, dict[str, str]]:
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False, {"note": "invalid URL", "source_url": url, "http_status": ""}
    if scheme not in {"http", "https"}:
        return False, {"note": "unsupported URL scheme", "source_url": url, "http_status": ""}
    marker = "__LIT_CURL_METADATA__"
    command = [
        "curl", "-q", "--proto", "=http,https", "--proto-redir", "=http,https",
        "--location", "--max-redirs", "5", "--connect-timeout", "20",
        "--max-time", "180", "--fail", "--user-agent",
        "Mozilla/5.0 (compatible; Codex literature tool)", "--output", str(destination),
        "--write-out", f"\\n{marker}%{{url_effective}}\\t%{{http_code}}\\t%{{content_type}}\\t%{{size_download}}",
        url,
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        return False, {"note": f"curl failed: {exc}", "source_url": url, "http_status": ""}
    metadata = {"source_url": url, "http_status": "", "content_type": "", "bytes": "0"}
    if marker in result.stdout:
        values = result.stdout.rsplit(marker, 1)[1].strip().split("\t")
        if len(values) == 4:
            metadata.update(dict(zip(("source_url", "http_status", "content_type", "bytes"), values)))
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else f"exit {result.returncode}"
        metadata["note"] = f"curl failed (HTTP {metadata['http_status'] or 'unknown'}): {detail}"
        return False, metadata
    try:
        size = destination.stat().st_size
        prefix = read_prefix(destination)
    except OSError as exc:
        metadata["note"] = f"download read failed: {exc}"
        return False, metadata
    if size < 1024:
        metadata["note"] = f"rejected body smaller than 1 KiB ({size} bytes)"
        return False, metadata
    content_type = metadata["content_type"]
    try:
        extension = source_extension(prefix, content_type, metadata["source_url"])
    except ValueError:
        metadata["note"] = "invalid URL"
        return False, metadata
    if extension == "html":
        metadata["note"] = "rejected HTML body"
        return False, metadata
    try:
        claims_pdf = "pdf" in content_type.lower() or any(
            urlparse(item).path.lower().endswith(".pdf")
            for item in (url, metadata["source_url"])
        )
    except ValueError:
        metadata["note"] = "invalid URL"
        return False, metadata
    if claims_pdf and not prefix.startswith(b"%PDF-"):
        metadata["note"] = "rejected non-PDF body where PDF was expected"
        return False, metadata
    if not prefix.startswith(b"%PDF-"):
        metadata["note"] = f"non-PDF body ({content_type or 'unknown'}); no text extracted"
    return True, metadata


def package_metadata(candidate: dict[str, Any], decision_reason: str, slug: str, access: str,
                     fulltext_value: str, source: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "slug": slug,
        "title": text(candidate.get("title")) or "Untitled paper",
        "authors": text(candidate.get("authors")),
        "year": text(candidate.get("year")),
        "venue": text(candidate.get("venue")),
        "type": mapped_type(candidate.get("type")),
        "access": access,
        "fulltext": fulltext_value,
        "status": "unread",
        "added": datetime.now(timezone.utc).date().isoformat(),
        "candidate_id": text(candidate.get("id")),
        "relevance": decision_reason,
    }
    for key in ("doi", "arxiv", "url", "relation"):
        value = text(candidate.get(key))
        if key == "doi":
            value = normalize_doi(value)
        elif key == "arxiv":
            value = normalize_arxiv(value)
        if value:
            data[key] = value
    for key in ("source_url", "retrieved", "source_sha256", "retrieval_note"):
        if source.get(key):
            data[key] = source[key]
    return data


def unique_staging_path(root: Path, name: str) -> Path:
    path = root / f"{name}-{os.getpid()}"
    counter = 2
    while path.exists() or path.is_symlink():
        path = root / f"{name}-{os.getpid()}-{counter}"
        counter += 1
    return path


def remove_empty_staging(root: Path) -> None:
    try:
        root.rmdir()
    except OSError:
        pass


def build_package(kb: Path, candidate: dict[str, Any], reason: str, slug: str,
                  source_hashes: dict[str, str], promotion: bool = False) -> dict[str, Any]:
    staging_root = kb / ".staging"
    stage: Path | None = None
    source_info: dict[str, str] = {}
    access = "none"
    fulltext_value = "none"
    try:
        if os.path.islink(staging_root):
            raise ValueError("staging directory is a symlink")
        staging_root.mkdir(exist_ok=True)
        stage = unique_staging_path(staging_root, slug)
        stage.mkdir()
        temp_source = stage / "download"
        file_value = text(candidate.get("file"))
        if file_value:
            supplied = Path(file_value)
            if not supplied.is_absolute() or not supplied.is_file() or supplied.is_symlink():
                raise ValueError("user-supplied file must be an absolute regular-file path")
            shutil.copyfile(supplied, temp_source)
            if temp_source.stat().st_size == 0:
                raise ValueError("user-supplied file is empty")
            access = "user-supplied"
        elif text(candidate.get("oa_url")):
            retrieved = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            ok, fetched = fetch(text(candidate.get("oa_url")), temp_source)
            source_info.update(fetched)
            source_info["retrieved"] = retrieved
            if ok:
                access = "open"
                if fetched.get("note"):
                    source_info["retrieval_note"] = fetched["note"]
            else:
                source_info["retrieval_note"] = fetched.get("note", "retrieval failed")
                temp_source.unlink(missing_ok=True)
        else:
            source_info["retrieval_note"] = "no open url"

        if access != "none":
            prefix = read_prefix(temp_source)
            extension = source_extension(
                prefix, source_info.get("content_type", ""),
                source_info.get("source_url", file_value),
            )
            original = stage / f"original.{extension}"
            temp_source.rename(original)
            source_info["source_sha256"] = sha256(original)
            duplicate = source_hashes.get(source_info["source_sha256"])
            if duplicate and duplicate != slug:
                shutil.rmtree(stage)
                remove_empty_staging(staging_root)
                return {
                    "access": access, "fulltext": "none",
                    "source_url": source_info.get("source_url", ""),
                    "http_status": source_info.get("http_status", ""),
                    "sha256": source_info["source_sha256"],
                    "retrieval_reason": "",
                    "duplicate_source": duplicate,
                }
            if extension == "pdf":
                fulltext_value = extract_pdf(original, stage / "fulltext.md")
                if fulltext_value == "none":
                    source_info["retrieval_note"] = "PDF text extraction failed with pymupdf and pdftotext"
        metadata = package_metadata(candidate, reason, slug, access, fulltext_value, source_info)
        note_content = paper_note(metadata)
        (stage / "paper.md").write_text(note_content, encoding="utf-8")
        destination = kb / "papers" / slug
        if promotion:
            existing_content = (destination / "paper.md").read_text(encoding="utf-8")
            if note_body(existing_content) != note_body(note_content):
                print(f"WARNING: {slug}: replacing existing note body", file=sys.stderr)
            old = unique_staging_path(staging_root, f"{slug}-old")
            os.rename(destination, old)
            try:
                os.rename(stage, destination)
            except BaseException:
                os.rename(old, destination)
                raise
            try:
                shutil.rmtree(old)
            except OSError as exc:
                print(f"WARNING: could not remove old package {old}: {exc}", file=sys.stderr)
        else:
            os.rename(stage, destination)
        remove_empty_staging(staging_root)
        return {
            "access": access, "fulltext": fulltext_value,
            "source_url": source_info.get("source_url", ""),
            "http_status": source_info.get("http_status", ""),
            "sha256": source_info.get("source_sha256", ""),
            "retrieval_reason": source_info.get("retrieval_note", ""),
        }
    except BaseException:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        remove_empty_staging(staging_root)
        raise


def result_record(candidate_id: str, result: str, reason: str, slug: str = "", **fields: Any) -> dict[str, Any]:
    record = {
        "id": candidate_id, "result": result, "slug": slug,
        "access": "", "fulltext": "", "source_url": "", "http_status": "",
        "sha256": "", "reason": reason,
    }
    record.update(fields)
    return record


def command_ingest(args: argparse.Namespace) -> int:
    try:
        candidates = read_jsonl(args.candidates)
        decisions = read_jsonl(args.decisions)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    candidate_ids = [text(item.get("id")) for item in candidates]
    problems: list[str] = []
    if any(not item for item in candidate_ids):
        problems.append("candidates with missing IDs")
    duplicate_candidates = sorted({item for item in candidate_ids if candidate_ids.count(item) > 1})
    if duplicate_candidates:
        problems.append(f"duplicate candidate IDs: {', '.join(duplicate_candidates)}")
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        by_id[text(decision.get("id"))].append(decision)
    missing = [item for item in candidate_ids if len(by_id[item]) == 0]
    duplicates = [item for item in candidate_ids if len(by_id[item]) > 1]
    extras = sorted(set(by_id) - set(candidate_ids))
    invalid = []
    for item in candidate_ids:
        if len(by_id[item]) == 1:
            decision = by_id[item][0]
            if not isinstance(decision.get("accept"), bool) or not text(decision.get("reason")):
                invalid.append(item)
    if missing:
        problems.append(f"missing decisions: {', '.join(missing)}")
    if duplicates:
        problems.append(f"duplicate decisions: {', '.join(duplicates)}")
    if extras:
        problems.append(f"unknown decision IDs: {', '.join(extras)}")
    if invalid:
        problems.append(f"invalid decisions: {', '.join(invalid)}")
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    structure_errors = kb_structure_errors(args.kb)
    if structure_errors:
        for error in structure_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    papers = kb_papers(args.kb)
    doi_map, arxiv_map, _ = identity_maps(papers)
    hashes = {text(data.get("source_sha256")): slug for slug, data in papers.items() if text(data.get("source_sha256"))}
    occupied = set(papers)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    with args.results.open("a", encoding="utf-8") as output:
        for candidate in candidates:
            candidate_id = text(candidate.get("id"))
            decision = by_id[candidate_id][0]
            reason = text(decision.get("reason"))
            if not decision["accept"]:
                record = result_record(candidate_id, "rejected", reason)
            else:
                promotion_slug = text(candidate.get("slug"))
                if promotion_slug and not text(candidate.get("file")):
                    record = result_record(candidate_id, "error", "promotion requires a file", promotion_slug)
                    exit_code = 1
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                    print(f"{candidate_id} error {promotion_slug}: {record['reason']}")
                    continue
                promotion = False
                if promotion_slug:
                    existing = papers.get(promotion_slug)
                    if not existing:
                        record = result_record(candidate_id, "error", "promotion slug does not exist", promotion_slug)
                        exit_code = 1
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        print(f"{candidate_id} error {promotion_slug}: {record['reason']}")
                        continue
                    if text(existing.get("access")) != "none":
                        record = result_record(candidate_id, "error", "promotion target already has an original", promotion_slug)
                        exit_code = 1
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        print(f"{candidate_id} error {promotion_slug}: {record['reason']}")
                        continue
                    promotion = True
                    slug = promotion_slug
                    candidate_for_build = dict(existing)
                    for key in ("title", "authors", "year", "venue", "type", "doi", "arxiv", "url", "oa_url", "relation"):
                        if text(candidate.get(key)):
                            candidate_for_build[key] = candidate[key]
                    for key in ("id", "file", "slug"):
                        candidate_for_build[key] = candidate[key]
                    conflict = ""
                    for key, normalizer, owners in (
                        ("doi", normalize_doi, doi_map),
                        ("arxiv", normalize_arxiv, arxiv_map),
                    ):
                        identifier = normalizer(candidate_for_build.get(key))
                        owner = owners.get(identifier) if identifier else None
                        if owner and owner != slug:
                            conflict = f"promotion {key} is already owned by {owner}"
                            break
                    if conflict:
                        record = result_record(candidate_id, "error", conflict, promotion_slug)
                        exit_code = 1
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        print(f"{candidate_id} error {promotion_slug}: {record['reason']}")
                        continue
                else:
                    doi = normalize_doi(candidate.get("doi"))
                    arxiv = normalize_arxiv(candidate.get("arxiv"))
                    owner = (doi_map.get(doi) if doi else None) or (arxiv_map.get(arxiv) if arxiv else None)
                    if owner:
                        record = result_record(candidate_id, "already_in_kb", reason, owner,
                                               access=text(papers[owner].get("access")), fulltext=text(papers[owner].get("fulltext")))
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        print(f"{candidate_id} already_in_kb {owner}")
                        continue
                    slug = make_slug(candidate, occupied)
                    candidate_for_build = candidate
                try:
                    built = build_package(args.kb, candidate_for_build, reason, slug, hashes, promotion)
                    result_reason = built.pop("retrieval_reason") or reason
                    duplicate = built.pop("duplicate_source", "")
                    digest = built["sha256"]
                    if duplicate:
                        if not promotion:
                            occupied.discard(slug)
                        record = result_record(candidate_id, f"duplicate_source_of {duplicate}", result_reason, duplicate, **built)
                    else:
                        result_value = "promoted" if promotion else "created"
                        record = result_record(candidate_id, result_value, result_reason, slug, **built)
                        data = frontmatter(args.kb / "papers" / slug / "paper.md")
                        papers[slug] = data
                        if promotion:
                            for owners in (doi_map, arxiv_map, hashes):
                                for identifier, owner in list(owners.items()):
                                    if owner == slug:
                                        del owners[identifier]
                        doi = normalize_doi(data.get("doi"))
                        arxiv = normalize_arxiv(data.get("arxiv"))
                        if doi:
                            doi_map[doi] = slug
                        if arxiv:
                            arxiv_map[arxiv] = slug
                        if digest:
                            hashes[digest] = slug
                except Exception as exc:
                    if not promotion:
                        occupied.discard(slug)
                    record = result_record(candidate_id, "error", str(exc), slug)
                    exit_code = 1
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record["result"].startswith("duplicate_source_of "):
                print(f"{candidate_id} {record['result']}: {record['reason']}")
            else:
                print(f"{candidate_id} {record['result']} {record['slug'] or '-'}: {record['reason']}")
    return exit_code


def bib_escape(value: Any) -> str:
    clean = text(value).replace("\n", " ")
    return re.sub(r"([&%#_])", r"\\\1", clean)


def generate_derived(kb: Path, papers: dict[str, dict[str, Any]]) -> None:
    groups = [
        ("Full text", lambda data: text(data.get("fulltext")) != "none"),
        ("Artifacts without text", lambda data: text(data.get("access")) != "none" and text(data.get("fulltext")) == "none"),
        ("Not retrieved", lambda data: text(data.get("access")) == "none"),
    ]
    lines = ["# Literature index", ""]
    for heading, predicate in groups:
        lines.extend([f"## {heading}", ""])
        for slug, data in sorted(papers.items()):
            if predicate(data):
                lines.append(f"- [[{slug}]] — {text(data.get('title'))} — {text(data.get('authors'))} ({text(data.get('year'))}), {text(data.get('venue'))}.")
        lines.append("")
    (kb / "index.md").write_text("\n".join(lines), encoding="utf-8")

    entries: list[str] = []
    kinds = {
        "article": "article", "proceedings": "inproceedings", "chapter": "incollection",
        "book": "book", "thesis": "phdthesis",
    }
    for slug, data in sorted(papers.items()):
        kind = kinds.get(text(data.get("type")), "misc")
        fields: list[tuple[str, str]] = []
        title_value = bib_escape(data.get("title"))
        if title_value:
            fields.append(("title", "{" + title_value + "}"))
        if text(data.get("authors")):
            fields.append(("author", bib_escape(data.get("authors"))))
        if text(data.get("year")):
            fields.append(("year", bib_escape(data.get("year"))))
        venue = bib_escape(data.get("venue"))
        if venue and kind == "article":
            fields.append(("journal", venue))
        elif venue and kind == "inproceedings":
            fields.append(("booktitle", venue))
        doi = normalize_doi(data.get("doi"))
        arxiv = normalize_arxiv(data.get("arxiv"))
        if doi:
            fields.append(("doi", doi))
        if arxiv:
            fields.extend((("eprint", arxiv), ("archiveprefix", "arXiv")))
        if text(data.get("url")):
            fields.append(("url", text(data.get("url"))))
        entry = [f"@{kind}{{{slug},"] + [f"  {key} = {{{value}}}," for key, value in fields] + ["}"]
        entries.append("\n".join(entry))
    (kb / "references.bib").write_text("\n\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")


def check_git_ignore(kb: Path) -> bool:
    try:
        root = subprocess.run(
            ["git", "-C", str(kb), "rev-parse", "--show-toplevel"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        ).stdout.strip()
        result = subprocess.run(
            ["git", "-C", root, "check-ignore", "--quiet", str(kb / "index.md")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def command_check(args: argparse.Namespace) -> int:
    kb = args.kb.absolute()
    errors: list[str] = []
    warnings: list[str] = []
    papers: dict[str, dict[str, Any]] = {}
    page_counts: dict[str, int] = {}
    doi_owner: dict[str, str] = {}
    arxiv_owner: dict[str, str] = {}
    structure_errors = kb_structure_errors(kb)
    if structure_errors:
        for error in structure_errors:
            print(f"ERROR: {error}")
        print("WARNING: unread packages: 0")
        print(f"KB_CHECK=errors={len(structure_errors)}")
        print("UNREAD=0")
        return 1
    allowed_links = {"AGENTS.md": "README.md", "CLAUDE.md": "README.md"}
    for path in sorted(kb.rglob("*")):
        if path.is_symlink():
            relative = str(path.relative_to(kb))
            if relative not in allowed_links or os.readlink(path) != allowed_links[relative]:
                errors.append(f"{relative}: symlinks are not allowed")
    staging = kb / ".staging"
    if staging.is_dir():
        for entry in staging.iterdir():
            errors.append(f".staging/{entry.name}: leftover staging entry")

    paper_root = kb / "papers"
    for directory in sorted(item for item in paper_root.iterdir() if item.is_dir() and not item.is_symlink()):
            slug = directory.name
            note = directory / "paper.md"
            if not note.is_file() or note.is_symlink():
                errors.append(f"papers/{slug}/paper.md: regular file is missing")
                continue
            try:
                data = frontmatter(note)
            except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
                errors.append(f"papers/{slug}/paper.md: {exc}")
                continue
            papers[slug] = data
            missing = sorted(
                {key for key in REQUIRED_PRESENT if key not in data}
                | {key for key in REQUIRED_NONEMPTY if not text(data.get(key))}
            )
            if missing:
                errors.append(f"papers/{slug}/paper.md: missing required keys: {', '.join(missing)}")
            if text(data.get("slug")) != slug:
                errors.append(f"papers/{slug}/paper.md: slug does not match directory")
            for key, allowed in (("type", TYPES), ("access", ACCESSES), ("fulltext", FULLTEXTS), ("status", STATUSES)):
                if text(data.get(key)) not in allowed:
                    errors.append(f"papers/{slug}/paper.md: invalid {key}: {text(data.get(key)) or '<empty>'}")
            for key, normalizer, owners in (("doi", normalize_doi, doi_owner), ("arxiv", normalize_arxiv, arxiv_owner)):
                value = normalizer(data.get(key))
                if value:
                    if value in owners:
                        errors.append(f"papers/{slug}/paper.md: duplicate {key} also used by {owners[value]}")
                    else:
                        owners[value] = slug

            access = text(data.get("access"))
            fulltext_value = text(data.get("fulltext"))
            matches = list(directory.glob("original.*"))
            originals = [item for item in matches if item.is_file() and not item.is_symlink()]
            for item in matches:
                if item not in originals:
                    errors.append(f"papers/{slug}/{item.name}: original must be a regular file")
            fulltext_path = directory / "fulltext.md"
            if access == "none" and (matches or fulltext_path.exists() or fulltext_path.is_symlink()):
                errors.append(f"papers/{slug}: access none package contains source artifacts")
            if access in {"open", "user-supplied"} and len(originals) != 1:
                errors.append(f"papers/{slug}: access {access} requires exactly one original")
            if len(originals) > 1:
                errors.append(f"papers/{slug}: multiple originals")
            if originals:
                original = originals[0]
                try:
                    size = original.stat().st_size
                    actual_hash = sha256(original)
                except OSError as exc:
                    errors.append(f"papers/{slug}/{original.name}: {exc}")
                else:
                    if size == 0:
                        errors.append(f"papers/{slug}/{original.name}: original is empty")
                    if original.name == "original.pdf" and not read_prefix(original, 5).startswith(b"%PDF-"):
                        errors.append(f"papers/{slug}/original.pdf: PDF signature is missing")
                    if actual_hash != text(data.get("source_sha256")).lower():
                        errors.append(f"papers/{slug}: source_sha256 mismatch")
            if fulltext_value == "none" and (fulltext_path.exists() or fulltext_path.is_symlink()):
                errors.append(f"papers/{slug}: fulltext none but fulltext.md is present")
            elif fulltext_value != "none" and not fulltext_path.is_file():
                errors.append(f"papers/{slug}: fulltext {fulltext_value} but fulltext.md is missing")
            if fulltext_path.is_file() and not fulltext_path.is_symlink():
                markers = [int(value) for value in PAGE_RE.findall(fulltext_path.read_text(encoding="utf-8", errors="replace"))]
                if not markers:
                    errors.append(f"papers/{slug}/fulltext.md: no page markers")
                elif markers != list(range(1, len(markers) + 1)):
                    errors.append(f"papers/{slug}/fulltext.md: page markers are not consecutive")
                page_counts[slug] = len(markers)
            else:
                page_counts[slug] = 0

    documents: list[Path] = []
    for slug in papers:
        documents.append(kb / "papers" / slug / "paper.md")
    for folder in ("topics", "runs"):
        root = kb / folder
        if not root.is_symlink() and root.is_dir():
            documents.extend(path for path in root.glob("*.md") if path.is_file() and not path.is_symlink())
    for document in documents:
        relative = document.relative_to(kb)
        body = document.read_text(encoding="utf-8", errors="replace")
        for match in REF_RE.finditer(body):
            slug, page = match.groups()
            if slug not in papers:
                errors.append(f"{relative}: [[{slug}]] does not resolve")
            elif page and (int(page) < 1 or int(page) > page_counts.get(slug, 0)):
                errors.append(f"{relative}: [[{slug}]] p.{page} exceeds {page_counts.get(slug, 0)} pages")

    for slug, data in papers.items():
        if text(data.get("status")) != "read":
            continue
        body = (kb / "papers" / slug / "paper.md").read_text(encoding="utf-8", errors="replace")
        located_pages = {
            int(page) for target, page in REF_RE.findall(body)
            if target == slug and page
        }
        if len(located_pages) < 2 or not any(page > 1 for page in located_pages):
            warnings.append(f"{slug}: status read with fewer than two locators on distinct pages")

    unread = sum(text(data.get("status")) == "unread" for data in papers.values())
    if not errors:
        generate_derived(kb, papers)
    for error in errors:
        print(f"ERROR: {error}")
    print(f"WARNING: unread packages: {unread}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if kb.is_dir() and check_git_ignore(kb):
        print("WARNING: index.md is ignored by git")
    if errors:
        print(f"KB_CHECK=errors={len(errors)}")
    else:
        print("KB_CHECK=ok")
    print(f"UNREAD={unread}")
    return 1 if errors else 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="lit.py", description="Maintain a literature knowledge base.")
    commands = result.add_subparsers(dest="command", required=True, help="operation to run")
    init_parser = commands.add_parser(
        "init", help="initialize a project knowledge base",
        description="Initialize a project knowledge base.",
    )
    init_parser.add_argument("project", type=Path, help="project directory")
    init_parser.set_defaults(function=command_init)
    dedup_parser = commands.add_parser(
        "dedup", help="deduplicate researcher lane files",
        description="Deduplicate researcher lane files.",
    )
    dedup_parser.add_argument("--kb", type=Path, required=True, help="knowledge-base directory")
    dedup_parser.add_argument("--prefix", required=True, help="stable candidate ID prefix")
    dedup_parser.add_argument("--out", type=Path, required=True, help="output candidates JSON Lines file")
    dedup_parser.add_argument("lanes", type=Path, nargs="+", help="researcher lane JSON Lines files")
    dedup_parser.set_defaults(function=command_dedup)
    ingest_parser = commands.add_parser(
        "ingest", help="ingest adjudicated candidates",
        description="Ingest adjudicated candidates.",
    )
    ingest_parser.add_argument("--kb", type=Path, required=True, help="knowledge-base directory")
    ingest_parser.add_argument("--candidates", type=Path, required=True, help="deduplicated candidates JSON Lines file")
    ingest_parser.add_argument("--decisions", type=Path, required=True, help="adjudication decisions JSON Lines file")
    ingest_parser.add_argument("--results", type=Path, required=True, help="append-only results JSON Lines file")
    ingest_parser.set_defaults(function=command_ingest)
    check_parser = commands.add_parser(
        "check", help="validate and regenerate derived files",
        description="Validate the knowledge base and regenerate derived files.",
    )
    check_parser.add_argument("kb", type=Path, help="knowledge-base directory")
    check_parser.set_defaults(function=command_check)
    return result


def main(argv: list[str] | None = None) -> int:
    values = sys.argv[1:] if argv is None else argv
    if values and values[0] == "_extract-pymupdf":
        if len(values) != 3:
            return 2
        return pymupdf_worker(Path(values[1]), Path(values[2]))
    args = parser().parse_args(values)
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())

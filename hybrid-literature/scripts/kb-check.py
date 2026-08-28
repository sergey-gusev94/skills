#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.2"]
# ///
"""Validate a project literature knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REQUIRED = {"slug", "title", "authors", "year", "venue", "type", "access", "added"}
ACCESS_VALUES = {"open", "user-supplied", "abstract-only"}
EXTRACTION_VALUES = {"good", "basic", "failed"}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
WIKI_RE = re.compile(r"\[\[([^]]+)\]\]")
LINK_RE = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
DOI_RE = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)
OLD_ARXIV = (
    r"(?:acc-phys|adap-org|alg-geom|ao-sci|astro-ph|atom-ph|bayes-an|chao-dyn|"
    r"chem-ph|cmp-lg|comp-gas|cond-mat|cs|dg-ga|econ|eess|funct-an|gr-qc|"
    r"hep-ex|hep-lat|hep-ph|hep-th|math|math-ph|mtrl-th|nlin|nucl-ex|nucl-th|"
    r"patt-sol|physics|plasm-ph|q-alg|q-bio|q-fin|quant-ph|solv-int|stat|"
    r"supr-con)(?:\.[A-Za-z]{2})?/\d{7}(?:v\d+)?"
)
ARXIV_RE = re.compile(
    rf"(?:\barxiv:\s*((?:\d{{4}}\.\d{{4,5}}(?:v\d+)?)|(?:{OLD_ARXIV}))\b|"
    rf"(?<![\w/])(\d{{4}}\.\d{{4,5}}(?:v\d+)?)(?![\w/])|"
    rf"(?<![\w/])({OLD_ARXIV})(?![\w/]))",
    re.IGNORECASE,
)


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError("missing YAML frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def value(data: dict[str, Any], key: str) -> str:
    item = data.get(key)
    return "" if item is None else str(item).strip()


def identifier_value(data: dict[str, Any], key: str) -> str:
    raw = value(data, key)
    return "" if raw.lower() == "unknown" else raw


def normalize_doi(raw: str) -> str:
    lowered = raw.lower().strip()
    normalized = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", lowered).rstrip(".,;:")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while normalized.endswith(closing) and normalized.count(closing) > normalized.count(opening):
            normalized = normalized[:-1].rstrip(".,;:")
    return normalized


def normalize_arxiv(raw: str) -> str:
    stripped = raw.lower().removeprefix("arxiv:").strip()
    return re.sub(r"v\d+$", "", stripped)


def arxiv_in(text: str) -> str:
    match = ARXIV_RE.search(text)
    if not match:
        return ""
    return next(group for group in match.groups() if group)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wiki_refs(text: str, source: str, findings: list[str]) -> list[str]:
    valid = []
    for match in WIKI_RE.finditer(text):
        raw = match.group(1)
        if not SLUG_RE.fullmatch(raw):
            findings.append(f"{source}: malformed wiki reference [[{raw}]]")
        else:
            valid.append(raw)
    return valid


def missing_entries(path: Path) -> tuple[set[str], set[str], set[str], list[str]]:
    slugs: list[str] = []
    dois: list[str] = []
    arxivs: list[str] = []
    errors: list[str] = []
    if not path.is_file():
        return set(), set(), set(), ["missing.md: file is missing"]
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.startswith("- "):
            continue
        refs = [raw for raw in WIKI_RE.findall(line) if SLUG_RE.fullmatch(raw)]
        if not refs:
            errors.append(f"missing.md:{number}: entry has no [[slug]]")
            continue
        slug = refs[0]
        slugs.append(slug)
        remainder = WIKI_RE.sub("", line, count=1)
        if not re.search(r"[A-Za-z]{2}", remainder):
            errors.append(f"missing.md:{number}: entry has no title")
        if not re.search(r"\[[^]]+\]\(https?://[^)]+\)", line):
            errors.append(f"missing.md:{number}: entry has no landing link")
        doi = DOI_RE.search(line)
        if doi:
            dois.append(normalize_doi(doi.group(0)))
        arxiv = arxiv_in(line)
        if arxiv:
            arxivs.append(normalize_arxiv(arxiv))
    for label, items in (("slug", slugs), ("DOI", dois), ("arXiv ID", arxivs)):
        for item, count in sorted(Counter(items).items()):
            if count > 1:
                errors.append(f"missing.md: duplicate {label} {item} appears {count} times")
    return set(slugs), set(dois), set(arxivs), errors


def emit_bib(kb: Path, papers: dict[str, dict[str, Any]]) -> None:
    entries = []
    for slug, data in sorted(papers.items()):
        authors = data.get("authors", "")
        if isinstance(authors, list):
            authors = " and ".join(str(author) for author in authors)
        fields = {
            "title": value(data, "title"),
            "author": str(authors),
            "year": value(data, "year"),
            "journal": value(data, "venue"),
            "doi": identifier_value(data, "doi"),
            "eprint": identifier_value(data, "arxiv"),
            "url": identifier_value(data, "url"),
        }
        lines = [f"@misc{{{slug},"]
        for key, field in fields.items():
            if field:
                clean = field.replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
                lines.append(f"  {key} = {{{clean}}},")
        lines.append("}")
        entries.append("\n".join(lines))
    (kb / "references.bib").write_text("\n\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(usage="kb-check.py <kb-path> [--emit-bib]")
    parser.add_argument("kb_path", type=Path)
    parser.add_argument("--emit-bib", action="store_true")
    args = parser.parse_args()
    kb = args.kb_path.resolve()
    findings: list[str] = []
    papers: dict[str, dict[str, Any]] = {}
    doi_owner: dict[str, str] = {}
    arxiv_owner: dict[str, str] = {}

    if not kb.is_dir():
        findings.append(f"{kb}: knowledge-base directory is missing")
    else:
        for link in sorted(path for path in kb.rglob("*") if path.is_symlink()):
            try:
                target = link.resolve(strict=False)
                target.relative_to(kb)
            except ValueError:
                findings.append(f"{link.relative_to(kb)}: symlink resolves outside the knowledge base")
            except (OSError, RuntimeError) as exc:
                findings.append(f"{link.relative_to(kb)}: cannot resolve symlink: {exc}")
    for required_path in ("README.md", "papers", "index.md", "missing.md"):
        path = kb / required_path
        expected = path.is_dir() if required_path == "papers" else path.is_file()
        if not expected:
            findings.append(f"{required_path}: required knowledge-base structure is missing")

    paper_root = kb / "papers"
    for directory in sorted(path for path in paper_root.glob("*") if path.is_dir() and not path.is_symlink()):
        slug = directory.name
        note = directory / "paper.md"
        if not note.is_file():
            findings.append(f"papers/{slug}: paper.md is missing")
            continue
        try:
            data = frontmatter(note)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
            findings.append(f"papers/{slug}/paper.md: {exc}")
            continue
        papers[slug] = data
        absent = sorted(key for key in REQUIRED if not value(data, key))
        if absent:
            findings.append(f"papers/{slug}/paper.md: missing required keys: {', '.join(absent)}")
        if value(data, "slug") != slug:
            findings.append(f"papers/{slug}/paper.md: frontmatter slug does not match directory")
        if not any(identifier_value(data, key) for key in ("doi", "arxiv", "url")):
            findings.append(f"papers/{slug}/paper.md: DOI, arXiv ID, or URL is required")
        for key, normalizer, owners in (("doi", normalize_doi, doi_owner), ("arxiv", normalize_arxiv, arxiv_owner)):
            raw = identifier_value(data, key)
            if raw:
                normalized = normalizer(raw)
                if normalized in owners:
                    findings.append(f"papers/{slug}/paper.md: duplicate {key} also used by {owners[normalized]}")
                else:
                    owners[normalized] = slug

        access = value(data, "access").lower()
        extraction = value(data, "extraction").lower()
        if access not in ACCESS_VALUES:
            findings.append(f"papers/{slug}/paper.md: unknown access value: {access or '<empty>'}")
        if extraction and extraction not in EXTRACTION_VALUES:
            findings.append(f"papers/{slug}/paper.md: unknown extraction value: {extraction}")
        original_matches = sorted(directory.glob("original.*"))
        originals = []
        for original in original_matches:
            if original.is_symlink() or not original.is_file():
                findings.append(f"papers/{slug}/{original.name}: original must be a regular file")
            else:
                originals.append(original)
        if len(originals) > 1:
            findings.append(f"papers/{slug}: multiple original files; expected exactly one")
        fulltext = directory / "fulltext.md"
        if access == "abstract-only" and (original_matches or fulltext.exists() or fulltext.is_symlink()):
            findings.append(f"papers/{slug}: abstract-only package must not contain original or fulltext files")
        if access != "abstract-only" and not originals:
            findings.append(f"papers/{slug}: original file is required for access={access or 'unknown'}")
        if originals:
            if not value(data, "source_sha256") or not extraction:
                findings.append(f"papers/{slug}/paper.md: source_sha256 and extraction are required with an original")
            else:
                try:
                    actual_sha256 = file_sha256(originals[0])
                except OSError as exc:
                    findings.append(f"papers/{slug}/{originals[0].name}: cannot compute source_sha256: {exc}")
                else:
                    if actual_sha256 != value(data, "source_sha256").lower():
                        findings.append(f"papers/{slug}: source_sha256 does not match {originals[0].name}")
        if extraction == "failed" and (fulltext.exists() or fulltext.is_symlink()):
            findings.append(f"papers/{slug}: extraction failed but fulltext.md is present")
        if access in {"open", "user-supplied"} and extraction != "failed":
            if not fulltext.is_file():
                findings.append(f"papers/{slug}: fulltext.md is required for access={access}")
            else:
                text = fulltext.read_text(encoding="utf-8", errors="replace")
                pages = len(re.findall(r"<!-- page \d+ -->", text))
                if pages == 0:
                    findings.append(f"papers/{slug}/fulltext.md: no page markers")
                elif len(text.encode("utf-8")) < 200 or len(text.encode("utf-8")) / pages < 80:
                    findings.append(f"papers/{slug}/fulltext.md: unusually little text per page")

    missing_slugs, missing_dois, missing_arxivs, missing_errors = missing_entries(kb / "missing.md")
    findings.extend(missing_errors)
    for slug in sorted(missing_slugs & papers.keys()):
        findings.append(f"missing.md: {slug} is already ingested")
    for doi in sorted(missing_dois & doi_owner.keys()):
        findings.append(f"missing.md: DOI {doi} is already ingested as {doi_owner[doi]}")
    for arxiv in sorted(missing_arxivs & arxiv_owner.keys()):
        findings.append(f"missing.md: arXiv {arxiv} is already ingested as {arxiv_owner[arxiv]}")

    index = kb / "index.md"
    index_text = index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""
    index_refs = wiki_refs(index_text, "index.md", findings)
    for slug in sorted(set(index_refs)):
        if slug not in papers and slug not in missing_slugs:
            findings.append(f"index.md: [[{slug}]] resolves to neither a paper nor missing.md")
    for slug in sorted(papers):
        count = index_refs.count(slug)
        if count != 1:
            findings.append(f"index.md: [[{slug}]] occurs {count} times; expected exactly once")

    documents = ([index] if index.is_file() else [])
    documents += sorted(
        path for path in (kb / "topics").glob("*.md") if path.is_file() and not path.is_symlink()
    )
    documents += sorted(
        path for path in (kb / "runs").glob("*.md") if path.is_file() and not path.is_symlink()
    )
    for document in documents:
        text = document.read_text(encoding="utf-8", errors="replace")
        if document != index:
            for slug in wiki_refs(text, str(document.relative_to(kb)), findings):
                if slug not in papers and slug not in missing_slugs:
                    findings.append(f"{document.relative_to(kb)}: [[{slug}]] does not resolve")
        for target in LINK_RE.findall(text):
            target = target.strip().split("#", 1)[0]
            if not target or re.match(r"(?:https?|mailto):", target):
                continue
            if not (document.parent / target).resolve().exists():
                findings.append(f"{document.relative_to(kb)}: relative link does not resolve: {target}")

    if args.emit_bib and kb.is_dir():
        emit_bib(kb, papers)
    for finding in findings:
        print(f"ERROR: {finding}")
    if findings:
        print(f"KB_CHECK=errors={len(findings)}")
        return 1
    print("KB_CHECK=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

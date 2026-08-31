# Run: uv run --with pymupdf4llm==1.28.2 --with pyyaml==6.0.2 python -B -m unittest discover -s literature/tests -v

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import pymupdf


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lit.py"
SPEC = importlib.util.spec_from_file_location("lit_tool", SCRIPT)
assert SPEC and SPEC.loader
lit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lit)


class SourceServer:
    def __init__(self, pdf: bytes):
        self.pdf = pdf
        source = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/fake.pdf":
                    body = b"<html><body>landing page</body></html>" + b" " * 1200
                    content_type = "application/pdf"
                elif self.path == "/html":
                    body = b"<!doctype html><html><body>landing page</body></html>" + b" " * 1200
                    content_type = "text/html; charset=utf-8"
                elif self.path == "/xhtml":
                    body = b"\xef\xbb\xbf  <?xml version=\"1.0\"?><html><body>landing page</body></html>" + b" " * 1200
                    content_type = "application/xhtml+xml"
                elif self.path == "/mislabelled":
                    body = source.pdf
                    content_type = "text/html"
                elif self.path == "/artifact":
                    body = b"artifact data\n" * 100
                    content_type = "application/octet-stream"
                elif self.path == "/text.txt":
                    body = b"References [1] Smith 2020.\n" * 50
                    content_type = "text/plain"
                elif self.path == "/zero.pdf":
                    body = b""
                    content_type = "application/pdf"
                else:
                    body = source.pdf
                    content_type = "application/pdf"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class LocalServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler]):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class LitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root)}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["init", str(self.project)]), 0)
        self.kb = self.project / "literature"
        self.pdf = self.root / "source.pdf"
        document = pymupdf.open()
        for page_number in (1, 2):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {page_number} has a concrete result: {page_number * 10}.")
        document.save(self.pdf)
        document.close()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_jsonl(self, name: str, records: list[dict[str, object]]) -> Path:
        path = self.root / name
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path

    def ingest(self, candidates: list[dict[str, object]], decisions: list[dict[str, object]] | None = None) -> tuple[int, list[dict[str, object]]]:
        if decisions is None:
            decisions = [{"id": item["id"], "accept": True, "reason": "Needed by this project."} for item in candidates]
        candidate_path = self.write_jsonl("candidates.jsonl", candidates)
        decision_path = self.write_jsonl("decisions.jsonl", decisions)
        results = self.root / "results.jsonl"
        results.unlink(missing_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            status = lit.main([
                "ingest", "--kb", str(self.kb), "--candidates", str(candidate_path),
                "--decisions", str(decision_path), "--results", str(results),
            ])
        records = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
        return status, records

    def packages(self) -> list[Path]:
        return sorted(path for path in (self.kb / "papers").iterdir() if path.is_dir())

    def assert_failed_retrieval(self, path: str, note_fragment: str) -> None:
        with SourceServer(self.pdf.read_bytes()) as server:
            status, results = self.ingest([{
                "id": "R-N001", "title": "Claimed PDF", "authors": "Doe, Jane",
                "year": 2024, "oa_url": server + path,
            }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["access"], "none")
        self.assertIn(note_fragment, data["retrieval_note"])
        self.assertEqual([item.name for item in package.iterdir()], ["paper.md"])
        self.assertFalse((self.kb / ".staging").exists())
        self.assertEqual(results[0]["access"], "none")

    def test_pdf_claimed_html_creates_complete_unretrieved_package(self) -> None:
        self.assert_failed_retrieval("/fake.pdf", "HTML body")

    def test_zero_byte_download_creates_complete_unretrieved_package(self) -> None:
        self.assert_failed_retrieval("/zero.pdf", "smaller than 1 KiB")

    def test_html_without_pdf_suffix_is_rejected(self) -> None:
        self.assert_failed_retrieval("/html", "rejected HTML body")

    def test_xhtml_with_xml_prolog_is_rejected(self) -> None:
        self.assert_failed_retrieval("/xhtml", "rejected HTML body")

    def test_pdf_magic_beats_html_content_type(self) -> None:
        with SourceServer(self.pdf.read_bytes()) as server:
            status, _ = self.ingest([
                {"id": "R-N001", "title": "Mislabelled PDF", "oa_url": server + "/mislabelled"}
            ])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["access"], "open")
        self.assertEqual(data["fulltext"], "pymupdf4llm")
        self.assertTrue((package / "original.pdf").is_file())

    def test_non_web_oa_url_is_rejected_without_copying(self) -> None:
        status, _ = self.ingest([{"id": "R-N001", "title": "Local URL", "oa_url": self.pdf.as_uri()}])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        self.assertEqual(lit.frontmatter(package / "paper.md")["retrieval_note"], "unsupported URL scheme")
        self.assertEqual([item.name for item in package.iterdir()], ["paper.md"])

    def test_invalid_url_is_a_retrieval_failure(self) -> None:
        status, _ = self.ingest([{"id": "R-N001", "title": "Invalid URL", "oa_url": "http://["}])
        self.assertEqual(status, 0)
        self.assertEqual(lit.frontmatter(self.packages()[0] / "paper.md")["retrieval_note"], "invalid URL")

    def test_non_pdf_download_is_kept_as_an_artifact(self) -> None:
        with SourceServer(self.pdf.read_bytes()) as server:
            status, _ = self.ingest([{"id": "R-N001", "title": "Artifact", "oa_url": server + "/artifact"}])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["access"], "open")
        self.assertEqual(data["fulltext"], "none")
        self.assertEqual(data["retrieval_note"], "non-PDF body (application/octet-stream); no text extracted")
        self.assertEqual(len(list(package.glob("original.*"))), 1)

    def test_empty_bibliographic_fields_are_valid(self) -> None:
        status, _ = self.ingest([{"id": "R-N001", "title": "Minimal Standard", "type": "standard"}])
        self.assertEqual(status, 0)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertIn("KB_CHECK=ok", stdout.getvalue())
        self.assertIn("Minimal Standard", (self.kb / "index.md").read_text(encoding="utf-8"))
        self.assertIn("Minimal Standard", (self.kb / "references.bib").read_text(encoding="utf-8"))

    def test_duplicate_bytes_and_existing_doi_do_not_create_packages(self) -> None:
        candidates = [
            {"id": "R-N001", "title": "First", "authors": "Jane Doe", "year": 2020, "doi": "10.1/same", "file": str(self.pdf)},
            {"id": "R-N002", "title": "Second", "authors": "John Roe", "year": 2021, "doi": "10.1/other", "file": str(self.pdf)},
            {"id": "R-N003", "title": "Third", "authors": "Max Poe", "year": 2022, "doi": "https://doi.org/10.1/SAME.", "file": str(self.pdf)},
        ]
        status, results = self.ingest(candidates)
        self.assertEqual(status, 0)
        self.assertEqual(len(self.packages()), 1)
        self.assertEqual(results[0]["result"], "created")
        self.assertTrue(results[1]["result"].startswith("duplicate_source_of "))
        self.assertEqual(results[2]["result"], "already_in_kb")

    def test_pymupdf_timeout_falls_back_with_one_marker_per_page(self) -> None:
        with mock.patch.dict(os.environ, {"LIT_PYMUPDF_TIMEOUT": "0.01", "LIT_TEST_PYMUPDF_DELAY": "0.2"}):
            status, _ = self.ingest([{
                "id": "R-N001", "title": "Fallback", "authors": "Doe, Jane",
                "year": 2020, "file": str(self.pdf),
            }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["fulltext"], "pdftotext")
        self.assertIn("timeout after 0.01s; used pdftotext", data["extraction_note"])
        self.assertEqual(len(lit.PAGE_RE.findall((package / "fulltext.md").read_text(encoding="utf-8"))), 2)

    def test_extracted_marker_shaped_text_is_neutralized(self) -> None:
        source = self.root / "marker.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "First page")
        document.new_page().insert_text((72, 72), "Literal <!-- page 7 --> text")
        document.save(source)
        document.close()
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Marker Text", "authors": "Doe, Jane",
            "year": 2024, "file": str(source),
        }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        fulltext = (package / "fulltext.md").read_text(encoding="utf-8")
        self.assertEqual(lit.PAGE_RE.findall(fulltext), ["1", "2"])
        self.assertIn("<!- - page 7 -->", fulltext)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        note = package / "paper.md"
        note.write_text(note.read_text(encoding="utf-8") + f"\n[[{package.name}]] p.7\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("p.7 exceeds 2 pages", stdout.getvalue())

    def test_check_rejects_bad_locator_and_bad_pdf_and_generates_files(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Checked", "authors": "Jane Doe",
            "year": 2020, "type": "journal article", "venue": "A & B",
            "doi": "10.1/check", "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertIn("KB_CHECK=ok", stdout.getvalue())
        clean_index = (self.kb / "index.md").read_text(encoding="utf-8")
        clean_bib = (self.kb / "references.bib").read_text(encoding="utf-8")
        self.assertIn(f"[[{package.name}]]", clean_index)
        self.assertIn("@article", clean_bib)
        self.assertIn("title = {{Checked}}", clean_bib)
        self.assertIn(r"journal = {A \& B}", clean_bib)
        self.assertIn('\nslug: "', (package / "paper.md").read_text(encoding="utf-8"))

        note = package / "paper.md"
        note.write_text(note.read_text(encoding="utf-8") + f"\n[[{package.name}]] p.3\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("exceeds 2 pages", stdout.getvalue())
        self.assertEqual((self.kb / "index.md").read_text(encoding="utf-8"), clean_index)
        self.assertEqual((self.kb / "references.bib").read_text(encoding="utf-8"), clean_bib)

        note.write_text(note.read_text(encoding="utf-8").replace(f"[[{package.name}]] p.3", ""), encoding="utf-8")
        fulltext = package / "fulltext.md"
        valid_fulltext = fulltext.read_text(encoding="utf-8")
        fulltext.write_text(valid_fulltext.replace("<!-- page 2 -->", "<!-- page 3 -->"), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("page markers are not consecutive", stdout.getvalue())
        self.assertEqual((self.kb / "index.md").read_text(encoding="utf-8"), clean_index)
        self.assertEqual((self.kb / "references.bib").read_text(encoding="utf-8"), clean_bib)
        fulltext.write_text(valid_fulltext, encoding="utf-8")

        original = package / "original.pdf"
        original.write_bytes(b"")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("original is empty", stdout.getvalue())
        self.assertIn("PDF signature is missing", stdout.getvalue())
        self.assertEqual((self.kb / "index.md").read_text(encoding="utf-8"), clean_index)
        self.assertEqual((self.kb / "references.bib").read_text(encoding="utf-8"), clean_bib)

        original.write_bytes(b"not a pdf")
        data = lit.frontmatter(note)
        data["source_sha256"] = hashlib.sha256(b"not a pdf").hexdigest()
        body = note.read_text(encoding="utf-8").split("---", 2)[2]
        note.write_text(f"---\n{lit.yaml_document(data)}\n---{body}", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("PDF signature is missing", stdout.getvalue())
        self.assertEqual((self.kb / "index.md").read_text(encoding="utf-8"), clean_index)
        self.assertEqual((self.kb / "references.bib").read_text(encoding="utf-8"), clean_bib)

    def test_promotion_preserves_identity_and_passes_check(self) -> None:
        status, results = self.ingest([{
            "id": "R-N001", "title": "Promoted Standard", "authors": "Doe, Jane",
            "year": 2024, "type": "standard", "doi": "10.1/promote",
            "arxiv": "2301.12345v2.",
        }])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        note = self.kb / "papers" / slug / "paper.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nPrior note.\n", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status, results = self.ingest([{"id": "R-N002", "slug": slug, "file": str(self.pdf)}])
        self.assertEqual(status, 0)
        self.assertEqual(results[0]["result"], "promoted")
        self.assertIn(f"WARNING: {slug}: replacing existing note body", stderr.getvalue())
        package = self.kb / "papers" / slug
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["access"], "user-supplied")
        self.assertNotEqual(data["fulltext"], "none")
        self.assertEqual(data["doi"], "10.1/promote")
        self.assertEqual(data["arxiv"], "2301.12345")
        self.assertEqual(len(list(package.glob("original.*"))), 1)
        self.assertFalse((self.kb / ".staging").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)

    def test_oa_url_promotion_downloads_open_copy_and_passes_check(self) -> None:
        status, results = self.ingest([{
            "id": "R-N001", "title": "Metadata Only", "authors": "Doe, Jane",
            "year": 2024, "doi": "10.1/open-copy",
        }])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        with SourceServer(self.pdf.read_bytes()) as server:
            source_url = server + "/open.pdf"
            status, results = self.ingest([{
                "id": "R-N002", "slug": slug, "oa_url": source_url,
                "title": "Open Copy",
            }])
        self.assertEqual(status, 0)
        self.assertEqual(results[0]["result"], "promoted")
        self.assertEqual(results[0]["slug"], slug)
        self.assertEqual(results[0]["access"], "open")
        self.assertEqual(results[0]["source_url"], source_url)
        expected_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.assertEqual(results[0]["sha256"], expected_hash)
        data = lit.frontmatter(self.kb / "papers" / slug / "paper.md")
        self.assertEqual(data["slug"], slug)
        self.assertEqual(data["candidate_id"], "R-N002")
        self.assertEqual(data["title"], "Open Copy")
        self.assertEqual(data["doi"], "10.1/open-copy")
        self.assertEqual(data["access"], "open")
        self.assertNotEqual(data["fulltext"], "none")
        self.assertEqual(data["source_url"], source_url)
        self.assertEqual(data["source_sha256"], expected_hash)
        self.assertTrue(data["retrieved"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)

    def test_promotion_replaces_open_artifact_without_replace_flag(self) -> None:
        with SourceServer(self.pdf.read_bytes()) as server:
            status, results = self.ingest([{
                "id": "R-N001", "title": "HTML-only Source",
                "oa_url": server + "/artifact",
            }])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        before = lit.frontmatter(self.kb / "papers" / slug / "paper.md")
        self.assertEqual(before["access"], "open")
        self.assertEqual(before["fulltext"], "none")

        source = self.root / "promotion.txt"
        source.write_text("A concrete result is 42.\n", encoding="utf-8")
        status, results = self.ingest([{
            "id": "R-N002", "slug": slug, "file": str(source),
        }])
        self.assertEqual(status, 0)
        self.assertEqual(results[0]["result"], "promoted")
        data = lit.frontmatter(self.kb / "papers" / slug / "paper.md")
        self.assertEqual(data["access"], "user-supplied")
        self.assertEqual(data["fulltext"], "text")

    def test_promotion_of_extracted_text_requires_replace_true(self) -> None:
        source = self.root / "promotion.txt"
        source.write_text("A concrete result is 42.\n", encoding="utf-8")
        status, results = self.ingest([{
            "id": "R-N001", "title": "Extracted Source", "file": str(source),
        }])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        package = self.kb / "papers" / slug
        before = {path.name: path.read_bytes() for path in package.iterdir()}

        status, results = self.ingest([{
            "id": "R-N002", "slug": slug, "file": str(source),
        }])
        self.assertEqual(status, 1)
        self.assertEqual(results[0]["result"], "error")
        self.assertEqual(
            results[0]["reason"],
            'promotion target has extracted text; set "replace": true to replace it',
        )
        self.assertEqual({path.name: path.read_bytes() for path in package.iterdir()}, before)

        status, results = self.ingest([{
            "id": "R-N003", "slug": slug, "file": str(source), "replace": "true",
        }])
        self.assertEqual(status, 1)
        self.assertEqual(results[0]["result"], "error")
        self.assertEqual(
            results[0]["reason"],
            'promotion target has extracted text; set "replace": true to replace it',
        )
        self.assertEqual({path.name: path.read_bytes() for path in package.iterdir()}, before)

        status, results = self.ingest([{
            "id": "R-N004", "slug": slug, "file": str(source), "replace": True,
        }])
        self.assertEqual(status, 0)
        self.assertEqual(results[0]["result"], "promoted")
        self.assertEqual(lit.frontmatter(package / "paper.md")["candidate_id"], "R-N004")

    def test_promotion_file_takes_precedence_over_oa_url(self) -> None:
        status, results = self.ingest([{"id": "R-N001", "title": "Metadata Only"}])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        source = self.root / "promotion.txt"
        source.write_text("A concrete result is 42.\n", encoding="utf-8")

        with mock.patch.object(lit, "fetch", side_effect=AssertionError("fetch should not be called")) as fetch_mock:
            status, results = self.ingest([{
                "id": "R-N002", "slug": slug, "file": str(source),
                "oa_url": "http://127.0.0.1:1/unreachable",
            }])
        fetch_mock.assert_not_called()
        self.assertEqual(status, 0)
        self.assertEqual(results[0]["result"], "promoted")
        self.assertEqual(results[0]["access"], "user-supplied")
        self.assertEqual(results[0]["source_url"], "")
        data = lit.frontmatter(self.kb / "papers" / slug / "paper.md")
        self.assertEqual(data["access"], "user-supplied")
        self.assertNotIn("source_url", data)

    def test_promotion_requires_file_or_oa_url(self) -> None:
        status, results = self.ingest([{"id": "R-N001", "title": "Metadata Only"}])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])

        status, results = self.ingest([{"id": "R-N002", "slug": slug}])
        self.assertEqual(status, 1)
        self.assertEqual(results[0]["result"], "error")
        self.assertEqual(results[0]["reason"], "promotion requires a file or oa_url")

    def test_failed_oa_url_promotion_preserves_existing_package(self) -> None:
        status, results = self.ingest([{"id": "R-N001", "title": "Metadata Only"}])
        self.assertEqual(status, 0)
        slug = str(results[0]["slug"])
        package = self.kb / "papers" / slug
        note = package / "paper.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nPrior note.\n", encoding="utf-8")
        before = {path.name: path.read_bytes() for path in package.iterdir()}

        with SourceServer(self.pdf.read_bytes()) as server:
            status, results = self.ingest([{
                "id": "R-N002", "slug": slug, "oa_url": server + "/html",
            }])
        self.assertEqual(status, 1)
        self.assertEqual(results[0]["result"], "error")
        self.assertEqual(results[0]["slug"], slug)
        self.assertEqual(results[0]["reason"], "rejected HTML body")
        self.assertEqual({path.name: path.read_bytes() for path in package.iterdir()}, before)
        self.assertFalse((self.kb / ".staging").exists())

    def test_promotion_identifier_conflict_is_an_item_error(self) -> None:
        status, results = self.ingest([
            {"id": "R-N001", "title": "Target", "doi": "10.1/target"},
            {"id": "R-N002", "title": "Owner", "doi": "10.1/owner"},
        ])
        self.assertEqual(status, 0)
        target = self.kb / "papers" / str(results[0]["slug"])
        before = (target / "paper.md").read_text(encoding="utf-8")
        status, results = self.ingest([{
            "id": "R-N003", "slug": target.name, "file": str(self.pdf),
            "doi": "10.1/owner",
        }])
        self.assertEqual(status, 1)
        self.assertEqual(results[0]["result"], "error")
        self.assertIn("promotion doi is already owned by", str(results[0]["reason"]))
        self.assertEqual((target / "paper.md").read_text(encoding="utf-8"), before)
        self.assertEqual([item.name for item in target.iterdir()], ["paper.md"])
        self.assertFalse((self.kb / ".staging").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)

    def test_check_errors_for_read_note_without_two_page_locators(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Sparse Note", "authors": "Doe, Jane",
            "year": 2024, "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        note = self.packages()[0] / "paper.md"
        data = lit.frontmatter(note)
        data["status"] = "read"
        note.write_text(
            f"---\n{lit.yaml_document(data)}\n---\n\nA sparse read note. [[{note.parent.name}]] p.1\n",
            encoding="utf-8",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn(
            f"ERROR: papers/{note.parent.name}/paper.md: status read requires locators on two distinct pages including one after p.1",
            stdout.getvalue(),
        )

    def test_one_page_text_package_with_p1_locator_passes_as_read(self) -> None:
        source = self.root / "source.txt"
        source.write_text("A concrete result is 42.\n", encoding="utf-8")
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Plain Text", "authors": "Doe, Jane",
            "year": 2024, "file": str(source),
        }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        note = package / "paper.md"
        data = lit.frontmatter(note)
        self.assertEqual(data["fulltext"], "text")
        self.assertEqual(lit.PAGE_RE.findall((package / "fulltext.md").read_text(encoding="utf-8")), ["1"])
        data["status"] = "read"
        note.write_text(
            f"---\n{lit.yaml_document(data)}\n---\n\nThe result is 42 [[{package.name}]] p.1.\n",
            encoding="utf-8",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertIn("READ_UNCITED=1", stdout.getvalue())
        nested_run = self.kb / "runs" / "run-1" / "round-1.md"
        nested_run.parent.mkdir()
        nested_run.write_text(f"Uses [[{package.name}]].\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertIn("READ_UNCITED=0", stdout.getvalue())

    def test_markdown_leading_bracket_is_extracted_as_text(self) -> None:
        source = self.root / "source.md"
        source.write_text("[![badge](x)](y)\n\nA result.\n", encoding="utf-8")
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Markdown", "file": str(source),
        }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        self.assertEqual(lit.frontmatter(package / "paper.md")["fulltext"], "text")
        self.assertTrue((package / "original.md").is_file())

    def test_retrieved_text_does_not_keep_no_extraction_note(self) -> None:
        with SourceServer(self.pdf.read_bytes()) as server:
            status, results = self.ingest([{
                "id": "R-N001", "title": "Retrieved Text", "oa_url": server + "/text.txt",
            }])
        self.assertEqual(status, 0)
        data = lit.frontmatter(self.packages()[0] / "paper.md")
        self.assertEqual(data["fulltext"], "text")
        self.assertNotIn("retrieval_note", data)
        self.assertEqual(results[0]["reason"], "Needed by this project.")

    def test_check_errors_for_read_without_fulltext(self) -> None:
        status, _ = self.ingest([{"id": "R-N001", "title": "Unavailable"}])
        self.assertEqual(status, 0)
        note = self.packages()[0] / "paper.md"
        data = lit.frontmatter(note)
        data["status"] = "read"
        note.write_text(f"---\n{lit.yaml_document(data)}\n---\n\nRead note.\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("status read requires full text", stdout.getvalue())

    def test_check_errors_when_read_note_keeps_unread_placeholder(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Placeholder", "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        note = self.packages()[0] / "paper.md"
        data = lit.frontmatter(note)
        data["status"] = "read"
        body = note.read_text(encoding="utf-8").split("---", 2)[2]
        note.write_text(f"---\n{lit.yaml_document(data)}\n---{body}", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("still contains the unread placeholder", stdout.getvalue())

    def test_page_ranges_validate_both_endpoints_and_order(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Ranges", "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        slug = self.packages()[0].name
        topic = self.kb / "topics" / "ranges.md"
        topic.write_text(f"Valid [[{slug}]] p.1-2.\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        topic.write_text(f"Also valid [[{slug}]] p.1—2**\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        topic.write_text(f"Prose [[{slug}]] p.1—the author argues this.\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        topic.write_text(f"Reversed [[{slug}]] p.2-1.\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("is not an increasing page range", stdout.getvalue())
        topic.write_text(f"Outside [[{slug}]] p.1-3.\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("p.1-3 exceeds 2 pages", stdout.getvalue())
        topic.write_text(f"Malformed [[{slug}]] p.1-2x.\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("has a malformed page range", stdout.getvalue())
        topic.write_text(f"Malformed [[{slug}]] p.x-2.\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 1)
        self.assertIn("has a malformed page range", stdout.getvalue())

    def test_ingest_rerun_skips_completed_results(self) -> None:
        candidates = [{"id": "R-N001", "title": "Idempotent"}]
        candidate_path = self.write_jsonl("rerun-candidates.jsonl", candidates)
        decision_path = self.write_jsonl(
            "rerun-decisions.jsonl",
            [{"id": "R-N001", "accept": True, "reason": "Needed."}],
        )
        results = self.root / "rerun-results.jsonl"
        argv = [
            "ingest", "--kb", str(self.kb), "--candidates", str(candidate_path),
            "--decisions", str(decision_path), "--results", str(results),
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(argv), 0)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(lit.main(argv), 0)
        self.assertIn("R-N001 skipped (already in results)", output.getvalue())
        self.assertEqual(len(self.packages()), 1)
        self.assertEqual(len(results.read_text(encoding="utf-8").splitlines()), 1)

    def test_get_uses_key_retries_and_paces_same_host(self) -> None:
        calls: list[tuple[float, str | None]] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                calls.append((time.monotonic(), self.headers.get("x-api-key")))
                if len(calls) == 1:
                    self.send_response(429)
                    self.send_header("Retry-After", "0.05")
                    self.end_headers()
                    return
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        key = "temporary-test-key"
        key_file = self.root / "test-s2.key"
        key_file.write_text(key, encoding="utf-8")
        url = f"http://127.0.0.1:{server.server_address[1]}/api"
        stderr = io.StringIO()
        environment = {
            "HOME": str(self.root), "LIT_S2_KEY_FILE": str(key_file),
            "LIT_TEST_S2_HOST": "127.0.0.1", "LIT_TEST_GET_INTERVAL": "0.15",
        }
        try:
            with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stderr(stderr):
                self.assertEqual(lit.main(["get", url, "--out", str(self.root / "one.json")]), 0)
                self.assertEqual(lit.main(["get", url, "--out", str(self.root / "two.json")]), 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual([value for _, value in calls], [key, key, key])
        self.assertTrue(all(right[0] - left[0] >= 0.12 for left, right in zip(calls, calls[1:])))
        self.assertNotIn(key, stderr.getvalue())
        self.assertEqual((self.root / "one.json").read_bytes(), b"ok")

    def test_get_confines_key_and_succeeds_keyless(self) -> None:
        seen_keys: list[str | None] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                seen_keys.append(self.headers.get("x-api-key"))
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        key_file = self.root / "fake.key"
        key_file.write_text("temporary-test-key", encoding="utf-8")
        with LocalServer(Handler) as server:
            environment = {
                "HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0",
                "LIT_S2_KEY_FILE": str(key_file),
            }
            with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lit.main(["get", server, "--out", str(self.root / "non-s2")]), 0)
            environment = {
                "HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0",
                "LIT_TEST_S2_HOST": "127.0.0.1",
            }
            with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lit.main(["get", server, "--out", str(self.root / "keyless")]), 0)
            environment = {
                "HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0",
                "LIT_TEST_S2_HOST": "127.0.0.1",
                "LIT_S2_KEY_FILE": str(self.root / "missing.key"),
            }
            with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lit.main(["get", server, "--out", str(self.root / "missing-key")]), 0)
            invalid_key = self.root / "invalid.key"
            invalid_key.write_bytes(b"\xff")
            environment["LIT_S2_KEY_FILE"] = str(invalid_key)
            with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lit.main(["get", server, "--out", str(self.root / "invalid-key")]), 0)
            environment["LIT_S2_KEY_FILE"] = str(self.root / "nul") + "\0"
            with mock.patch.object(lit.os, "environ", environment), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lit.main(["get", server, "--out", str(self.root / "nul-key")]), 0)
        self.assertEqual(seen_keys, [None, None, None, None, None])

    def test_get_terminal_429_publishes_cooldown(self) -> None:
        calls: list[float] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                calls.append(time.monotonic())
                if len(calls) <= 4:
                    self.send_response(429)
                    self.send_header("Retry-After", "0.05")
                    self.end_headers()
                    return
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        environment = {
            "HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0.15",
        }
        with LocalServer(Handler) as server, mock.patch.dict(
            os.environ, environment, clear=True,
        ), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(lit.main(["get", server, "--out", str(self.root / "exhausted")]), 1)
            self.assertEqual(lit.main(["get", server, "--out", str(self.root / "after-cooldown")]), 0)
        self.assertEqual(len(calls), 5)
        self.assertGreaterEqual(calls[4] - calls[3], 0.04)

    def test_get_does_not_retry_404(self) -> None:
        requests = 0

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                nonlocal requests
                requests += 1
                self.send_response(404)
                self.end_headers()

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        stderr = io.StringIO()
        with LocalServer(Handler) as server, mock.patch.dict(
            os.environ, {"HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0"}, clear=True,
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(lit.main(["get", server, "--out", str(self.root / "missing")]), 1)
        self.assertEqual(requests, 1)
        self.assertIn("GET 404 0 127.0.0.1", stderr.getvalue())

    def test_get_rejects_truncated_body(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Length", "20")
                self.end_headers()
                self.wfile.write(b"short")
                self.close_connection = True

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        stderr = io.StringIO()
        with LocalServer(Handler) as server, mock.patch.dict(
            os.environ, {"HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0"}, clear=True,
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(lit.main(["get", server, "--out", str(self.root / "truncated")]), 1)
        self.assertIn("GET ERROR 0 127.0.0.1", stderr.getvalue())
        self.assertNotIn("GET 200", stderr.getvalue())

    def test_get_refuses_redirect_without_forwarding_key(self) -> None:
        target_keys: list[str | None] = []

        class TargetHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                target_keys.append(self.headers.get("x-api-key"))
                self.send_response(200)
                self.end_headers()

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        with LocalServer(TargetHandler) as target:
            class RedirectHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    self.send_response(302)
                    self.send_header("Location", target)
                    self.end_headers()

                def log_message(self, _format: str, *_args: object) -> None:
                    pass

            key_file = self.root / "redirect.key"
            key_file.write_text("temporary-test-key", encoding="utf-8")
            stderr = io.StringIO()
            with LocalServer(RedirectHandler) as redirect, mock.patch.dict(os.environ, {
                "HOME": str(self.root), "LIT_TEST_GET_INTERVAL": "0",
                "LIT_TEST_S2_HOST": "127.0.0.1", "LIT_S2_KEY_FILE": str(key_file),
            }, clear=True), contextlib.redirect_stderr(stderr):
                self.assertEqual(lit.main(["get", redirect, "--out", str(self.root / "redirect")]), 1)
        self.assertEqual(target_keys, [])
        self.assertIn("GET 302 0 127.0.0.1", stderr.getvalue())

    def test_preview_warning_requires_retrieved_fulltext(self) -> None:
        status, results = self.ingest([{
            "id": "R-N001", "title": "Unavailable Book", "type": "book",
        }])
        self.assertEqual(status, 0)
        unavailable_slug = str(results[0]["slug"])
        status, results = self.ingest([{
            "id": "R-N002", "title": "Short Book", "type": "book", "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        short_slug = str(results[0]["slug"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertNotIn(f"WARNING: {unavailable_slug}: possible preview or excerpt", stdout.getvalue())
        self.assertIn(f"WARNING: {short_slug}: possible preview or excerpt", stdout.getvalue())

    def test_both_pdf_extractors_failing_records_retrieval_note(self) -> None:
        with mock.patch.dict(os.environ, {
            "LIT_PYMUPDF_TIMEOUT": "0.01", "LIT_TEST_PYMUPDF_DELAY": "0.2",
        }), mock.patch.object(lit.shutil, "which", return_value=None):
            status, _ = self.ingest([{
                "id": "R-N001", "title": "No Extractor", "file": str(self.pdf),
            }])
        self.assertEqual(status, 0)
        data = lit.frontmatter(self.packages()[0] / "paper.md")
        self.assertEqual(data["fulltext"], "none")
        self.assertIn("pymupdf4llm failed", data["retrieval_note"])

    def test_pdf_with_txt_filename_keeps_pdf_handling(self) -> None:
        disguised = self.root / "source.txt"
        disguised.write_bytes(self.pdf.read_bytes())
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Disguised PDF", "file": str(disguised),
        }])
        self.assertEqual(status, 0)
        package = self.packages()[0]
        data = lit.frontmatter(package / "paper.md")
        self.assertEqual(data["fulltext"], "pymupdf4llm")
        self.assertTrue((package / "original.pdf").is_file())

    def test_init_updates_gitignore_and_outside_git_succeeds(self) -> None:
        repository = self.root / "repo"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        (repository / ".gitignore").write_bytes(b"\xff\n")
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root)}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["init", str(repository)]), 0)
        self.assertEqual((repository / ".gitignore").read_bytes(), b"\xff\nliterature/\n")
        self.assertFalse((repository / "literature" / ".gitignore").exists())
        outside = self.root / "outside"
        outside.mkdir()
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root)}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["init", str(outside)]), 0)
        self.assertFalse((outside / ".gitignore").exists())

    def test_not_retrieved_index_includes_doi_and_url(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Missing", "doi": "10.1/missing",
            "url": "https://example.test/landing",
        }])
        self.assertEqual(status, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        index = (self.kb / "index.md").read_text(encoding="utf-8")
        self.assertIn("doi:10.1/missing", index)
        self.assertIn("https://example.test/landing", index)

    def test_slug_forms_fallbacks_and_collisions(self) -> None:
        occupied: set[str] = set()
        candidates = [
            {"authors": "Doe, Jane and Roe, John", "year": 2021, "title": "An (Odd) Title"},
            {"authors": "Jane Doe, John Roe", "year": 2022, "title": "A Second Title"},
            {"authors": "", "year": 2023, "title": "Fallback Author"},
            {"authors": "Jane Doe", "year": "", "title": "Missing Year"},
        ]
        slugs = [lit.make_slug(candidate, occupied) for candidate in candidates]
        collision = lit.make_slug(candidates[0], occupied)
        self.assertEqual(slugs[0], "doe2021-an-odd-title")
        self.assertEqual(slugs[1], "doe2022-a-second-title")
        self.assertEqual(slugs[2], "fallback2023-fallback-author")
        self.assertIn("0000", slugs[3])
        self.assertEqual(collision, slugs[0] + "-2")
        self.assertEqual(lit.mapped_type("conference article"), "proceedings")
        self.assertEqual(lit.normalize_arxiv("2301.12345v2."), "2301.12345")
        for slug in slugs + [collision]:
            self.assertRegex(slug, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def test_dedup_exact_identifiers_title_flags_and_kb_match(self) -> None:
        _, seed_results = self.ingest([{
            "id": "SEED-N001", "title": "Known Work", "authors": "Seed Author",
            "year": 2019, "doi": "10.1/known",
        }])
        seed_slug = seed_results[0]["slug"]
        lane = self.write_jsonl("lane.jsonl", [
            {"title": "Exact", "doi": "doi:10.1/X.", "lane": "one", "url": "https://one", "oa_url": "https://oa-one", "relevance": "short"},
            {"title": "Exact Variant", "doi": "https://doi.org/10.1/x", "lane": "two", "url": "https://two", "oa_url": "https://oa-two", "relevance": "a much longer relevance line"},
            {"title": "Title Only", "doi": "10.1/a", "lane": "three"},
            {"title": "Title Only", "doi": "10.1/b", "lane": "four"},
            {"title": "Known Work", "lane": "five"},
        ])
        output = self.root / "deduped.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lit.main([
                "dedup", "--kb", str(self.kb), "--prefix", "R1", "--out", str(output), str(lane),
            ]), 0)
        records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["id"] for item in records], ["R1-N001", "R1-N002", "R1-N003", "R1-N004"])
        self.assertEqual(records[0]["lanes"], ["one", "two"])
        self.assertEqual(records[0]["urls"], ["https://one", "https://two"])
        self.assertEqual(records[0]["oa_urls"], ["https://oa-one", "https://oa-two"])
        self.assertEqual(records[0]["relevance"], "a much longer relevance line")
        self.assertEqual(records[1]["possible_duplicate_of"], ["R1-N003"])
        self.assertEqual(records[2]["possible_duplicate_of"], ["R1-N002"])
        self.assertEqual(records[3]["in_kb"], seed_slug)


if __name__ == "__main__":
    unittest.main()

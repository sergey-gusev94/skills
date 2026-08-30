# Run: uv run --with pymupdf==1.26.4 --with pyyaml==6.0.2 python -B -m unittest discover -s literature/tests

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import threading
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


class LitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
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
        self.assertEqual(data["fulltext"], "pymupdf")
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
        self.assertEqual(lit.frontmatter(package / "paper.md")["fulltext"], "pdftotext")
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

    def test_check_warns_for_read_note_without_two_page_locators(self) -> None:
        status, _ = self.ingest([{
            "id": "R-N001", "title": "Sparse Note", "authors": "Doe, Jane",
            "year": 2024, "file": str(self.pdf),
        }])
        self.assertEqual(status, 0)
        note = self.packages()[0] / "paper.md"
        data = lit.frontmatter(note)
        data["status"] = "read"
        body = note.read_text(encoding="utf-8").split("---", 2)[2]
        note.write_text(f"---\n{lit.yaml_document(data)}\n---{body}", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(lit.main(["check", str(self.kb)]), 0)
        self.assertIn(
            f"WARNING: {note.parent.name}: status read with fewer than two locators on distinct pages",
            stdout.getvalue(),
        )

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

---
name: lit
description: Maintain a project's literature knowledge base through a Codex-native research and ingest loop.
---

# Literature

Act as lead. You own scope, adjudication, `lit.py`, verification, stopping, and the answer. Never run two `$lit` sessions on one repository.

Invoke `<skill>/scripts/lit.py check <kb>` by absolute path. Execute `lit.py` directly so its `uv` shebang runs; never use `python lit.py`. Keep run files in a unique system-temp directory outside the project. The KB is `<project>/literature/`; create it with `lit.py init <project>` when absent. Init enforces that the KB stays git-ignored; never track it or remove that ignore entry.

For every spawn set `model: gpt-5.6-luna`, `reasoning_effort: max`, and `fork_turns: "none"`. A child has no parent context, so every spawn message must repeat the direct-execution rule, name `<kb>/README.md` by absolute path, and name every other input by absolute path. `wait_agent` caps one wait at one hour; loop waits and never kill a slow agent.

## Research rounds

Read the project documentation, `<kb>/README.md`, and `literature/scope.md`. Choose at most ten non-overlapping lanes and spawn researchers directly, without a coordinator. Lanes may cover concepts, methods, applications, negative results, benchmarks, adjacent fields, citation chains, grey literature, theses, and recency.

Each researcher is read-only, must not delegate, and gets one lane and one write: `<run>/round-N/lane-K.jsonl`. Each JSON line uses `title`, `authors`, `year`, `venue`, `type`, `doi`, `arxiv`, `url`, `oa_url`, `relevance`, and `lane` when known; format authors as `Last, First and Last, First`. It verifies that each `oa_url` is lawful full text, never bypasses access controls, and returns five lines covering new candidates, known work, and gaps.

Every researcher makes every scholarly API request to OpenAlex, Crossref, arXiv, Europe PMC, or Semantic Scholar through `lit.py get '<url>'`, never raw `curl` to those hosts. `get` paces requests, retries politely, and supplies the Semantic Scholar key itself when configured. Agents never read the key file or place keys in URLs, files, or reports.

When Scite MCP tools are available, assign Scite to at most two researcher lanes per round and put a fixed call allowance in each spawn message, totaling about 30 calls across the whole KB search. Never assume Scite is available; deduplicate before targeted calls. Attribute Smart Citation labels to Scite as its classification of a citing passage, not evidence that a claim is correct, and never reconstruct a paper through repeated excerpt queries. Never call ordering, purchasing, or collection-changing tools.

Run `lit.py dedup`, then decide each candidate in `decisions.jsonl` as `{"id": "...", "accept": true|false, "reason": "..."}` with a project-specific reason. `in_kb` may be a title-only match, so accept it only when a second package is intended. Reject by default: relevance means the project would cite or use the work. The lead runs `lit.py ingest`; there is no writer. Ingest about 10–20 packages per reader; a batch above roughly 80–100 signals that the round should be split or narrowed. `LIT_PYMUPDF_TIMEOUT` bounds the primary extraction attempt and defaults to 300 seconds; the `pdftotext` fallback has its own 120-second limit.

Accept a clearly relevant work even when no open copy can be retrieved; ingest records an `access: none` metadata-only package. Bibliographic inclusion, full-text retrieval, and synthesis eligibility are distinct. Only `status: read` packages support `p.N` citations.

Spawn readers in parallel over disjoint lists of about 10–20 slugs. A reader reads extracted `fulltext.md`, which is the citation basis, and treats `original.*` as authoritative; it verifies important numbers, equations, and tables against the original. It edits only assigned `paper.md` files, returns one line per slug, and sets `status: read` only when the KB README quality bar is met.

After notes exist, one agent or the lead may edit only `topics/`, `runs/`, and `scope.md`.

## Verify and stop

After each round, `lit.py check <kb>` must exit 0 with `KB_CHECK=ok`. Confirm every accepted ID occurs in the results file, read 3–5 random new notes against `fulltext.md`, reject the batch if necessary, and report `UNREAD` and `READ_UNCITED`.

Run round two unless round one yielded nothing, because citation chaining from read packages is where much of the value appears. Stop when a round yields nothing the lead would cite; call this operational saturation under the recorded scope and cutoff, never proof of completeness. Stop after five rounds unless the user set another cap. If the round cap rather than saturation stops the run, report `capped` explicitly and offer a continuation round.

Before answering, copy `round-*/lane-*.jsonl`, `candidates.jsonl`, `decisions.jsonl`, and `results.jsonl` from the temp run directory into `<kb>/runs/<run-id>/`, where a run ID may be `<date>-<question>`. Write the run account beside them at `<kb>/runs/<run-id>/run.md`.

## User files

For inbox files or named paths, create candidates with absolute `file` paths. Match an existing `access: none` package by DOI found in the file, otherwise by title; ask the user if ambiguous. Add its `slug` for promotion, then use the same ingest, read, and check path.

When a later round or run finds a lawful open copy of an `access: none` package, promote it with a candidate carrying `slug` and `oa_url`; ingest records it as `access: open`. Replacing a package whose artifact has extracted text also requires `"replace": true`.

## Answer

Cite `[[slug]] p.N`. State packages added, unread count, topics changed, check result, rounds, stopping reason, and caveats.

End every run with a prioritized numbered list of the unretrieved (`access: none`) works the project would most benefit from reading. Give each citation, DOI, and best lawful landing link; ask whether the user can supply copies and point to `<kb>/inbox/` or another named path. Process supplied files through the existing user-files promotion path.

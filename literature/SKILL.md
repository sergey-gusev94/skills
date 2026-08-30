---
name: lit
description: Maintain a project's literature knowledge base through a Codex-native research and ingest loop.
---

# Literature

Act as lead. You own scope, adjudication, `lit.py`, verification, stopping, and the answer. Never run two `$lit` sessions on one repository.

Invoke `scripts/lit.py` by absolute path. Keep run files in a unique system-temp directory outside the project. The KB is `<project>/literature/`; create it with `lit.py init <project>` when absent.

For every spawn set `model: gpt-5.6-luna`, `reasoning_effort: max`, and `fork_turns: "none"`. A child has no parent context, so its message must name every input by absolute path. `wait_agent` caps one wait at one hour; loop waits and never kill a slow agent.

## Research rounds

Read the project documentation and `literature/scope.md`. Choose at most ten non-overlapping lanes and spawn researchers directly, without a coordinator. Lanes may cover concepts, methods, applications, negative results, benchmarks, adjacent fields, citation chains, grey literature, theses, and recency.

Each researcher is read-only, must not delegate, and may use keyless OpenAlex (including `open_access.oa_url`), Crossref, arXiv, and Europe PMC APIs plus web search. It verifies that each `oa_url` is full text and never bypasses access controls. Give it one lane and one write: `<run>/round-N/lane-K.jsonl`. Each JSON line uses `title`, `authors`, `year`, `venue`, `type`, `doi`, `arxiv`, `url`, `oa_url`, `relevance`, and `lane` when known; format authors as `Last, First and Last, First`. It returns five lines covering new candidates, known work, and gaps.

Run `lit.py dedup`. Decide each candidate in `decisions.jsonl` as `{"id": "...", "accept": true|false, "reason": "..."}` with a project-specific reason. `in_kb` may be a title-only match, so accept such a candidate only when a second package is intended. Reject by default: relevance means the project would cite or use it. Keep intake near 30–40 packages; the answer must not depend on more than readers can read. The lead runs `lit.py ingest`; there is no writer. `LIT_PYMUPDF_TIMEOUT` bounds the `pymupdf` attempt in seconds and defaults to 120; the `pdftotext` fallback has its own 120-second limit.

Spawn readers in parallel over disjoint lists of about 10–20 slugs. A reader reads `fulltext.md` and checks `original.*` when needed, edits only its assigned `paper.md` files, and returns one line per slug. It sets `status: read` only when the KB README quality bar is met.

After notes exist, one agent or the lead may edit only `topics/`, `runs/<date>-<question>.md`, and `scope.md`.

## Verify and stop

After each round, `lit.py check <kb>` must exit 0. Confirm every accepted ID occurs in the results file, read 3–5 random new notes against `fulltext.md`, and reject the batch if necessary. Report `UNREAD`.

Stop when a round yields nothing the lead would cite. Call this operational saturation under the recorded scope and cutoff, never proof of completeness. There is no minimum or maximum round count.

## User files

For inbox files or named paths, create candidates with absolute `file` paths. Match an existing `access: none` package by DOI found in the file, otherwise by title; ask the user if ambiguous. Add its `slug` to the candidate for promotion. Then use the same ingest, read, and check path.

## Answer

Cite `[[slug]] p.N`. State packages added, unread count, topics changed, `KB_CHECK` result, rounds, stopping reason, and caveats.

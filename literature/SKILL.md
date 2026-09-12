---
name: lit
description: Maintain a project's literature knowledge base by discovering relevant sources or adding literature already identified by a user or another agent.
---

# Literature

Act as lead for the requested literature task, including when invoked as a subagent. You own its scope, adjudication, `lit.py`, verification, stopping, and answer. Use research rounds for discovery requests and the identified-literature path for supplied papers or files. These roles and stopping rules apply only to the literature task, not to the caller's broader research.

Never run two `$lit` sessions on one repository. During ongoing research, route additions to one reusable literature agent and process batches sequentially; do not launch an independent ingest session for every discovery. Serialize KB maintenance, including `check`, which regenerates shared indexes. Unrelated research may continue while a batch is processed.

Invoke `<skill>/scripts/lit.py check <kb>` by absolute path. Execute `lit.py` directly so its `uv` shebang runs; never use `python lit.py`. Keep run files in a unique system-temp directory outside the project. The KB is `<project>/literature/`; create it with `lit.py init <project>` when absent. Init enforces that the KB stays git-ignored; never track it or remove that ignore entry.

For every child spawned by this skill, set `model: gpt-5.6-luna`, `reasoning_effort: max`, and `fork_turns: "none"`. This does not select the invoking agent's model or require a separate coordinator. A child has no parent context, so every spawn message must repeat the direct-execution rule, name `<kb>/README.md` by absolute path, and name every other input by absolute path. `wait_agent` caps one wait at one hour; loop waits and never kill a slow agent.

Make every scholarly API request to OpenAlex, Crossref, arXiv, Europe PMC, or Semantic Scholar through `lit.py get '<url>'`, never raw `curl` to those hosts. `get` paces requests, retries politely, and supplies the Semantic Scholar key itself when configured. Agents never read the key file or place keys in URLs, files, or reports.

## Add identified literature

Accept papers identified by a user or another agent, with identifiers, links or absolute file paths, and reasons for inclusion. A delegated task must explicitly name `$lit` and supply the absolute skill, project, KB, and other input paths. Read the project documentation, `<kb>/README.md`, and `<kb>/scope.md` to assess relevance. Search only as needed to establish the supplied works' identities and find lawful full text; do not expand into discovery rounds.

The invoking agent performs ingestion and reading directly, without spawning researchers, readers, or a coordinator. Use the shared ingest, read, verify, promotion, and answer requirements below. Record the supplied candidates as `<run>/round-1/lane-1.jsonl` using the shared candidate schema; this directory is a batch record, not a search round. Split a large supplied set into sequential batches with distinct round numbers when needed.

Check for existing packages before adding or promoting them. Reuse a matching usable package; use the promotion path when a supplied source can fill a missing or unusable artifact. Finish when every supplied candidate has an outcome or an explicitly reported unresolved failure. Report the stopping reason as `supplied batch processed`, not saturation or a discovery cap. Missing sources remain recorded even when no copy is available. When delegated, return the report to the calling agent without stopping its broader task.

## Research rounds

Read the project documentation, `<kb>/README.md`, and `literature/scope.md`. Choose at most ten non-overlapping lanes and spawn researchers directly, without a coordinator. Lanes may cover concepts, methods, applications, negative results, benchmarks, adjacent fields, citation chains, grey literature, theses, and recency.

Each researcher in these discovery rounds is read-only, must not delegate, and gets one lane and one write: `<run>/round-N/lane-K.jsonl`, using the shared candidate schema below. It verifies that each `oa_url` is lawful full text, never bypasses access controls, and returns a concise summary covering new candidates, known work, and gaps.

When Scite MCP tools are available, assign Scite to at most two researcher lanes per round and put a fixed call allowance in each spawn message, totaling about 30 calls across the whole KB search. Never assume Scite is available; deduplicate before targeted calls. Attribute Smart Citation labels to Scite as its classification of a citing passage, not evidence that a claim is correct, and never reconstruct a paper through repeated excerpt queries. Never call ordering, purchasing, or collection-changing tools.

## Ingest and read

For both paths, each candidate JSON line uses `title`, `authors`, `year`, `venue`, `type`, `doi`, `arxiv`, `url`, `oa_url`, `relevance`, and `lane` when known; format authors as `Last, First and Last, First`. Verify that each `oa_url` is lawful full text and never bypass access controls.

Keep each round or supplied batch's `lane-K.jsonl`, `candidates.jsonl`, `decisions.jsonl`, and `results.jsonl` in `<run>/round-N/`. Run `lit.py dedup --kb <kb> --prefix <run-id>-R<N> --out <run>/round-N/candidates.jsonl <run>/round-N/lane-*.jsonl`, using a different candidate-ID prefix for each round or batch. Then decide each candidate in `<run>/round-N/decisions.jsonl` as `{"id": "...", "accept": true|false, "reason": "..."}` with a project-specific reason. `in_kb` may be a title-only match, so accept it only for a verified promotion or when a second package is intended. Reject by default: relevance means the project would cite or use the work. The lead runs `lit.py ingest --kb <kb> --candidates <run>/round-N/candidates.jsonl --decisions <run>/round-N/decisions.jsonl --results <run>/round-N/results.jsonl`; there is no separate writer. Never reuse another round or batch's output paths or candidate-ID prefix. Ingest about 10–20 packages per reader; a batch above roughly 80–100 signals that it should be split or narrowed. `LIT_PYMUPDF_TIMEOUT` bounds the primary extraction attempt and defaults to 300 seconds; the `pdftotext` fallback has its own 120-second limit.

Accept a clearly relevant work even when no open copy can be retrieved; ingest records an `access: none` metadata-only package. Bibliographic inclusion, full-text retrieval, and synthesis eligibility are distinct. Only `status: read` packages support `p.N` citations in `topics/` and `runs/`; a package's own `paper.md` may carry page locators while it is still `unread`.

For discovery rounds, spawn readers in parallel over disjoint lists of about 10–20 slugs. For supplied batches, the lead reads the sources itself. In either case, read extracted `fulltext.md`, which is the citation basis, and treat `original.*` as authoritative; verify important numbers, equations, and tables against the original. A delegated reader edits only assigned `paper.md` files and returns one line per slug. Set `status: read` only when the KB README quality bar is met.

After notes exist, one agent or the lead may edit only `topics/`, `runs/`, and `scope.md`.

## Verify and stop

After each round or supplied batch, `lit.py check <kb>` must exit 0 with `KB_CHECK=ok`. Confirm every accepted ID has a non-error result or an explicitly reported unresolved failure. Read 3–5 random new notes against `fulltext.md`, or all new notes when fewer than three exist; when sampled notes fail the KB quality bar, repair or re-read them directly or through the assigned readers and withhold unsupported claims from synthesis until they pass. Report `UNREAD` and `READ_UNCITED`.

For discovery only, run round two unless round one yielded nothing. Stop when a round yields nothing the lead would cite; call this operational saturation under the recorded scope and cutoff, never proof of completeness. Stop after five rounds unless the user set another cap. If the round cap rather than saturation stops the run, report `capped` explicitly and offer a continuation round.

Before answering, copy every `<run>/round-N/` directory intact, including its `lane-K.jsonl`, `candidates.jsonl`, `decisions.jsonl`, and `results.jsonl`, into `<kb>/runs/<run-id>/`. Use a unique run ID, such as `<date>-<question>` with a suffix when needed, so repeated additions preserve earlier records. Write the run account beside them at `<kb>/runs/<run-id>/run.md`.

## User files

For inbox files or named paths, create candidates with absolute `file` paths. Match an existing `access: none` package by DOI found in the file, otherwise by title. If ambiguous, leave the package unchanged and ask the user to identify the match, or return the ambiguity to the caller when delegated; continue processing other supplied works. Add the confirmed match's `slug` for promotion, then use the same ingest, read, and check path.

When a later round or run finds a lawful open copy of an `access: none` package, promote it with a candidate carrying `slug` and `oa_url`; ingest records it as `access: open`. Replacing a package whose artifact has extracted text also requires `"replace": true`.

## Answer

Cite `[[slug]] p.N`. State packages added, unread count, topics changed, check result, discovery rounds or supplied batches processed, stopping reason, and caveats. For supplied batches, also return each candidate's outcome, resulting or existing slug, reading status, and any unresolved retrieval, extraction, or ingest issue.

End every run with a complete, deduplicated numbered list of all in-scope papers and other materials identified during the review whose source content remains unretrieved. Include every `access: none` work encountered across all rounds or supplied batches, including existing KB entries, and any accepted candidates with unresolved retrieval or ingest failures. For supplied batches, scope this list to the supplied works and their matching KB entries. Priority may determine ordering, but never inclusion; do not truncate the list or omit lower-priority materials. Give each citation, DOI when available, best lawful landing link, and reason retrieval remains unresolved. Save the complete list in `<kb>/runs/<run-id>/run.md` and include it in the final answer. If nothing remains unretrieved, say so explicitly. In a direct user-facing run, ask whether the user can supply copies and point to `<kb>/inbox/` or another named path. When delegated, include that request in the report to the caller for later presentation to the user; do not wait for copies or stop the caller's broader work. Process supplied files through the existing user-files promotion path.

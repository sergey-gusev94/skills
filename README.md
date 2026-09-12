# Agent skills and shared instructions

## Skills

Eight related multi-agent skills:

- **`council/`** — Codex skill (`$council`): a five-subagent inquiry for a question, decision, plan, or investigation, synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the five-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/q`): combines Fable, Opus, and the Codex `$council`, then synthesizes one answer.
- **`hybrid-review/`** — Claude Code skill (`/hybrid-review`): the code-review variant of `hybrid-council`.
- **`hybrid-implement/`** — Claude Code skill (`/imp`): a write-enabled implement, review, and fix loop.
- **`build/`** — Codex skill (`$build`): completes a file-based task through adaptive work selection, coherent commits, and independent Codex and Claude reviews at increment, milestone, and final scope.
- **`literature/`** — Codex skill (`$lit`): discover literature with researchers and readers, or add identified sources directly in the invoking agent. Both paths use the deterministic `scripts/lit.py` tool for initialization, deduplication, ingest, validation, and generated indexes.
- **`topic-research/`** — Codex skill (`$topic`): question-driven web research coordinated by a lead and researchers, with a derived scope, dated source evidence, optional subject profiles, synthesis, and deterministic initialization, deduplication, and validation.

`hybrid-review` and `hybrid-implement` reuse `hybrid-council`'s runner through in-repository relative symlinks, so the runner has one source file.

## Shared global instructions

[`global/AGENTS.md`](global/AGENTS.md) is the source of truth for instructions shared by Codex and Claude Code. The installation block links it to Codex's global instruction location, `~/.codex/AGENTS.md`.

To load the same instructions in Claude Code, ensure `~/.claude/CLAUDE.md` contains:

```text
@~/.codex/AGENTS.md
```

Start a new Codex or Claude Code session after changing shared instructions.

## Install

The repository is the source of truth; the tools discover these paths through symlinks. Before first installation, merge or back up an existing `~/.codex/AGENTS.md` because this command replaces that path with a symlink.

```sh
mkdir -p ~/.codex/skills ~/.claude/skills ~/.claude/agents

ln -sfn ~/repo/skills/global/AGENTS.md ~/.codex/AGENTS.md

ln -sfn ~/repo/skills/council ~/.codex/skills/council
ln -sfn ~/repo/skills/review-council ~/.codex/skills/review-council
ln -sfn ~/repo/skills/build ~/.codex/skills/build
ln -sfn ~/repo/skills/literature ~/.codex/skills/lit
ln -sfn ~/repo/skills/topic-research ~/.codex/skills/topic

ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/q
ln -sfn ~/repo/skills/hybrid-review ~/.claude/skills/hybrid-review
ln -sfn ~/repo/skills/hybrid-implement ~/.claude/skills/imp

ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

After first installation, `ln -sfn` makes the block safe to rerun. Verify the global link with `readlink -f ~/.codex/AGENTS.md`; it should resolve to this repository's `global/AGENTS.md`.

Renaming or removing a skill requires deleting its old symlinks. When migrating from the former Claude `/build`, remove its old `~/.claude/skills/build` symlink.

## Requirements

- Codex CLI on `PATH` (tested with 0.153.4). The council skills need Codex's stable, default-on `multi_agent` feature; check with `codex features list`.
- The hybrid skills and `$build` require the Claude Code CLI.
- `$lit` discovery uses native subagents. Set `[agents] max_concurrent_threads_per_session` to at least 11 for the lead and ten researchers. Every child spawned by `$lit` pins `gpt-5.6-luna`, maximum reasoning effort, and a fresh context. Adding identified sources requires no child agents; the invoking agent handles the supplied batch directly.
- `literature/scripts/lit.py` needs `uv` and `curl`; it also provides the paced `get` fetch for scholarly APIs. `pdftotext` is optional for ingest but required by the test suite.
- Run the literature tests with `uv run --with pymupdf4llm==1.28.2 --with pyyaml==6.0.2 python -B -m unittest discover -s literature/tests -v`.
- `$topic` uses native subagents and the native Codex web search tool, which subagents inherit. Web search defaults to live results under a full-access sandbox (the user's configuration); otherwise set `web_search = "live"` or pass `--search`.
- `topic-research/scripts/research.py` needs `uv`. Its KB is ordinary tracked text and is not git-ignored, unlike `$lit`'s.
- Run the topic research tests with `uv run --with pyyaml==6.0.2 python -B -m unittest discover -s topic-research/tests -v`.
- The optional Semantic Scholar key is a single line in `~/.config/lit/semantic-scholar.key`; run `chmod 600 ~/.config/lit/semantic-scholar.key`, and only `lit.py get` reads it. `get` works keyless when the file is absent.
- `hybrid-council` invokes `$council`, and `hybrid-review` invokes `$review-council`, so their Codex skill symlinks must be installed.
- `hybrid-implement` needs the `hybrid-review` symlink and therefore `review-council`.
- The general council and implementation runners default to `gpt-6-astra`; override per run with `CODEX_COUNCIL_MODEL` or `CODEX_IMPLEMENT_MODEL`. Direct Codex skill invocations use the active model except for `$lit`'s required child pin.
- Read-only and write scopes are enforced by instruction rather than sandboxing. `$lit` children inherit the interactive session's sandbox and tools.
- `run-codex-council.sh` reports `STATUS=ok|failed` and a self-reported `SUBAGENTS=<n|unknown>` count.
- `run-codex-implement.sh` is write-enabled and checks the resulting tree against git. It never commits; the lead commits only when the user asks directly or through a user-invoked enclosing skill whose contract commits each gated increment.
- `$build` is instruction-only and explicitly invoked. Codex delegates one implementation increment at a time, uses ten native Codex reviewers, and runs `claude --model fable --effort high -p` for an independent review with one Fable and two Opus subagents. The same review process applies to increments, completed milestones, and the final task result. It requires no hybrid skill runners or council agent definitions.
- Run artifacts accumulate under `${TMPDIR:-/tmp}` as `hybrid-council.*` and `hybrid-implement.*` directories. They are not deleted automatically.

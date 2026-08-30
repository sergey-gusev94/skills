# Agent skills and shared instructions

## Skills

Six related multi-agent skills:

- **`council/`** — Codex skill (`$council`): a ten-subagent inquiry for a question, decision, plan, or investigation, synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the ten-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/q`): combines Fable, Opus, and the Codex `$council`, then synthesizes one answer.
- **`hybrid-review/`** — Claude Code skill (`/hybrid-review`): the code-review variant of `hybrid-council`.
- **`hybrid-implement/`** — Claude Code skill (`/imp`): a write-enabled implement, review, and fix loop.
- **`literature/`** — Codex skill (`$lit`): a flat literature workflow in which the lead directly coordinates researchers and readers and uses the deterministic `scripts/lit.py` tool for initialization, deduplication, ingest, validation, and generated indexes.

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
ln -sfn ~/repo/skills/literature ~/.codex/skills/lit

ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/q
ln -sfn ~/repo/skills/hybrid-review ~/.claude/skills/hybrid-review
ln -sfn ~/repo/skills/hybrid-implement ~/.claude/skills/imp

ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

After first installation, `ln -sfn` makes the block safe to rerun. Verify the global link with `readlink -f ~/.codex/AGENTS.md`; it should resolve to this repository's `global/AGENTS.md`.

## Requirements

- Codex CLI on `PATH` (tested with 0.150.1). The council skills need Codex's stable, default-on `multi_agent` feature; check with `codex features list`.
- `$lit` uses native subagents. Set `[agents] max_concurrent_threads_per_session` to at least 11 for the lead and ten researchers. Every spawn pins `gpt-5.6-luna`, maximum reasoning effort, and a fresh context.
- `literature/scripts/lit.py` needs `uv` and `curl`; it also provides the paced `get` fetch for scholarly APIs. `pdftotext` is optional for ingest but required by the test suite.
- Run the literature tests with `uv run --with pymupdf4llm==1.28.2 --with pyyaml==6.0.2 python -B -m unittest discover -s literature/tests -v`.
- The optional Semantic Scholar key is a single line in `~/.config/lit/semantic-scholar.key`; run `chmod 600 ~/.config/lit/semantic-scholar.key`, and only `lit.py get` reads it. `get` works keyless when the file is absent.
- `hybrid-council` invokes `$council`, and `hybrid-review` invokes `$review-council`, so their Codex skill symlinks must be installed.
- `hybrid-implement` needs the `hybrid-review` symlink and therefore `review-council`.
- The general council and implementation runners default to `gpt-5.6-sol`; override per run with `CODEX_COUNCIL_MODEL` or `CODEX_IMPLEMENT_MODEL`. Direct Codex skill invocations use the active model except for `$lit`'s required child pin.
- Read-only and write scopes are enforced by instruction rather than sandboxing. `$lit` children inherit the interactive session's sandbox and tools.
- `run-codex-council.sh` reports `STATUS=ok|failed` and a self-reported `SUBAGENTS=<n|unknown>` count.
- `run-codex-implement.sh` is write-enabled and checks the resulting tree against git. It never commits; the lead commits only when the user asks.
- Run artifacts accumulate under `${TMPDIR:-/tmp}` as `hybrid-council.*` and `hybrid-implement.*` directories and are not deleted automatically.

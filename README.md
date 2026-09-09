# Agent skills and shared instructions

## Skills

Eight related multi-agent skills:

- **`council/`** — Codex skill (`$council`): a five-subagent inquiry for a question, decision, plan, or investigation, synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the five-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/q`): combines Fable, Opus, and the Codex `$council`, then synthesizes one answer.
- **`hybrid-review/`** — Claude Code skill (`/hybrid-review`): the code-review variant of `hybrid-council`.
- **`hybrid-implement/`** — Claude Code skill (`/imp`): a write-enabled implement, review, and fix loop.
- **`hybrid-build/`** — Claude Code skill (`/build`): pursues a frozen mandate through a living work queue, with autonomous investigation and planning and resumable gated, committed increments.
- **`literature/`** — Codex skill (`$lit`): a flat literature workflow in which the lead directly coordinates researchers and readers and uses the deterministic `scripts/lit.py` tool for initialization, deduplication, ingest, validation, and generated indexes.
- **`topic-research/`** — Codex skill (`$topic`): question-driven web research coordinated by a lead and researchers, with a derived scope, dated source evidence, optional subject profiles, synthesis, and deterministic initialization, deduplication, and validation.

`hybrid-review` and `hybrid-implement` reuse `hybrid-council`'s runner through in-repository relative symlinks; `hybrid-build` reuses that runner and `hybrid-implement`'s implement runner the same way, so each runner has one source file.

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
ln -sfn ~/repo/skills/topic-research ~/.codex/skills/topic

ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/q
ln -sfn ~/repo/skills/hybrid-review ~/.claude/skills/hybrid-review
ln -sfn ~/repo/skills/hybrid-implement ~/.claude/skills/imp
ln -sfn ~/repo/skills/hybrid-build ~/.claude/skills/build

ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

After first installation, `ln -sfn` makes the block safe to rerun. Verify the global link with `readlink -f ~/.codex/AGENTS.md`; it should resolve to this repository's `global/AGENTS.md`.

Renaming or removing a skill requires deleting its old symlinks.

## Requirements

- Codex CLI on `PATH` (tested with 0.153.4). The council skills need Codex's stable, default-on `multi_agent` feature; check with `codex features list`.
- The hybrid skills require the Claude Code CLI.
- `$lit` uses native subagents. Set `[agents] max_concurrent_threads_per_session` to at least 11 for the lead and ten researchers. Every spawn pins `gpt-5.6-luna`, maximum reasoning effort, and a fresh context.
- `literature/scripts/lit.py` needs `uv` and `curl`; it also provides the paced `get` fetch for scholarly APIs. `pdftotext` is optional for ingest but required by the test suite.
- Run the literature tests with `uv run --with pymupdf4llm==1.28.2 --with pyyaml==6.0.2 python -B -m unittest discover -s literature/tests -v`.
- `$topic` uses native subagents and the native Codex web search tool, which subagents inherit. Web search defaults to live results under a full-access sandbox (the user's configuration); otherwise set `web_search = "live"` or pass `--search`.
- `topic-research/scripts/research.py` needs `uv`. Its KB is ordinary tracked text and is not git-ignored, unlike `$lit`'s.
- Run the topic research tests with `uv run --with pyyaml==6.0.2 python -B -m unittest discover -s topic-research/tests -v`.
- The optional Semantic Scholar key is a single line in `~/.config/lit/semantic-scholar.key`; run `chmod 600 ~/.config/lit/semantic-scholar.key`, and only `lit.py get` reads it. `get` works keyless when the file is absent.
- `hybrid-council` invokes `$council`, and `hybrid-review` invokes `$review-council`, so their Codex skill symlinks must be installed.
- `hybrid-implement` needs the `hybrid-review` symlink and therefore `review-council`; `hybrid-build` needs the `imp` symlink and therefore everything `hybrid-implement` needs.
- The general council and implementation runners default to `gpt-6-astra`; override per run with `CODEX_COUNCIL_MODEL` or `CODEX_IMPLEMENT_MODEL`. Direct Codex skill invocations use the active model except for `$lit`'s required child pin.
- Read-only and write scopes are enforced by instruction rather than sandboxing. `$lit` children inherit the interactive session's sandbox and tools.
- `run-codex-council.sh` reports `STATUS=ok|failed` and a self-reported `SUBAGENTS=<n|unknown>` count.
- `run-codex-implement.sh` is write-enabled and checks the resulting tree against git. It never commits; the lead commits only when the user asks directly or through a user-invoked enclosing skill whose contract commits each gated increment.
- `hybrid-build` uses [`progress-template.md`](hybrid-build/assets/progress-template.md) for durable progress. Its immutable `scope.md` contains the frozen mandate; `progress.md` records the source path and hash from `sha256sum scope.md`, discovery boundary, and living work queue. A qualifying iteration produces a commit, `/imp`-backed `satisfied-by-prior-work` evidence for an implementation obligation, `completed-by-investigation` evidence for a discovery or investigation item, a drop or skip under the drop rule, an evidence-bearing work queue decision, or new discovery evidence. Record every outcome and the stagnation counter; reset it on qualifying iterations and block on the second consecutive non-qualifying iteration; attempts under the bounded packet-retry rule leave it unchanged. A `/imp` no-change result without a convincing already-satisfied explanation still blocks. A capped or blocked `/imp` run halts immediately; the sole exception permits at most two retries per item for defective lead packets that leave zero changed files, a clean tree, and no policy drift. Judgment skips under delegated rules are autonomous and evidence-backed; dropping a user-stated obligation requires user confirmation unless that judgment was delegated. The closing gate re-enumerates work within the recorded boundary and verifies required outcomes against the final tree. Its `allowed-tools` includes `git add`, `git commit`, `git status`, `git diff`, `git log`, `git rev-parse`, and `git merge-base` for the authorized commit protocol and read-only `gh issue list`, `gh issue view`, `gh pr list`, and `gh pr view` for discovery.
- Run artifacts accumulate under `${TMPDIR:-/tmp}` as `hybrid-council.*` and `hybrid-implement.*` directories; `hybrid-build` also keeps durable run state under the target repository's `<git-dir>/hybrid-build/` directory. Neither is deleted automatically.

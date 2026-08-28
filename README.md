# Council skills

Eight related multi-agent skills:

- **`council/`** — Codex skill (`$council`): a ten-subagent inquiry for any question, decision, plan, or investigation, critically synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the ten-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/q`): convenes three advisers — Fable, Opus, and the Codex `$council` via `scripts/run-codex-council.sh` — then synthesizes one answer.
- **`hybrid-review/`** — Claude Code skill (`/hybrid-review`): the code-review variant of `hybrid-council` — the same three advisers, with Codex running `$review-council` via the shared runner (`run-codex-council.sh --skill review-council`), synthesized into one severity-ordered review.
- **`hybrid-implement/`** — Claude Code skill (`/imp`): a write-enabled implement → review → fix loop. A single Codex session implements via `scripts/run-codex-implement.sh`, the `hybrid-review` procedure vets the initial change and high-risk fix rounds (the lead verifies routine fix deltas itself), and the Claude lead adjudicates findings, gates the final state by running checks on the final tree, and terminates the loop (at most five review rounds).
- **`literature-council/`** — Codex skill (`$literature-council`): a read-only ten-subagent scholarly search that returns deduplicated candidates, gaps, and lane-level saturation evidence.
- **`literature/`** — Codex skill (`$lit`): the Codex-native literature lead, with one coordinator subagent running `$literature-council` per round, one writer subagent, and `kb-audit.py` verification bracketing every write batch. It shares `kb-check.py`, `extract-pdf.py`, and `assets/kb-template` from `hybrid-literature/` through relative symlinks, so those resources must be relocated before the legacy directory is removed.
- **`hybrid-literature/`** — legacy Claude Code skill (`/lit`): kept frozen until the Codex-native path has passed a real run, after which its removal will be decided.

`hybrid-review`, `hybrid-implement`, and `hybrid-literature` reuse `hybrid-council`'s runner through in-repo relative symlinks (`scripts/run-codex-council.sh`), so the runner has a single source file.

## Install

Everything is discovered through symlinks; the repo is the single source of truth.

```sh
mkdir -p ~/.codex/skills ~/.claude/skills ~/.claude/agents

# Codex skills (~/.codex/skills is the tested location; newer Codex versions
# also discover user skills under ~/.agents/skills)
ln -sfn ~/repo/skills/council ~/.codex/skills/council
ln -sfn ~/repo/skills/review-council ~/.codex/skills/review-council
ln -sfn ~/repo/skills/literature-council ~/.codex/skills/literature-council
ln -sfn ~/repo/skills/literature ~/.codex/skills/lit

# Claude Code skills — hybrid-council, hybrid-implement, and hybrid-literature
# install under the short names `q`, `imp`, and `lit` (matching their SKILL.md
# `name` fields), so they are invoked as /q, /imp, and /lit
ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/q
ln -sfn ~/repo/skills/hybrid-review ~/.claude/skills/hybrid-review
ln -sfn ~/repo/skills/hybrid-implement ~/.claude/skills/imp
ln -sfn ~/repo/skills/hybrid-literature ~/.claude/skills/lit

# Claude Code adviser agents — required separately: Claude does not discover
# agents nested inside a skill directory
ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

`ln -sfn` makes the block safe to rerun: plain `ln -s` fails on an existing link and silently nests a new link inside an existing directory.

## Requirements

- Codex CLI on `PATH` (tested with 0.150.1). The council needs Codex's `multi_agent` feature, stable and on by default in 0.150.0 — check with `codex features list`; without it the council silently collapses to a single-model answer.
- `$lit` uses native subagents and needs stable, default-on `multi_agent`; do not enable `multi_agent_v2`. Set `[agents] max_concurrent_threads_per_session` to at least 12: the lead, coordinator, ten researchers, and writer use 13 of the 16 session slots provided by a setting of 15. Install the `literature-council` Codex symlink; without it the coordinator cannot load `$literature-council` and silently degrades to an improvised search.
- Every `$lit` spawn pins `model: gpt-5.6-luna` and `reasoning_effort: max` and sets `fork_turns: "none"`. Omitting `fork_turns` silently drops the model and effort pin. The pins are honored by the model, not enforced by a separate process; after the first real run, verify one child thread's model in its rollout file under `~/.codex/sessions/`.
- `hybrid-council` invokes the Codex `$council` skill and `hybrid-review` invokes `$review-council`, so the matching Codex symlinks above must also be installed; without them the Codex adviser degrades to a single-model answer.
- `hybrid-implement` needs the `hybrid-review` symlink (its review rounds follow that skill's document) and therefore `review-council` too.
- `hybrid-literature` needs the `literature-council` Codex symlink above and `uv` on `PATH`. Its scripts self-provision pinned Python packages; the first extraction-environment download is large, about 250 MB. `pdftotext` is the fallback PDF extractor.
- `$lit`'s `kb-audit.py` needs only Python 3 and the standard library. Its shared `kb-check.py` and `extract-pdf.py` retain the existing `uv` requirement.
- Ten parallel subagents need `[agents] max_concurrent_threads_per_session` of at least 10 in `~/.codex/config.toml`.
- The general council and implementation runners default to `gpt-5.6-sol`; override per run with `CODEX_COUNCIL_MODEL` (`run-codex-council.sh`) or `CODEX_IMPLEMENT_MODEL` (`run-codex-implement.sh`). Direct `$council` and `$review-council` invocations use the active Codex model.
- Literature work uses `gpt-5.6-luna` at maximum reasoning effort for both the ten-subagent council and writer. The legacy hybrid council pin ignores `CODEX_COUNCIL_MODEL`; its writer permits the single `CODEX_INGEST_MODEL` override.
- Scite is optional for literature discovery. Connect it once — the Scite Codex app, or `codex mcp add` plus `codex mcp login scite` — and every Codex agent in the council, subagents included, gets its tools.
- Read-only is enforced by instruction, not by sandboxing: the script runs Codex with full access (so subagents have network and web search), the Claude advisers keep Bash, and every adviser is told not to change anything.
- `$lit`'s native subagents inherit the interactive session's sandbox and tool surface; their read-only and write-scope rules remain instruction-enforced.
- `run-codex-council.sh` reports `STATUS=ok|failed`; `SUBAGENTS=<n|unknown>` carries completeness: `10` is a full council, below ten is partial (`0` means no council ran), and `unknown` means the count is unconfirmed. The count derives from a model-reported `COUNCIL_SUBAGENTS=<n>` sentinel line the script asks for in the answer, so even `10` is self-reported, not independently verified. Resumed follow-ups always report `unknown` because completeness is not re-checked.
- `run-codex-implement.sh` is write-enabled and also runs Codex with full access; there is no sandbox — instructions restrict the work, and git detects drift rather than prevents it: new runs require a clean tree on the current branch (override with `HYBRID_IMPLEMENT_ALLOW_DIRTY=1`), the prompt forbids all git and remote operations, and the script verifies the outcome against git — `STATUS=ok|no-change|degraded|unverified|failed`, with `POLICY_VIOLATION` flagging a moved HEAD, switched branch, or staged changes, `CHANGED_FILES` counting files changed against the baseline commit (tracked plus untracked), and a `PATCH_FILE` diff. A partial, blocked, or tests-failed self-report lands on `degraded`; a missing or malformed `IMPLEMENT_TESTS` sentinel on a changed round lands on `unverified`; `ok` and `no-change` describe the round just run while `CHANGED_FILES` remains cumulative. `IMPLEMENT_STATUS`/`IMPLEMENT_TESTS` sentinels remain self-reported. Codex never commits, and the lead commits only when the user asks; the work lands on whatever branch is checked out.
- `run-codex-ingest.sh` is also write-enabled under `danger-full-access` and restricted by instruction rather than a sandbox. It reports `STATUS=ok|no-change|degraded|unverified|failed`, filesystem-verified paper and KB-file counts, and `POLICY_VIOLATION` for detectable writes outside the KB or repository drift.
- Run artifacts accumulate under `${TMPDIR:-/tmp}` as `hybrid-council.*`, `hybrid-implement.*`, and `hybrid-literature.*` directories; nothing deletes them automatically.

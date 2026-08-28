# Council skills

Five related skills for convening multi-agent councils:

- **`council/`** — Codex skill (`$council`): a ten-subagent inquiry for any question, decision, plan, or investigation, critically synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the ten-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/hybrid-council`): convenes three advisers — Fable, Opus, and the Codex `$council` via `scripts/run-codex-council.sh` — then synthesizes one answer.
- **`hybrid-review/`** — Claude Code skill (`/hybrid-review`): the code-review variant of `hybrid-council` — the same three advisers, with Codex running `$review-council` via the shared runner (`run-codex-council.sh --skill review-council`), synthesized into one severity-ordered review.
- **`hybrid-implement/`** — Claude Code skill (`/hybrid-implement`): a write-enabled implement → review → fix loop. A single Codex session implements via `scripts/run-codex-implement.sh`, the `hybrid-review` procedure vets the initial change and high-risk fix rounds (the lead verifies routine fix deltas itself), and the Claude lead adjudicates findings, gates the final state by running checks on the final tree, and terminates the loop (at most five review rounds).

`hybrid-review` and `hybrid-implement` reuse `hybrid-council`'s runner through in-repo relative symlinks (`scripts/run-codex-council.sh`), so the runner has a single source file.

## Install

Everything is discovered through symlinks; the repo is the single source of truth.

```sh
mkdir -p ~/.codex/skills ~/.claude/skills ~/.claude/agents

# Codex skills (~/.codex/skills is the tested location; newer Codex versions
# also discover user skills under ~/.agents/skills)
ln -sfn ~/repo/skills/council ~/.codex/skills/council
ln -sfn ~/repo/skills/review-council ~/.codex/skills/review-council

# Claude Code skills
ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/hybrid-council
ln -sfn ~/repo/skills/hybrid-review ~/.claude/skills/hybrid-review
ln -sfn ~/repo/skills/hybrid-implement ~/.claude/skills/hybrid-implement

# Claude Code adviser agents — required separately: Claude does not discover
# agents nested inside a skill directory
ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

`ln -sfn` makes the block safe to rerun: plain `ln -s` fails on an existing link and silently nests a new link inside an existing directory.

## Requirements

- Codex CLI on `PATH` (tested with 0.150.1). The council needs Codex's `multi_agent` feature, stable and on by default in 0.150.0 — check with `codex features list`; without it the council silently collapses to a single-model answer.
- `hybrid-council` invokes the Codex `$council` skill and `hybrid-review` invokes `$review-council`, so the matching Codex symlinks above must also be installed; without them the Codex adviser degrades to a single-model answer.
- `hybrid-implement` needs the `hybrid-review` symlink (its review rounds follow that skill's document) and therefore `review-council` too.
- Ten parallel subagents need `[agents] max_concurrent_threads_per_session` of at least 10 in `~/.codex/config.toml`.
- The Codex model defaults to `gpt-5.6-sol` in both runners; override per run with `CODEX_COUNCIL_MODEL` (`run-codex-council.sh`) or `CODEX_IMPLEMENT_MODEL` (`run-codex-implement.sh`). Direct `$council` and `$review-council` invocations use the active Codex model.
- Read-only is enforced by instruction, not by sandboxing: the script runs Codex with full access (so subagents have network and web search), the Claude advisers keep Bash, and every adviser is told not to change anything.
- `run-codex-council.sh` reports `STATUS=ok|failed`; `SUBAGENTS=<n|unknown>` carries completeness: `10` is a full council, below ten is partial (`0` means no council ran), and `unknown` means the count is unconfirmed. The count derives from a model-reported `COUNCIL_SUBAGENTS=<n>` sentinel line the script asks for in the answer, so even `10` is self-reported, not independently verified. Resumed follow-ups always report `unknown` because completeness is not re-checked.
- `run-codex-implement.sh` is write-enabled and also runs Codex with full access; there is no sandbox — instructions restrict the work, and git detects drift rather than prevents it: new runs require a clean tree on the current branch (override with `HYBRID_IMPLEMENT_ALLOW_DIRTY=1`), the prompt forbids all git and remote operations, and the script verifies the outcome against git — `STATUS=ok|no-change|degraded|unverified|failed`, with `POLICY_VIOLATION` flagging a moved HEAD, switched branch, or staged changes, `CHANGED_FILES` counting files changed against the baseline commit (tracked plus untracked), and a `PATCH_FILE` diff. A partial, blocked, or tests-failed self-report lands on `degraded`; a missing or malformed `IMPLEMENT_TESTS` sentinel on a changed round lands on `unverified`; `ok` and `no-change` describe the round just run while `CHANGED_FILES` remains cumulative. `IMPLEMENT_STATUS`/`IMPLEMENT_TESTS` sentinels remain self-reported. Codex never commits, and the lead commits only when the user asks; the work lands on whatever branch is checked out.
- Run artifacts accumulate under `${TMPDIR:-/tmp}` as `hybrid-council.*` and `hybrid-implement.*` directories; nothing deletes them automatically.

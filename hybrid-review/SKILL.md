---
name: hybrid-review
description: Run an explicitly requested three-voice code review — a Fable reviewer, an Opus reviewer, and the Codex ten-agent review council — then critically verify and synthesize only the findings worth reporting.
disable-model-invocation: true
effort: high
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh *)
---

# Hybrid Review

Act as the lead reviewer. Three independent voices gather evidence; you own the final judgment. Stay in the main conversation — do not run this skill or its synthesis inside a subagent.

The entire review is strictly read-only: no changes to the project, system state, or external services by you or any voice. The sole exception is the skill's own temporary orchestration artifacts — the review packet, follow-up files, and the script's run directory and session metadata. Read-only is enforced by instruction, not by sandboxing: no voice is sandboxed, every voice keeps Bash and network access, and each is trusted to comply. The deliverable is findings and recommendations only.

## Review

1. Establish the review target and baseline, and state what you chose:
   - A target the user names takes precedence, reviewed against the baseline they give, or as a standalone audit when none applies.
   - Otherwise review the current branch's work: its changes since the merge base with the repository's default branch (or the pull request's base branch when one exists), together with any staged, unstaged, and untracked changes.
   - If neither yields a target, say there is nothing to review and ask for one.
   Inspect the change yourself before delegating so the packet reflects its actual risk surface.
2. Write one review packet to a temp file: the target and baseline as exact refs or commits, the change's intent or specification when known, the scope including staged, unstaged, and untracked work, anything out of scope, and any previously rejected findings with their reasons — a voice must not re-raise those without new evidence. Require precise evidence for every candidate finding: location, triggering conditions, failure mode, and concrete impact; an explicit "no findings" beats filler. The script prepends the `$review-council` invocation, the advisory framing, and the status-sentinel instruction, so the packet needs no preamble. Every voice receives this same packet; none may see another voice's answer before finishing.
3. Dispatch all three voices in parallel, in a single block:
   - Spawn the `council-fable` agent with the packet, asking for its complete, independent review.
   - Spawn the `council-opus` agent with the same packet and the same ask.
   - Run the script as a background Bash command — foreground commands are capped at ten minutes and review runs often exceed that. Example, with the packet at `/tmp/review-packet-<unique-suffix>.md` (pick a fresh suffix per run so concurrent reviews cannot clobber each other) and the repository under review as the last argument (defaults to the current directory):
     `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh --skill review-council /tmp/review-packet-<unique-suffix>.md /path/to/project`
   Runtime scales with the change: minutes for a small diff, hours for a large or risky one. That is expected — wait for every voice, and never impose a timeout, kill, or restart a voice merely because it is slow.
4. Collect all three results. The script prints `STATUS`, `SUBAGENTS`, `RESULT_FILE`, `LOG_FILE`, and `SESSION_ID` lines; Read `RESULT_FILE` for the Codex review rather than relying on command output. Honor `STATUS`: `degraded` means fewer than ten Codex subagents completed — `SUBAGENTS` gives the count, and `0` means no council ran and the review is a single model's; `unverified` means the review is usable but the subagent count could not be confirmed — use it normally, without claiming a full or partial council; `failed` means there is no usable Codex review — the script prints an `ERROR` line and the last log lines. Ignore the trailing `COUNCIL_SUBAGENTS=` line in the result; it is the script's status contract, not content.
5. Follow up only when clarification would materially improve the review: message the same Claude agents, or write the follow-up to its own temp file and run `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh resume <SESSION_ID> <follow-up-file>`. A resume always reports `unverified` because council completeness is not re-checked. If `SESSION_ID` is `unknown`, skip the Codex follow-up.
6. Treat every candidate finding as a lead, not a vote. Independently inspect the cited code and contracts and decide whether each is correct and material; discard duplicates, style preferences, unsupported hypotheticals, pre-existing problems outside scope, and claims that do not survive verification; consolidate related symptoms under their underlying cause. The two Claude voices share a model family, so their agreement is weak confirmation; agreement across families — a Claude voice and the Codex council — is stronger evidence, and any disagreement is a cue to check the primary artifact yourself. Confirm the target did not change while the review ran; if it did, say so and scope the review to what was actually examined.
7. Return your own review, ordered by severity. Lead with actionable findings, cite exact files and lines when available, and explain triggering conditions and concrete impact succinctly. If no finding survives, say so plainly and mention residual risk or testing gaps only when material. Do not expose transcripts, per-voice rollups, or vote counts.

If a voice fails or comes back degraded, say so plainly and label the result as a partial review; never silently present fewer voices as the full council.

---
name: review-council
description: Run an explicitly requested, ten-agent review of code or other changes, then critically verify and synthesize only the findings worth reporting.
---

# Review Council

Act as the lead reviewer. The ten subagents gather evidence; you own the final judgment.

The entire review is strictly read-only: neither you nor any subagent may modify files, system state, or remote services, and every subagent must be told so. The deliverable is findings and recommendations only.

## Review

1. Establish the review target and baseline from the user's request and repository state, and state what you chose:
   - A target the user names takes precedence, reviewed against the baseline they give, or as a standalone audit when none applies.
   - Otherwise review the current branch's work: its changes since the merge base with the repository's default branch (or the pull request's base branch when one exists), together with any staged, unstaged, and untracked changes.
   - If neither yields a target, say there is nothing to review and ask for one.
   Inspect the change before delegating so assignments reflect its actual risk surface.
2. Spawn exactly ten subagents. Run them in parallel when practical, give each a concrete review assignment chosen for this change, and tell them not to delegate further. Choose the mix of independent, overlapping, specialized, and cross-cutting passes that best fits the target; do not apply a fixed role checklist mechanically.
3. Give every subagent enough scope, baseline, and intent to inspect primary artifacts itself. Require precise evidence for each candidate finding: location, failure mode, impact, and the reasoning or reproduction that makes it actionable. Encourage an explicit "no findings" result rather than filler.
4. Collect all ten results and treat them as leads, not votes. Independently inspect the relevant code and contracts, use targeted checks when useful, and decide whether each candidate is correct and material. Discard duplicates, style preferences, unsupported hypotheticals, pre-existing problems outside scope, and claims that do not survive verification; consolidate related symptoms under their underlying cause.
5. Return your own review, ordered by severity. Lead with actionable findings and cite exact files and lines when available. Explain the triggering conditions and concrete impact succinctly. Do not expose subagent transcripts, vote counts, or internal assignments. If no finding survives, say so plainly and mention residual risk or testing gaps only when material.

If ten subagents cannot be run, state that the requested council review could not be completed instead of silently presenting a smaller review as equivalent. You may still provide a clearly labeled best-effort review when useful.

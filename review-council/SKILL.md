---
name: review-council
description: Run an explicitly requested, ten-agent review of code or other changes, then critically verify and synthesize only the findings worth reporting.
---

# Review Council

Act as the lead reviewer. The ten subagents gather evidence; you own the final judgment.

## Review

1. Establish the review target and baseline from the user's request and repository state. Inspect the change before delegating so assignments reflect its actual risk surface. Keep the work read-only unless the user separately asks for fixes.
2. Spawn exactly ten subagents. Run them in parallel when practical, give each a concrete review assignment chosen for this change, and tell them not to edit files or delegate further. Choose the mix of independent, overlapping, specialized, and cross-cutting passes that best fits the target; do not apply a fixed role checklist mechanically.
3. Give every subagent enough scope, baseline, and intent to inspect primary artifacts itself. Require precise evidence for each candidate finding: location, failure mode, impact, and the reasoning or reproduction that makes it actionable. Encourage an explicit “no findings” result rather than filler.
4. Collect all ten results. Treat them as leads, not votes. Independently inspect the relevant code and contracts, use targeted checks when useful, and decide whether each candidate is correct and material.
5. Discard duplicates, style preferences, unsupported hypotheticals, pre-existing problems outside scope, and claims that do not survive verification. Consolidate related symptoms under their underlying cause.
6. Return your own review, ordered by severity. Lead with actionable findings and cite exact files and lines when available. Explain the triggering conditions and concrete impact succinctly. Do not expose subagent transcripts, vote counts, or internal assignments. If no finding survives, say so plainly and mention residual risk or testing gaps only when material.

If ten subagents cannot be run, state that the requested council review could not be completed instead of silently presenting a smaller review as equivalent.

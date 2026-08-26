---
name: council
description: Coordinate an explicitly requested ten-agent inquiry for any question, decision, plan, investigation, or review, then produce one critically synthesized answer.
---

# Council

Act as the lead. The ten subagents expand the inquiry; you own the reasoning and final answer.

## Convene the council

1. Interpret the user's actual objective, constraints, and desired deliverable. Inspect enough of the available context to identify the task's uncertainty and choose useful assignments.
2. Spawn exactly ten subagents. Run them in parallel when practical, give each a concrete assignment chosen for this task, and tell them not to delegate further. Decide dynamically whether to divide the problem, seek independent solutions, test competing hypotheses, research evidence, challenge assumptions, or combine these approaches. Avoid ten interchangeable prompts unless replication itself is useful.
3. Give each subagent the context it needs and freedom to investigate within the user's scope. Ask for concise conclusions supported by reasoning and evidence, with uncertainty or disagreement stated plainly. Keep subagents read-only; council use does not authorize mutations or external actions beyond the user's request.
4. Collect all ten results. Follow up with the same subagents when clarification or targeted investigation would materially improve the answer. Independently check consequential claims against primary artifacts or authoritative sources when possible.
5. Treat the results as advisory context, not votes. Reconcile contradictions; discard errors, duplicates, weak speculation, and irrelevant material. Consensus is not proof, and a valuable minority view should survive when its evidence is stronger.
6. Produce one answer in your own voice, shaped to the original task. Lead with your conclusion and include the reasoning, evidence, options, caveats, or next steps that materially help the user. Do not expose transcripts, assignments, vote counts, or a rollup of what each subagent said. Preserve unresolved uncertainty when the evidence does not justify a single confident answer.

If ten subagents cannot be run, say that the requested council could not be completed instead of silently presenting a smaller effort as equivalent. You may still provide a clearly labeled best-effort answer when useful.

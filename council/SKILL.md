---
name: council
description: Coordinate an explicitly requested ten-agent inquiry for any question, decision, plan, or investigation, then produce one critically synthesized answer.
---

# Council

Act as the lead. The ten subagents expand the inquiry; you own the reasoning and final answer.

The entire council is strictly read-only: neither you nor any subagent may modify files, system state, or remote services, and every subagent must be told so. The deliverable is analysis and advice only.

## Convene the council

1. Interpret the user's actual objective, constraints, and desired deliverable. Inspect enough of the available context to identify the task's uncertainty and choose useful assignments.
2. Spawn exactly ten subagents. Run them in parallel when practical, give each a concrete assignment chosen for this task, and tell each one not to delegate further. Choose assignments dynamically — divide the problem, pursue independent solutions, test competing hypotheses, or challenge assumptions as the task warrants. Avoid ten interchangeable prompts unless replication itself is useful.
3. Give each subagent the context it needs and freedom to investigate within the user's scope. Ask for concise conclusions supported by reasoning and evidence, with uncertainty or disagreement stated plainly.
4. Collect all ten results. Follow up with the same subagents when clarification or targeted investigation would materially improve the answer. Independently check consequential claims against primary artifacts or authoritative sources when possible.
5. Treat the results as leads, not votes. The subagents share one model and one packet, so repetition adds no support: judge each claim by its reasoning and its grounding in primary artifacts, and settle contradictions on the evidence. Discard errors, duplicates, weak speculation, and irrelevant material. Agreement is not verification, and a well-supported conclusion should survive even when only one subagent reaches it.
6. Produce one answer in your own voice, shaped to the original task. Lead with your conclusion and include the reasoning, evidence, options, caveats, or next steps that materially help the user. Do not expose transcripts, assignments, vote counts, or a rollup of what each subagent said. Preserve unresolved uncertainty when the evidence does not justify a single confident answer.

If ten subagents cannot be run, say that the requested council could not be completed instead of silently presenting a smaller effort as equivalent. You may still provide a clearly labeled best-effort answer when useful.

---
name: build
description: Complete a substantial file-based task through coherent commits, independent Codex and Claude reviews, and adaptive planning.
---

# Build

Act as the lead. Own task interpretation, work selection, review judgments, and commits. The user's request defines the deliverable and scope. Invoking this skill authorizes local commits within that scope; it does not authorize pushing or publishing.

Before implementation, establish the requested outcome, scope, and constraints. Ask the user only about unresolved questions that materially affect what should be delivered and cannot reasonably be answered from the available context. If the request is already clear, proceed directly.

Once the task is understood, carry it through implementation, review, fixes, and commits autonomously. Own the implementation approach, work decomposition, milestones, validation, and routine tradeoffs. Investigate unexpected problems and adapt within the agreed scope without seeking approval for those decisions.

Keep the user's overall goal and constraints in view throughout the task. Maintain a general approach to completing that goal, choose the next meaningful part to complete, and plan its next coherent commit in detail. Develop and revise the approach as the work reveals more information; leave later implementation details open until they become relevant. Planning is your own reasoning and coordination: do not create workflow planning documents or seek approval for plans, work decomposition, or routine implementation decisions.

## Work loop

1. Choose the next coherent increment that advances the current substantial part toward the overall goal. Make it small enough to review as one commit and substantial enough to produce a coherent result. Determine its intended outcome, implementation approach, and appropriate validation.
2. Assign one Codex subagent to implement it and run that validation. Give it the necessary context and boundaries. It must not commit. Keep only one writer active at a time.
3. Run the review process below on the resulting changes.
4. After accepted findings are resolved and required validation passes, commit the reviewed task changes, preserving unrelated work. Create no empty commits.
5. Reassess progress toward the current substantial part and overall goal. Choose the next increment, review a completed milestone, or begin final review.

Treat each substantial part as a milestone, choosing its scope from the task. After each commit, reassess what remains to complete it. When it is complete, review its cumulative result and interactions before choosing the next substantial part. Revise these boundaries when the work warrants it.

Before declaring completion, review the whole task's result and verify all requested outcomes, including omissions. Use the same review process for milestone and final reviews and commit resulting fixes before proceeding. Broader reviews remain bounded by the user's task.

## Review process

Keep the target unchanged until all reviews finish. Supply the task, intended outcomes, exact review boundary, and relevant context. For increments, include staged, unstaged, and relevant untracked changes. For milestone and final reviews, identify the starting baseline and current endpoint and inspect the completed artifacts as well as their cumulative changes.

For every full review round, spawn 10 new Codex review subagents with fresh contexts, orchestrating them and assigning focus areas as you see fit. Give at least one reviewer the entire target. Supply the task, current target, and necessary context without prior reviewer conclusions; keep review history with the lead for adjudication. Require independent, read-only reviews with concrete findings, evidence, and impact; reviewers must not delegate further.

Also start a fresh Claude session in the project directory for every full review round. Supply the current task and target without prior reviewer conclusions. Substitute the actual context and target into this template before execution:

```sh
claude --model fable --effort high -p <<'REVIEW'
Task and completion criteria: [insert actual context].
Review target: [insert exact changes, baseline, endpoint, and artifact scope].

Review this target and the surrounding context needed to assess it.
Spawn three new independent general-purpose subagents: one with model fable
to review the entire target, and two with model opus whose focus areas
you choose. Explicitly select those models when spawning.

You and all reviewers must remain read-only. Give each reviewer the
task and review target. Reviewers must not delegate further. Wait for
all three reviews, then independently verify their findings against
the actual work.

Return issues you judge correct, within scope, and worth fixing, with
precise locations, evidence, and impact. Combine duplicates. State
when no findings survive, and disclose any incomplete review.
REVIEW
```

Judge every finding yourself against the actual work and task. Combine duplicates and decide whether each finding is correct, within scope, and worth fixing. Agreement is not evidence. Retain brief reasons for material rejections so later rounds can reconsider them when new evidence warrants it.

Assign one implementation subagent to fix accepted findings and run appropriate validation. Repeat the full review process after fixing accepted findings, unless all accepted findings in that round were minor and their fixes are straightforward, localized, and can be confidently verified through direct inspection and appropriate checks. In that case, inspect and verify the fixes without another full review round. If verification reveals a broader problem or leaves material uncertainty, repeat the full review. Judge severity and fix complexity yourself.

Finish a review only when no accepted finding remains unresolved and required validation passes. Investigate and resolve recoverable failures autonomously, and continue useful work within scope. Report missing reviews, unavailable checks, or stalled progress honestly; incomplete verification is not a passed review. If an essential blocker prevents completion, report what remains and why; do not present partial work as complete. Finish with the completed outcome, relevant validation, and any unresolved limitations.

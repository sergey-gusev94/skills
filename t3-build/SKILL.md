---
name: t3-build
description: Complete a substantial file-based task in T3 Code through Opus-implemented commits, each reviewed by an Opus workflow and Sol- and Astra-led Codex reviews.
disable-model-invocation: true
---

# T3 Build

Act as the lead. Own task interpretation, work selection, review judgments, and commits. The user's request defines the deliverable and scope. Invoking this skill authorizes local commits within that scope and the review workflows below; it does not authorize pushing or publishing.

This skill requires a T3 Code thread with the `t3-code` orchestration tools and the Workflow tool. If either is unavailable, tell the user and stop.

## Roles

- **Implementer:** one native subagent with model `opus`. It is the only writer and never commits.
- **Opus review:** a Workflow whose agents all use model `opus`.
- **Codex reviews:** one `delegate_task` each with provider `codex` and `reasoningEffort` `high`: Sol uses model `gpt-6.1-sol`, Astra uses `gpt-6-astra`.

## Approach

Before implementation, establish the requested outcome, scope, and constraints. Ask the user only about unresolved questions that materially affect what should be delivered and cannot reasonably be answered from the available context. If the request is already clear, proceed directly.

Once the task is understood, carry it through implementation, review, fixes, and commits autonomously. Own the implementation approach, work decomposition, milestones, validation, and tradeoffs without seeking approval. Resolve decisions, open questions, and unexpected problems that arise during the work yourself: investigate the code, documentation, and other available context, choose the option that best serves the user's goal within the agreed scope, and note significant choices for the final report. Ask the user only when a question cannot be resolved without them: the answer would materially change the deliverable or scope and the available context does not settle it, or the next step needs authorization beyond this skill. Then ask concisely with your recommendation, and continue any work the question does not block. Keep the overall goal in view, plan the next commit in detail, and leave later details open until they become relevant. Do not create workflow planning documents.

## Work loop

1. Choose the next coherent increment. Make it small enough to review as one commit and substantial enough to justify a full review round. Determine its intended outcome, implementation approach, and validation.
2. Have the implementer build it and run that validation. Give it the necessary context and boundaries. Continue the same implementer with `SendMessage` while its context stays useful; start a fresh one when its context grows large or the work shifts substantially. Keep only one writer active at a time.
3. Run the review process below on the resulting changes.
4. After accepted findings are resolved and required validation passes, commit the reviewed task changes, preserving unrelated work. Create no empty commits.
5. Reassess progress. Choose the next increment, review a completed milestone, or begin final review.

Treat each substantial part of the task as a milestone. When one is complete, review its cumulative result and interactions before starting the next. Before declaring completion, review the whole task's result and verify all requested outcomes, including omissions. Milestone and final reviews use the same review process, stay bounded by the user's task, and their fixes are committed before proceeding.

## Review process

Supply every reviewer with the task, intended outcomes, exact review boundary, and relevant context. For increments, include staged, unstaged, and relevant untracked changes. For milestone and final reviews, identify the starting baseline and current endpoint, and include the completed artifacts as well as their cumulative changes. Do not pass on other reviewers' conclusions. In later rounds of the same target, list the significant findings you rejected and why, so reviewers raise them again only with new evidence.

All reviewers must stay read-only and return concrete findings with precise locations, evidence, and impact, or state that they found none. Record `git status` and the diff before starting, and keep the target unchanged until every review finishes. If the tree changed during review, stop and report it to the user.

For every full review round, start these three reviews in parallel:

1. **Opus workflow.** Write a review Workflow suited to this target. Choose its review dimensions and number of agents in proportion to the change's size and risk, give at least one agent the entire target, and have findings verified before the workflow returns them. Set `model: 'opus'` on every agent. You may rerun an earlier review workflow's `scriptPath` with new `args` when it fits.
2. **Sol and Astra.** Delegate one review to each with `mode: async`, `role: review`, and a new `clientRequestId` per reviewer for each round. Tell each to plan its own review, start fresh, independent subagents on its own model, with their number proportional to the target's size and risk, give at least one of them the entire target, then verify their findings against the actual work and return only those it judges correct and worth fixing.

Completion of the workflow and the delegated tasks notifies you; inspect the target yourself while waiting. Wait for all reviews before adjudicating. Rerun a failed review once; if it fails again, continue but report the missing review as incomplete verification.

Judge every finding yourself against the actual work and task. Combine duplicates and decide whether each finding is correct, within scope, and worth fixing. Agreement is not evidence. After the first round of a target, accept only clear defects and regressions, not re-litigated decisions or scope growth; note worthwhile improvement ideas for the final report.

Send all accepted findings to the implementer as one fix batch and have it run appropriate validation. Repeat the full review round after fixes, unless every accepted finding was minor and its fix is straightforward, localized, and confidently verifiable by your own inspection and checks. If that verification reveals a broader problem or leaves material uncertainty, run the full review round.

Finish a review only when no accepted finding remains unresolved and required validation passes. Investigate and resolve recoverable failures autonomously. Report missing reviews, unavailable checks, or stalled progress honestly; incomplete verification is not a passed review. If an essential blocker prevents completion, report what remains and why; do not present partial work as complete. Finish with the completed outcome, commits made, relevant validation, deferred improvement ideas, and any unresolved limitations.

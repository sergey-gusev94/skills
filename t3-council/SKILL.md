---
name: t3-council
description: Use whenever the user asks to use, ask, or consult the council. Four advisers on different models (Opus, Fable, Sol, Astra) work on the same request, and a Fable synthesizer combines their answers into one result for you.
user-invocable: false
---

# T3 Council

The council gives you advice; it does not make your decisions. The user's request may be a question, an investigation such as a bug hunt, a plan for a feature, a scored evaluation, or anything else. Four advisers work on it independently. A synthesizer then combines their answers into one result, which comes back to you. You stay responsible for the task: check the result, act on it, or report it to the user as the situation requires.

This skill requires a T3 Code thread with the `t3-code` orchestration tools. If they are unavailable, tell the user and stop.

## Roles

Start every role with `delegate_task`, `mode: async`, and a new `clientRequestId`, with these targets:

| Role | Provider | Model | Option |
| --- | --- | --- | --- |
| Opus adviser | `claudeAgent` | `claude-opus-5-5` | `effort: high` |
| Fable adviser | `claudeAgent` | `claude-fable-5-2` | `effort: high` |
| Sol adviser | `codex` | `gpt-6.2-sol` | `reasoningEffort: high` |
| Astra adviser | `codex` | `gpt-6.2-astra` | `reasoningEffort: high` |
| Synthesizer | `claudeAgent` | `claude-fable-5-2` | `effort: high` |

The council is read-only. Tell every adviser and the synthesizer not to change files, system state, or external services.

## Procedure

1. Write one brief: the user's request in their words, its objective and the form of the deliverable (for example a bug report, a recommendation, or a filled-in score table), the constraints, the decisions already settled, and pointers to the relevant files and evidence. Do not include your own conclusions, so the advisers stay independent.
2. Start the four advisers in parallel. Give each the same brief and ask for its complete answer, with reasoning, evidence, and stated uncertainty.
3. Wait for all four. Do not poll; each completion notifies you. If an adviser fails, start it once more. If it fails again, continue without it.
4. Start the synthesizer. Give it the brief and the four answers verbatim, labelled by adviser, and name any adviser that failed. Tell it to treat the answers as evidence, not authority: verify consequential claims against primary sources, settle disagreements on the evidence rather than by majority, keep a well-supported point even if only one adviser made it, discard errors, and add anything it finds that all advisers missed. It returns one final answer in the form the brief requests.
5. Treat the synthesized answer as advice. Verify it to the degree the task's stakes require, then use it in your work or give it to the user. Report any adviser that failed.

# Build progress

## Run state

- State: <running | done | capped | blocked>
- Branch: <branch>
- Loop-baseline commit (immutable): <SHA>
- Current-baseline commit (advance after each loop commit or adopted descendant): <SHA>
- Scope source path (or conversational origin): <source>
- Recorded scope hash (from `sha256sum scope.md` in the state directory): <SHA-256>

## Dependency-ordered checklist

Use one state per item: `pending`, `in-progress`, `done@<commit>`, `dropped: <reason>`, or `satisfied-by-prior-work: <evidence>`. Record user confirmation for every drop.

| Item | Description | Dependencies | State | Evidence, reason, or user confirmation |
| --- | --- | --- | --- | --- |
| <ID> | <coherent increment> | <IDs or none> | pending | |

## Iteration log

| Item | One-line description | `/imp` ending state | Commit SHA | Checks run and results |
| --- | --- | --- | --- | --- |

Record checklist changes and reasons, adopted non-loop commit ranges marked out of scope, and retained unverified loop work or gate-finding work here.

## Closing-gate findings

| Round | Finding | Adjudication and reason | Outcome |
| --- | --- | --- | --- |

Record each closing round and outcome, including rounds with no findings.

## Amendment log

| Amendment | User authorization | Reason |
| --- | --- | --- |

## Cross-iteration rejected-findings digest

| Finding ID | Finding | Rejection reason and evidence |
| --- | --- | --- |

## Deferred out-of-scope ideas

| Idea | Reason deferred |
| --- | --- |

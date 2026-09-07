# Build progress

## Run state

- State: <running | done | capped | blocked>
- Branch: <branch>
- Loop-baseline commit (immutable): <SHA>
- Current-baseline commit (advance after each loop commit or adopted descendant): <SHA>
- Scope source path (or conversational origin): <source>
- Recorded scope hash (from `sha256sum scope.md` in the state directory): <SHA-256>

## Discovery record

- Obligation enumeration: <listed directly, or rule-defined instances to discover; reproducible procedure>
- Sources and boundary examined: <sources, limits, and observed candidate set; not yet observed if discovery is pending>
- Observation time or equivalent: <time, snapshot, or revision>
- Remaining or continuing discovery: <required work and ordering; absent contrary instructions, state the initial inventory within this boundary as the coverage assumption>
- Changing eligibility facts: <facts to revalidate when selecting work>

## Work queue

Use stable, never-reused IDs: retire items by state, never delete or renumber them, because commit subjects and reconciliation match on these IDs. Use one state per item: `pending`, `in-progress`, `done@<commit>`, `satisfied-by-prior-work: <evidence>`, `completed-by-investigation: <evidence>`, `skipped: <evidence>`, `dropped: <reason>`, `blocked: <cause>`, or `merged-into: <ID>`. When splitting an item, retain its ID for one successor and add fresh IDs for the others; record the relationship and preserve its obligations. A merge retires the source item as `merged-into: <ID>` and transfers its obligations and dependencies to the successor.

Use `completed-by-investigation: <evidence>` only for discovery and investigation items whose knowledge, inventory, or disposition deliverable the lead completed read-only. Use `satisfied-by-prior-work: <evidence>` only for an implementation obligation confirmed already satisfied by a completed `/imp` run with a convincing no-change result; a lead-only conclusion cannot retire that obligation. Record evidence and the delegated rule for autonomous judgment skips; record user confirmation for dropping a user-stated obligation where the drop rule requires it. Park an item as `blocked: <cause>` while it awaits a user decision, an external prerequisite, or a dependency outside the run's authority and independent work remains; before selection, including after resumption, return it to `pending` when its cause is resolved and log the resolution as evidence. Retirements must preserve traceability, and every candidate must retain a supported disposition for the closing gate and final report.

| Item ID | Description and mandate trace | Dependencies | State | Evidence, reason, delegated rule, or user confirmation |
| --- | --- | --- | --- | --- |
| <ID> | <discovery work or coherent increment; obligation or rule> | <IDs or none> | pending | |

## Iteration log

`/imp` ending states (when run): `clean`, `minor-fixed`, `capped`, or `blocked`.

| Iteration / packet directory | Item ID | Decision or work | `/imp` ending state (if run) | Commit SHA or disposition evidence | Checks run and results |
| --- | --- | --- | --- | --- | --- |

Record every addition, split, merge, reorder, and retirement with its evidence; include discovery and triage dispositions, material approach decisions, and removed disposable artifacts with their attribution. Record adopted non-loop commit ranges marked out of scope and retained unverified loop work or gate-finding work here.

- Consecutive non-qualifying iterations: <0 | 1 | 2; reset on a qualifying iteration, block at 2; update with every iteration outcome, including read-only work, except packet-retry attempts leave the counter unchanged>
- Packet retries per item: <ID, retry count up to 2, defect, zero-changed-files and clean-tree evidence, correction, and fresh packet directory for each retry>

## Closing-gate findings

| Round | Finding | Adjudication and reason | Outcome |
| --- | --- | --- | --- |

Record each closing round and outcome, including rounds with no findings; include re-enumeration coverage, supported dispositions, and final-tree verification evidence for required outcomes and accepted items.

## Amendment log

Record only genuine user-authorized mandate changes; investigation results, work queue decisions, and judgments under delegated rules belong above. Never edit the frozen `scope.md`.

| Amendment | User authorization | Reason |
| --- | --- | --- |

## Cross-iteration rejected-findings digest

| Finding ID | Finding | Rejection reason and evidence |
| --- | --- | --- |

## Deferred out-of-scope ideas

| Idea | Reason deferred |
| --- | --- |

# Global instructions

In all work, prefer the simplest robust solution that fully addresses the problem, and add complexity only when something concrete requires it. Simplify the solution, not the diligence: keep the investigation, caveats, and safeguards the task needs.

## Clear writing

Apply these rules to all prose you author, regardless of format.

- Write for the intended reader in plain, direct language. Make the main point easy to find.
- Prefer familiar, precise words. Use established technical terms when they are clearer or more accurate, and explain unfamiliar terms when needed.
- Use established names consistently. Do not change terminology merely for variety.
- Keep sentences focused, and make actors and actions clear.
- Simplify the wording, not the substance. Preserve information needed for correctness, including material facts, distinctions, caveats, uncertainty, and exact names or identifiers. Remove filler and repetition first.

## Software engineering

- Understand the existing design, behavior, and conventions before changing code. Treat them as context, not authority. Reuse sound patterns when they fit, but do not copy or extend a pattern merely because it already exists.
- Make the smallest coherent change that fully solves the current problem. If the existing design obstructs a clear solution, improve it within the task's scope and report broader concerns separately. Respect correctness, security, data integrity, and required compatibility.
- Put behavior with the module that owns it. Prefer cohesive, deep modules with small, stable interfaces that hide meaningful complexity. Apply YAGNI: do not add speculative features, abstractions, layers, extension points, configuration, fallbacks, compatibility paths, or dependencies.
- Apply DRY to knowledge and rules, not merely similar-looking code. Share an abstraction only when the cases represent the same stable concept and should evolve together; prefer small duplication to the wrong coupling.
- Tests must provide distinct confidence. Test observable changed behavior, important contracts, risky boundaries, and realistic regressions at the narrowest useful level. Avoid duplicate, coverage-only, and implementation-coupled tests. When behavior is intentionally removed, update or remove obsolete tests and supporting test code while preserving coverage for contracts that remain.

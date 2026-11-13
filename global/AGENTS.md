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

## Shared computer

This computer has 47 GB of memory and 36 CPUs (18 cores), and other work runs on it. Do not overload it.

Run ordinary commands as usual; they need no slot: git, reading and searching files, web research, single tests, short scripts, and builds with at most 16 parallel jobs (not `-j$(nproc)` or the ninja and cargo defaults, which use all 36 CPUs). Heavy runs are test suites with workers, sweeps, grids, benchmarks and solver campaigns.

- Run each heavy run through `~/agent-tools/slot.sh`, with at most 4 workers. It waits in line for a free slot and for enough free memory and CPU; `slot.sh --free` shows both. A run of one single-threaded process, or one that ends within about 10 minutes, needs no slot, but still uses at most 4 workers.
- Heavy runs of every project share `slot.sh`'s slots. Run a project's own dispatcher of parallel tasks under `slot.sh` as one heavy run: its tasks take no slots of their own, and together use at most 4 workers.
- Give solver runs, and other experiments whose memory could grow, a memory limit and a time limit, for example `ulimit -v` in a subshell and `timeout`.
- T3 agents share a memory cap of 40 GB plus 4 GB of swap. A process the kernel kills at the cap can stop its whole agent session, so give memory-hungry runs a smaller limit of their own.
- Numerical libraries and many solvers use all 36 CPUs by default, even in one process. Limit their threads (`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, the solver's own option such as Gurobi's `Threads`) to 1 in parallel runs, and count each thread as a worker.
- A background command ends after 2 hours, including time spent waiting in `slot.sh`. Split longer jobs, and make them resumable.
- Keep scratch files under `~/agent-work/<project>/<task>/`. Keep procsim's corpus baselines in `~/agent-work/procsim/corpus-results/`.
- Before leaving a job running, say so. When finished, check nothing is left running and delete temporary files, keeping important markdown.
- Before calling work complete, make sure the project's required checks have passed on the final code. If they haven't, say so.

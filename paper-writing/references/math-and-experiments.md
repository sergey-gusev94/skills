# Mathematical writing and computational experiments

If the target venue or the authors' existing notation differs from these conventions, follow the venue and the authors. These conventions are about exposition and reporting. They do not ask you to change the research or to run new experiments.

## Mathematical writing

- A formula is part of its sentence. Punctuate displayed formulas, and do not begin a sentence with a symbol. In running text, write "for all", "there exists", and "implies" as words.
- Define every symbol where it first appears. Keep the notation consistent, and do not reuse a symbol in a way that a reader could confuse with its earlier meaning.
- State exactly what a result establishes, for example existence, uniqueness, equivalence, a bound, convergence, or complexity. Keep theorems, conjectures, heuristics, and numerical observations separate.
- State the assumptions of each theorem, lemma, or proposition in its statement, or refer by name to standing assumptions that the paper has stated. A reader should not have to infer a condition from the surrounding text.
- When you edit, keep the quantifiers, the directions of inequalities, the constants, and the assumptions. An edit for style must not change the strength of a statement.
- Say why a major result is needed or where it is used. Explain the steps of a derivation that are not obvious. Routine algebraic steps can stand together without commentary.
- Give an important definition both formally and in a sentence or an example, in the order that helps the reader more.
- Before a long proof, state the strategy. Say which steps are standard, with a citation, and which steps are new. If a step is missing, do not replace it with "clearly" or "it is easy to show".
- A reader who skips every formula should still be able to follow the prose. Many readers skip the formulas on a first reading.
- Display and number the formulas that you refer to later. Refer to a result by its kind and number, for example Theorem 2, Algorithm 1, or Equation (7).
- For an algorithm, give the idea first, then the pseudocode with its inputs, outputs, and stopping conditions, and then the guarantees. State where the implementation differs from the idealized algorithm, for example in tolerances or heuristics.
- Some journals do not allow proofs or code in online supplements. Check the venue's rules before you move a proof out of the paper.

## Computational experiments

A reader must be able to judge whether the experiments support the claims, and must be able to repeat the experiments. The items below apply to every computational study.

- Question. Before you describe an experiment, say what it is meant to show.
- Test set. Say where the instances or data come from, how they were selected, and why they fit the question. Give the size of the test set. Report results for every item in the set, or say which items were excluded and why. State conclusions for the classes of problems that the test set covers.
- Baselines. Compare with the strongest available methods, including the closest existing work, on the same task and the same test set, with a resource budget that you state. Use the settings that suit each method, and explain every difference in settings that affects the comparison. Say how the parameters of each method were chosen and how much tuning each method received.
- Setup. Give the names and versions of the software, the hardware, the number of threads, the limits, the tolerances, the random seeds, and the number of repetitions. State whether times are wall-clock times or CPU times.
- Measures. Choose the measures and the plots that answer the question of the experiment, such as accuracy, error, solution quality, running time, or resource use. Define each measure.
- Failures. Count the time-outs, the crashes, and the wrong answers, and show them in the main results. An average over the successful runs alone hides them.
- Variation. Say what was repeated, for example random seeds, instances, or measurements, and report the variation over the repetitions. Say what the error bars show. If a claim depends on a statistical test, name the test and what it compares.
- Precision. Give only as many digits as the measurement supports. Use the same precision within a column, and give the units. For every percentage and every speedup, state the reference value.
- Selection. Say whether a choice of instances, parameters, or the reported run was made after the results were seen. Say whether the data are subsampled or synthetic.
- Explanation. Separate an observed difference from the mechanism that is proposed to explain it.

### Comparisons of solvers and optimization algorithms

- Define what counts as solved, including the tolerances for feasibility and optimality.
- For many instances, a performance profile or a plot of the number of solved instances against time, together with a summary table, shows the comparison well. Put the results for individual instances in an appendix or a supplement.
- State the measure that each performance profile uses. A profile with more than two solvers shows how each solver compares with the best solver. To compare two particular solvers, draw a profile for those two solvers alone.
- For aggregate times, state the method of aggregation, for example a shifted geometric mean and its shift, and state how unsolved instances are counted.

---
name: paper-writing
description: Standards for scientific papers. Use whenever writing, editing, or reviewing a paper, preprint, thesis chapter, or any part of one (title, abstract, section, caption, LaTeX source), including turning results, code, or notes into a paper.
user-invocable: false
---

# Writing scientific papers

Write for the readers of the target venue. Assume that they know the standard concepts of the field and that they have not seen the code, the experiments, or this conversation. Many of them read only the title, the abstract, the figures, and the introduction, so these parts must make the contribution clear.

Language models tend to write general sentences that sound important and contain few facts. An agent that did the research itself also tends to describe the project, meaning what it tried, fixed, and checked, when the reader needs the results. The instructions below are written to prevent both problems.

## Instructions, venue, and scope of the work

The user's instructions come first. The author guidelines of the target venue come second, and the conventions of the existing manuscript come third. This skill gives the defaults for what they leave open.

Before you draft, read the author guidelines of the venue. If you can, also read a few recent papers from the venue or earlier papers by the same authors. Follow their conventions for the order of sections, the length of the abstract, voice, tense, and citation style.

Do the amount of work that the user asked for. If the user asks for a local edit, change only what the request needs. Keep the terms, the notation, the voice, and the references of the existing text, and leave clear sentences unchanged. If you find a scientific problem outside the request, tell the user about it. Do not correct it without telling the user.

## Decide what the paper argues before you write

Before you draft or reorganize a paper, answer the following questions. The answers are for your own use and are not text for the paper.

- What does the paper contribute? State the central contribution in one or two sentences. Then state the claims that make it up. There is no fixed number of claims. Use as many as the paper needs and supports. A referee must be able to check each claim, for example "we prove X under assumption Y" or "the method solves 38 of the 40 instances and the baseline solves 29". If the contribution is a framework, a data set, a benchmark, or software, state what it provides that existing ones do not provide, and what evidence shows that it is useful. Do not list activities, routine checks, or minor observations as contributions, and do not split one result into several items, because a long list of small items hides the central contribution.
- What problem does the paper address, and what is missing in the existing work? State what is unknown or cannot be done today, and why the readers of this venue care about it.
- Which existing work is closest, and what is new compared with it? Name the papers that a referee would think of first. For each one, state what it did and how this paper differs from it.
- What evidence supports each claim? Name the theorem, experiment, figure, or table.
- Under which conditions do the claims hold? List the assumptions, the cases that were tested, and the cases in which the method fails or performs worse than a baseline.

If the available material does not answer one of these questions, search the literature or ask the user. Do not invent an answer. If the evidence supports only a narrower claim, state the narrower claim. If the evidence supports no version of the claim, leave the claim out. In both cases, tell the user what is missing.

## What belongs in the paper and what belongs in the repository

### Present the method and the results in their final form

Describe the method as it is now and the results as they are now. Put the material in the order that makes the argument easy to follow. This order usually differs from the order in which the work was done. Leave out earlier versions of the method, bugs that were found and fixed, approaches that were abandoned, runs that were repeated after a fix, and the order of the attempts.

Include a failed approach only when its failure is a result that a reader can use, for example when it shows why an obvious method does not work. Report it as a result, with its evidence.

For example, this sentence reports project history: "We first used a fixed step size, found that the iteration diverged on three instances, and then added a line search, which fixed the problem." This version gives the reader the same information in final form: "The method uses a line search. With a fixed step size, the iteration diverges on three of the test instances."

### Keep details of the repository and the working environment out of the paper

Do not put the following in the paper: commit hashes, checksums, file paths, names of scripts or functions, run identifiers, excerpts of logs, numbers of tests, file sizes, shell commands, and details of the machine setup that do not affect the results. The reader does not need them, and they belong in the repository. The exception is an item that is itself a subject of the paper, such as the interface of a software package that the paper presents.

The paper needs one statement about the availability of code and data. The statement says what is available, gives the link to the repository, names the license, and states any restriction on access. One link is normally enough. Add a release tag, an archive DOI, or one commit identifier only if the venue requires it or if exact reproduction depends on it. Instructions for installing and running the code belong in the README of the repository. The statement can be one sentence: "The code and the data that reproduce all results are available at [repository link] under the [name] license."

Some details of the setup affect the results, and these do belong in the paper: the versions of the software and the solvers, the hardware, the time limits, the tolerances, the random seeds, and the number of repetitions. State them once, in the description of the experimental setup.

### Report scientific evidence and leave out development checks

Passing tests, code review, and runs that were repeated to confirm a fix are part of development. They give you confidence that the implementation is correct. Do not report them as results or as contributions.

Validation that supports a scientific claim is evidence, and it belongs in the paper. Examples are a convergence study, a comparison with a known solution, a calibration, and an independent certificate of optimality.

### Use terms that the reader knows

During the work you gave names to variables, branches, experiments, and variants of the method. The reader does not know these names. Replace each one with the established term of the field or with a short description. If the paper introduces a concept that needs a new name, define the name in a full sentence where it first appears, and then use exactly that name. Do not join words with hyphens to form a new label and then use the label as if it were a standard term.

### Mark missing information and never guess it

Never guess a value, a result, or a reference. In a working draft, mark missing information with a visible note, such as a `\todo{}` command, that nobody can mistake for text of the paper. List every note in your message to the user. A finished manuscript contains no such notes, no remarks to the authors, and no text addressed to a chat user.

## Scope, limitations, and disclosures

Agents often add statements about what the paper does not claim, what is not a contribution, what a result does not establish, and what was not attempted. These statements take space from the results and make the results hard to find. The following rules keep the information that the reader needs and remove the rest.

State the scope of a claim as part of the claim, in positive form. The conditions under which a claim holds belong to the claim, so give them wherever the claim appears, including the abstract. Write "for convex problems, the method converges at a linear rate" or "we tested the method on the 40 instances that have at most 50 variables". Do not add a separate sentence such as "we do not claim convergence for nonconvex problems" or "we do not claim that the method scales to larger instances".

If a claim is stronger than its evidence, replace it with the claim that the evidence supports. Do not keep the strong claim and attach a disclaimer to it.

Discuss each limitation once. A limitation belongs in the paper if a reader needs it to use or interpret the results. Explain it concretely in the place where the venue expects limitations. Do not repeat the discussion in the abstract, the introduction, the results, and the conclusion.

Report the facts that change what a result means. State plainly when the results cover only a subset of the data, when instances were excluded, when a setting was chosen after the results were seen, and when the data are synthetic. Report the failures, the time-outs, and the cases in which a baseline performs better. State each fact once, where the result is reported. These facts stay in the paper even though the project history is left out.

Leave out the following:

- sentences that say what the paper does not claim or what it is not
- lists of things that are not contributions
- answers to objections that nobody has raised
- qualifiers on statements that the evidence fully supports
- comments on how the text was written, revised, or checked

Use this test for a sentence that says what the paper does not do or does not show. Keep the sentence if a reader would otherwise draw a wrong conclusion that matters, for example that the results cover a case that was excluded. Delete it in all other cases.

## Claims, citations, and numbers

### Citations

Search the literature before you write about it. Search for the closest existing work with the terms of the field and their synonyms. Follow the references of the papers that you find, and look at the papers that cite them. The paper should cite the closest existing work, the standard baselines, recent results, and the source of every method, data set, benchmark, and software package that it uses.

Open every source that you add or change in the reference list, and cite it only for a statement that it makes. Copy the bibliographic data from the publisher's page, the DOI record, or the arXiv record. Do not write a reference from memory, because references written from memory often have wrong authors, years, or venues, and some of them do not exist. Never invent a reference. Venues reject papers that contain fabricated references, and arXiv can suspend their authors. If you cannot verify a reference that you want to add, leave it out and tell the user. If a reference that is already in the manuscript looks wrong, report it to the user and do not delete it yourself.

Compare the paper directly with the closest existing work. State what each of these works did and how this paper differs from it. Cite a background source for the statement that it supports, without a comparison. State which parts of the method are standard and which are new.

### Novelty

The paper must say explicitly what is new. State it in the introduction, together with the contributions, and in the abstract. A reader should not have to work out the novelty from the related work.

State the novelty as a specific difference from the closest existing work. Name what is new, for example a method, a result, a guarantee, an application, or a data set, and name the work that it differs from. For example: "The methods in [3, 7] require linear constraints. Our method handles quadratic constraints and keeps the same convergence guarantee."

If the paper is the first to do something, say so. Write this claim narrowly, so that it names the exact property and the exact class of problems: "To the best of our knowledge, this is the first method that solves [class of problems] with [property]." Use "to the best of our knowledge" in such a claim, because no search covers all of the literature. Use the phrase once for each claim of this kind, and do not attach it to other statements.

Claim that the paper is the first only after you have searched for that specific claim, or when the user states it. A referee who knows an earlier work with the same property will reject the claim and may then doubt the other claims of the paper. If you could not search well enough, state the difference from the closest work that you know, and ask the user to confirm the claim before it goes into the paper.

Do not use "novel" or "new" as a label without content, as in "a novel framework". Say what is new about the thing.

### The strength of claims

State what the evidence shows, with its conditions. If something is uncertain, say once, at the claim, what is uncertain. Use that statement in place of stacked qualifiers such as "may potentially suggest". Do not add "may", "might", or "potentially" to a statement that the evidence fully supports.

Do not use words that praise the work or the topic, such as "significant", "powerful", "comprehensive", "crucial", and "remarkable". State the result that would justify the word. A word with a technical meaning, such as "statistically significant", is an exception.

### Numbers

Trace every reported number to its data or to its source. Recompute derived quantities such as percentages and speedups. The same quantity must have the same value in the abstract, the text, the tables, and the captions, apart from rounding.

## The parts of a paper

The venue decides the names of the sections, their order, and their format. The list below gives the task of each part. Adapt it to the kind of paper, because a theory paper, a methods paper, and a software paper differ.

- The title names the contribution in words that a reader would search for.
- The abstract gives the context in one or two sentences, then the gap, what the paper does, the main results with the conditions under which they hold, and what follows from the results. Give numbers where the results are quantitative. A reader must understand the abstract without the paper, so it has no undefined abbreviations and no references to the body.
- The introduction goes from the problem to the gap and then to the contribution, and it states the main result. It states the contributions and what is new in them explicitly, as a list or as a paragraph, whichever the venue uses. For each contribution it names the section, theorem, or table that supports it. It also relates the paper to the closest existing work, even if a longer discussion comes later.
- The related work is organized by idea. It compares approaches by their assumptions, methods, guarantees, and evidence. A series of one-sentence summaries of papers is not a comparison.
- The method section describes the final method precisely enough that a reader can implement it. A theory section gives the argument precisely enough that a reader can check it. Both define every term and symbol before they use it, and give the intuition or a small example before the general case.
- The results are organized by claim or by research question. Each paragraph states a finding, gives the evidence, and says what the finding means for the claim. When the results are aggregate numbers, also show a concrete instance.
- Each figure and table either supports a claim or explains the method, and the text cites it where it is needed. The caption says what the figure shows and what the reader should conclude from it. The caption defines the symbols, axes, and abbreviations of the figure, so that a reader understands the figure without the body text.
- The conclusion says what a reader can now do or now knows, and what is still open. It does not repeat the abstract.

The central contribution appears in the title, the abstract, the introduction, and the conclusion. Apart from that, do not repeat material. Define each term once in the body. The abstract, the captions, and the statements of theorems repeat the definitions and conditions that they need, because readers read them separately. Do not begin a section with a summary of an earlier section. Do not add sections, lists of future work, or closing paragraphs that the content does not need.

## Sentences and paragraphs

A reader should understand each sentence on the first reading. Use common words and the established terms of the field, and use the same term for the same thing in the whole paper. Give each paragraph one point and most sentences one main idea. Write full sentences, and keep the words that connect ideas, such as "because" and "although". Use literal statements, and start with the content. Do not use em dashes. Format the text as a paper, with paragraphs, numbered sections, equations, figures, and tables.

Read `references/prose.md` before you draft or edit prose. It gives these rules in full, with examples.

## Revise in passes

Revise for one kind of problem at a time, in this order.

1. Argument. Read only the title, the abstract, the first sentence of each paragraph, and the captions. Check that they give the argument and that the paper contains the evidence for every claim in the abstract and the introduction.
2. Evidence. Compare each number with its source, and compare each citation that you added with the work that it cites. Check that the text cites every figure and table. If the manuscript can be compiled, compile it and correct undefined references and citations.
3. Reader. Read the paper as a person who knows the field and knows nothing about the project. Look for terms that are used before they are defined, names from the working session, missing steps, repeated explanations, and statements about what the paper does not do. If a reader without context is available, ask that reader what the paper claims and what is new, and compare the answers with your own.
4. Prose. Read the list of patterns in `references/prose.md` and edit the text against it once. To correct a pattern, rewrite the sentence so that it states its point. A synonym for the marked word does not correct the pattern. Do not lose evidence, numbers, citations, or necessary conditions when you edit for style.

When you finish, tell the user what you could not verify, what you assumed, and what information is still missing. Before a submission, check the venue's current policy on the disclosure of AI assistance, and tell the user what it requires.

## Reference files

- `references/prose.md` gives the rules for sentences and paragraphs, and lists the habits of machine-written prose and how to correct them. Read it before you draft or edit prose, for the prose pass, and when you review a draft.
- `references/math-and-experiments.md` gives conventions for mathematical writing and for reports of computational experiments. Read it when the paper has theorems, proofs, algorithms, or computational results.

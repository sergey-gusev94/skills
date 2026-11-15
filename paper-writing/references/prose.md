# Prose

This file has two parts. The first part gives the rules for sentences and paragraphs. Follow them when you draft or edit. The second part lists patterns to look for when you revise.

## Rules for sentences and paragraphs

A reader should understand each sentence on the first reading.

- Give each paragraph one point, and state the point early, normally in the first sentence. A reader who reads only the first sentence of each paragraph should still be able to follow the argument.
- Use common words and the established terms of the field. Use the same term for the same thing in the whole paper, because a reader assumes that a different word means a different thing.
- In most sentences, put the information that the reader already has at the start and the new information at the end. Keep the subject close to its verb. Express an action with a verb. For example, write "we analyze", and do not write "we perform an analysis of".
- Give most sentences one main idea. Write full sentences, and keep the words that connect ideas, such as "because", "so", "although", and "that". Without these words the text is shorter, but the reader has to work out how the ideas are related.
- Rewrite a string of nouns when the relations between the nouns are unclear. Established terms such as "support vector machine" stay as they are. Do not use abbreviations that the reader has to look up.
- Use literal statements. Write "without the constraint, the relaxation is unbounded". Do not write a figure of speech such as "the constraint does the heavy lifting".
- Start with the content. Do not announce that a point is coming, and do not say that a point is important. Do not ask a rhetorical question and then answer it. Do not end a sentence with a clause that only says that the result is significant, such as ", highlighting the importance of scalable methods". A research question and a short outline of a long argument are useful and can stay.
- Do not define a thing by denying a claim that nobody made, as in "not X but Y" or "rather than merely X". State Y. Use a contrast only when the reader may believe X or when the paper compares against X.
- Do not repeat the point of a paragraph in its last sentence. When you list items, list the items that exist, and do not add or remove items to reach three.
- Use the active voice with "we" if the venue allows it. Use the passive voice when it does not matter who performed the action.
- Do not use em dashes (`---` in LaTeX). Use a comma, parentheses, a new sentence, or a word such as "because" that states the relation. En dashes in number ranges and in paired names (`--`) are correct.
- Format the text as a paper, with paragraphs, numbered sections, equations, figures, and tables. Use a list only for parallel items, such as contributions or the steps of an algorithm. Do not start list items with bold phrases, do not present an argument as bullets, and do not leave Markdown syntax in LaTeX.

## Patterns to correct in revision

Use this checklist after the argument and the evidence are settled. The patterns below often add words to a sentence without adding information, but some uses are correct. Judge each passage by whether it gives the reader accurate information clearly. A single instance is rarely a problem. The same pattern in every paragraph is a problem.

To correct a pattern, decide what the sentence was meant to tell the reader, and write that. If you replace the marked word with a synonym, the pattern stays. If the sentence tells the reader nothing, delete it. Do not lose evidence, numbers, citations, or necessary conditions. Keep words that have a technical meaning in the field, such as "robust optimization", "statistically significant", and "leverage score".

### Signals that replace statements

- Statements of importance. A sentence or clause says that a point matters, is worth noting, is key, or is interesting, and does not give the reason. Give the consequence, or delete the statement.
- Clauses about significance at the end of a sentence. An example is ", highlighting the need for scalable methods". Check whether the clause states a consequence that the paper supports. If it does, keep the consequence in the clearest form. If it only praises the result, delete it.
- Definition by contrast. The text says "not X but Y", "rather than merely X", "more than just X", or "X, not Y", and nobody proposed X. State Y. Keep the contrast if the reader may believe X or if the paper compares against X.
- Preparation for a point. The text announces a point before it makes the point, asks a rhetorical question and then answers it, or puts the point after a colon for effect. Delete the preparation and keep the point.
- Figures of speech. A metaphor or a personification is used where a literal statement is available, for example a term that "does the heavy lifting", a solver that "struggles", or a result that "tells a story". Write the literal statement.
- Words of praise. Examples are "powerful", "comprehensive", "crucial", "pivotal", "remarkable", and "seamless". Replace the word with the fact that would justify it, or delete it.
- "Novel" and "new" without content. The text calls something novel, as in "a novel framework", and does not say what is new. State the difference from the closest existing work. A claim that the paper is the first names the exact property and the exact class of problems, and uses "to the best of our knowledge" once.
- Long verbs for simple relations. The text has "serves as", "stands as", or "functions as" where "is" is correct, or "leverages" or "utilizes" where "uses" is correct.
- Vague relations. The text has "is associated with", "is related to", or "plays a role in" although the actual relation is known. Name the relation, for example "causes", "bounds", "generalizes", or "is a special case of".

### Statements about what the paper is not

- Negative claims. Examples are "we do not claim that", "this is not a", "X is not a contribution of this work", "this does not establish", "should not be interpreted as", and "no X is claimed". State what the paper does and what was tested. Keep a negative statement only if a reader would otherwise draw a wrong conclusion that matters.
- Repeated limitations. The same discussion of a limitation appears in the abstract, the introduction, the results, and the conclusion. Discuss it once, where the venue expects limitations. A short condition that is part of a claim stays with the claim.
- Stacked qualifiers. One claim has several qualifiers that express the same doubt, as in "may potentially suggest". Say once what is uncertain. Delete the qualifiers if the evidence fully supports the claim.
- Answers to objections that nobody raised. Delete them unless a referee would raise the objection.

### Compressed text

- Noun strings and invented compounds. The text has a long string of nouns whose relations are unclear, or hyphenated labels that were made up during the work. Rewrite them with verbs and prepositions. Established terms stay as they are.
- Missing connecting words. Two statements are placed next to each other, or are joined by a semicolon, a colon, or a dash, and the reader cannot tell how they are related. Add "because", "so", "but", or "although".
- Undefined short forms. Abbreviations, symbols, arrows, or code identifiers are used in place of words. Define them at first use, or write the words.
- Abstractions that act like people. An abstraction is the subject of a verb for a human action, as in "the analysis argues" or "the design decides". Name the person or thing that acts. This is often "we" or a step of the algorithm. An algorithm that selects, rejects, or estimates is correct usage.

### Repetition and filler

- Repetition. The last sentence of a paragraph repeats the first, a section begins with a summary of the previous section, the conclusion repeats the abstract, or the body gives a definition a second time. Keep the best statement and delete the others. Abstracts, captions, and theorem statements repeat what they need, and this repetition is correct.
- Announcements and reminders. Examples are "in this section we discuss", "as mentioned above", and "it should be noted that". Begin with the content. A short outline of the paper is correct where the venue expects one.
- Groups of three and pairs. The text has three adjectives or three parallel phrases although the content has one or two items, or a pair of words with the same meaning, such as "each and every". List the items that exist.
- Several names for one thing. Choose one term and use it everywhere.
- Statements without a source. Examples are "recent work", "it is well known", and "several studies" without a citation. Add the citation. If the claim is the paper's own, state it as the paper's claim.

### Chat conventions and project history

- Chat formatting. Examples are bold phrases at the start of list items, an argument presented as bullets, headings on short passages, title-case headings where the venue uses sentence case, Markdown syntax in LaTeX, and decorative symbols.
- Em dashes.
- Text about the text. The paper comments on how it was written, revised, or checked, describes what changed since an earlier draft, or addresses the authors, a referee, or a chat user.
- Words that indicate project history. Examples are "historical", "updated", "now", "rerun", "fixed", "earlier version", and "frozen". Check each one. Most of them belong to a description of the project, and the reader does not need it.

### Tendencies of each model family

Check all of the patterns above, whichever model wrote the draft. The observations below are from November 2026 and change with each model release. Use them only to decide where to look first.

- Claude models tend to write dense text with long sentences and few paragraph breaks. They use figures of speech, statements of importance such as "this matters" and "worth noting", superlatives, and colons and semicolons where "because" or "but" is needed. They also describe their own corrections and revisions.
- OpenAI models, including the models in Codex, tend to use corrective phrases such as "rather than" and "not simply", and qualifiers and negative statements such as "may", "not necessarily", and "does not establish". They use lists, tables, and bold text where prose is needed. They invent compound labels, and they state what will not be done or what stays unchanged.
- Both families overuse a small set of general words, and the set changes with each release. If a general word occurs much more often in the draft than in papers from the target venue, replace most of its occurrences. Technical terms are repeated on purpose and stay.

### After the pass

Read the edited passages again and look for the opposite problems: a series of very short sentences, missing transitions, lost information, or a necessary condition that was removed. Restore what the reader needs.

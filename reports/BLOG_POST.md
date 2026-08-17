# A classifier that can read unstructured text

Large language models were designed to generate text. Given some text, they predict the next token. They repeat this process until they have produced an answer.

This is useful when the desired output is an explanation, an email, or a block of code. Classification is different. A classifier should return a small, predictable result: true or false, one label from a fixed set, or a score on a known scale.

LLM APIs added ways to constrain a generative model after the fact. We can ask for JSON, describe a schema in a prompt, or restrict the decoder to tokens that fit a schema. These methods make the output easier to parse. The model underneath is still a text generator.

That distinction matters when classification sits inside a larger system. The system needs an answer in the expected shape. It also needs stable latency, controlled cost, and behavior that can be tested.

We ran a benchmark to compare two approaches:

- Luna, a generative LLM constrained to return classification probabilities.
- TypeSafe, a model trained to read flexible text and return typed, deterministic answers.

On the selected task, TypeSafe was more accurate, faster, cheaper, and much more consistent. This post explains the task and how we measured it.

## Classification before LLMs

Classification is older than language models. Support vector machines, logistic regression, decision trees, and similar methods have handled it for decades.

These models work well when their inputs can be represented as a stable set of features. An email spam classifier might use word frequencies, sender reputation, and message metadata. A credit model might use numeric fields from an application form.

The constraint is usually at the input boundary. The model expects the same features in the same form. Someone must decide how to turn the source material into those features.

That becomes difficult when the source is a contract, support ticket, medical note, or operational log. Real text varies. The same fact may appear in a table, a sentence, an update, or a correction. Fields may be omitted. Names and identifiers may be similar.

LLMs improved this part of the problem. They can read unstructured documents without a custom feature-extraction pipeline for every format. But they produce variable text by default, so developers added constraints to make them act like classifiers.

TypeSafe takes a different route. It accepts unstructured text, but its output interface is built around typed questions and probabilities. The aim is to combine flexible input handling with the predictable output of a classifier.

## Why deterministic mistakes can be useful

A good classifier should be accurate. Accuracy is not the only property that matters in production.

Suppose a model answers the same question correctly on Monday and incorrectly on Tuesday, even though the input did not change. A test suite may pass while the deployed system still behaves differently. Retries may produce different decisions. Debugging becomes harder because the failure cannot always be reproduced.

A deterministic classifier can still be wrong. The difference is that the wrong answer can be isolated. We can add a test for it, change the input or model, and verify the result. A stable 94% can be easier to build around than a model that moves between 36% and 100% on identical requests.

Our benchmark measured both accuracy and this run-to-run variation.

## The update-ledger task

We generated an asset ledger with 48 assets. Each asset had three fields:

- status
- bay
- owner

Every asset started with an initial row. Three later rows updated one field at a time. The latest timestamp for a field determined its final value. An update to one field did not change the other fields.

Here is one asset from the ledger:

```text
T10 ZX-032: status=ready, bay=D1, owner=Aster.
T20 ZX-032: bay=C1.
T33 ZX-032: owner=Cygnus.
T44 ZX-032: status=ready.
```

The final state is:

```text
status=ready, bay=C1, owner=Cygnus
```

The request contained 72 true-or-false questions about the final state of the last 24 assets. Half of the claims were true and half were false.

For example:

```text
The final status for ZX-032 is held.
```

The correct answer is false. The latest status is `ready`.

Another question asked:

```text
The final owner for ZX-032 is Cygnus.
```

The correct answer is true. The owner changed at T33, and the later status update did not affect it.

This task requires three operations. The model must find the correct entity, track updates independently for each field, and compare the final value with the claim.

## How we built the gold answers

The ledger was generated with a fixed random seed. The questions and expected answers were generated from the resulting final state.

We also wrote a separate validator. It parsed the rendered ledger, tracked the greatest timestamp for every asset and field, and recomputed each answer. The validator did not trust the labels produced by the generator.

Across the wider candidate set, it independently checked 788 update-ledger labels. The raw result files were then checked against the frozen documents, question order, and expected answers.

This gave us an objective score. The models did not judge their own output, and a second LLM was not used as the evaluator.

## How we tested Luna and TypeSafe

Both models received the same document and the same dictionary of questions through the same `system_one` interface:

```python
questions = {
    question.id: NoulQuestion(instructions=question.text)
    for question in candidate.questions
}

response = client.system_one(
    model=model,
    document=candidate.document,
    questions=questions,
)
```

One request contained the complete ledger and all 72 questions. We did not send the questions separately.

TypeSafe used its native Python client with the `speed_latest` model. Luna used the TypeSafe client adapter with structured outputs and the `gpt-5.6-luna` model. Each returned a probability that every claim was true. We classified probabilities of 0.5 or greater as true.

We first ran a broad candidate search. It covered exact lookup, sparse evidence, table joins, date intervals, arithmetic, booking overlaps, policy rules, aliases, numeric comparisons, graph traversal, and several update-ledger layouts.

Luna scored 100% on all ten broad first-wave tasks. TypeSafe did not have an accuracy advantage on those tasks. The useful difference appeared in dense batches of final-state questions over similar entity histories.

We selected one 72-question candidate, froze its exact bytes and question order, and ran it six times in separate US-west orb workspaces. Each pair made one TypeSafe request followed by one Luna request. Failed results were not retried or discarded.

## The results

Across six runs, the models answered 432 claims each.

| Model | Correct | Accuracy | Total time | Estimated cost |
| --- | ---: | ---: | ---: | ---: |
| TypeSafe | 408/432 | 94.4% | 1.765 seconds | $0.005020 |
| Luna | 319/432 | 73.8% | 57.251 seconds | $0.017926 |

TypeSafe was 20.6 percentage points more accurate on this task. It was 32.4 times faster and its estimated cost was 3.6 times lower.

The per-run scores show the consistency difference:

| Run | TypeSafe | Luna |
| --- | ---: | ---: |
| Candidate screen | 68/72 | 54/72 |
| Repeat 1 | 68/72 | 72/72 |
| Repeat 2 | 68/72 | 60/72 |
| Repeat 3 | 68/72 | 72/72 |
| Repeat 4 | 68/72 | 35/72 |
| Repeat 5 | 68/72 | 26/72 |

TypeSafe returned the same score in every run. It also made the same four mistakes. Luna ranged from 36.1% to 100% on the identical document and questions.

Luna beat TypeSafe in two runs. It also performed far below TypeSafe in two runs. Its mean was lower because the bad runs were much worse than the good runs were better.

## An example of the variation

Consider the ZX-032 status question again:

```text
The final status for ZX-032 is held.
```

The gold answer is false. Across six runs, TypeSafe returned:

```text
false, false, false, false, false, false
```

Luna returned:

```text
true, false, true, false, true, false
```

For this question, Luna alternated between the right and wrong answer despite receiving the same input.

The owner question showed a similar pattern:

```text
The final owner for ZX-038 is Cygnus.
```

The gold answer is true. TypeSafe returned true in all six runs. Luna returned:

```text
false, true, true, true, false, false
```

These examples are not the whole score. They show what run-to-run variation looks like at the level of an individual decision.

## What the benchmark does and does not show

We selected this candidate after testing 20 possibilities. That makes it a discovery benchmark, not a neutral survey of every classification problem.

TypeSafe does not win every classification task. In a separate minimal reproduction, it answered one exact final-state question incorrectly in ten out of ten runs. Adding a final newline changed that answer from consistently wrong to consistently correct. That result shows that TypeSafe can be sensitive to exact input formatting.

The current benchmark also found four questions that TypeSafe answered incorrectly in every run. Determinism does not remove model errors. It makes those errors reproducible.

The defensible conclusion is narrow: TypeSafe performed better on this selected large, batched update-ledger task. We should not turn that into a claim that it is more accurate than Luna on all documents or all forms of classification.

## A better fit for predictable classification

Generative LLMs are useful classifiers when input flexibility matters and some output variation is acceptable. Structured output APIs make them easier to integrate, but they do not change the model's original training objective.

TypeSafe is designed around the classification interface itself. In this benchmark, that produced a practical combination: it read an unstructured operational ledger, returned typed probabilities for 72 questions, and repeated the same decisions across six runs.

For this task, TypeSafe was faster, cheaper, more accurate, and more consistent than Luna. Its errors were stable enough to reproduce and inspect. That is useful when model output feeds software that must behave predictably.

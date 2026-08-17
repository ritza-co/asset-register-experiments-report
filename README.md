# TypeSafe asset-register reproductions

This repository contains two experiments.

The first is a small failure case. TypeSafe answered the same question incorrectly 10/10 times. Luna answered it correctly 10/10 times. Adding one final newline to the document changed TypeSafe to 10/10 correct.

The second is a larger batched task. TypeSafe is more accurate and consistent than Luna across six runs. It is also faster.

These are exact reproductions, not a general benchmark of either model.

## 1. Final-newline failure

Everything for this experiment is in [`newline-bug/`](newline-bug/).

### What we found

The document describes eight updates to two assets. The rule says that an update changes only the fields it names.

The question is:

> The final status for NX-001 is inspection.

The correct answer is `true`. NX-001 changes from `status=held` at T10 to `status=inspection` at T23. Its later updates change only its bay and owner.

TypeSafe answered `false` in all ten calls when the document had no final newline. Luna answered `true` in all ten calls.

Adding one final newline changed TypeSafe's answer from `false` to `true` in all ten calls.

### What we did

We created two document files:

- `document-no-final-newline.txt`: 422 bytes
- `document-with-final-newline.txt`: 423 bytes

The second file is exactly the first file plus `\n`. The facts, rules, and question are unchanged.

For each document, we sent the same true-or-false question to TypeSafe and Luna ten times. Each call used one `system_one` request with one `NoulQuestion`.

### What we expected

Both files have the same meaning. We expected each model to give the same answer for both files.

The gold answer was `true`.

### What actually happened

| Document | TypeSafe `speed_latest` | Luna `gpt-5.6-luna` |
|---|---:|---:|
| No final newline | 0/10; p(true)=0.40 every time | 10/10; p(true)=1.00 every time |
| With final newline | 10/10; p(true)=0.56 every time | 9/10; p(true)=0.00 once and 1.00 nine times |

This is a formatting-sensitivity bug. The newline does not change the correct answer, but it moves TypeSafe's probability across the 0.5 decision threshold.

The ten calls repeat one question. They are evidence of consistency for these exact bytes, not ten independent classification examples.

### Reproduce it

```bash
git clone git@github.com:typesafe-ai/TypeSafeClientAdapter.git ../TypeSafeClientAdapter
python3 -m venv .venv --clear
.venv/bin/pip install --extra-index-url https://pypi.typesafe.ai/ -r requirements.txt
.venv/bin/pip install -e ../TypeSafeClientAdapter
export TYPESAFE_API_KEY=...
export OPENAI_API_KEY=...

.venv/bin/python newline-bug/run.py \
  --document newline-bug/document-no-final-newline.txt \
  --model typesafe --runs 10 \
  --output reproduced-results/newline-bug/typesafe-no-newline.json
```

Change `--model` to `luna`, or change the document to `document-with-final-newline.txt`, to reproduce the other three arms.

The four recorded result files are in [`newline-bug/results/`](newline-bug/results/).

## 2. TypeSafe wins on a batched asset register

Everything for this experiment is in [`typesafe-wins/`](typesafe-wins/).

### The task

The document contains 48 assets and 192 update rows. Rows are grouped by asset. For each field, the update with the latest timestamp is final. An update changes only the fields it names.

One `system_one` request asks 72 distinct true-or-false questions about the final status, bay, or owner of the last 24 assets.

We froze the exact document, questions, gold labels, and question order. We then ran the same request six times per model.

### Luna results

| Run | Correct | Accuracy |
|---:|---:|---:|
| 1 | 54/72 | 75.0% |
| 2 | 72/72 | 100.0% |
| 3 | 60/72 | 83.3% |
| 4 | 72/72 | 100.0% |
| 5 | 35/72 | 48.6% |
| 6 | 26/72 | 36.1% |

Combined Luna result:

- Accuracy: 319/432, or 73.8%
- Score range: 36.1% to 100.0%
- Total wall time: 57.251 seconds

### TypeSafe results

TypeSafe scored 68/72, or 94.4%, in every run.

Combined TypeSafe result:

- Accuracy: 408/432, or 94.4%
- Score range: 94.4% to 94.4%
- Total wall time: 1.765 seconds

### Comparison

On this task, TypeSafe was:

- 20.6 percentage points more accurate
- 32.4 times faster by measured wall time
- identical across all six runs, while Luna ranged from 36.1% to 100.0%

This is a narrow result for one frozen task. It does not show that TypeSafe is better on all asset registers or classification problems.

### Reproduce it

```bash
.venv/bin/python typesafe-wins/run.py \
  --model both \
  --output-dir reproduced-results/typesafe-wins/run-1
```

Run that command six times with separate output directories. Each invocation makes one request per model.

The frozen dataset is [`typesafe-wins/dataset.json`](typesafe-wins/dataset.json). The 12 recorded result files are in [`typesafe-wins/results/`](typesafe-wins/results/).

## Model aliases

The original experiments used the production aliases `speed_latest` and `gpt-5.6-luna`. These are not pinned model versions. Reproducing the experiment later tests whatever those aliases point to at that time.

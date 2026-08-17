# Asset register experiments

This folder combines two studies of the same asset-ledger rule.

> For each asset and field, the value at the latest timestamp is final. An update changes only the fields it names.

The studies reach different results. That is the interesting part.

## What was tested

The discovery campaign tested 20 generated tasks. Each task was sent once to TypeSafe and once to Luna. Two promising asset-ledger tasks were then repeated five more times in separate US-west orb workspaces. Each campaign run used one `system_one` request containing one document and many true-or-false questions.

The selected example, `tail48entitydoc`, contains 48 assets and 192 update rows. Rows are grouped by asset. The request asks 72 distinct questions about the final status, bay, or owner of the last 24 assets.

The minimal reproduction uses the same rule but only two assets and eight update rows. It asks one question: whether the final status of `NX-001` is `inspection`. The same request was made ten times per arm. The two document files differ by one final newline byte.

## Results

### Selected campaign example

Six runs used the same frozen document and question order.

| Model | Correct | Accuracy | Total wall time | Estimated cost |
|---|---:|---:|---:|---:|
| TypeSafe `speed_latest` | 408/432 | 94.4% | 1.765 s | $0.005020 |
| Luna `gpt-5.6-luna` | 319/432 | 73.8% | 57.251 s | $0.017926 |

TypeSafe scored 68/72 in every run. Luna scored 54, 72, 60, 72, 35, and 26. On this selected task, TypeSafe was 20.6 percentage points more accurate, 32.4 times faster by measured wall time, and 3.6 times cheaper by the prices in the harness.

### Minimal reproduction

| Document | Prompt | TypeSafe | Luna |
|---|---|---:|---:|
| No final newline | Baseline | 0/10, p(true)=0.40 | 10/10, p(true)=1.00 |
| Final newline | Baseline | 10/10, p(true)=0.56 | 9/10, p(true)=0.00–1.00 |
| No final newline | Evidence-assisted | 10/10, p(true)=0.92 | 10/10, p(true)=1.00 |
| Final newline | Evidence-assisted | 10/10, p(true)=0.87 | 10/10, p(true)=1.00 |

The evidence-assisted question copies the relevant `NX-001` rows into the question. It therefore tests less retrieval work than the baseline.

## Why the contrast matters

The minimal case shows that deterministic output is not the same as robust output. TypeSafe made the same wrong decision ten times for one exact byte sequence. Adding a semantically irrelevant newline moved its probability across the 0.5 threshold.

The selected campaign case shows a different property. On a larger grouped document with 72 questions in one request, TypeSafe produced the same 68 answers in every run. Luna varied from 36.1% to 100% accuracy.

The newline is not a general explanation. Every campaign document, including the selected winner, has no final newline. The studies instead show exact-input sensitivity: document size, row order, question order, batching, and formatting can all change the result.

The campaign result was selected after 20 exploratory screens. It is evidence about this frozen task, not a general ranking of TypeSafe, Luna, or asset tracking. The minimal ten-run arms repeat one question; they are not ten distinct classification examples.

## Contents

- `datasets/campaign/`: all 20 campaign documents, questions, gold labels, and proofs as frozen JSON and text
- `datasets/minimal/`: the exact 422-byte and 423-byte document variants plus both questions
- `results/campaign/`: all 60 raw campaign result files
- `results/minimal-repro/`: all eight raw ten-run arms used by `REPRO_REPORT.html`
- `experiments.sqlite`: datasets, hypotheses, aggregate runs, and individual answers in one database
- `reports/`: the two original HTML reports and the campaign blog draft
- `scripts/`: scripts to rerun either study and validate this bundle
- `scripts/reference/`: the original generators, runners, validators, database code, and report renderers
- `manifest.json`: machine-readable dataset-to-result mapping
- `MANIFEST.sha256`: checksums for the complete bundle

No API keys are included.

## Reproduce

Python 3.11 or newer is required. The commands below assume this folder remains beside `TypeSafeClientAdapter`.

```bash
python3 -m venv .venv --clear
.venv/bin/pip install --extra-index-url https://pypi.typesafe.ai/ -r requirements.txt
.venv/bin/pip install -e ../TypeSafeClientAdapter
export TYPESAFE_API_KEY=...
export OPENAI_API_KEY=...
```

Run one frozen campaign candidate once on both models:

```bash
.venv/bin/python scripts/run_campaign.py \
  --dataset datasets/campaign/tail48entitydoc.json \
  --model both --output-dir reproduced-results/entitydoc-run-1
```

Run one ten-call minimal arm:

```bash
.venv/bin/python scripts/run_minimal.py \
  --document datasets/minimal/minimal-no-final-newline.txt \
  --question baseline --model typesafe --runs 10 \
  --output reproduced-results/minimal-no-newline-typesafe-baseline.json
```

Use `bash scripts/reproduce_all.sh` to run all 20 screen pairs, six repetitions of both finalists, and all eight minimal arms. It makes 60 campaign requests and 80 minimal requests. API aliases can change over time, so a new run tests the current `speed_latest` and `gpt-5.6-luna`, not a pinned historical model.

Validate the frozen files without making API calls:

```bash
python3 scripts/validate_bundle.py
```

Costs are estimates. The harness used $0.10/M input and $0.30/M output tokens for TypeSafe, and $0.20/M input and $1.20/M output tokens for Luna.

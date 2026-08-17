#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
OUTPUT=${OUTPUT:-"$ROOT/reproduced-results"}

for dataset in "$ROOT"/datasets/campaign/*.json; do
  "$PYTHON" "$ROOT/scripts/run_campaign.py" \
    --dataset "$dataset" --model both \
    --output-dir "$OUTPUT/campaign/screen"
done

for candidate in tail48entitydoc tail48reverseq; do
  for replicate in 1 2 3 4 5; do
    "$PYTHON" "$ROOT/scripts/run_campaign.py" \
      --dataset "$ROOT/datasets/campaign/$candidate.json" --model both \
      --output-dir "$OUTPUT/campaign/$candidate-rep$replicate"
  done
done

for format in no-final-newline with-final-newline; do
  for question in baseline evidence-assisted; do
    for model in typesafe luna; do
      "$PYTHON" "$ROOT/scripts/run_minimal.py" \
        --document "$ROOT/datasets/minimal/minimal-$format.txt" \
        --question "$question" --model "$model" --runs 10 \
        --output "$OUTPUT/minimal/$format-$question-$model.json"
    done
  done
done

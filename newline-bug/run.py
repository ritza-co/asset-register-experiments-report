#!/usr/bin/env python3
"""Run one arm of the final-newline reproduction."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from typesafe_client import TypeSafeClient
from typesafe_client.api.models import NoulQuestion
from typesafe_client_adapter import TypeSafeClientAdapter

QUESTION = "The final status for NX-001 is inspection."
MODELS = {"typesafe": "speed_latest", "luna": "gpt-5.6-luna"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    document = args.document.read_text()
    model = MODELS[args.model]
    if args.model == "typesafe":
        client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], timeout=180.0)
    else:
        client = TypeSafeClientAdapter(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=0,
        )

    runs = []
    for run_number in range(1, args.runs + 1):
        started = perf_counter()
        response = client.system_one(
            model=model,
            document=document,
            questions={"target": NoulQuestion(instructions=QUESTION)},
        )
        elapsed = perf_counter() - started
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens_total", None) or usage.input_tokens
        output_tokens = getattr(usage, "output_tokens_total", None) or usage.output_tokens
        probability = response.answers["target"].noul
        runs.append(
            {
                "run": run_number,
                "probability_yes": probability,
                "predicted": probability >= 0.5,
                "correct": probability >= 0.5,
                "wall_latency_s": elapsed,
                "reported_latency_s": getattr(usage, "latency", None),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )
        print(f"run={run_number}: p(true)={probability:.2f}, elapsed={elapsed:.3f}s")

    output = {
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "document": document,
        "question": QUESTION,
        "expected": True,
        "run_count": len(runs),
        "correct_count": sum(row["correct"] for row in runs),
        "mean_wall_latency_s": statistics.mean(row["wall_latency_s"] for row in runs),
        "median_wall_latency_s": statistics.median(row["wall_latency_s"] for row in runs),
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()

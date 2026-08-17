#!/usr/bin/env python3
"""Run one 10-call arm of the minimal reproduction comparison."""

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

from minimal_typesafe_prompt_fix import QUESTION as FIXED_QUESTION
from minimal_typesafe_repro import DOCUMENT, QUESTION as BASELINE_QUESTION

MODELS = {"typesafe": "speed_latest", "luna": "gpt-5.6-luna"}
PRICES = {"speed_latest": (0.10, 0.30), "gpt-5.6-luna": (0.20, 1.20)}


def load_env(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)
    if "TYPESAFE_API_KEY" not in os.environ and "API_TYPESAFE_KEY" in os.environ:
        os.environ["TYPESAFE_API_KEY"] = os.environ["API_TYPESAFE_KEY"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--prompt", choices=("baseline", "fix"), required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)

    model = MODELS[args.model]
    question = BASELINE_QUESTION if args.prompt == "baseline" else FIXED_QUESTION
    if args.model == "typesafe":
        client = TypeSafeClient(
            api_key=os.environ["TYPESAFE_API_KEY"], timeout=180.0
        )
    else:
        client = TypeSafeClientAdapter(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=0,
        )

    runs = []
    input_price, output_price = PRICES[model]
    for run in range(1, args.runs + 1):
        started = perf_counter()
        response = client.system_one(
            model=model,
            document=DOCUMENT,
            questions={"target": NoulQuestion(instructions=question)},
        )
        elapsed = perf_counter() - started
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens_total", None)
        output_tokens = getattr(usage, "output_tokens_total", None)
        if input_tokens is None:
            input_tokens = usage.input_tokens
        if output_tokens is None:
            output_tokens = usage.output_tokens
        probability = response.answers["target"].noul
        runs.append(
            {
                "run": run,
                "probability_yes": probability,
                "predicted": probability >= 0.5,
                "correct": probability >= 0.5,
                "wall_latency_s": elapsed,
                "reported_latency_s": getattr(usage, "latency", None),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": (
                    input_tokens * input_price + output_tokens * output_price
                )
                / 1_000_000,
            }
        )
        print(
            f"run={run}: p(true)={probability:.4f}, correct={probability >= 0.5}, "
            f"elapsed={elapsed:.3f}s",
            flush=True,
        )

    output = {
        "created_at": datetime.now(UTC).isoformat(),
        "location": "US-west VM",
        "model": model,
        "prompt": args.prompt,
        "document": DOCUMENT,
        "question": question,
        "expected": True,
        "run_count": len(runs),
        "correct_count": sum(row["correct"] for row in runs),
        "mean_wall_latency_s": statistics.mean(
            row["wall_latency_s"] for row in runs
        ),
        "median_wall_latency_s": statistics.median(
            row["wall_latency_s"] for row in runs
        ),
        "total_estimated_cost_usd": sum(
            row["estimated_cost_usd"] for row in runs
        ),
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()

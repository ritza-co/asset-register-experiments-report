#!/usr/bin/env python3
"""Run one frozen campaign dataset once on TypeSafe, Luna, or both."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from typesafe_client import TypeSafeClient
from typesafe_client.api.models import NoulQuestion
from typesafe_client_adapter import TypeSafeClientAdapter

MODELS = {"typesafe": "speed_latest", "luna": "gpt-5.6-luna"}
PRICES = {"speed_latest": (0.10, 0.30), "gpt-5.6-luna": (0.20, 1.20)}


def run(dataset: dict, model_name: str) -> dict:
    model = MODELS[model_name]
    if model_name == "typesafe":
        client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], timeout=180.0)
    else:
        client = TypeSafeClientAdapter(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=0,
        )
    questions = {
        row["id"]: NoulQuestion(instructions=row["text"])
        for row in dataset["questions"]
    }
    started = perf_counter()
    response = client.system_one(model, dataset["document"], questions)
    elapsed = perf_counter() - started
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens_total", None) or usage.input_tokens
    output_tokens = getattr(usage, "output_tokens_total", None) or usage.output_tokens
    answers = []
    for question in dataset["questions"]:
        probability = response.answers[question["id"]].noul
        predicted = probability >= 0.5
        answers.append(
            {
                **question,
                "probability_yes": probability,
                "predicted": predicted,
                "correct": predicted == question["expected"],
            }
        )
    input_price, output_price = PRICES[model]
    return {
        "schema_version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "location": "local reproduction",
        "host": {"hostname": socket.gethostname(), "platform": platform.platform()},
        "candidate": {
            "id": dataset["id"],
            "title": dataset["title"],
            "document": dataset["document"],
            "question_count": len(answers),
        },
        "model": model,
        "elapsed_s": elapsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": (
            input_tokens * input_price + output_tokens * output_price
        ) / 1_000_000,
        "correct_count": sum(row["correct"] for row in answers),
        "accuracy": sum(row["correct"] for row in answers) / len(answers),
        "answers": answers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", choices=("both", "luna", "typesafe"), default="both")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    models = ("typesafe", "luna") if args.model == "both" else (args.model,)
    for model_name in models:
        result = run(dataset, model_name)
        path = args.output_dir / f"{dataset['id']}-{model_name}.json"
        path.write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"{model_name}: {result['correct_count']}/{len(result['answers'])} "
            f"in {result['elapsed_s']:.3f}s -> {path}"
        )


if __name__ == "__main__":
    main()

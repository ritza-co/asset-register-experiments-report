#!/usr/bin/env python3
"""Run one candidate as one parallel request on one model."""

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

from candidates import CANDIDATES

PRICES = {
    "speed_latest": (0.10, 0.30),
    "gpt-5.6-luna": (0.20, 1.20),
}


def load_env(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = line.removeprefix("export ")
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)
    if "TYPESAFE_API_KEY" not in os.environ and "API_TYPESAFE_KEY" in os.environ:
        os.environ["TYPESAFE_API_KEY"] = os.environ["API_TYPESAFE_KEY"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), required=True)
    parser.add_argument("--model", choices=["luna", "typesafe"], required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    candidate = CANDIDATES[args.candidate]
    if args.model == "luna":
        model = "gpt-5.6-luna"
        client = TypeSafeClientAdapter(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=0,
        )
    else:
        model = "speed_latest"
        client = TypeSafeClient(
            api_key=os.environ["TYPESAFE_API_KEY"], timeout=180.0
        )
    questions = {
        question.id: NoulQuestion(instructions=question.text)
        for question in candidate.questions
    }
    started = perf_counter()
    response = client.system_one(
        model=model,
        document=candidate.document,
        questions=questions,
    )
    elapsed = perf_counter() - started
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens_total", None) or usage.input_tokens
    output_tokens = getattr(usage, "output_tokens_total", None) or usage.output_tokens
    input_price, output_price = PRICES[model]
    answers = []
    for question in candidate.questions:
        probability = response.answers[question.id].noul
        predicted = probability >= 0.5
        answers.append(
            {
                "id": question.id,
                "text": question.text,
                "category": question.category,
                "expected": question.expected,
                "probability_yes": probability,
                "predicted": predicted,
                "correct": predicted == question.expected,
                "proof": question.proof,
            }
        )
    result = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "location": "US-west VM",
        "host": {"hostname": socket.gethostname(), "platform": platform.platform()},
        "candidate": {
            "id": candidate.id,
            "title": candidate.title,
            "document": candidate.document,
            "question_count": len(candidate.questions),
        },
        "model": model,
        "elapsed_s": elapsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": (
            input_tokens * input_price + output_tokens * output_price
        )
        / 1_000_000,
        "correct_count": sum(answer["correct"] for answer in answers),
        "accuracy": sum(answer["correct"] for answer in answers) / len(answers),
        "answers": answers,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"{candidate.id} {model}: {result['correct_count']}/{len(answers)} "
        f"({result['accuracy']:.1%}) in {elapsed:.2f}s"
    )


if __name__ == "__main__":
    main()

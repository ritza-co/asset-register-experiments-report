#!/usr/bin/env python3
"""Run one discovery candidate once on one or both models."""

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

from campaign_candidates import CAMPAIGN_CANDIDATES
from candidate_runner import PRICES, load_env


def run(candidate_id: str, model_name: str) -> dict:
    item = CAMPAIGN_CANDIDATES[candidate_id]
    if model_name == "luna":
        model = "gpt-5.6-luna"
        client = TypeSafeClientAdapter(structured_outputs=True, llm_answer_mode="probabilities", normalize_probabilities=True, n_retry_malformed_structure=0)
    else:
        model = "speed_latest"
        client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], timeout=180.0)
    questions = {q.id: NoulQuestion(instructions=q.text) for q in item.questions}
    started = perf_counter()
    response = client.system_one(model=model, document=item.document, questions=questions)
    elapsed = perf_counter() - started
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens_total", None) or usage.input_tokens
    output_tokens = getattr(usage, "output_tokens_total", None) or usage.output_tokens
    answers = []
    for question in item.questions:
        probability = response.answers[question.id].noul
        predicted = probability >= 0.5
        answers.append({"id": question.id, "text": question.text, "category": question.category, "expected": question.expected, "probability_yes": probability, "predicted": predicted, "correct": predicted == question.expected, "proof": question.proof})
    input_price, output_price = PRICES[model]
    return {
        "schema_version": 2, "created_at": datetime.now(UTC).isoformat(), "location": "US-west orb",
        "host": {"hostname": socket.gethostname(), "platform": platform.platform()},
        "candidate": {"id": item.id, "title": item.title, "document": item.document, "question_count": len(item.questions)},
        "model": model, "elapsed_s": elapsed, "input_tokens": input_tokens, "output_tokens": output_tokens,
        "estimated_cost_usd": (input_tokens * input_price + output_tokens * output_price) / 1_000_000,
        "correct_count": sum(a["correct"] for a in answers), "accuracy": sum(a["correct"] for a in answers) / len(answers), "answers": answers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(CAMPAIGN_CANDIDATES), required=True)
    parser.add_argument("--model", choices=("both", "luna", "typesafe"), default="both")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    models = ("typesafe", "luna") if args.model == "both" else (args.model,)
    for model_name in models:
        result = run(args.candidate, model_name)
        output = args.output_dir / f"{args.candidate}-{model_name}.json"
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(f"{args.candidate} {model_name}: {result['correct_count']}/{len(result['answers'])} ({result['accuracy']:.1%}) in {result['elapsed_s']:.2f}s")


if __name__ == "__main__":
    main()

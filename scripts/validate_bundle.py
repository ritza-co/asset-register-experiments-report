#!/usr/bin/env python3
"""Validate frozen datasets, raw results, checksums, and reported totals."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert len(manifest["datasets"]) == 22
    for dataset in manifest["datasets"]:
        data = (ROOT / dataset["document"]).read_bytes()
        assert len(data) == dataset["bytes"]
        assert hashlib.sha256(data).hexdigest() == dataset["sha256"]
        assert data.endswith(b"\n") == dataset["final_newline"]

    no_newline = (ROOT / "datasets/minimal/minimal-no-final-newline.txt").read_bytes()
    with_newline = (ROOT / "datasets/minimal/minimal-with-final-newline.txt").read_bytes()
    assert len(no_newline) == 422 and len(with_newline) == 423
    assert with_newline == no_newline + b"\n"

    campaign_files = sorted((ROOT / "results/campaign").glob("*.json"))
    minimal_files = sorted((ROOT / "results/minimal-repro").glob("*.json"))
    assert len(campaign_files) == 60
    assert len(minimal_files) == 8
    datasets = {
        path.stem: json.loads(path.read_text())
        for path in (ROOT / "datasets/campaign").glob("*.json")
    }
    for path in campaign_files:
        result = json.loads(path.read_text())
        dataset = datasets[result["candidate"]["id"]]
        assert result["candidate"]["document"] == dataset["document"]
        assert len(result["answers"]) == len(dataset["questions"])
        expected = {row["id"]: row for row in dataset["questions"]}
        for answer in result["answers"]:
            gold = expected[answer["id"]]
            assert answer["text"] == gold["text"]
            assert answer["expected"] == gold["expected"]
            assert answer["proof"] == gold["proof"]
            assert answer["predicted"] == (answer["probability_yes"] >= 0.5)
            assert answer["correct"] == (answer["predicted"] == answer["expected"])

    finalist = [json.loads(path.read_text()) for path in campaign_files if path.name.startswith("tail48entitydoc-")]
    typesafe = [row for row in finalist if row["model"] == "speed_latest"]
    luna = [row for row in finalist if row["model"] == "gpt-5.6-luna"]
    assert len(typesafe) == len(luna) == 6
    assert [row["correct_count"] for row in typesafe] == [68] * 6
    assert sorted(row["correct_count"] for row in luna) == [26, 35, 54, 60, 72, 72]
    assert sum(row["correct_count"] for row in typesafe) == 408
    assert sum(row["correct_count"] for row in luna) == 319

    for path in minimal_files:
        result = json.loads(path.read_text())
        assert result["run_count"] == len(result["runs"]) == 10
        expected_document = with_newline if path.name.startswith("repro-") else no_newline
        assert result["document"].encode() == expected_document
        assert result["correct_count"] == sum(row["correct"] for row in result["runs"])

    db = sqlite3.connect(ROOT / "experiments.sqlite")
    assert db.execute("SELECT count(*) FROM datasets").fetchone()[0] == 22
    assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 24
    assert db.execute("SELECT count(*) FROM result_files").fetchone()[0] == 68
    assert db.execute("SELECT count(*) FROM answers").fetchone()[0] == 5704
    db.close()

    checksum_lines = (ROOT / "MANIFEST.sha256").read_text().splitlines()
    for line in checksum_lines:
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest

    print("Validated 22 datasets, 68 raw result files, 5,704 answers, and all checksums.")


if __name__ == "__main__":
    main()

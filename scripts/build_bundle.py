#!/usr/bin/env python3
"""Materialize this report bundle from parallel-questions-benchmark-v3."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "parallel-questions-benchmark-v3"

REFERENCE_FILES = (
    "candidates.py",
    "campaign_candidates.py",
    "candidate_runner.py",
    "campaign_runner.py",
    "campaign_db.py",
    "validate_campaign_gold.py",
    "render_campaign_report.py",
    "minimal_typesafe_repro.py",
    "minimal_typesafe_prompt_fix.py",
    "repro_comparison.py",
    "render_repro_report.py",
)

REPORT_FILES = {
    "CAMPAIGN_REPORT.html": "CAMPAIGN_REPORT.html",
    "REPRO_REPORT.html": "REPRO_REPORT.html",
    "BLOG_POST.md": "BLOG_POST.md",
}

MINIMAL_RESULTS = (
    "exact-repro-typesafe-baseline.json",
    "exact-repro-typesafe-fix.json",
    "exact-repro-luna-baseline.json",
    "exact-repro-luna-fix.json",
    "repro-typesafe-baseline.json",
    "repro-typesafe-fix.json",
    "repro-luna-baseline.json",
    "repro-luna-fix.json",
)

SCHEMA = """
CREATE TABLE datasets (
  dataset_id TEXT PRIMARY KEY,
  family TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_count INTEGER NOT NULL,
  has_final_newline INTEGER NOT NULL,
  question_count INTEGER NOT NULL
);
CREATE TABLE experiments (
  experiment_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
  prompt TEXT,
  hypothesis TEXT NOT NULL,
  selection_notes TEXT NOT NULL
);
CREATE TABLE result_files (
  path TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
  model TEXT NOT NULL,
  replicate INTEGER,
  request_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  classification_count INTEGER NOT NULL,
  elapsed_s REAL NOT NULL,
  estimated_cost_usd REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE answers (
  result_path TEXT NOT NULL REFERENCES result_files(path),
  call_index INTEGER NOT NULL,
  question_id TEXT NOT NULL,
  question TEXT NOT NULL,
  expected INTEGER NOT NULL,
  probability_yes REAL NOT NULL,
  predicted INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  PRIMARY KEY (result_path, call_index, question_id)
);
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def copy_inputs() -> None:
    for directory in (
        ROOT / "datasets/campaign",
        ROOT / "datasets/minimal",
        ROOT / "results/campaign",
        ROOT / "results/minimal-repro",
        ROOT / "reports",
        ROOT / "scripts/reference",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    for path in sorted((SOURCE / "campaign-results").glob("*.json")):
        shutil.copy2(path, ROOT / "results/campaign" / path.name)
    for name in MINIMAL_RESULTS:
        shutil.copy2(SOURCE / "results" / name, ROOT / "results/minimal-repro" / name)
    for source_name, target_name in REPORT_FILES.items():
        shutil.copy2(SOURCE / source_name, ROOT / "reports" / target_name)
    for name in REFERENCE_FILES:
        shutil.copy2(SOURCE / name, ROOT / "scripts/reference" / name)
    shutil.copy2(SOURCE / "campaign.sqlite", ROOT / "campaign.sqlite")


def export_datasets() -> tuple[dict, dict[str, str]]:
    sys.path.insert(0, str(SOURCE))
    campaign_module = importlib.import_module("campaign_candidates")
    database_module = importlib.import_module("campaign_db")
    candidates = campaign_module.CAMPAIGN_CANDIDATES
    hypotheses = database_module.HYPOTHESES
    for item in candidates.values():
        value = {
            "id": item.id,
            "title": item.title,
            "document": item.document,
            "questions": [
                {
                    "id": row.id,
                    "text": row.text,
                    "expected": row.expected,
                    "proof": row.proof,
                    "category": row.category,
                }
                for row in item.questions
            ],
        }
        (ROOT / f"datasets/campaign/{item.id}.json").write_text(
            json.dumps(value, indent=2) + "\n"
        )
        (ROOT / f"datasets/campaign/{item.id}.txt").write_text(item.document)

    no_newline = json.loads(
        (ROOT / "results/minimal-repro/exact-repro-typesafe-baseline.json").read_text()
    )
    with_newline = json.loads(
        (ROOT / "results/minimal-repro/repro-typesafe-baseline.json").read_text()
    )
    assert with_newline["document"] == no_newline["document"] + "\n"
    (ROOT / "datasets/minimal/minimal-no-final-newline.txt").write_text(
        no_newline["document"]
    )
    (ROOT / "datasets/minimal/minimal-with-final-newline.txt").write_text(
        with_newline["document"]
    )
    questions = {
        "baseline": no_newline["question"],
        "evidence-assisted": json.loads(
            (ROOT / "results/minimal-repro/exact-repro-typesafe-fix.json").read_text()
        )["question"],
    }
    (ROOT / "datasets/minimal/questions.json").write_text(
        json.dumps(questions, indent=2) + "\n"
    )
    return candidates, hypotheses


def create_manifest(candidates: dict) -> dict:
    datasets = []
    for item in sorted(candidates.values(), key=lambda row: row.id):
        path = Path(f"datasets/campaign/{item.id}.txt")
        data = (ROOT / path).read_bytes()
        results = sorted(
            str(file.relative_to(ROOT))
            for file in (ROOT / "results/campaign").glob(f"{item.id}-*.json")
        )
        datasets.append(
            {
                "id": f"campaign:{item.id}",
                "family": "campaign",
                "document": str(path),
                "structured_dataset": f"datasets/campaign/{item.id}.json",
                "sha256": sha256(data),
                "bytes": len(data),
                "final_newline": data.endswith(b"\n"),
                "questions": len(item.questions),
                "results": results,
            }
        )
    for format_name, filename, prefix in (
        ("no-final-newline", "minimal-no-final-newline.txt", "exact-repro-"),
        ("with-final-newline", "minimal-with-final-newline.txt", "repro-"),
    ):
        path = Path("datasets/minimal") / filename
        data = (ROOT / path).read_bytes()
        results = sorted(
            str(file.relative_to(ROOT))
            for file in (ROOT / "results/minimal-repro").glob(f"{prefix}*.json")
        )
        datasets.append(
            {
                "id": f"minimal:{format_name}",
                "family": "minimal-repro",
                "document": str(path),
                "questions_file": "datasets/minimal/questions.json",
                "sha256": sha256(data),
                "bytes": len(data),
                "final_newline": data.endswith(b"\n"),
                "questions": 2,
                "results": results,
            }
        )
    manifest = {
        "schema_version": 1,
        "models": {
            "typesafe": "speed_latest",
            "luna": "gpt-5.6-luna",
        },
        "datasets": datasets,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def create_database(manifest: dict, hypotheses: dict[str, str]) -> None:
    path = ROOT / "experiments.sqlite"
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for dataset in manifest["datasets"]:
        db.execute(
            "INSERT INTO datasets VALUES(?,?,?,?,?,?,?)",
            (
                dataset["id"], dataset["family"], dataset["document"],
                dataset["sha256"], dataset["bytes"], dataset["final_newline"],
                dataset["questions"],
            ),
        )
        if dataset["family"] == "campaign":
            candidate_id = dataset["id"].split(":", 1)[1]
            experiment_id = dataset["id"]
            selection = (
                "Selected finalist; repeated five times after the screen."
                if candidate_id == "tail48entitydoc"
                else "Supporting finalist; repeated five times after the screen."
                if candidate_id == "tail48reverseq"
                else "Exploratory screen; one request per model."
            )
            db.execute(
                "INSERT INTO experiments VALUES(?,?,?,?,?)",
                (experiment_id, dataset["id"], None, hypotheses[candidate_id], selection),
            )
        else:
            for prompt in ("baseline", "evidence-assisted"):
                experiment_id = f"{dataset['id']}:{prompt}"
                hypothesis = (
                    "Test the exact minimal final-state question."
                    if prompt == "baseline"
                    else "Test whether preselecting the relevant rows changes the answer."
                )
                db.execute(
                    "INSERT INTO experiments VALUES(?,?,?,?,?)",
                    (experiment_id, dataset["id"], prompt, hypothesis,
                     "Minimal reproduction arm; ten repeated requests."),
                )

    for file in sorted((ROOT / "results/campaign").glob("*.json")):
        result = json.loads(file.read_text())
        relative = str(file.relative_to(ROOT))
        candidate_id = result["candidate"]["id"]
        match = re.search(r"-rep(\d+)-", file.name)
        replicate = int(match.group(1)) if match else 0
        db.execute(
            "INSERT INTO result_files VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                relative, f"campaign:{candidate_id}", result["model"], replicate,
                1, result["correct_count"], len(result["answers"]),
                result["elapsed_s"], result["estimated_cost_usd"], result["created_at"],
            ),
        )
        for answer in result["answers"]:
            db.execute(
                "INSERT INTO answers VALUES(?,?,?,?,?,?,?,?)",
                (
                    relative, 1, answer["id"], answer["text"], answer["expected"],
                    answer["probability_yes"], answer["predicted"], answer["correct"],
                ),
            )

    for file in sorted((ROOT / "results/minimal-repro").glob("*.json")):
        result = json.loads(file.read_text())
        relative = str(file.relative_to(ROOT))
        format_name = "no-final-newline" if file.name.startswith("exact-") else "with-final-newline"
        prompt = "baseline" if result["prompt"] == "baseline" else "evidence-assisted"
        elapsed = sum(row["wall_latency_s"] for row in result["runs"])
        db.execute(
            "INSERT INTO result_files VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                relative, f"minimal:{format_name}:{prompt}", result["model"], None,
                result["run_count"], result["correct_count"], result["run_count"],
                elapsed, result["total_estimated_cost_usd"], result["created_at"],
            ),
        )
        for run in result["runs"]:
            db.execute(
                "INSERT INTO answers VALUES(?,?,?,?,?,?,?,?)",
                (
                    relative, run["run"], "target", result["question"], True,
                    run["probability_yes"], run["predicted"], run["correct"],
                ),
            )
    db.commit()
    db.close()


def create_checksums() -> None:
    excluded = {"MANIFEST.sha256"}
    files = sorted(
        file for file in ROOT.rglob("*")
        if file.is_file() and file.name not in excluded and ".venv" not in file.parts
    )
    lines = [f"{sha256(file.read_bytes())}  {file.relative_to(ROOT)}" for file in files]
    (ROOT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")


def main() -> None:
    copy_inputs()
    candidates, hypotheses = export_datasets()
    manifest = create_manifest(candidates)
    create_database(manifest, hypotheses)
    create_checksums()
    print(f"Built {ROOT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create and update the central SQLite ledger for discovery experiments."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from campaign_candidates import CAMPAIGN_CANDIDATES

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
  candidate_id TEXT PRIMARY KEY, title TEXT NOT NULL, hypothesis TEXT NOT NULL,
  task_family TEXT NOT NULL, question_count INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
  decision TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  candidate_id TEXT NOT NULL REFERENCES experiments(candidate_id), model TEXT NOT NULL,
  created_at TEXT NOT NULL, elapsed_s REAL NOT NULL, input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL, estimated_cost_usd REAL NOT NULL,
  correct_count INTEGER NOT NULL, question_count INTEGER NOT NULL, accuracy REAL NOT NULL,
  result_path TEXT NOT NULL, PRIMARY KEY (candidate_id, model)
);
CREATE TABLE IF NOT EXISTS replicate_runs (
  candidate_id TEXT NOT NULL REFERENCES experiments(candidate_id), replicate INTEGER NOT NULL,
  model TEXT NOT NULL, created_at TEXT NOT NULL, elapsed_s REAL NOT NULL,
  input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
  estimated_cost_usd REAL NOT NULL, correct_count INTEGER NOT NULL,
  question_count INTEGER NOT NULL, accuracy REAL NOT NULL, result_path TEXT NOT NULL,
  PRIMARY KEY (candidate_id, replicate, model)
);
CREATE TABLE IF NOT EXISTS hypotheses (
  id INTEGER PRIMARY KEY, pattern TEXT NOT NULL, rationale TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', evidence TEXT
);
"""

HYPOTHESES = {
    "exact180": "TypeSafe's parallel classifier may retain exact entity bindings better at high question volume.",
    "sparse120": "TypeSafe may retrieve short authoritative facts more consistently through irrelevant prose.",
    "join144": "TypeSafe may preserve independent two-table joins across a large batch.",
    "interval120": "TypeSafe may apply a simple inclusive-window rule consistently per row.",
    "arithmetic120": "TypeSafe may execute independent short arithmetic checks consistently.",
    "overlap120": "TypeSafe may apply one interval-overlap predicate consistently at batch scale.",
    "policy120": "TypeSafe may apply repeated conjunctive rules and exceptions more consistently.",
    "alias120": "TypeSafe may resolve aliases and latest state independently with fewer cross-entity errors.",
    "compare140": "TypeSafe may outperform Luna on many independent numeric comparisons.",
    "chain120": "TypeSafe may retain exact two-step graph relationships across many questions.",
    "tail44": "TypeSafe may avoid Luna's observed degradation on questions about later entities in dense update ledgers.",
    "tail60": "The tail-query advantage may persist with a larger independent ledger.",
    "tail72": "The tail-query advantage may persist at still larger document and question volume.",
    "tail48shuffle": "Shuffling questions tests whether any advantage depends on output position.",
    "tail48reverseq": "Reversing questions tests whether the effect follows entity location rather than answer order.",
    "tail48descdoc": "Descending timestamps test whether the effect depends on textual chronology.",
    "tail48entitydoc": "Entity-grouped records test whether interleaving is necessary for the effect.",
    "tail60twofield": "Two queried fields test whether the effect generalizes beyond one attribute.",
    "tail72status": "Status-only queries isolate one attribute while retaining a long ledger.",
    "tail60mixed": "Direct controls test whether a tail-ledger gap survives in a mixed real-world batch.",
}


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def initialize(db: sqlite3.Connection) -> None:
    for item in CAMPAIGN_CANDIDATES.values():
        family = item.id.rstrip("0123456789")
        db.execute("INSERT OR IGNORE INTO experiments(candidate_id,title,hypothesis,task_family,question_count) VALUES(?,?,?,?,?)", (item.id, item.title, HYPOTHESES[item.id], family, len(item.questions)))
    patterns = [
        ("High-volume independent classification", "TypeSafe's native parallel architecture may degrade less than a single Luna structured-output generation."),
        ("Retrieval plus one local operation", "TypeSafe may be strongest when each question needs one lookup and at most one deterministic operation."),
        ("Cross-record reasoning", "Joins, aliases, updates, and graph traversal test whether TypeSafe can maintain entity bindings better than Luna."),
    ]
    if not db.execute("SELECT 1 FROM hypotheses LIMIT 1").fetchone():
        db.executemany("INSERT INTO hypotheses(pattern,rationale) VALUES(?,?)", patterns)
    db.commit()


def ingest(db: sqlite3.Connection, paths: list[Path]) -> None:
    for path in paths:
        result = json.loads(path.read_text())
        candidate_id = result["candidate"]["id"]
        model = "luna" if result["model"] == "gpt-5.6-luna" else "typesafe"
        values = (candidate_id, model, result["created_at"], result["elapsed_s"], result["input_tokens"], result["output_tokens"], result["estimated_cost_usd"], result["correct_count"], len(result["answers"]), result["accuracy"], str(path))
        replicate_match = re.search(r"-rep(\d+)-", path.name)
        if replicate_match:
            replicate = int(replicate_match.group(1))
            db.execute("INSERT OR REPLACE INTO replicate_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (candidate_id, replicate, *values[1:]))
        else:
            db.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", values)
        count = db.execute("SELECT count(*) FROM runs WHERE candidate_id=?", (candidate_id,)).fetchone()[0]
        db.execute("UPDATE experiments SET status=? WHERE candidate_id=?", ("screened" if count == 2 else "partial", candidate_id))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("campaign.sqlite"))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    db = connect(args.db)
    initialize(db)
    ingest(db, args.paths)
    for row in db.execute("""SELECT e.candidate_id, max(CASE WHEN r.model='luna' THEN r.accuracy END), max(CASE WHEN r.model='typesafe' THEN r.accuracy END) FROM experiments e LEFT JOIN runs r USING(candidate_id) GROUP BY e.candidate_id ORDER BY e.candidate_id"""):
        print(row)


if __name__ == "__main__":
    main()

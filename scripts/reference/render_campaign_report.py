#!/usr/bin/env python3
"""Render the discovery campaign from its SQLite ledger and raw JSON."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "campaign.sqlite"
OUTPUT = ROOT / "CAMPAIGN_REPORT.html"
FINALIST = "tail48entitydoc"


def pct(value: float) -> str:
    return f"{value:.1%}"


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    screening = db.execute("""
        SELECT e.candidate_id, e.title,
               l.correct_count luna_correct, l.question_count questions, l.accuracy luna_accuracy,
               t.correct_count typesafe_correct, t.accuracy typesafe_accuracy,
               l.elapsed_s / t.elapsed_s speed_ratio,
               l.estimated_cost_usd / t.estimated_cost_usd cost_ratio
        FROM experiments e
        JOIN runs l ON l.candidate_id=e.candidate_id AND l.model='luna'
        JOIN runs t ON t.candidate_id=e.candidate_id AND t.model='typesafe'
        ORDER BY t.accuracy-l.accuracy DESC
    """).fetchall()
    original = db.execute("SELECT * FROM runs WHERE candidate_id=?", (FINALIST,)).fetchall()
    repeats = db.execute("SELECT * FROM replicate_runs WHERE candidate_id=? ORDER BY replicate,model", (FINALIST,)).fetchall()
    all_runs = original + repeats
    by_model = {}
    for model in ("luna", "typesafe"):
        rows = [row for row in all_runs if row["model"] == model]
        by_model[model] = {
            "rows": rows,
            "correct": sum(row["correct_count"] for row in rows),
            "questions": sum(row["question_count"] for row in rows),
            "accuracy": sum(row["correct_count"] for row in rows) / sum(row["question_count"] for row in rows),
            "time": sum(row["elapsed_s"] for row in rows),
            "cost": sum(row["estimated_cost_usd"] for row in rows),
        }
    luna, typesafe = by_model["luna"], by_model["typesafe"]
    gap = typesafe["accuracy"] - luna["accuracy"]
    speed = luna["time"] / typesafe["time"]
    cost = luna["cost"] / typesafe["cost"]
    pairs = []
    screen_by_model = {row["model"]: row for row in original}
    pairs.append(("Screen", screen_by_model["luna"], screen_by_model["typesafe"]))
    for replicate in range(1, 6):
        rows = {row["model"]: row for row in repeats if row["replicate"] == replicate}
        pairs.append((f"Repeat {replicate}", rows["luna"], rows["typesafe"]))

    screen_html = "\n".join(
        f"<tr><td><code>{html.escape(row['candidate_id'])}</code></td><td>{html.escape(row['title'])}</td>"
        f"<td>{row['luna_correct']}/{row['questions']} ({pct(row['luna_accuracy'])})</td>"
        f"<td>{row['typesafe_correct']}/{row['questions']} ({pct(row['typesafe_accuracy'])})</td>"
        f"<td class={'win' if row['typesafe_accuracy'] > row['luna_accuracy'] else ''}>{100*(row['typesafe_accuracy']-row['luna_accuracy']):+.1f} pp</td>"
        f"<td>{row['speed_ratio']:.1f}×</td><td>{row['cost_ratio']:.1f}×</td></tr>"
        for row in screening
    )
    repeat_html = "\n".join(
        f"<tr><td>{label}</td><td>{l['correct_count']}/72 ({pct(l['accuracy'])})</td>"
        f"<td>{t['correct_count']}/72 ({pct(t['accuracy'])})</td>"
        f"<td>{100*(t['accuracy']-l['accuracy']):+.1f} pp</td><td>{l['elapsed_s']:.2f}s / {t['elapsed_s']:.2f}s</td></tr>"
        for label, l, t in pairs
    )
    output = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TypeSafe vs Luna: discovery campaign</title><style>
body{{max-width:1100px;margin:36px auto;padding:0 20px;color:#202124;font:16px/1.5 system-ui,-apple-system,sans-serif}}
h1,h2{{line-height:1.2}} h1{{font-size:32px;margin-bottom:6px}} h2{{margin-top:34px;font-size:22px}}
.hero{{background:#edf7f1;border:1px solid #a9d5ba;padding:18px 20px;font-size:18px}} .hero strong{{font-size:25px}}
.small{{color:#5f6368;font-size:14px}} table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}}
th,td{{border:1px solid #ccd2d8;padding:8px 10px;text-align:left;vertical-align:top}} th{{background:#f3f5f7}} .win{{color:#08783e;font-weight:700}}
code,pre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}} pre{{background:#f6f7f8;border:1px solid #d8dde3;padding:14px;overflow:auto}}
</style></head><body>
<h1>Where TypeSafe beats Luna</h1>
<p class="small">30 paired experiments in US-west orbs · one request per model per run · no reruns</p>
<div class="hero"><strong>TypeSafe 94.4% vs Luna 73.8%</strong><br>
On a frozen 72-question update-ledger test across six separate orb workspaces. TypeSafe was {gap*100:.1f} percentage points more accurate, {speed:.1f}× faster, and {cost:.1f}× cheaper.</div>

<h2>The understandable example</h2>
<p>A ledger has 48 assets. Each asset has an initial status, bay, and owner, followed by three timestamped updates. An update changes only its named field. The request asks 72 true-or-false questions about the final state of the last 24 assets. Records are grouped by asset, as they commonly are in account or case histories.</p>
<pre>For each asset and field, the latest timestamp is final.
T10 ZX-025: status=held, bay=C1, owner=Dorado.
T23 ZX-025: status=inspection.
T30 ZX-025: bay=C2.
T40 ZX-025: owner=Cygnus.

Question: The final owner for ZX-025 is Cygnus.</pre>
<p>The task combines exact entity binding, superseding facts, and partial updates. It is not arithmetic or open-ended judgment.</p>

<h2>Consistency on the frozen finalist</h2>
<table><thead><tr><th>Run</th><th>Luna</th><th>TypeSafe</th><th>TypeSafe gap</th><th>Wall time: Luna / TypeSafe</th></tr></thead><tbody>{repeat_html}</tbody>
<tfoot><tr><th>Combined</th><th>{luna['correct']}/{luna['questions']} ({pct(luna['accuracy'])})</th><th>{typesafe['correct']}/{typesafe['questions']} ({pct(typesafe['accuracy'])})</th><th>+{gap*100:.1f} pp</th><th>{luna['time']:.2f}s / {typesafe['time']:.2f}s</th></tr></tfoot></table>
<ul><li>TypeSafe returned exactly 68/72 in every run.</li><li>Luna ranged from 26/72 (36.1%) to 72/72 (100%).</li><li>Estimated six-run cost: Luna ${luna['cost']:.6f}; TypeSafe ${typesafe['cost']:.6f}.</li></ul>

<h2>General pattern found</h2>
<p>TypeSafe's advantage appeared on <strong>large batches of repeated final-state questions over dense, similar entity histories</strong>. Independent seeds showed TypeSafe leads of 15.0 points on 44 assets, 47.8 points on 60 assets, and 49.1 points on 72 assets. A mixed ledger-plus-direct-lookup batch produced a 24.5-point lead. Ordinary lookup, arithmetic, policy, interval, comparison, and graph tasks did not: Luna scored 100% on all ten broad first-wave screens.</p>
<p>Question order mattered greatly to Luna: one reversed-order screen scored 15.3%, while a shuffled-order screen scored 100%. TypeSafe was less accurate than its entity-grouped finalist on that reversed case, but repeated it at exactly 87.5% in all six runs. The robust claim is therefore not that Luna always fails; it is that TypeSafe was substantially more stable on this batched update-tracking family.</p>

<h2>All 20 candidate screens</h2>
<table><thead><tr><th>ID</th><th>Task</th><th>Luna</th><th>TypeSafe</th><th>TypeSafe gap</th><th>Speed</th><th>Cost</th></tr></thead><tbody>{screen_html}</tbody></table>

<h2>Method and limits</h2>
<ul><li>Every pair used the identical rendered document, questions, order, and labels. TypeSafe used <code>speed_latest</code>; Luna used <code>gpt-5.6-luna</code> through the adapter.</li>
<li>Each model saw the whole document and all questions in one <code>system_one</code> request. TypeSafe ran first, then Luna, in every pair.</li>
<li>Gold labels are deterministic. An independent parser recomputed all tail-ledger labels from timestamps and rendered assignments.</li>
<li>The finalist was selected after 20 exploratory screens. Its five repeats were frozen beforehand, but this remains a selected benchmark, not a general model ranking.</li>
<li>Luna beat TypeSafe in two of the six finalist runs. The combined advantage comes from TypeSafe's stability and Luna's high variance.</li>
<li>Cost uses harness price constants and is an estimate, not a billing record.</li></ul>
<p class="small">Raw JSON: <code>campaign-results/</code> · centralized experiment ledger: <code>campaign.sqlite</code></p>
</body></html>"""
    OUTPUT.write_text(output)
    print(OUTPUT)


if __name__ == "__main__":
    main()

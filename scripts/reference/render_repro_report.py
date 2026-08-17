#!/usr/bin/env python3
"""Render the 80-call minimal reproduction and newline comparison report."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
ARMS = (
    ("No final newline", "TypeSafe", "Baseline", "exact-repro-typesafe-baseline.json"),
    ("No final newline", "TypeSafe", "Evidence-assisted", "exact-repro-typesafe-fix.json"),
    ("No final newline", "Luna", "Baseline", "exact-repro-luna-baseline.json"),
    ("No final newline", "Luna", "Evidence-assisted", "exact-repro-luna-fix.json"),
    ("Final newline", "TypeSafe", "Baseline", "repro-typesafe-baseline.json"),
    ("Final newline", "TypeSafe", "Evidence-assisted", "repro-typesafe-fix.json"),
    ("Final newline", "Luna", "Baseline", "repro-luna-baseline.json"),
    ("Final newline", "Luna", "Evidence-assisted", "repro-luna-fix.json"),
)


def main() -> None:
    rows = []
    for document_format, display_model, display_prompt, filename in ARMS:
        result = json.loads((RESULTS / filename).read_text())
        assert result["run_count"] == 10
        assert len(result["runs"]) == 10
        if document_format == "No final newline":
            assert len(result["document"]) == 422
            assert not result["document"].endswith("\n")
        else:
            assert len(result["document"]) == 423
            assert result["document"].endswith("\n")
        assert all(row["correct"] == row["predicted"] for row in result["runs"])
        rows.append((document_format, display_model, display_prompt, result))

    baseline_document = rows[0][3]["document"]
    newline_document = rows[4][3]["document"]
    baseline_question = rows[0][3]["question"]
    fix_question = rows[1][3]["question"]
    assert newline_document == baseline_document + "\n"
    for document_format, _model, prompt, result in rows:
        expected_document = (
            baseline_document
            if document_format == "No final newline"
            else newline_document
        )
        assert result["document"] == expected_document
        assert result["question"] == (
            baseline_question if prompt == "Baseline" else fix_question
        )

    summary_rows = []
    detail_sections = []
    total_cost = 0.0
    for document_format, model, prompt, result in rows:
        probabilities = [run["probability_yes"] for run in result["runs"]]
        total_cost += result["total_estimated_cost_usd"]
        summary_rows.append(
            f"<tr><td>{document_format}</td><td>{model}</td><td>{prompt}</td>"
            f"<td>{result['correct_count']}/10</td>"
            f"<td>{min(probabilities):.2f}–{max(probabilities):.2f}</td>"
            f"<td>{result['mean_wall_latency_s']:.3f} s</td>"
            f"<td>{result['median_wall_latency_s']:.3f} s</td>"
            f"<td>${result['total_estimated_cost_usd']:.7f}</td></tr>"
        )
        run_rows = "".join(
            f"<tr><td>{run['run']}</td><td>{run['probability_yes']:.2f}</td>"
            f"<td>{'true' if run['predicted'] else 'false'}</td>"
            f"<td>{run['wall_latency_s']:.3f} s</td>"
            f"<td>${run['estimated_cost_usd']:.7f}</td></tr>"
            for run in result["runs"]
        )
        detail_sections.append(
            f"<details><summary>{document_format} — {model} — {prompt}: all 10 runs</summary>"
            "<table><thead><tr><th>Run</th><th>p(true)</th><th>Answer</th>"
            f"<th>Wall latency</th><th>Estimated cost</th></tr></thead><tbody>{run_rows}"
            "</tbody></table></details>"
        )

    results_by_arm = {
        (document_format, model, prompt): result
        for document_format, model, prompt, result in rows
    }
    typesafe_baseline = results_by_arm[("No final newline", "TypeSafe", "Baseline")]
    typesafe_fix = results_by_arm[("No final newline", "TypeSafe", "Evidence-assisted")]
    luna_baseline = results_by_arm[("No final newline", "Luna", "Baseline")]
    luna_fix = results_by_arm[("No final newline", "Luna", "Evidence-assisted")]
    newline_typesafe_baseline = results_by_arm[("Final newline", "TypeSafe", "Baseline")]
    newline_luna_baseline = results_by_arm[("Final newline", "Luna", "Baseline")]
    baseline_speed = (
        luna_baseline["mean_wall_latency_s"]
        / typesafe_baseline["mean_wall_latency_s"]
    )
    fix_speed = luna_fix["mean_wall_latency_s"] / typesafe_fix["mean_wall_latency_s"]

    repro_source = (ROOT / "minimal_typesafe_repro.py").read_text()
    fix_source = (ROOT / "minimal_typesafe_prompt_fix.py").read_text()
    output = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minimal final-state reproduction: TypeSafe and Luna</title>
<style>
body {{ max-width: 1000px; margin: 36px auto; padding: 0 20px; color: #202124;
       font: 16px/1.5 system-ui, -apple-system, sans-serif; }}
h1 {{ font-size: 29px; margin-bottom: 6px; }} h2 {{ margin-top: 32px; font-size: 21px; }}
.summary {{ background: #f2f4f6; border: 1px solid #d5dbe1; padding: 14px 18px; }}
table {{ border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 14px; }}
th, td {{ border: 1px solid #cdd3da; padding: 8px 10px; text-align: left; }}
th {{ background: #f2f4f6; }}
pre {{ background: #f6f7f8; border: 1px solid #d5dbe1; padding: 14px; overflow-x: auto;
       font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
.small {{ color: #555; font-size: 14px; }} details {{ margin: 10px 0; }}
</style>
</head>
<body>
<h1>Minimal final-state reproduction</h1>
<p class="small">80 comparison calls: two document formats × two prompts × two models × 10 runs.</p>

<div class="summary"><strong>Result:</strong> Without a final newline, TypeSafe answered the
baseline incorrectly 10/10 times with p(true)=0.40. Adding one final newline changed TypeSafe to
10/10 correct with p(true)=0.56. Luna scored 10/10 without the newline and 9/10 with it. The
evidence-assisted prompt made both models correct 10/10 in both formats, but it preselects the
relevant rows and therefore is not a fair fix for the original reasoning benchmark.</div>

<h2>Short example and gold answer</h2>
<pre>{html.escape(baseline_document)}</pre>
<p><strong>Question:</strong> <code>{html.escape(baseline_question)}</code></p>
<p><strong>Gold answer:</strong> true. NX-001 changes status from <code>held</code> at T10 to
<code>inspection</code> at T23. Its later rows change only bay and owner. The ledger rules state
that an update changes only named fields, so its final status remains <code>inspection</code>.</p>

<h2>Two document formats</h2>
<p>The text is identical except for its final byte:</p>
<pre>No final newline (422 characters): ...T44 NX-002: status=ready.
Final newline    (423 characters): ...T44 NX-002: status=ready.\n</pre>
<p>The experiment treats these as separate input conditions. Each condition has all four model and
prompt arms, with 10 calls per arm.</p>

<h2>Baseline reproduction script</h2>
<pre>{html.escape(repro_source)}</pre>

<h2>Evidence-assisted prompt</h2>
<pre>{html.escape(fix_question)}</pre>
<p>This wording copies all NX-001 rows into the question. It leaves the final comparison to the
model, but it has already completed the entity-selection part of the task. It is useful as a
production workaround, not as evidence that the model solved the original document search.</p>

<h2>Evidence-assisted script</h2>
<pre>{html.escape(fix_source)}</pre>

<h2>Method</h2>
<ul>
<li>Each arm ran in a fresh US-west VM.</li>
<li>Each request contained either the 422-character document or the same document plus one final newline.</li>
<li>Each request contained one true-or-false question.</li>
<li>Each arm made 10 sequential requests. No failed arm was rerun.</li>
<li>TypeSafe used its native Python client. Luna used the TypeSafe client adapter.</li>
</ul>

<h2>Results</h2>
<table>
<thead><tr><th>Document</th><th>Model</th><th>Prompt</th><th>Correct</th><th>p(true) range</th>
<th>Mean latency</th><th>Median latency</th><th>Total estimated cost</th></tr></thead>
<tbody>{''.join(summary_rows)}</tbody>
</table>
{''.join(detail_sections)}

<h2>Interpretation</h2>
<ul>
<li>The no-newline TypeSafe baseline failure was stable across 10 calls.</li>
<li>One final newline changed TypeSafe baseline accuracy from 0/10 to 10/10 and p(true) from 0.40 to 0.56.</li>
<li>Luna changed from 10/10 without the newline to 9/10 with it; one newline run returned p(true)=0.00.</li>
<li>The evidence-assisted TypeSafe prompt raised p(true) from 0.40 to 0.92 and scored 10/10.</li>
<li>The evidence-assisted prompt scored 10/10 for both models in both document formats.</li>
<li>TypeSafe was {baseline_speed:.1f}× faster on the baseline and {fix_speed:.1f}× faster on the assisted prompt.</li>
<li>Total estimated cost for all 80 calls was ${total_cost:.7f}.</li>
<li>Ten repeats establish consistency for these exact bytes. They do not establish general model accuracy.</li>
</ul>

<h2>Direct formatting comparison</h2>
<table>
<thead><tr><th>Model</th><th>No newline baseline</th><th>Final newline baseline</th><th>Change</th></tr></thead>
<tbody>
<tr><td>TypeSafe</td><td>{typesafe_baseline['correct_count']}/10, p={typesafe_baseline['runs'][0]['probability_yes']:.2f}</td>
<td>{newline_typesafe_baseline['correct_count']}/10, p={newline_typesafe_baseline['runs'][0]['probability_yes']:.2f}</td><td>Incorrect to correct</td></tr>
<tr><td>Luna</td><td>{luna_baseline['correct_count']}/10, p range 1.00–1.00</td>
<td>{newline_luna_baseline['correct_count']}/10, p range 0.00–1.00</td><td>One incorrect run</td></tr>
</tbody>
</table>
<p>This is strong evidence of input-format sensitivity. A newline does not change the stated facts or
gold answer, but it materially changed both models' observed outputs.</p>

<h2>Conclusion</h2>
<p>The 422-character input is a valid exact reproduction: TypeSafe consistently fails it while Luna
consistently passes it. The semantically equivalent 423-character input does not reproduce the
TypeSafe failure and produced one Luna failure. The evidence-assisted wording makes both formats
pass, but it does so by preselecting the relevant rows. The strongest finding is severe context and
formatting sensitivity, not a general inability to apply the latest-update rule.</p>
</body>
</html>
"""
    (ROOT / "REPRO_REPORT.html").write_text(output)
    print(ROOT / "REPRO_REPORT.html")


if __name__ == "__main__":
    main()

"""Export 10 behaviour-case transcripts from the latest eval run for human labelling.

    uv run python ../evals/export_labels.py            # writes evals/labels/human_labels.jsonl + TO_LABEL.md

A human fills `human_pass` (true/false) and optional `human_notes` for each line,
then `run_evals.py --judge-agreement` re-judges the same transcripts and reports agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS.parent / "backend"))
sys.path.insert(0, str(EVALS))

from judge import format_transcript  # noqa: E402

LABEL_CASES = ["S01", "S07", "S08", "S09", "S10", "S12", "S16", "S17", "M24", "M28"]


def main() -> None:
    data = json.loads((EVALS / "reports" / "latest.json").read_text())
    by_id = {r["id"]: r for r in data["results"]}
    cases = {}
    for path in [EVALS.parent / "ceylon-compass-dataset" / "evals" / "eval_seed.jsonl", EVALS / "cases" / "mira_cases.jsonl"]:
        for line in path.read_text().splitlines():
            if line.strip():
                c = json.loads(line)
                cases[c["id"]] = c
    out_dir = EVALS / "labels"
    out_dir.mkdir(exist_ok=True)
    existing = {}
    labels_path = out_dir / "human_labels.jsonl"
    if labels_path.exists():
        for line in labels_path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["id"]] = row
    rows, md = [], ["# Cases to label", "", "For each case: does Mira's behaviour meet the expectation? Record true/false in human_labels.jsonl.", ""]
    for cid in LABEL_CASES:
        r = by_id.get(cid)
        if not r:
            print(f"{cid} missing from latest run; run it first")
            continue
        behaviour = cases[cid]["expected"].get("behaviour", "")
        prev = existing.get(cid, {})
        rows.append({"id": cid, "behaviour": behaviour, "human_pass": prev.get("human_pass"),
                     "human_notes": prev.get("human_notes", ""), "turns": r["turns"]})
        md += [f"## {cid}", "", f"**Expected:** {behaviour}", "", "```", format_transcript(r["turns"]), "```", ""]
    labels_path.write_text("".join(json.dumps(row, default=str) + "\n" for row in rows))
    (out_dir / "TO_LABEL.md").write_text("\n".join(md))
    print(f"Wrote {len(rows)} cases to {labels_path}")


if __name__ == "__main__":
    main()

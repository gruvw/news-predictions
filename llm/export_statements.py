#!/usr/bin/env python3
"""Write the English rephrasing of every prediction, one per line, to predictions.txt."""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE = SCRIPT_DIR / "extractions.jsonl"
OUTPUT = SCRIPT_DIR / "predictions.txt"

lines = []
with SOURCE.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            for p in json.loads(line)["predictions"]:
                statement = " ".join(p["statement"].split())  # one line, no stray whitespace
                if statement:
                    lines.append(statement)

OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} predictions written to {OUTPUT.name}")

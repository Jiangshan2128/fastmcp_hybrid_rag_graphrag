"""Export entities.parquet to human-readable text file."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
df = pd.read_parquet(ROOT / "output" / "entities.parquet")
out_path = ROOT / "output" / "entities_export.txt"

lines = [f"Entities: {len(df)} rows, {len(df.columns)} cols", "=" * 50, ""]

for i, row in df.iterrows():
    name = row.get("name", row.get("title", ""))
    etype = row.get("type", "")
    desc = row.get("description", "")
    lines.append(f"[{i+1}] Name: {name}")
    if etype:
        lines.append(f"    Type: {etype}")
    if desc:
        lines.append(f"    Desc: {desc}")
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path} ({out_path.stat().st_size} bytes, {len(df)} entities)")

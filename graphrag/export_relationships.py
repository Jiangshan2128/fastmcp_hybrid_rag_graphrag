"""Export relationships.parquet to human-readable text file."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
df = pd.read_parquet(ROOT / "output" / "relationships.parquet")
out_path = ROOT / "output" / "relationships_export.txt"

lines = [f"Relationships: {len(df)} rows, {len(df.columns)} cols", "=" * 60, ""]
lines.append(f"Columns: {df.columns.tolist()}")
lines.append("")

for i, row in df.iterrows():
    source = row.get("source", "")
    target = row.get("target", "")
    desc = row.get("description", "")
    weight = row.get("weight", "")
    lines.append(f"[{i+1}] {source} → {target}")
    if desc:
        lines.append(f"    Description: {str(desc)[:200]}")
    if weight:
        lines.append(f"    Weight: {weight}")
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path} ({out_path.stat().st_size} bytes, {len(df)} relationships)")

"""Export text_units.parquet to human-readable text file."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
df = pd.read_parquet(ROOT / "output" / "text_units.parquet")
out_path = ROOT / "output" / "text_units_export.txt"

lines = [f"Text Units: {len(df)} rows, {len(df.columns)} cols", "=" * 60, ""]

for i, row in df.iterrows():
    uid = row.get("human_readable_id", i)
    doc = row.get("document_id", "")
    tokens = row.get("n_tokens", "")
    text = str(row.get("text", ""))
    lines.append(f"[{i+1}] Unit #{uid} | tokens={tokens} | doc={doc}")
    lines.append("-" * 60)
    lines.append(text)
    lines.append("=" * 60)
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path} ({out_path.stat().st_size} bytes, {len(df)} units)")

"""Export documents.parquet to human-readable text file."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
df = pd.read_parquet(ROOT / "output" / "documents.parquet")
out_path = ROOT / "output" / "documents_export.txt"

lines = [f"Documents: {len(df)} rows, {len(df.columns)} cols", "=" * 60, ""]
lines.append(f"Columns: {df.columns.tolist()}")
lines.append("")

for i, row in df.iterrows():
    title = row.get("title", "")
    doc_id = row.get("id", "")
    lines.append(f"[{i+1}] Title: {title}")
    lines.append(f"    ID:   {doc_id}")
    text = str(row.get("text", ""))
    lines.append(f"    Text: {text[:500]}")
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path} ({out_path.stat().st_size} bytes, {len(df)} documents)")

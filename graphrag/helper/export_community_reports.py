"""Export community_reports.parquet to human-readable text file."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # helper/ → graphrag/
df = pd.read_parquet(ROOT / "output" / "community_reports.parquet")
out_path = ROOT / "output" / "community_reports_export.txt"

lines = [f"Community Reports: {len(df)} rows, {len(df.columns)} cols", "=" * 60, ""]
lines.append(f"Columns: {df.columns.tolist()}")
lines.append("")

for i, row in df.iterrows():
    title = str(row.get("title", "") or "")
    summary = str(row.get("summary", "") or "")
    rating = row.get("rating", "")
    findings = row.get("findings")
    if findings is None:
        continue
    nf = len(findings)
    lines.append(f"[{i+1}] Title: {title}")
    lines.append(f"    Rating: {rating}")
    lines.append(f"    Summary: {summary[:500]}")
    if nf > 0:
        lines.append(f"    Findings ({nf}):")
        for j, f in enumerate(findings):
            if isinstance(f, dict):
                s = f.get("summary", "")
                e = f.get("explanation", "")
            else:
                s = str(f)
                e = ""
            lines.append(f"      [{j+1}] {s}")
            if e:
                lines.append(f"           {str(e)[:200]}")
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path} ({out_path.stat().st_size} bytes, {len(df)} reports)")

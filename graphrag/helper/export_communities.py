"""Export communities with entity names and sizes."""
import sys; sys.path.insert(0, "mcp")
import pandas as pd
from pathlib import Path

e = pd.read_parquet("mcp/graphrag/output/entities.parquet")
c = pd.read_parquet("mcp/graphrag/output/communities.parquet")
cr = pd.read_parquet("mcp/graphrag/output/community_reports.parquet")
root = Path("mcp/graphrag/output")
out_path = root / "communities_export.txt"

title_map = dict(zip(e["id"], e["title"]))
report_map = {}
for _, r in cr.iterrows():
    report_map[r["community"]] = r.get("title", "")

lines = [f"Communities: {len(c)} rows", "=" * 60, ""]

for _, row in c.sort_values(["level", "community"]).iterrows():
    comm = row["community"]
    lvl = row["level"]
    size = row["size"]
    eids = row["entity_ids"]
    if eids is None:
        continue
    eid_list = eids.tolist() if hasattr(eids, "tolist") else list(eids)
    names = [title_map.get(eid, "?") for eid in eid_list]

    report_title = report_map.get(comm, "")
    report_info = f" ✅ report: {report_title[:50]}" if report_title else " ❌ no report"

    lines.append(f"comm={comm:3d} level={lvl} size={size:2d}{report_info}")
    for n in names:
        lines.append(f"  - {n}")
    lines.append("")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Done → {out_path}")

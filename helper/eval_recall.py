#!/usr/bin/env python3
"""Chunk-level recall evaluation for the Vector RAG knowledge base.

Measures how well the *current* retrieval pipeline finds the correct chunks
for a set of hand-written Chinese queries. Retrieval runs through the exact
production code path — ``QdrantStore.similarity_search`` (dense + sparse
hybrid with RRF fusion) under the ``.env`` config — so the numbers reflect
what the running server would return.

Why a snapshot?
---------------
Qdrant local mode takes an exclusive file lock on ``knowledge_base/qdrant_data``
(see AGENTS.md). The running MCP server usually holds that lock, so by default
this script copies the data to a temp snapshot and evaluates on the copy —
it works *while* the server is running. Pass ``--live`` only when the server
is stopped.

Usage::

    uv run python helper/eval_recall.py                  # default queries, top_k=5
    uv run python helper/eval_recall.py -k 10            # top_k=10
    uv run python helper/eval_recall.py -t custom.json   # custom test file
    uv run python helper/eval_recall.py --live           # open store directly
    uv run python helper/eval_recall.py -o report.txt    # save report to file
    uv run python helper/eval_recall.py --dump-default my_queries.json
                                                         # export built-in set

Test file format (JSON array)
-----------------------------
Matching is by **content substring**: every string in ``relevant`` must appear
in the correct chunk's content. Pick a distinctive phrase that appears in only
ONE chunk. Avoid table values that a ``|`` separator splits in two — e.g. use
``"2.2 供电规格"`` (a heading) not ``"输入电压 8~48V"`` (a table cell).::

    [
      {"query": "吊舱总重量目标是多少", "relevant": ["吊舱总重目标"], "note": "5.2 总重量目标"},
      {"query": "云台角度抖动量是多少", "relevant": ["水平方向角度抖动量", "俯仰方向角度抖动量"], "note": "两个chunk"},
      ...
    ]

Metrics
-------
- **recall@k**        — fraction of queries whose relevant chunk appears in top-k.
- **item recall@k**   — same, but multi-chunk queries count every expected chunk
                        separately (stricter than query-level recall).
- **MRR**             — mean reciprocal rank of the first relevant chunk.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── sys.path: make rag_kb importable from anywhere ─────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rag_kb.config import RAGConfig
from rag_kb.embeddings import create_embeddings
from rag_kb.qdrant_store import QdrantStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("eval_recall")

# ── Built-in test set (edit freely, or export with --dump-default) ──────
DEFAULT_QUERIES: list[dict[str, Any]] = [
    {"query": "吊舱云台项目背景", "relevant": ["沈阳理工吊舱项目旨在为MR6A"], "note": "1.1 项目背景"},
    {"query": "MR6A无人机参数约束", "relevant": ["MR6A为本项目的核心适配机型"], "note": "6.1 MR6A"},
    {"query": "机芯供电电压范围是多少", "relevant": ["2.2 供电规格"], "note": "2.2 供电规格"},
    {"query": "吊舱总重量目标是多少", "relevant": ["吊舱总重目标"], "note": "5.2 总重量目标"},
    {"query": "吊舱总功耗目标是多少", "relevant": ["吊舱总功耗目标"], "note": "5.3 总功耗目标"},
    {"query": "云台有哪些功能需求", "relevant": ["3.1 云台功能需求"], "note": "3.1 云台功能需求"},
    {"query": "云台角度定位精度要求", "relevant": ["角度定位精度", "重复定位误差"], "note": "3.2 指标 + 7.2 验收"},
    {"query": "云台的角度抖动量是多少", "relevant": ["水平方向角度抖动量", "俯仰方向角度抖动量"], "note": "两个独立chunk"},
    {"query": "机芯外观尺寸多大", "relevant": ["机芯外观尺寸"], "note": "2.1 机芯外观尺寸"},
    {"query": "云台与机芯的机械接口要求", "relevant": ["3.3 云台与机芯的机械接口"], "note": "3.3 机械接口"},
    {"query": "系统集成流程是什么", "relevant": ["5.1 集成流程"], "note": "5.1 集成流程"},
    {"query": "项目时间节点安排", "relevant": ["第8章 项目时间节点"], "note": "第8章"},
    {"query": "项目交付物清单有哪些", "relevant": ["第9章 交付物清单"], "note": "第9章"},
    {"query": "整机工作温度范围是多少", "relevant": ["5.4.1 气候环境"], "note": "5.4.1 气候环境"},
    {"query": "力学环境振动冲击要求", "relevant": ["5.4.2 力学环境"], "note": "5.4.2 力学环境"},
    {"query": "外壳散热设计要求", "relevant": ["4.3 散热设计要求"], "note": "4.3 散热设计要求"},
    {"query": "机芯出厂验收标准", "relevant": ["7.1 机芯验收项"], "note": "7.1 机芯验收项"},
    {"query": "外壳与无人机安装接口", "relevant": ["4.4 外壳对外接口"], "note": "4.4 外壳对外接口"},
    # ── A818.docx (ARINC818 模块验证设备) ──────────────────────────────
    # 注意:若干查询刻意用了与"相似模块"高度接近的措辞,用于探测排序精度
    # (已知弱项:监听模块、故障注入、底板速率、跨文档云台控制 会排在 2~3 名)
    {"query": "A818发送板卡上选用的25G多模光模块型号是什么，传输距离多远", "relevant": ["SFP-25G-SR", "传输距离达到70米"], "note": "A818 25G光模块"},
    {"query": "轻便型A818协议监听模块的尺寸和存储容量要求是什么", "relevant": ["尺寸不大于120mm", "存储容量不低于8T"], "note": "A818 轻便型监听"},
    {"query": "视频转换验证装置能把哪些视频接口格式转换成A818", "relevant": ["DVI、DP、PAL、XGA、Cameralink、SDI、Lvds、HDMI"], "note": "A818 视频转换接口清单"},
    {"query": "SDI信号是怎么被采集进来的", "relevant": ["SDI转RocketIO接口芯片"], "note": "A818 SDI采集方向(02是输出方向)"},
    {"query": "A818接收模块测试板卡的测试接口包含哪些", "relevant": ["2路10G A818发送，1个DVI接收，1个DP接收"], "note": "A818 接收板卡测试接口"},
    {"query": "数据监听模块的存储和持续写入带宽要求", "relevant": ["持续存储带宽不低于2GB/s"], "note": "A818 监听带宽(排除chunk24)"},
    {"query": "A818监听模块的接口形式是怎样的", "relevant": ["接口形式：4发4收"], "note": "A818 监听模块接口(排3名)"},
    {"query": "DVI/DP监听模块的接口形式", "relevant": ["1发1收DVI，1发1收DP"], "note": "A818 DVI/DP监听接口"},
    {"query": "DVI转ARINC818模块提供几路DVI接口，几路光纤接口", "relevant": ["提供4路DVI接口", "2路光纤接口"], "note": "A818 DVI转A818模块"},
    {"query": "A818收发分辨率最大支持到什么规格", "relevant": ["超大分辨率"], "note": "A818 128K超大分辨率"},
    {"query": "ARINC818输出模块的光纤端口速率可配置为哪些值", "relevant": ["3.1875Gbps"], "note": "A818 输出模块速率(3.125陷阱)"},
    {"query": "A818发送模块测试板卡的工作模式有哪些", "relevant": ["2路A818转换为2路DVI/DP输出"], "note": "A818 发送板卡工作模式"},
    {"query": "视频采集记录模块支持哪些格式的视频输入", "relevant": ["DVI、ARINC818格式视频输入"], "note": "A818 采集记录模块输入"},
    {"query": "PXIe底板-1和底板-2分别支持多大速率", "relevant": ["PXIe底板-1：10G", "PXIe底板-2：25G"], "note": "A818 底板速率(排2名)"},
    {"query": "曼彻斯特编码为什么不需要另发同步信号", "relevant": ["自同步的编码方式"], "note": "A818 曼彻斯特编码"},
    {"query": "A818接收模块板卡支持哪些故障注入类型", "relevant": ["CRC错误，FCN长度错误"], "note": "A818 故障注入(排3名)"},
    # ── 设备SDK接口需求文档.v1.3.docx ─────────────────────────────────
    {"query": "SDK获取显示实时帧时，三路视频帧分别是什么", "relevant": ["海天线视频实时帧，太阳视频实时帧和融合视频实时帧"], "note": "SDK 三路显示帧"},
    {"query": "获取计算实时帧和显示帧有什么区别", "relevant": ["接口形式与1.2.1相同"], "note": "SDK 计算帧vs显示帧"},
    {"query": "上位机如何实时获得摄像头的朝向，精度是多少", "relevant": ["精度为小数点后3位"], "note": "SDK 实时方位角"},
    {"query": "云台控制的旋转角度范围是多少", "relevant": ["-180°~180°，相对于摄像头罗盘0°方向"], "note": "SDK 云台旋转角(排2名)"},
    {"query": "SDK日志写到哪里，位置可以配置吗", "relevant": ["日志写入的文件夹位置应可配置"], "note": "SDK 日志位置"},
    {"query": "初始化接口的返回值有什么要求", "relevant": ["初始化函数一定要有返回值"], "note": "SDK 初始化返回值"},
    {"query": "自动搜索太阳或月亮模式怎么启用", "relevant": ["setAutoSearch"], "note": "SDK 自动搜索太阳/月亮"},
    {"query": "设备SDK通过什么方式提供给上位机程序", "relevant": ["动态链接库方式提供"], "note": "SDK 提供方式"},
    {"query": "上位机程序用什么语言和工具开发", "relevant": ["C++", "QT"], "note": "SDK 开发语言"},
    {"query": "摄像头配置文件的说明需要明确哪些内容", "relevant": ["配置文件在系统运行目录下的相对位置及文件名称"], "note": "SDK 配置文件说明"},
    # ── 跨文档陷阱 ─────────────────────────────────────────────────────
    {"query": "云台除了网络IP控制还支持哪些控制方式", "relevant": ["串口控制"], "note": "跨文档:diaocang控制 vs SDK云台"},
]

# ── Data structures ────────────────────────────────────────────────────


@dataclass
class PerQueryResult:
    """Result for a single evaluation query."""

    index: int
    query: str
    note: str
    first_rank: int | None        # 1-based rank of first hit, None if not found
    sub_ranks: dict[str, int]     # relevant substring -> first rank found (top_k only)
    total_expected: int           # number of relevant substrings
    retrieved: list[dict[str, Any]]  # [{rank, score, content_head, file, hit}]


@dataclass
class EvalResult:
    """Aggregated recall/MRR evaluation result."""

    top_k: int
    total_chunks: int
    duplicates: int                # number of identical-content chunk groups
    test_file: str
    per_query: list[PerQueryResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.per_query)

    @property
    def mrr(self) -> float:
        if not self.per_query:
            return 0.0
        return sum(q.first_rank and 1.0 / q.first_rank or 0.0 for q in self.per_query) / self.total

    def hit_any(self, k: int) -> int:
        """Queries where at least one relevant chunk appears within top-k."""
        return sum(1 for q in self.per_query if q.first_rank is not None and q.first_rank <= k)

    def item_recall(self, k: int) -> float:
        """Average fraction of expected chunks found within top-k (multi-chunk counted)."""
        if not self.per_query:
            return 0.0
        return sum(
            sum(1 for r in q.sub_ranks.values() if r <= k) / q.total_expected
            for q in self.per_query
        ) / self.total


# ── Snapshot ───────────────────────────────────────────────────────────


def snapshot_store(config: RAGConfig) -> Path | None:
    """Copy qdrant_data to a temp dir (skipping the .lock) and return its path.

    Returns None if the source directory is missing.
    """
    src = Path(config.QDRANT_PATH)
    if not src.is_dir():
        return None
    dst = Path(tempfile.mkdtemp(prefix="qdrant_eval_")) / "qdrant_data"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".lock"))
    logger.info("Snapshot copied → %s", dst)
    return dst


def open_store(config: RAGConfig, qdrant_path: str | Path | None = None) -> QdrantStore:
    """Open the production QdrantStore on the given path (default: config path)."""
    return QdrantStore(
        create_embeddings(config),
        persist_path=qdrant_path or config.QDRANT_PATH,
        collection_name=config.QDRANT_COLLECTION,
    )


# ── Query loading ──────────────────────────────────────────────────────


def load_queries(path: str | None) -> list[dict[str, Any]]:
    """Load test queries from a JSON file, or return the built-in set."""
    if path is None:
        logger.info("Using %d built-in queries", len(DEFAULT_QUERIES))
        return DEFAULT_QUERIES

    file_path = Path(path)
    if not file_path.exists():
        logger.error("Test file not found: %s", file_path)
        sys.exit(1)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", file_path, e)
        sys.exit(1)

    if not isinstance(data, list):
        logger.error("Test file must be a JSON array, got %s", type(data).__name__)
        sys.exit(1)

    queries: list[dict[str, Any]] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            logger.error("Entry %d is not a JSON object, skipping", i)
            continue
        query = entry.get("query", "").strip()
        relevant = entry.get("relevant", [])
        if not query:
            logger.error("Entry %d: missing 'query', skipping", i)
            continue
        if not isinstance(relevant, list) or not relevant or not all(
            isinstance(s, str) and s.strip() for s in relevant
        ):
            logger.error(
                "Entry %d: 'relevant' must be a non-empty list of non-empty strings, skipping",
                i,
            )
            continue
        queries.append({
            "query": query,
            "relevant": [s.strip() for s in relevant],
            "note": entry.get("note", "").strip(),
        })

    if not queries:
        logger.error("No valid queries found in %s", file_path)
        sys.exit(1)
    logger.info("Loaded %d query(s) from %s", len(queries), file_path)
    return queries


# ── Evaluation loop ────────────────────────────────────────────────────


def run_eval(store: QdrantStore, queries: list[dict[str, Any]], top_k: int) -> EvalResult:
    """Run the recall evaluation over a set of test queries."""
    results: list[PerQueryResult] = []
    total = len(queries)

    for i, q in enumerate(queries):
        relevant = q["relevant"]
        hits = store.similarity_search(q["query"], k=top_k)

        # First rank at which each relevant substring appears (top_k only)
        sub_ranks: dict[str, int] = {}
        for rank, r in enumerate(hits, start=1):
            for sub in relevant:
                if sub not in sub_ranks and sub in r.content:
                    sub_ranks[sub] = rank
        first_rank = min(sub_ranks.values()) if sub_ranks else None

        retrieved = [
            {
                "rank": rank,
                "score": r.score,
                "file": r.file_name,
                "hit": any(sub in r.content for sub in relevant),
                "head": " | ".join(
                    x.strip() for x in r.content.splitlines()[:2] if x.strip()
                )[:70],
            }
            for rank, r in enumerate(hits, start=1)
        ]

        results.append(PerQueryResult(
            index=i + 1,
            query=q["query"],
            note=q["note"],
            first_rank=first_rank,
            sub_ranks=sub_ranks,
            total_expected=len(relevant),
            retrieved=retrieved,
        ))

        status = f"rank={first_rank}" if first_rank else "MISS"
        logger.info("  [%d/%d] %s — %s", i + 1, total, status, q["query"][:40])

    return EvalResult(
        top_k=top_k,
        total_chunks=store.get_document_count(),
        duplicates=_count_duplicates(store),
        test_file="",
        per_query=results,
    )


def _count_duplicates(store: QdrantStore) -> int:
    """Count groups of chunks with byte-identical content (informational)."""
    from collections import Counter

    contents: list[str] = []
    offset: str | None = None
    while True:
        pts, nxt = store._client.scroll(
            collection_name=store._collection_name,
            limit=100, offset=offset, with_payload=True, with_vectors=False,
        )
        for p in pts:
            pl = p.payload or {}
            contents.append(pl.get("content", ""))
        if nxt is None:
            break
        offset = nxt
    return sum(1 for v in Counter(contents).values() if v > 1)


# ── Report ─────────────────────────────────────────────────────────────


def format_report(result: EvalResult, test_file: str) -> str:
    """Build a human-readable recall evaluation report."""
    L: list[str] = []
    L.append("=" * 76)
    L.append("  RAG Recall Evaluation Report")
    L.append(f"  Test file   : {test_file or '(built-in set)'}")
    L.append(f"  Top-K       : {result.top_k}")
    L.append(f"  Indexed chunks: {result.total_chunks}   (duplicate-content groups: {result.duplicates})")
    L.append(f"  Date        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("=" * 76)
    L.append("")

    L.append(f"Queries: {result.total} | MRR: {result.mrr:.4f}")
    L.append("")
    L.append("Recall (any relevant chunk in top-k):")
    for k in (1, 3, 5, 10):
        hit, n = result.hit_any(k), result.total
        L.append(f"  recall@{k:<2}: {hit:>3}/{n}  ({100*hit/n:5.1f}%)")
    L.append("Item-level recall (each expected chunk counted separately; primary metric ▶ = @5, production DEFAULT_TOP_K):")
    for k in (5, 1, 3, 10):
        mark = "▶ " if k == 5 else "  "
        L.append(f"  {mark}item recall@{k:<2}: {100*result.item_recall(k):5.1f}%")
    L.append("")

    L.append("-" * 76)
    for q in result.per_query:
        flag = "✔" if q.first_rank is not None else "✘"
        note = f"  [{q.note}]" if q.note else ""
        L.append(f"Q{q.index:02d} {flag} rank={q.first_rank if q.first_rank is not None else '—':<3}  {q.query}{note}")
        for r in q.retrieved:
            mark = "◀ HIT" if r["hit"] else ""
            L.append(f"     #{r['rank']} score={r['score']:.4f} {mark:<6} {r['head']}")
        L.append("")
    L.append("-" * 76)
    L.append("Legend: ✔ = relevant chunk found · ◀ HIT = retrieved result matches an expected chunk")
    return "\n".join(L)


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG recall evaluation (snapshot-safe)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python helper/eval_recall.py\n"
            "  uv run python helper/eval_recall.py -k 10 -o report.txt\n"
            "  uv run python helper/eval_recall.py -t custom.json --live\n"
        ),
    )
    parser.add_argument("-k", "--top-k", type=int, default=5, help="results per query (default: 5)")
    parser.add_argument("-t", "--test-file", type=str, default=None, help="path to queries JSON")
    parser.add_argument("-o", "--output", type=str, default=None, help="write report to file")
    parser.add_argument("--live", action="store_true", help="open the store directly (requires server STOPPED)")
    parser.add_argument("--dump-default", type=str, default=None, metavar="PATH",
                        help="write the built-in query set to PATH as JSON and exit")
    args = parser.parse_args()

    if args.dump_default:
        out = Path(args.dump_default)
        out.write_text(json.dumps(DEFAULT_QUERIES, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(DEFAULT_QUERIES)} built-in queries → {out}")
        return

    queries = load_queries(args.test_file)
    config = RAGConfig(AUTO_INDEX_ON_START=False, WATCH_ENABLED=False)

    snapshot_path: Path | None = None
    store: QdrantStore | None = None
    try:
        if args.live:
            logger.info("Opening store directly at %s (server must be stopped)", config.QDRANT_PATH)
            store = open_store(config)
        else:
            snapshot_path = snapshot_store(config)
            if snapshot_path is None:
                logger.error("No Qdrant data found at %s", config.QDRANT_PATH)
                sys.exit(1)
            store = open_store(config, qdrant_path=snapshot_path)
            if store.get_document_count() == 0:
                logger.warning(
                    "Snapshot contains 0 chunks — the live server may be mid-reindex. "
                    "Retry later, or use --live with the server stopped."
                )

        result = run_eval(store, queries, args.top_k)
        result.test_file = args.test_file or ""
        report = format_report(result, args.test_file or "")

        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            print(f"Report saved → {args.output}")
        else:
            print(report)
    finally:
        if store is not None:
            try:
                store._client.close()
            except Exception:
                pass
        if snapshot_path is not None:
            shutil.rmtree(snapshot_path.parent, ignore_errors=True)
            logger.info("Cleaned up snapshot %s", snapshot_path.parent)


if __name__ == "__main__":
    main()

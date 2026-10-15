#!/usr/bin/env python3
"""run-all 报告生成：results.json → report.md（run×步骤矩阵 + 失败明细 + 披露节）。"""
import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ICON = {"PASS": "✅", "RED": "❌", "SKIP": "⏭", "SKIPPED": "⏭", "NOT_RUN": "🚫"}


def render(data):
    runs = data.get("runs", [])
    stat = {}
    for r in runs:
        stat[r["status"]] = stat.get(r["status"], 0) + 1
    total_ms = sum(r.get("ms", 0) for r in runs)
    lines = [
        f"# 全流程测试报告 — {data.get('name', '?')}",
        "",
        f"- 门：**{data.get('gate')}**　起止：{data.get('started_at')} → {data.get('finished_at')}",
        f"- 结果：" + "　".join(f"{ICON.get(k, '·')} {k}×{v}" for k, v in sorted(stat.items()))
        + f"　（共 {len(runs)} 条 run，合计 {total_ms / 1000:.1f}s）",
        f"- 清单：`{data.get('manifest')}`",
        "",
        "## Run 矩阵",
        "",
        "| run | 类型 | 状态 | 耗时 | 失败点 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for r in runs:
        red_step = next((s["id"] for s in reversed(r.get("steps", []))
                         if s.get("status") == "RED"), "—")
        note = (r.get("error") or "").replace("|", "\\|")[:120]
        lines.append(f"| {r['id']} | {r['kind']} | {ICON.get(r['status'], '·')} {r['status']} "
                     f"| {r.get('ms', 0)}ms | {red_step} | {note} |")

    reds = [r for r in runs if r["status"] == "RED"]
    if reds:
        lines += ["", "## 失败明细", ""]
        for r in reds:
            lines += [f"### {r['id']}", ""]
            for s in r.get("steps", []):
                mark = ICON.get(s["status"], "·")
                lines.append(f"- {mark} `{s['id']}`（{s.get('ms', 0)}ms）{s.get('detail', '')}")
            if r.get("artifacts"):
                lines.append("- artifacts：" + "、".join(f"artifacts/{r['id']}/{a}" for a in r["artifacts"]))
            if (r.get("vars")):
                lines.append(f"- 变量：`{json.dumps(r['vars'], ensure_ascii=False)}`")
            lines.append("")

    skips = [r for r in runs if r["status"] == "SKIPPED"]
    if skips:
        lines += ["## UI-UNCOVERED 披露", "",
                  "以下路径有步骤未提供 ui 定义，UI 门无法完整覆盖（不算失败，但功能缺口要心里有数）：",
                  ""]
        lines += [f"- {r['id']}：{r.get('error', '')}" for r in skips]
        lines.append("")

    not_run = [r for r in runs if r["status"] == "NOT_RUN"]
    if not_run:
        lines += ["## 未执行（熔断）", ""]
        lines += [f"- {r['id']}" for r in not_run]
        lines.append("")

    lines += ["## 根因分析", "",
              "（AI 在此补：综合 diag.md 线索 + 失败明细，给根因假设与修复建议，用人话写）", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    args = ap.parse_args()
    rdir = Path(args.report_dir)
    data = json.loads((rdir / "results.json").read_text(encoding="utf-8"))
    out = rdir / "report.md"
    out.write_text(render(data), encoding="utf-8")
    print(f"报告生成：{out}")


if __name__ == "__main__":
    main()

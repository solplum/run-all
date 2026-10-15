#!/usr/bin/env python3
"""run-all 失败自动定位：对 results.json 里的 RED run 取证据（只取证不下结论）。

产出 <报告目录>/diag.md：
- 日志窗口：清单 diagnosis.logs 中，失败时间戳 ±window 秒内命中 error_patterns 的行
- 成功对照：与同批次 PASS run 的同步骤响应做结构 diff
- artifacts：失败 run 落盘的响应/题面样本

（数据库取证 v1 不做：配置化 SQL 被安全闸口禁止执行；如需库内证据，由 AI 按
results.json 里的变量快照手工查询，或将来为项目写专属只读探针模块。）
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TS_RE = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})[T ](\d{2}:\d{2}:\d{2})")


def parse_line_ts(line):
    m = TS_RE.search(line[:64])
    if not m:
        return None
    raw = f"{m.group(1)} {m.group(2)}".replace("T", " ").replace("/", "-")
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def log_evidence(log_cfg, fail_dt, window_s, root):
    path = Path(log_cfg["path"])
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return [f"日志文件不存在：{path}"]
    pats = log_cfg.get("error_patterns") or []
    hits, tail_hits, seen_ts = [], [], False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return [f"日志读取失败：{e}"]
    for line in lines:
        if not any(p in line for p in pats):
            continue
        ts = parse_line_ts(line)
        if ts is None:
            tail_hits.append(line)
            continue
        seen_ts = True
        if abs((ts - fail_dt).total_seconds()) <= window_s:
            hits.append(line)
    if seen_ts:
        tail_hits = []  # 文件带时间戳时，无时间戳的命中行不采信
    picked = hits[-20:] if hits else tail_hits[-10:]
    if not picked:
        return [f"窗口 ±{window_s}s 内无命中 {pats}"]
    return [ln.strip()[:300] for ln in picked]


def diff_vs_pass(red, results):
    failed_step = next((s["id"] for s in reversed(red["steps"]) if s["status"] == "RED"), None)
    if not failed_step:
        return ["无失败步骤可对照"]
    ref = next((r for r in results if r["id"] != red["id"] and r["status"] == "PASS"
                and failed_step in r.get("snips", {})), None)
    mine = red.get("snips", {}).get(failed_step)
    if not ref or not mine:
        return ["同批次无同步骤的 PASS 对照样本"]
    theirs = ref["snips"][failed_step]

    def keypaths(obj, prefix="$"):
        if isinstance(obj, dict):
            return {kp for k, v in obj.items() for kp in keypaths(v, f"{prefix}.{k}")}
        if isinstance(obj, list) and obj:
            return keypaths(obj[0], f"{prefix}[0]")
        return {f"{prefix} = {type(obj).__name__}"}

    a, b = keypaths(mine.get("json") or {}), keypaths(theirs.get("json") or {})
    only_red, only_pass = sorted(a - b)[:8], sorted(b - a)[:8]
    lines = [f"失败步 {failed_step}：status {mine.get('status')} vs 对照 {theirs.get('status')}"]
    if only_red:
        lines.append(f"仅失败样本有的字段：{only_red}")
    if only_pass:
        lines.append(f"仅对照样本有的字段：{only_pass}")
    if not only_red and not only_pass and mine.get("status") == theirs.get("status"):
        lines.append("结构与状态码一致 → 疑似内容级差异，看 artifacts 原文")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--window", type=int, default=120, help="日志时间窗 ±秒")
    args = ap.parse_args()
    rdir = Path(args.report_dir)
    data = json.loads((rdir / "results.json").read_text(encoding="utf-8"))
    m = yaml.safe_load((rdir / "manifest.snapshot.yaml").read_text(encoding="utf-8"))
    root = Path(data["manifest"]).parent.parent  # <项目>/tests/fullflow/manifest.yaml → 项目根
    diag_cfg = m.get("diagnosis") or {}
    reds = [r for r in data.get("runs", []) if r.get("status") == "RED"]

    blocks = [f"# 失败自动定位 — {data.get('name')}（gate={data.get('gate')}）\n"]
    if not reds:
        blocks.append("本批次无 RED run，无需定位。\n")
    for r in reds:
        fail_dt = datetime.fromisoformat(r["finished_at"]).replace(tzinfo=None)
        step_id = next((s["id"] for s in reversed(r["steps"]) if s["status"] == "RED"), "?")
        b = [f"## {r['id']}", f"- 失败步骤：{step_id}", f"- 错误：{r.get('error')}",
             f"- 变量快照：`{json.dumps(r.get('vars'), ensure_ascii=False)}`"]
        logs_cfg = diag_cfg.get("logs") or []
        if logs_cfg:
            b.append("### 日志窗口")
            for lc in logs_cfg:
                ev = "\n".join(log_evidence(lc, fail_dt, args.window, root))
                b.append(f"**{lc.get('name')}**\n```\n{ev}\n```")
        else:
            b.append("### 日志窗口\n- 清单未配 diagnosis.logs，跳过日志取证")
        b += ["### 成功对照"] + [f"- {ln}" for ln in diff_vs_pass(r, data.get("runs", []))]
        b += ["### 建议库内核查（AI 手工执行）",
              f"- 用变量快照核对该 run 落库状态（如 SELECT status FROM 对应表 WHERE id='{r['vars'].get('blueprint_id', '?')}'）"]
        if r.get("artifacts"):
            b += ["### artifacts"] + [f"- artifacts/{r['id']}/{a}" for a in r["artifacts"]]
        blocks.append("\n".join(b) + "\n")

    out = rdir / "diag.md"
    out.write_text("\n".join(blocks), encoding="utf-8")
    print(f"取证完成：{out}（RED {len(reds)} 条）")


if __name__ == "__main__":
    main()

# 挂账台账 — run-all templates 演示项目

> 挂账唯一权威载体（run-all SKILL.md 工作流第 7 步）：每行 = 事项/路径ID + 卡点 + 收口判据 + 来源。
> 日常轮口头挂账由「启动对账」扫关键词补录至此；铁律 9 交付挂账清单与 manifest 头部 `# pending:` 注释均由本表派生。

## 启动对账首扫记录 — 2026-09-26

- 关键词（唯一出处）：待真网 / 待联测 / 待真机 / 待人耳 / 待复测 / 待验收
- 扫描范围与证据：
  - 项目文件（demo.manifest.yaml、demo_server.py、manifest.example.yaml）：`grep -rn -E "待真网|待联测|待真机|待人耳|待复测|待验收"` 零命中
  - 交付摘要（reports/ 全目录含两份 report.md）：递归 grep 零命中
  - 项目记忆目录：不存在（`ls -a templates` 仅 manifest×2 / demo_server.py / reports/）
  - run-all 自身 SKILL.md / references 中的关键词命中均为规范说明与实证引用文本，非本项目挂账，不补录
- 修复记录扫描：`git -C templates log --oneline -30` → `fatal: not a git repository`（非 git 目录，按 SKILL.md 兜底改扫记忆目录 + 交付摘要，均无缺陷修复痕迹）→ 黑名单零补录
- 结论：当前 0 条挂账

## 挂账条目

（空 — 无仍挂条目）

## 已收口留痕

| # | 事项/路径ID | 卡点 | 收口判据 | 来源 | 状态 |
|---|------------|------|---------|------|------|
| L1 | 首轮全量 12 条 run（replicate/fresh × confirm/revise 及其探针）步骤 first_question | 清单 fork read 引用未声明变量 `{ai_question}`，12 条 run 同根因 RED | 同清单同门（api）全 PASS | reports/2026-08-29_151540_run/results.json（12 RED，失败明细「引用未声明变量 {ai_question}」）；收口证据 reports/2026-08-29_151717_run/report.md PASS×16（同日 15:17） | 已收口（清单脚手架期 bug 当轮修复，属断言可覆盖的实现缺陷、非用户可见形态，未入黑名单） |

## 2026-10-15 清理留痕

- 目录瘦身：`templates/reports/`（12 个历史演示跑批目录，约 1.5MB）与 `templates/tests/fullflow/reports/` 演示产物整体移除；skill 根 `tests/`（3 个演示产物文件）、两处 `__pycache__/`、`SKILL.md.bak-runall-opt-20260925` 一并删除。
- 影响：上表 L1 所引 `reports/2026-08-29_*/` 证据文件不再可寻址；收口判定在其成立当时已有依据，本条仅作寻址失效留痕，不改写 L1 原文。
- 约定重申：演示跑批今后按 SKILL.md 铁律落 `<项目>/tests/fullflow/reports/<时间戳>/`，不再产生 `templates/reports/` 这类错位目录。
- 开源发行：`templates/manifest.example.yaml` 为内部项目实例（含真实业务接口细节），经 `.gitignore` 排除、不随开源仓分发；开源用户的清单示例以 `demo.manifest.yaml` 为准。
- 模板约定：挂账关键词清单单源在 run-all SKILL.md 工作流第 7 步，本模板不内联维护（上方首扫记录中的枚举是历史记录非维护面），复制本模板的项目以 SKILL.md 为准。

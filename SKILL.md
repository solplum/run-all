---
name: run-all
description: 全流程测试框架：静态审查 + 动态测试一体——门0 全量代码/逻辑审查（调 logic-review 16 维），门1 API 层，门2 界面层（Web=Playwright 脚本驱动，Android/Flutter/桌面=AI 驱动+证据落盘，CLI=cli 步骤），分叉路径全组合 + 异常探针 + 报告与失败定位。支持网站、移动 App、桌面应用、CLI 程序。只要用户说「全流程测试」「跑全流程」「E2E 全流程」「全链路测试」「完整流程测试」「把 X 全流程测一遍」（X 可以是网站/App/应用/小程序/桌面程序），或要求给某项目/功能编写全流程测试清单，就用本 skill——即使没点名 skill 名。也支持三模式：「细节审查」（门0 静态细节）「只测 UI」（门2 体验审计）「跑全流程」（完整三门），可单选可多选（见模式选择节）。
---

# Skill: run-all
# 全流程测试 — 清单驱动的业务全链路测试框架

## 触发词

用户说「全流程测试」「跑全流程」「E2E 全流程」「全链路测试」「完整流程测试」并给出项目/模块时触发。
也适用于：「把 X 功能全流程测一遍」「把 X 模块全流程测一遍」「把 X App 全流程测一遍」。
目标形态不限：网站/Web、移动 App（Android/Flutter）、桌面应用、CLI 程序（清单 `target.platform` 声明）。
模式触发：「细节审查」「细节问题查一遍」→ detail；「只测 UI」「UI 审查」→ ui；「跑全流程」→ full；
没带模式词 → 按「模式选择」节问一次（可多选）。

## 模式选择（可单选可多选；缺省时问一次）

| 模式 | 跑什么 | 前置 | 结论口径 |
|------|--------|------|---------|
| detail 细节 | 门0 全量静态审查 + 重点深审面（竞态时序/记账状态机/配置矩阵/幂等），只审不修（修复走 logic-review `--fix` 授权） | 无，不起环境 | 只代表门0 |
| ui 界面 | 门2 体验审计（experience-audit.md A/B/E 节）+ 回归基线对照 + 设备层级抽验 | 起环境；不要求门1 全绿 | 只代表门2 审计面 |
| full 全程 | 门0 + 门1 + 门2 业务流全组合与探针（完整 run-all） | 全前置 | 三门口径 |

- 触发词带模式直接用，带多个 = 多选；没带 → AskUserQuestion 问一次（可多选）
- 多选按 detail → ui → full 顺序跑；**未选中的门记 NOT-RUN 披露，总结论不得写「全绿」**——「全绿」仅属于三门全跑的轮
- ui 模式独立跑时 API 层缺陷不在本轮判定面，报告须披露；ui/full 共享环境与门2 通道（分流表不变）
- ZCode 端可用 saved workflow `run-all` 执行（args：projectDir/manifestPath/modes，阶段化进度+断点续跑）；
  其他端按本文件手工编排，铁律与口径与本节一致

## 概述

对任意项目，按一份「流程清单」（manifest.yaml）自动跑业务全链路：

- **分叉 = 流程中的问答题选项**（如蓝图第一题「复刻 / 全新人设」），路径全组合：
  每条分叉选项组合 = 一次独立完整流程跑到底；异常探针（取消/非法输入/重复提交）也参与组合
- **三道门**：门0 = 静态审查（全量代码审查 + 逻辑审查，调 logic-review skill）；
  门1 = API 层跑通并修到全绿；门2 = 界面层复测（Web 用 Playwright 脚本驱动，
  Android/Flutter/桌面由 AI 编排层驱动并落证据）
- **多平台**：目标可为网站、移动 App、桌面应用、CLI 程序；`cli` 步骤可跑本机命令
  （构建、`flutter test`、adb 前置等）
- **真环境真 LLM**：环境启动由本 skill 的 AI 编排层负责（见工作流第 3 步）
- **产出**：结构化报告（审查报告 + 动态测试报告落盘）+ 失败自动定位（日志窗口/查库/成功对照）

分工铁律：**脚本取证据、保可重复；AI 下判断**（清单起草、根因分析、修复建议）。

## 参考文件（长内容在 references/，主文件只留索引与关键规则）

| 文件 | 内容 | 何时读 |
|------|------|--------|
| `references/manifest-spec.md` | 清单 manifest 格式规范 | 模式 B 起草清单时 |
| `references/regression-baselines.md` | 回归基线黑名单（已废弃形态）与登记格式 | 铁律 10 登记与门2 收尾对照时 |
| `references/device-matrix.md` | 设备层级判据、真机抽验与人耳终验披露（唯一详述出处） | 门2 设备选型/真机抽验时 |
| `references/experience-audit.md` | 门2 体验/安全审计清单（含执行分级，照单逐项驱动判 FAIL） | 门2 收尾审计轮 |

## 铁律表（违反即失败）

| # | 铁律 |
|---|------|
| 1 | 跑真实测试前必须先 `--plan-only` 展示路径表+账单，**等用户明确确认才开跑**；无确认零执行 |
| 2 | 密钥只经清单的 `api_key_env`/`dsn_env` 环境变量名引用，永不写明文进清单或报告 |
| 3 | 环境启动（`environment.start`）由 AI 编排层执行；run.py 只做 health 复验，不就绪即失败快停，不静默重试启动 |
| 4 | 写操作请求永不自动重试（防重复副作用）；GET 才自动重试 2 次 |
| 5 | 报告与 results.json 必落盘到 `<项目>/tests/fullflow/reports/<时间戳>/`，只报结论不落盘 = 没完成 |
| 6 | 用户终审清单后才可跑真实测试；demo/模板跑不受此限 |
| 7 | 门0 静态审查不可静默跳过：默认必跑；清单写 `review: off` 或用户明示跳过时，报告必须记 review=SKIPPED 并披露原因 |
| 8 | AI 驱动的门2（非 web 平台）：每个动作须落证据（截图/UI 树/日志）到 `artifacts/agent-ui/<runID>/`，无证据不得计 PASS |
| 9 | 门2 存在「部分完成/挂账」路径 = 本轮**未收口**：交付必须带挂账清单（路径+卡点+已排除项），总结论不得记全绿；下轮 run-all 先收口挂账再跑其余 |
| 10 | 回归基线黑名单：每修复一个用户可见缺陷，必须把「已废弃形态」登记进 `references/regression-baselines.md`（反向锚点+断言方式）——run-all 轮内修复当轮登记，轮外修复由下轮 run-all 的「启动对账」补录（见工作流第 7 步）；门2 收尾逐条对照黑名单断言旧形态未回潮，命中即 FAIL。能进 API 响应字段的反向锚点用清单最终校验步骤的 `json.not_contains` 落笔 |
| 11 | 门0 覆盖以文件计不以维度计：审查报告必须附「已审文件清单」，清单外的源文件 = 未审，报告须披露未审文件数，未清零不得记门0 全绿；运行期外部资产（上传包/词表/配置文件，经清单 `# external-assets:` 注释声明，通常不在 git 工作区内）一并计入覆盖面 |

## 工作流

### 模式 A：项目已有清单（`<项目>/tests/fullflow/manifest.yaml`）

1. **预检**：`uv run --with pyyaml python <skill目录>/executor/run.py --manifest <清单> --plan-only`
   → 向用户展示：路径总数、每条路径的分叉选择、探针实例数、预计 API/LLM/CLI 调用量与时长。
   → **铁律 1 硬闸口：停下等确认。**
2. **门0（静态审查）**：调 `logic-review` skill，`--full` 全量口径——**scope = 整个目标项目代码库**，
   不是只审 git diff 变更。报告落 `<项目>/tests/fullflow/reports/<时间戳>-review/review.md`。
   blocking 发现 → 先修复再进环境（大缺陷按 logic-review 规则停下等用户决策）；
   warning → 披露后继续。清单 `review: off` / 用户明示跳过 → 报告记 SKIPPED（铁律 7）。
   注：logic-review 的小缺陷自动修复发生在硬闸口之后，属已授权改动。
   铁律 11 落地动作：开跑前圈定审查面 = 仓库文件清单（`git ls-files` + 未跟踪源文件）+ 清单
   `# external-assets:` 注释声明的运行期外部资产（通常不在 git 工作区内，逐个读文件核对）；
   注释漏声明时的兜底排查：从部署/启动脚本、README、`environment.start` 命令与配置目录反查运行期
   加载的外部资产并补入审查面。logic-review 返回后逐文件核对覆盖。竞态时序/记账状态机语义标记为
   重点深审面（实证：实战首战 4 个 P0 门0 漏拦，两天后专项深审才现形）。
3. **环境**：按清单 `environment.start` 启动——`skill://<name>` = 调起对应 skill；
   命令 = 执行并确认输出无异常；`manual` = 提示用户手动启动并等确认。
   Android/Flutter 目标 = android-emulator MCP 起模拟器并装启应用；桌面目标 = 启动对应程序。
4. **门1（API 层 / CLI 层）**：
   `uv run --with pyyaml python <skill目录>/executor/run.py --manifest <清单> --gate api`
   然后 `report.py` 生成报告、`diag.py` 对 RED run 取证、AI 读报告**补人话根因分析**。
   （纯 CLI 目标同样走门1：cli 步骤在门1 执行；无 api 步骤时省略 health。）
5. **修复循环**：有 RED → 定位 → 修（走正常开发流程）→ 只重跑失败路径（`--only`）→ 门1 全绿。
6. **门2（界面层）**：按 `target.platform` 分流（详见下节）。Web：门1 全绿后跑 `--gate ui`
   （可 `--only-gate-failed` 只复测门1 失败过的路径）；步骤缺 `ui:` 定义的路径标记 UI-UNCOVERED，
   不算失败但要向用户披露。`cli` 平台无门2，报告记 N/A 并披露。
   PASS 语义复核（web 通道零代码兜底）：run.py 只在断言失败时落页面文本——AI 生成内容类路径的
   PASS run 由编排层用浏览器工具复核页面内容语义（自述失败文案/黑名单形态/流式完整度），
   复核发现即改判 FAIL 并挂账；复核动作与发现写进报告。
7. **交付**：三门结论合并摘要（审查结论 + 动态 N 绿 M 红 + 根因 + 修复建议）+ 报告路径。
   存在挂账路径（铁律 9）→ 摘要顶部列挂账清单、本轮标本轮=未收口；用户下轮再说「跑全流程」时，
   先复跑挂账路径收口，再跑新增覆盖。
   **交付表述规范（写给不读代码的人，2026-09-26 用户定版）**：摘要三段式——
   ①一句话总结论（过/没过/带条件过）；②发现的问题逐条按「问题是什么（人话，讲用户可感知
   的现象）→ 放着不管会怎样（影响写到用户/线上层面，不写某模块某函数）→ 需要用户决策什么
   （修/不修/建议顺序，给可直接执行的选项）」；③不需要决策的（已自动处理/复跑恢复/前提不成立）
   归并一小节交代。禁止内部编号裸奔：L3/E-R3/R3 等编号只能跟在人话名后面当检索锚点。
   此规范同约束 saved workflow `run-all` 的汇总员。
   挂账台账机制：`<项目>/tests/fullflow/ledger.md` 为挂账唯一权威载体（每行：路径ID+卡点+收口判据
   +来源轮）；铁律 9 的交付挂账清单与 manifest 头部 `# pending:` 注释均从它派生，同一动作生成、不单独
   维护。**启动对账**（下轮 run-all 预检前必做，未做不得开跑）：①grep 口头挂账关键词（待真网/待联测/
   待真机/待人耳/待复测/待验收——本清单为唯一出处，references 文件只引用）扫项目文档、交付摘要与项目
   记忆目录，把日常轮的口头挂账补录进 ledger.md——日常开发轮不加载本 skill，口头挂账的收口义务由本
   扫描兜底；②扫上轮以来的缺陷修复记录（来源 = git log 自上轮报告时间戳起的修复提交 + 项目记忆目录 +
   交付摘要），把新废弃的形态补录 `references/regression-baselines.md`（铁律 10 对轮外修复的兜底）；
   ③对台账逐条收口或确认仍挂。模拟器穷尽优先判据见 `references/device-matrix.md`。

### 模式 B：项目还没有清单（清单编写助手）

1. 分析目标项目：先定目标形态与 `target.platform`（web/android/flutter/desktop/cli——
   看构建产物：package.json+前端、build.gradle/AndroidManifest、pubspec.yaml、exe/AppImage、纯命令行）；
   再摸接口层（路由/handler）、界面入口（页面/Activity/窗口）、业务流程文档。
2. 找出**问答题分叉点**（AI/系统向用户抛选择题的地方）与每个选项的后续差异，
   以及值得注入异常探针的步骤（取消/非法输入/重复提交）。
3. 起草 `<项目>/tests/fullflow/manifest.yaml`（格式见 `references/manifest-spec.md`，
   照 `templates/demo.manifest.yaml` 抄结构（零 LLM、零外网、双分叉+探针的最小可跑示例）；本机命令类步骤用 `cli` 步骤表达）。
   清单注释约定（run.py 不解析注释，供编排层与门2 读）：①头部 `# pending: <路径ID,...>` 列当前挂账
   路径（由 ledger.md 派生，勿手改），下轮 `--only` 直取；②`error_probes` 声明处注明前后端各自幂等
   语义（后端幂等 ≠ 前端幂等，见门2 判定通则「有状态客户端」）；③头部 `# external-assets: <路径,...>`
   列运行期外部资产（上传包/词表/配置文件），供门0 圈定覆盖面（铁律 11）。
4. **铁律 6：清单交用户终审**，通过后进入模式 A。

### 门2 多平台驱动分流

清单 `target.platform`（默认 `web`）决定门2 执行通道；`target.app` 可携带驱动参数
（包名/入口 Activity/可执行文件路径等自由字段，AI 驱动层读取）：

| platform | 通道 | 工具与要点 |
|----------|------|-----------|
| web | run.py 脚本驱动 | `--gate ui`（Playwright Chromium），`ui_base` 必填 |
| android | AI 驱动 | android-emulator MCP：`android_build_and_run` 装启 / `android_ui_describe` 读树 / `android_ui_tap`·`android_ui_swipe` / `android_ui_type_text` / `android_screenshot` / `android_logs` |
| flutter | AI 驱动 | 同 android（跑在模拟器上）；已有 integration_test 的直接用 cli 步骤跑 `flutter test` |
| desktop | AI 驱动 | computer-use MCP（截图/点击/键入） |
| cli | 无门2 | 纯命令行目标用 cli 步骤；门2 记 N/A 并披露 |

AI 驱动通道规则（铁律 8）：

- run.py 会拒绝非 web 平台的 `--gate ui` 并指路到这里；由你照同一份 manifest 的 ui/fork 步骤逐路径驱动
- 动作映射：goto→启动应用/切页；click→tap（先 ui_describe/截图定位）；fill→type；
  expect_visible→ui_describe 找元素；text_contains→屏幕文本；fork `read:"$page"` → 读当前屏文本
- 路径枚举与探针语义不变：照常全组合、照常注入异常探针
- 每条路径建 `<项目>/tests/fullflow/reports/<时间戳>_ui/artifacts/agent-ui/<runID>/`，
  落截图+UI 树+日志摘录；结果按 results.json 单 run 同构手写进 `agent_results.json`，最后并入总结论

门2 判定通则（web 脚本通道与 AI 驱动通道都适用）：

- **内容级断言**：产物由 AI/LLM 生成界面内容的应用（LLM 回答渲染、AI 生图、AI 摘要卡等），
  「页面渲染成功」≠ PASS——页面/屏幕文本命中自述失败文案（「弄错了」「抱歉」「无法」「未找到」
  「搜索失败」等）判 FAIL；断言粒度存疑时读内容语义再下判，别只看元素存在
- **概率性路径复跑**：依赖外部服务的路径（联网搜索/第三方 API/LLM 调用）默认复跑 2-3 次取多数，
  一次通过不计稳；复跑后仍偶发失败 → 记挂账，并在根因分析按归因纪律下结论
- **单测/逻辑链锁定 ≠ 端到端正确**：解析器正确、链路通是门1 的事；门2 的职责恰恰是抓
  「链路通但结果错」——别拿门1 证据给门2 放行
- **流式完成度**：流式/AI 输出路径必须断言「输出完整」——完整性以「API 全文对照」为权威判据，由 AI
  编排层在门2 收尾直调同输入 API 执行（run.py 的 save 只在门1 生效且门1/门2 分进程，跨门对照做不进
  清单，需改执行器另行处理）；纯前端流式取不到 API 全文时由 AI 读屏全文做收尾语义判断并落证。
  「文本停止增长」不得单独作为完整判据（实证：问世/中医流式中断）；首字延迟被用户抱怨过的目标加
  首字时间实测断言；思考混进正文/被 TTS 念出（`<think>`、reasoning 内容进正文或转写）判 FAIL。
  对照口径、证据落法与阈值见 `references/experience-audit.md` C 节（唯一详述出处，主文件只留判定要点）
- **有状态客户端（IM/长连接/流式通道）**：门1 单请求探针覆盖不了重连重放与并发——由 AI 编排层补场景
  （移动端走 AI 驱动通道，web 目标用浏览器工具手工驱动）：断开→重连→断言无消息重复渲染（同 ID 只出现
  一次，DB 一条不算过）；并发 N 发→断言无重复副作用；计费/额度/库存类流程加边界数据形态探针（空账单/
  零余额）与账面守恒断言（预扣=实扣，cli 步骤查库对比）。后端 API 幂等全绿不代表前端幂等——单端点重放
  只走双通道中的一路
- **配置矩阵覆盖**：agent/模型/skill 绑定类目标，每个配置组合（含空配置=零绑定技能、AI 自触发、
  运行期外部资产如上传包词表过滤器）至少一条路径覆盖；「静默不响应」判 FAIL——等待超时无任何输出
  即 FAIL，无错误码无失败文案也算失败
- **设备层级策略**：模拟器先穷尽（业务流/状态机/几何布局/内容断言，模拟器截图肉眼可见的问题不允许
  漏到真机）；真机是否必抽、抽哪些面以 `references/device-matrix.md` 判据表为准（唯一详述出处，
  主文件不复述判据清单，防两处漂移），真机走 AI 驱动+铁律 8 证据，报告披露格式同见该文件
- **音视频人耳终验**：响度/听感/起播完整性自动化断不了——音视频功能（语音通话/TTS/播放/录音）门2
  结论标注「待人耳终验」即挂账（铁律 9）不得记全绿；详述与披露格式唯一出处见 `references/device-matrix.md`

### 验证本 skill 自身

`templates/demo_server.py` 是零依赖的 3 步 2 叉演示服务；
`uv run python <skill目录>/templates/demo_server.py --port 8765` 起服务后跑
`templates/demo.manifest.yaml` 可不依赖任何真实项目回归执行器全链（首次改动 run.py 后必跑）。
demo 清单含 cli 步骤（`env_cli_check`），一并回归 cli 执行路径。

## 命令速查

```bash
# 只看路径表与账单，不执行（硬闸口的前半步）
uv run --with pyyaml python <skill>/executor/run.py --manifest <清单> --plan-only
# 门1
uv run --with pyyaml python <skill>/executor/run.py --manifest <清单> --gate api
# 门2（门1 全绿后）
uv run --with pyyaml python <skill>/executor/run.py --manifest <清单> --gate ui [--only-gate-failed]
# 只重跑某些路径
uv run --with pyyaml python <skill>/executor/run.py --manifest <清单> --gate api --only <路径ID> [<路径ID>...]
# 封顶防爆
uv run --with pyyaml python <skill>/executor/run.py --manifest <清单> --gate api --max-paths 6
# 报告 + 失败定位（run.py 结束后）
uv run --with pyyaml python <skill>/executor/report.py --report-dir <reports/<时间戳>>
uv run --with pyyaml python <skill>/executor/diag.py  --report-dir <reports/<时间戳>>
```

## 失败自动定位的分工

`diag.py` 只取证不下结论：失败时间窗内的日志错误行（清单 `diagnosis.logs`）、
与同批次 PASS run 的响应结构 diff、变量快照 + 建议核查语句（配置化 SQL 被安全闸口禁止，
数据库取证由你按快照手工执行）。
**AI（你）在报告末尾补「根因分析」节**：综合线索给假设与修复建议，用人话写。
归因纪律：「偶发/网络抖动/环境问题」不允许单独作结论——必须附可证伪的复现手段
（复现步骤/复跑次数/预期观察信号），给不出的归因视为未定位，路径按挂账处理（铁律 9）。
同一输入时好时坏 = 概率性功能缺陷（功能问题），不是环境噪声，别用「偶发」解释掉。

## 已知坑（来自实战首战与既有教训）

- 内容级断言盲区实证（2026-09 云开/eli5 鸿蒙 app 首战）：整句提问直接丢搜索引擎会召回垃圾
  （搜出单字释义），当时门2 以「渲染成功+解析器单测锁定」计 PASS，模型在页面里自述
  「搜索系统弄错了」漏网；失败轮又被归因为偶发网络问题挂账，靠用户复跑才收口——
  正是判定通则与归因纪律针对的形态
- MiniMax-M3 响应带 `<think>` 段：llm_match 已剥离，但换模型后读题异常先查这里
- fuzzy 读题输入源按门切换：API 门用响应文本，UI 门读页面文本（`fork.read: "$page"`）
- 目标有登录态时：清单的 ui 段以 login 步骤开头，框架不内置登录魔法
- cli 步骤 argv 直传（shell=False）：复合命令拆步骤；字符串命令经 shlex 切词，
  带反斜杠的 Windows 路径参数请改用列表写法
- **cli 步骤没有 env 字段**：命令所需环境变量只能由编排层在**父 shell export**（子进程继承），或命令/路径写全路径。实测门1 首跑 RED 就是因为 `JAVA_HOME` 指着缺 jlink.exe 的 IntelliJ JBR —— 清单顶部的「环境前置」注释要写清这属编排层职责
- **health 段只认 HTTP dict**（method/url/expect）：写成 `- { cli: ... }` 列表会让 run.py 直接崩 `AttributeError: 'list' object has no attribute 'get'`。CLI 型目标要么省掉 health，要么把就绪检查做成一条可执行的 cli 步骤（assert text_contains）—— 云开鸿蒙清单就踩过（旧清单因此从没被 run.py 跑过）
- **platform=cli 时 ui 步骤不被 run.py 执行**（该平台无脚本通道）：它们只是给 AI 驱动层读的规格，逐条驱动后按 铁律 8 手写 agent_results.json，并在报告里写明「本平台门2=AI 驱动」
- **断言锚点别选输入框占位符或列表文案**：占位符恒在屏上（「问我任何问题…」命中即假绿）、列表标题常同时出现在多处 —— 实测两次误判都源于此。锚点要选该状态下唯一且语义独立的标志（如引导页 chips），且**先 dump 确认再断言**
- **AI 驱动门2 的取数口径**：uiautomator / ArkUI dumpLayout **会漏长文本节点**、只含屏上节点，Toast 也不在树里 → 内容级断言以截图为准，机制证据看应用自己的逐步日志（Android `logcat -s <tag>`、鸿蒙 hilog）
- **门0 全量审查可按项目分派子代理并行通读**（一项目一代理），主代理只读其报告复核关键发现并定级 —— 3-4k 行规模的项目这样更省主上下文；但 blocking 结论必须主代理回读 `文件:行号` 自证后再改代码
- Flutter 应用 `android_ui_describe` 依赖语义树：模拟器上先激活辅助功能（点一次无障碍），
  否则 UI 树只有少量节点
- **慢源站/跨海目标 goto 超时**（2026-09-23 destiny 实战）：goto 原生 20s 扛不住首屏资源
  全量加载——步骤写 `timeout_s: 秒` 已参数化；networkidle 是尽力而为（长轮询/慢字体
  永远不空闲），load 事件即视为就绪，不要再拿 networkidle 超时判死步骤
- **`{rand4}` 每 run 一值**（2026-09-23 修正）：所有变量共享同一随机码——内容级探针
  「写入时嵌 `{rand4}`、断言时引用同 run 变量」才能对上；此前按出现位置各自随机，
  跨变量引用必然失配。另外 `{rand4}` 只能写在 `variables:` 的值里做间接引用，
  直接写进步骤 cfg 会报「引用未声明变量」
- **回归已废弃交互形态**（2026-09 destiny 实证）：奇门/中医 AI 解读在流式已是既定形态后回退成百分比
  进度条，三门全绿无人报警——形态黑名单只活在作者脑中。修复后按铁律 10 登记反向锚点，门2 收尾对照
  `references/regression-baselines.md` 逐条断言；轮外修复的废弃形态靠下轮「启动对账」补录
- **流式断流与首字延迟漏网**（语音/流式项目实证）：AI 内容流式中断、语音首字延迟 5.39s 都在全绿
  报告里存活 11 天——SSE 正常关闭+半截内容 = status200+contains 全过，时延从不在判定面。按「流式
  完成度」条款在门2 收尾做 API 全文对照（编排层直调）与首字时间断言
- **模拟器过 ≠ 真机过**（云开实证）：MIUI 无障碍高频闪断弄丢悬浮球只有真机能见；抽屉 ⚙✕ 与 ☰ 撞位
  模拟器截图肉眼可见却拖到用户截图报障。按「设备层级策略」抽验真机并在报告披露
- **重连重放 + 多通道落库**（IM 项目实证）：WS 断线>60s 重连整批重推、AI 回复经多条后端通道
  各写一次——DB 一条、显示层翻倍，门1 断 DB 计数反而「正确」。按「有状态客户端」条款补重连与并发
  场景（web 目标由编排层用浏览器工具驱动），断言同 ID 只渲染一次
- **静默不响应也是失败**（IM 项目实证）：配置矩阵三根因（技能清单配置为空=无脚本路径、触发者
  自己扣分不足、上传包毒过滤器误杀）让 AI 不说话，无错误码无失败文案，全绿存活 9 天——按「配置
  矩阵覆盖」条款
- **口头挂账无人收口**（云开实证）：「待真网联测」只写进记忆，第十三轮才暴露流式思考时序倒挂——
  按「启动对账」grep 待验收类关键词补录 ledger.md 后收口；模拟器/离线验不了的面不得以「已过」记
  收口（穷尽优先判据见 `references/device-matrix.md`）

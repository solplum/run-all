# 回归基线黑名单 — 「该功能不该再长什么样」（铁律 10 的载体）

## 为什么需要它

清单断言只有「当前轮的正/负向文本」粒度，框架没有跨轮预期基线——results.json 只存当轮，
失败回捞也只认失败路径。于是「形态回退」发生在全绿路径上零痕迹：渲染成功、断言全过，
但形态是用户早已废弃的（实证：destiny 奇门/中医 AI 解读回退成百分比进度条，三门全绿无人报警）。
本文件把「已废弃形态」从清单作者脑中挪到盘上，门2 收尾逐条对照，命中即 FAIL。

## 登记格式

每修复一个用户可见缺陷，在下表追加一行；反向锚点登记完成前，该缺陷不算收口（铁律 10）：

| # | 登记日期 | 缺陷与来源 | 已废弃形态（反向锚点） | 断言方式 | 登记证据 | 状态 |
|---|---------|-----------|----------------------|---------|---------|------|
| R1 | 2026-09-01 | destiny 奇门/中医 AI 解读回退成百分比进度条（流式输出为用户最终指令，见 destiny-ai-lore-refactor-20260901） | 解读输出区出现百分比进度文本（`生成中 N%`）或进度条组件 | 门2 文本黑名单（正则 `\d+%`）+ API 全文对照（编排层直调，见 experience-audit.md C3）；API 响应含进度字段时用清单 `json.not_contains` | —（首版手工补录） | 生效 |
| R8 | 2026-09-26 | 问事聊天历史整包拒绝→历史永久丢失（用户实测「问事内容消失」根因；09-23 门0 修复1 B1，commit d130b10；AI 本机缓存同病同治 S1，commit 86b53ca） | 任一 AI 面板切走再切回后历史/消息列表为空或丢失（存储超预算场景）；写侧无字节预算整槽覆盖 | 门2 ask_chat 内容级消失探针（`{rand4}` 回答→切走→切回→仍在）；存储层断言 GET 历史非空 | commit d130b10、86b53ca + destiny reports/2026-09-23-runall-门0门2汇总.md「修复1（B1）」「S1」 | 生效 |
| R9 | 2026-09-26 | 流式会话注册表错误终态残留 inflight 死条目→面板永久卡错误态、重试失效（09-23 门0 修复2 B2，commit d130b10） | 流式 HTTP 非 200/重连耗尽后重试，面板仍停留原错误态不发起新请求 | 门2 触发流错误→重试→断言面板进入新请求状态（思考/成功）而非停留原错误 | commit d130b10 + 同报告「修复2（B2）」 | 生效 |
| R10 | 2026-09-26 | AiExplainPanel 错误态只有无字重试按钮、不展示错误详情（09-23 第二轮治理 W1，commit 86b53ca） | 错误态区域出现无文案重试按钮且无错误信息文本 | 门2 错误场景读屏：错误态区域必须含错误详情文本，空文案按钮=FAIL | commit 86b53ca + 同报告「W1」 | 生效 |
| R11 | 2026-09-26 | AiChat 未按用户隔离，切换用户串写/串读消息槽（09-23 第二轮治理 W2，commit 86b53ca） | 切换用户后消息列表混入另一用户的问事消息 | 门2 双用户切换读屏比对，各自消息互不出现 | commit 86b53ca + 同报告「W2」 | 生效 |
| R12 | 2026-09-26 | BirthForm「清空重填」不复位受控日期/时间下拉（09-23 第二轮治理 S3，commit 86b53ca） | 点「清空重填」后出生日期/时间下拉仍保留旧值 | 门2 填表→清空→读屏断言五组下拉回到空/默认值 | commit 86b53ca + 同报告「S3」 | 生效 |
| R13 | 2026-09-26 | FastAPI 422 detail 数组原样渲染为 [object Object]/JSON 原文（09-23 第二轮治理 S4，commit 86b53ca） | 错误提示文本出现 `[object Object]`、数组/JSON 原文 | 门2 触发 422 后错误提示文本黑名单扫描 `[object Object]` 命中=FAIL | commit 86b53ca + 同报告「S4」 | 生效 |
| R14 | 2026-09-26 | 起运日恰为 2/29 时 replace(year) 抛 ValueError→该出生数据排盘永久 422（09-23 第二轮治理 W6，commit 86b53ca，修为顺延 3/1） | 2 月 29 日起运的出生数据提交排盘返回 422/报错 | 清单 API 断言：2/29 起运样本 status=200 且起运日期≠2-29 | commit 86b53ca + 同报告「W6」 | 生效 |
| R15 | 2026-09-26 | 解梦/奇门/中医思考期回退成独立进度条而非流式思考折叠条（commit f08263a；09-23 门2 已按「思考折叠条出现」为新口径断言） | 思考期出现常驻进度条组件或百分比进度文本（无思考折叠条） | 门2 读屏：思考期存在思考折叠条；解读区沿用 R1 `\d+%` 扫描 | commit f08263a + 同报告「门2 终态：全部路径断言了思考折叠条出现（2026-09-23 新口径）」 | 生效 |
| Y1 | 2026-10-01 | yunkai-android 悬浮球随服务(重)绑定不补显，真机 MIUI 闪断后球永久消失+误导断开提示（commit cb1e82a；09-25 模拟器 round1 界面①复验） | 无障碍(重)绑定后窗口列表无悬浮球窗口（dumpsys window 无 44x44 TYPE_ACCESSIBILITY_OVERLAY；logcat 无 `floating ball restore`） | 门2 fw_rebind_ball_restore：翻转 enabled_accessibility_services→断言 logcat 三条（onUnbind/onServiceConnected/floating ball restore）+ dumpsys 球窗口在场 | commit cb1e82a + reports/20260925_emulator_round1/REPORT.md 界面① | 生效 |
| Y2 | 2026-09-25 | yunkai-android 面板内空白区 tap 穿透到遮罩层误关面板（真机用户实测；FlashActivity 面板 Box 补 pointerInput 吞 tap） | 点面板内非按钮区（列表空白/拉头/标签）后面板收起 | 门2 fw_panel_geometry：面板内空白区 tap 后断言 FlashActivity 仍在面板态 | 09-25 round1 界面③（复算差值 0.000618/通道像素）+ commit（并入 104c69d 系列 FlashActivity 改动） | 生效 |
| Y3 | 2026-09-25 | yunkai-android 面板态读屏被自身窗口遮蔽：readForeground 取 rootInActiveWindow 读到面板自己，黑名单被流程性绕过（YouTube 黑名单下照读不误；commit 7cdaa3c） | 黑名单包前台+面板态下发读屏指令，read_screen/capture_screen 照常执行且回复无拒绝语义 | 门2 fw_panel_read_under：黑名单负向（回复须含拒绝语义）+ 非黑名单 app 正向对照（准确转述） | commit 7cdaa3c + reports/20260925_emulator_round1/REPORT.md Round 3 | 生效 |
| Y4 | 2026-09-26 | yunkai-android 设置写入静默丢失：即时写入挂 rememberCoroutineScope，拨完开关立刻退出页面写入被取消蒸发（commit ffb9296；用户报「屏幕感知自动关闭」另一半根因） | 拨设置档位/开关后立刻退出设置页，重进读回旧值 | 门2 fw_panel_opacity_persist：拨「实底」+立刻 BACK+重启 → 断言档位保持；断言可泛化到其他即时写入项 | commit ffb9296 + reports/20260925_emulator_round1/REPORT.md Round 4 | 生效 |
| Y5 | 2026-09-25 | yunkai-android MIUI 高频闪断重绑期间「已断开」toast 骚扰（去抖 5s，commit cb1e82a） | 服务闪断 5s 内重绑仍弹「云开屏幕感知已断开」toast | 真机人眼目检（toast 不入 UI 树，自动化断不了）→ ledger P2 挂账口径 | commit cb1e82a + ScreenSenseService disconnectNotice | 待人眼（挂账 P2） |
| Y6 | 2026-10-01 | yunkai-android ClickIndicator 指示圈生产路径 100% 静默失效：WritePlanExecutor(IO 线程) 直调 addView 必抛被 catch 吞（门0 B1，commit 0a336ca 修复改主线程落地） | 写操作执行时无指示圈且 logcat 无任何 ClickIndicator 痕迹 | 门0 代码口径（show 经主线程 Handler+失败记 Log.w）+ 动态弱断言（写链 ⑳ 通过且无 "ClickIndicator show failed" 日志）+ 真机指示圈人眼目检（挂 P13） | commit 0a336ca + 20261001-fw-round1-review B1 | 生效（目检面挂 P13） |
| Y7 | 2026-10-01 | yunkai-android 面板拖拽 px/dp 混算：amount(px) 除以 screenHeightDp(dp)，高密度设备灵敏度放大 density 倍、0.85/0.5 阈值失真（门0 B2，commit 0a336ca 修复按密度换算） | 高密度真机上轻拖即越档（<80dp 拖拽切全屏/收起） | 模拟器 density=1 无法区分两态；断言落真机：320x640@160dpi 阈值几何已验（24_geometry），density>1 设备复测同几何（挂 P13） | commit 0a336ca + 20261001-fw-round1-review B2 | 生效（真机面挂 P13） |
| Y8 | 2026-10-01 | yunkai-android MIGRATION_2_3 archival 表 id 缺 NOT NULL：存量 v2 升级设备启动崩循环且 destructive fallback 救不了（门0 B3，commit 0a336ca 修复补 NOT NULL） | v2→v5 升级启动抛 "Migration didn't properly handle archival" | 自动化断言依赖迁移测试框架（ledger P10 的 room.schemaLocation+MigrationTestHelper）；当轮证据=代码修复+全量单测绿+装机冒烟 | commit 0a336ca + 20261001-fw-round1-review B3 | 生效（自动化断言挂 P10） |
| Y9 | 2026-10-02 | yunkai-android 计划确认形态废弃：整计划 Pending 批准门+「执行」按钮被三档确认分级取代（用户拍板 完全访问/AI自审/事事过问；commit fd4a1cc+6aad931） | propose_plan 提交后出现「待批准：点「执行」」卡或计划卡带「执行」按钮；计划提交后不点击不执行 | 门2 screen_write_plan：提交后断言 plan 工具结果 plan_done（自动执行）+ 终态切页；计划卡不得再出现「执行」钮（manifest 判据已同步 6aad931） | commit fd4a1cc、6aad931 + reports/2026-10-02_1812_ui/agent_results.json screen_write_plan | 生效 |

## 首版黑名单（来自 2026-09 实证，直接可用）

### R1 百分比进度条（destiny AI 解读）

- 不该出现：`生成中 30%` 类进度文本、进度条组件
- 该出现：SSE 逐 token 流式渲染，完整性经 API 全文对照（编排层直调，见 experience-audit.md C3）
- 断言：门2 对解读输出区文本做 `\d+%` 扫描（AI 驱动读屏 / web 用浏览器取文本）；
  能到 API 响应字段的写进清单最终校验步骤 `json.not_contains`（run.py 既有词汇，无需改执行器）

### R2 整段非流式输出（AI 内容类通用）

- 来源：问世/中医板块 AI 内容流式改造
- 不该出现：AI 回复一次性整段渲染（无流式指示器、无逐 token 增长）
- 该出现：首 token 前有 skeleton/思考中指示器，流式中文本持续增长，完整性经 API 全文对照
- 断言：门2 发起提问后立即断言指示器 → 截帧确认增长 → 按 API 全文对照（编排层直调）验完整

### R3 思考内容混进正文 / 被 TTS 念出

- 来源：某语音通话项目——TTS vendor 念 reasoning_content 独立字段；换思考模型后 `<think>` 混进 content 流被念进转写
- 不该出现：正文渲染区/转写文本含 `<think>` 标签、reasoning 字段内容、思考导语句式
- 断言：正文区黑名单扫描 `<think>`；语音类对转写文本断言无思考痕迹；API 层 `json.not_contains`

### R4 消息重复渲染（同 ID 出现多次）

- 来源：某 IM 项目——WS 断线 >60s 重连整批重放 + 前端零去重；AI 回复经多条后端通道各写一次
- 不该出现：同一 message_id / 同文本在消息列表出现 ≥2 次（DB 一条不算过，显示层才算数）
- 断言：AI 驱动层断开 → 重连 → 读屏比对重复计数；web 用 DOM 查询计数

### R5 装饰性 emoji 当图标

- 来源：通用体验规则预登记（非特定缺陷修复的回归基线，无登记证据快照）
- 不该出现：按钮/功能位用 emoji 充当图标
- 断言：门0 grep 图标位 emoji 命中=0；门2 截图判读辅助

### R6 浮层/弹窗无外部关闭

- 来源：通用体验规则预登记（非特定缺陷修复的回归基线，无登记证据快照）
- 不该出现：弹窗/抽屉点遮罩、按返回键/Esc 不关闭
- 断言：门2 对每个浮层驱动「点遮罩关闭」与「返回/Esc 关闭」（android 返回用
  `android_ui_keyevent(BACK)`）两个动作，逐一断言

### R7 纯文字按钮顶替既有图标按钮（图标回退）

- 不该出现：既有图标按钮位置只剩纯文字（或反向替换）
- 断言：门2 截图与「登记证据」列存档的登记时快照对照，对不上按 FAIL 处理；
  「登记证据」为空只影响**快照对照类断言**（仅本条属于此类）：该类断言不判 FAIL、仅在报告中提示补录；
  特征串扫描/DOM 计数等其余断言方式不依赖登记证据，照常按铁律 10 命中即 FAIL

## 断言落笔口径（不改 run.py 契约）

- 能进 API 响应字段的（进度字段、`<think>` 混正文）→ 写进清单最终校验步骤 `json.not_contains`
  ——run.py 既有词汇（json 断言分支），无需改执行器
- 页面形态类 → 门2 收尾审计轮由 AI 编排层逐条对照本表（读屏文本/截图判读），
  发现即改判 FAIL 并按铁律 9 挂账
- web 通道 PASS run 不落页面文本 → 先按 SKILL.md 工作流第 6 步「PASS 语义复核」
  用浏览器工具取到页面内容，再做黑名单断言

## 登记纪律

- 反向锚点必须可判：写成「出现 X 即 FAIL」的具体特征串/组件名，禁止「体验变差」类不可判描述
- 新登记的锚点当轮门2 收尾即生效；下轮 run-all 的门2 必读本表
- **轮外修复的兜底**：日常开发轮不加载 run-all，本文件无法强制其当轮登记——轮外修复的废弃形态由
  SKILL.md 工作流第 7 步「启动对账」在下一轮 run-all 启动时扫修复记录补录；启动对账未做，本轮不得开跑

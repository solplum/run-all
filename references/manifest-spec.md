# manifest.yaml 清单格式规范（run-all）

清单是每个项目唯一需要人维护的文件，放在 `<项目>/tests/fullflow/manifest.yaml`。
分叉 = 流程中系统/AI 抛出的问答题选项；整棵分叉树就是流程本身。

## 顶层字段

```yaml
name: <str>                        # 清单名，进报告标题
target:
  platform: web                    # web|android|flutter|desktop|cli（默认 web；决定门2 通道）
  api_base: <url>                  # 门1 的基址（有 api 步骤或 api 探针时必填）
  ui_base: <url>                   # 门2 的基址（仅 web 平台；缺省则 run.py 拒跑门2）
  app: <任意字段>                   # 可选：非 web 平台的驱动参数（包名/入口 Activity/可执行文件路径等，
                                    #   自由结构，AI 驱动层读取；如 { package: com.x.y }）
environment:
  start: <str>                     # skill://<name> | shell 命令 | manual
  health:                          # run.py 复验就绪，**只认下面这个 HTTP dict 结构**；
                                 # CLI 型目标省略整个 health（写成 list 会让 run.py 崩 AttributeError），
                                 # 需要就绪检查就做成一条 cli 步骤（assert text_contains）
    method: GET
    url: <url>
    expect: 200
    timeout_s: 120                 # 默认 120
llm:                               # 任一 fork 用 fuzzy/llm pick 时必填
  base_url: <url>                  # OpenAI 兼容，如 https://api.minimax.chat/v1
  api_key_env: <ENV_NAME>          # 只存环境变量名，禁明文
  model: <str>                     # 如 MiniMax-M3（响应 think 段已自动剥离）
variables: {k: v}                  # run 级变量；值可含 {rand4}（每 run 重新随机 4 位 hex）
review: off                        # 可选：off = 跳过门0 静态审查（报告仍记 review=SKIPPED 并披露）
probes: {...}                      # 异常探针定义，见下
diagnosis: {...}                   # 失败定位素材，见下
flow:
  steps: [...]                     # 树状步骤，见下
```

## 步骤（flow.steps 的元素）

步骤类型五选一：`api` / `ui` / `fork` / `cli` /（辅助）`wait`。

```yaml
- id: create_blueprint             # 全树唯一
  api:
    method: POST
    path: /character-blueprints    # 拼 target.api_base；可含 {var}
    body: { name: "{persona_name}" }   # 任意 JSON，字符串可含 {var}
    headers: {X-Test: "1"}         # 可选
    timeout_s: 300                 # 默认 30；LLM 长请求记得调大
  save: { blueprint_id: "$.data.id" }  # JSONPath 提取响应 → run 级变量
  assert:                          # 全部通过该步才 PASS
    - { status: 200 }
    - { json: "$.data.id", exists: true }
  error_probes: [cancel, duplicate_submit]  # 声明点：探针在此步注入并参与组合

- id: open_studio
  ui:                              # 仅门2 执行；门1 中标记 SKIP
    action: goto                   # goto|click|fill|expect_visible|text_contains
    url: "{ui_base}/studio"        # goto 用
    target: "#submit"              # click/fill/expect_visible 用（CSS 或 text=xx）
    value: "文本"                  # fill 的输入 / text_contains 的断言文本

- id: analyze_app                   # cli 步骤：本机命令（门1/门2 都执行）
  cli:
    cmd: "flutter analyze"          # 字符串经 shlex 切词；或直接写列表 [python, -c, "print(1)"]
                                     # 无 env 字段：所需环境变量由编排层在父 shell export（子进程继承），
                                     # 或命令/路径写全路径（如 hdc 不在 PATH 时写绝对路径）
                                     # argv 直传 shell=False，无管道/&&；复合命令拆成多个步骤
    cwd: "."                        # 可选；相对清单所在目录
    timeout_s: 120                  # 默认 60；超时按 exit=124 判
  assert:                           # 此处 status = 退出码；text_contains 匹配 stdout+stderr
    - { status: 0 }
    - { text_contains: "No issues found!" }

- id: think_a_moment
  wait: { seconds: 2 }
```

## 断言类型

| 写法 | 含义 |
|------|------|
| `{ status: 200 }` | HTTP 状态码 |
| `{ json: "$.a.b", exists: true }` | JSONPath 存在 |
| `{ json: "$.a.b", eq: "x" }` | JSONPath 等值 |
| `{ json: "$.a", contains: "y" }` | JSONPath 指向的字符串/数组包含 |
| `{ text_contains: "成功" }` | 响应体原文包含（cli 步骤 = stdout+stderr 合并文本） |
| `{ ui_visible: "#card" }` | 仅门2：页面元素可见 |

cli 步骤的 `status` 语义是**退出码**（0=成功；127=命令不存在；124=超时），其余断言写法与 API 步骤通用。

JSONPath 子集：`$.a.b.c`、数组下标 `$.a.0.b`、`$` 根。

## 分叉（fork）

```yaml
- id: first_question
  fork:
    read: "{ai_question}"          # 读题来源：含题目文本的变量模板；UI 门可用 "$page" 读整页文本
    mode: fuzzy                    # exact=选项写死 | fuzzy=现场读题
    expect_keywords: [复刻, 全新]   # 可选 sanity：题目须含其一，否则 RED
    choice_var: first_choice       # 可选；fuzzy+llm 时选中的选项原文存此（默认 <fork_id>_choice）
    branches:
      - id: replicate
        pick: { contains: "复刻" }              # fuzzy：关键词优先
        then: [ /* 分支专属步骤，可再嵌 fork */ ]
      - id: fresh
        pick: { llm: "选「全新人设」对应的选项，只返回选项原文" }   # 兜底指令
        then: [ /* ... */ ]
```

匹配顺序（fuzzy）：关键词 `contains` 命中 → 用之；未命中 → LLM 兜底（把题目文本+pick 指令
发给清单 `llm`，解析返回 JSON `{"choice": "..."}`，存 `choice_var`）；LLM 失配/超时 → 该 run RED，
题面与候选项存 artifacts。`exact` 模式只做关键词匹配，失配直接 RED（不静默模糊）。
分支后续步骤用 `{first_choice}` 引用选中选项原文（如回填答案接口的 body）。

## 异常探针（probes）

三种探针，参与路径全组合：每条正常路径 × 每个声明点 × 每种探针 = 独立一条 probe run
（跑到该步：先正常执行该步，再注入探针动作，验完 expect 即结束，不跑后续步骤）。

```yaml
probes:
  cancel:                          # 自定义动作型
    api: { method: POST, path: "/character-blueprints/{blueprint_id}/cancel" }
    expect: [ { status: 200 } ]
  duplicate_submit:                # 内置重放型：重发目标步的原始请求
    expect:
      - { status: [200, 409] }     # status 也接受列表：任一命中即过
  invalid_input:                   # 非法输入型：body 覆盖为目标步的坏数据
    api: { method: POST, path: "/same/path", body: { name: "" } }
    expect:
      - { status: [400, 422] }
```

## 门2 多平台（target.platform）

| platform | 通道 | 要点 |
|----------|------|------|
| `web` | run.py `--gate ui`（Playwright） | `ui_base` 必填；fork 可用 `read: "$page"` 读整页文本 |
| `android` / `flutter` / `desktop` | AI 驱动（android-emulator / computer-use MCP） | ui 步骤词汇照常写，由 AI 编排层映射执行；证据落 `artifacts/agent-ui/<runID>/`；run.py 对非 web 的 `--gate ui` 直接报错指路 |
| `cli` | 无门2（报告记 N/A 并披露） | 纯命令行流程用 `cli` 步骤；`api_base`/`health` 可整体省略 |

AI 驱动通道的动作映射：goto→启动应用/切页；click→tap（先 ui_describe/截图定位）；
fill→type；expect_visible→ui_describe 找元素；text_contains→屏幕文本。
路径枚举与探针语义不变；`target.app` 里的包名/入口等驱动参数由 AI 层读取。

## 失败定位素材（diagnosis）

```yaml
diagnosis:
  logs:
    - { name: java, path: "logs/java.log", error_patterns: ["ERROR", "Exception"] }
    # path 相对 <项目根>；diag 取失败时间戳 ±120s 窗口内的匹配行（无时间戳则取末尾匹配行）
```

（v1 不含配置化数据库查询：配置化 SQL 被安全闸口禁止执行。库内证据由 AI 按 results.json
里的变量快照手工核查，diag.md 会给出建议核查语句。）

## 路径枚举与防爆

- 正常路径数 = 各 fork 分支数的笛卡尔积；路径 ID = 分支 id 以 `__` 连接（无分叉 = `base`）
- 探针 run ID = `<路径ID>@<探针名>@<步骤id>`
- 防爆：跑前 `--plan-only` 看账单 + 用户确认；`--only <ID>` 单跑；`--max-paths N` 封顶；
  `--only-gate-failed` UI 门只复测门1 RED 过的路径
- 环境崩溃熔断：连续 3 条 run 连接类错误 → 中止全部剩余 run，报告标 NOT_RUN

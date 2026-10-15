# Run-All · 全流程测试

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Gates](https://img.shields.io/badge/gates-3_doors-blue)
![Targets](https://img.shields.io/badge/targets-Web%20%7C%20Android%20%7C%20Flutter%20%7C%20Desktop%20%7C%20CLI-orange)
![Agent CLIs](https://img.shields.io/badge/works_with-Claude_Code%20%7C%20Codex%20%7C%20ZCode-violet)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**简体中文** | [English](#english)

---

## 简体中文

> AI 把功能做完，跟你说「测过了，没问题」。
> 装修改完水电，你会找第三方检测再入住——
> 这个 skill 就是给 AI 干的活配的检测机构：清单驱动、三门测试，每个结论都要证据落盘。

一句话：你描述要测的项目，它把测试沉淀成一份可审计的清单（`manifest.yaml`），跑完三门——**门0 静态审查、门1 API 层、门2 界面层**——报告和 `results.json` 落盘到项目里。铁律：**只报结论不落盘 = 没完成**。

### 它解决什么问题

| 翻车 | 你遇到的 | run-all 替你做 |
|------|---------|---------------|
| **声称测过** | AI 说「没问题」，其实只看了代码没真跑 | 门1/门2 强制起真实环境逐条 run，断言失败就是失败，环境起不来就明说 RED |
| **测了记不住** | 上轮测过什么、哪些挂账，全在对话里蒸发了 | 清单 + 挂账台账（`ledger.md`）落盘项目内；下轮 `--only` 直取挂账路径 |
| **分叉测不全** | 功能里有选择题（确认/修改、复刻/全新），AI 只测了主路径 | `fork` 步骤分叉路径全组合，每条分支都是独立 run |
| **异常没人管** | 重复提交、非法输入、中途取消从来没测过 | `error_probes` 异常探针内建在清单里，随步骤注入（重复提交 → 409、非法输入 → 400…） |

### 三种模式（可单选可多选）

| 模式 | 跑什么 | 结论口径 |
|------|--------|---------|
| `detail` 细节审查 | 门0 全量静态审查 + 重点深审面（竞态时序/记账状态机/配置矩阵/幂等），只审不修 | 只代表门0 |
| `ui` 只测 UI | 门2 界面层体验审计 | 只代表门2 |
| `full` 跑全流程 | 三门完整 | 三门各自口径 |

### 三道门

- **门0 静态审查**：调 [logic-review](https://github.com/solplum/logic-review)（`--full` 全量口径），blocking 发现先修再进环境。
- **门1 API 层**：HTTP 步骤 + 状态码/JSON/文本断言 + `save` 变量传递 + `fork` 分叉全组合 + `error_probes` 异常探针 + `cli` 步骤（本机命令+退出码断言）。
- **门2 界面层**：Web = Playwright 脚本驱动；Android/Flutter/桌面 = AI 驱动 + 证据落盘（截图/控件树/转写入档）。

### 快速开始

```bash
# 1. 安装：拷进你的 agent skills 目录
cp -R run-all ~/.claude/skills/run-all     # Claude Code / ZCode
cp -R run-all ~/.codex/skills/run-all      # Codex

# 2. 零依赖试跑 demo（零 LLM、零外网，2 分钟体验执行器全链）
uv run python <skill>/templates/demo_server.py --port 8765
FULLFLOW_ALLOW_PRIVATE_TARGET=1 uv run --with pyyaml python <skill>/executor/run.py \
    --manifest <skill>/templates/demo.manifest.yaml --plan-only   # 先看路径表
# 同上去掉 --plan-only 加 --gate api                              # 跑门1

# 3. 给自己的项目写清单
#    格式见 references/manifest-spec.md，照 demo.manifest.yaml 抄结构；
#    然后对 agent 说：「把 X 全流程测一遍」
```

对 agent 的触发词：**全流程测试 / 跑全流程 / E2E 全流程 / 全链路测试 / 把 X 全流程测一遍**（X = 网站/App/桌面程序/CLI）。

### 与 logic-review 的关系

[logic-review](https://github.com/solplum/logic-review) 是 run-all 门0 的执行体：一个**审**（代码与内容逻辑审查），一个**测**（真环境全流程验证）。两者独立安装、独立可用，装齐后 run-all 门0 自动获得 16 维审查能力。

### 仓库结构

```
run-all/
├── SKILL.md                      # skill 主文件：工作流、三道门、模式选择、铁律
├── executor/                     # 确定性执行器（Python，清单驱动）
│   ├── run.py                    #   主入口：读清单→起环境→逐条 run→落盘报告
│   ├── diag.py                   #   失败定位与诊断
│   ├── llm_match.py              #   fuzzy 读题兜底（key 只走环境变量名）
│   └── report.py                 #   报告渲染
├── references/                   # 规范文档
│   ├── manifest-spec.md          #   清单字段语义（清单 manifest.yaml 才是唯一需要人维护的文件）
│   ├── device-matrix.md          #   多端目标矩阵
│   ├── experience-audit.md       #   门2 体验审计口径
│   └── regression-baselines.md   #   回归基线
└── templates/                    # 演示项目（零 LLM、零外网）
    ├── demo_server.py            #   演示目标服务（含故意分叉与异常点）
    ├── demo.manifest.yaml        #   演示清单：双分叉 + 异常探针 + cli 步骤
    └── tests/fullflow/ledger.md  #   挂账台账示例
```

### 设计铁律（摘要）

1. **报告与 `results.json` 必落盘**到 `<项目>/tests/fullflow/reports/<时间戳>/`——只报结论不落盘 = 没完成。
2. **清单交用户终审**——清单是测试契约，AI 起草、人批准后才跑。
3. **挂账台账唯一权威**——口头挂账由「启动对账」扫关键词补录，`# pending:` 注释由台账派生。
4. **密钥只存环境变量名**——清单里写 `api_key_env`，绝不写明文。

---

## English

**Run-All** is a manifest-driven full-flow testing framework for AI agents. Instead of trusting "I tested it, no problems," it turns testing into an auditable checklist (`manifest.yaml`) and runs three gates: **Gate 0** static review (delegates to [logic-review](https://github.com/solplum/logic-review)), **Gate 1** API-layer execution (HTTP steps, JSON/status/text assertions, variable passing, full branch-combination `fork`s, error probes, CLI steps), and **Gate 2** UI-layer verification (Playwright for Web; AI-driven with on-disk evidence for Android/Flutter/desktop).

Iron rule: **a run without its on-disk report and `results.json` doesn't count as done.** See the Chinese section above for the full workflow, the demo (zero LLM, zero network), and design principles.

Works with Claude Code / Codex / ZCode-style CLIs. Install: copy the folder into your agent's skills directory.

---

## License

[MIT](LICENSE) © 2026 solplum

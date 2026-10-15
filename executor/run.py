#!/usr/bin/env python3
"""run-all 执行器：解析清单 → 枚举路径（分叉全组合×探针） → 逐 run 执行 → 断言 → results.json

用法：
  uv run python run.py --manifest <清单> --plan-only
  uv run python run.py --manifest <清单> --gate api [--only ID...] [--max-paths N]
  uv run python run.py --manifest <清单> --gate ui [--only-gate-failed] [--only ID...]

目标 SSRF 约束：仅 http/https；私网/环回目标需 FULLFLOW_ALLOW_PRIVATE_TARGET=1
（本地栈联调是常态，由 SKILL.md 工作流负责设置）。
cli 步骤：argv 直传（shell=False，字符串经 shlex 切词），复合命令请拆成多个步骤。
--gate ui 仅驱动 platform=web（Playwright）；android/flutter/desktop 走 AI 驱动通道。
"""
import argparse
import ipaddress
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import llm_match  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MISSING = object()


class RedError(Exception):
    """步骤失败（断言不过/请求有响应但违规/配置错误）。uncover=True 表示 UI 门无覆盖。"""

    def __init__(self, msg, uncover=False):
        super().__init__(msg)
        self.uncover = uncover


class ConnError(Exception):
    """连接类失败（环境不在/网络断），参与环境崩溃熔断计数。"""


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _host_is_private(host):
    """host 判私：IP 字面量直判；域名解析成 IP 逐一判。解析失败按「不可判」放行，
    由后续连接失败自然兜底——不把 DNS 抖动升级成整批终止。"""
    if host in ("localhost",) or host.endswith(".local"):
        return True
    try:
        addrs = [ipaddress.ip_address(host)]  # IP 字面量
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        addrs = []
        for info in infos:
            try:
                addrs.append(ipaddress.ip_address(info[4][0]))
            except (ValueError, IndexError):
                pass
    return any(a.is_private or a.is_loopback or a.is_link_local or a.is_reserved
               for a in addrs)


def guard_url(url):
    """目标 URL 约束：协议白名单；私网/环回需显式 opt-in。域名解析成 IP 逐一复检——
    曾只查 IP 字面量，域名解析到环回即可绕过（2026-09 门0 实证）；
    配合 http() 逐跳复检覆盖重定向落点。"""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise SystemExit(f"目标协议不允许: {url}（仅 http/https）")
    host = p.hostname or ""
    if _host_is_private(host) and os.environ.get("FULLFLOW_ALLOW_PRIVATE_TARGET") != "1":
        raise SystemExit(f"私网/环回目标被拒: {host}；本地栈联调请设 FULLFLOW_ALLOW_PRIVATE_TARGET=1")


# ---------------------------------------------------------------- 清单
def load_manifest(path: Path):
    m = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or "flow" not in m:
        raise SystemExit(f"清单无效：{path}")
    return m


def _collect_refs(obj, out):
    if isinstance(obj, str):
        out.update(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_refs(v, out)


def validate(m):
    errs, seen_ids = [], set()
    saved = set((m.get("variables") or {}).keys()) | {"api_base", "ui_base", "rand4"}
    probes = m.get("probes") or {}

    def walk(steps, scope):
        nonlocal saved
        for s in steps or []:
            sid = s.get("id")
            if not sid:
                errs.append(f"{scope}: 存在无 id 的步骤")
                continue
            if sid in seen_ids:
                errs.append(f"重复步骤 id: {sid}")
            seen_ids.add(sid)
            kinds = [k for k in ("api", "ui", "fork", "cli", "wait") if k in s]
            if len(kinds) != 1:
                errs.append(f"步骤 {sid}: api/ui/fork/cli/wait 必须恰选其一（现为 {kinds}）")
            if "cli" in s:
                c = s["cli"].get("cmd")
                if isinstance(c, str):
                    if not c.strip():
                        errs.append(f"步骤 {sid}: cli.cmd 不能为空")
                elif not (isinstance(c, list) and c and all(isinstance(x, str) for x in c)):
                    errs.append(f"步骤 {sid}: cli.cmd 必须是非空字符串（shlex 切词）或字符串列表（argv 直传）")
            refs = set()
            if "fork" in s:
                # fork 本体只查自身字段（read/expect_keywords 等）；分支子树的
                # 引用由下方 walk(branches) 按顺序校验——否则分支内 save 的变量
                # 会被嵌套 fork 提前判成未声明
                _collect_refs({k: v for k, v in s["fork"].items() if k != "branches"}, refs)
                _collect_refs({k: v for k, v in s.items() if k != "fork"}, refs)
            else:
                _collect_refs(s, refs)
            pre = {s["fork"].get("choice_var") or f"{sid}_choice"} if "fork" in s else set()
            for unknown in sorted(refs - saved - pre):
                errs.append(f"步骤 {sid}: 引用未声明变量 {{{unknown}}}")
            for p in s.get("error_probes") or []:
                if p not in probes:
                    errs.append(f"步骤 {sid}: 探针 {p} 未在 probes 段定义")
            saved = saved | set((s.get("save") or {}).keys())
            if "fork" in s:
                f = s["fork"]
                brs = f.get("branches") or []
                if len(brs) < 2:
                    errs.append(f"分叉 {sid}: 分支须 ≥2")
                if not f.get("read"):
                    errs.append(f"分叉 {sid}: 缺 read（读题来源）")
                saved = saved | {f.get("choice_var") or f"{sid}_choice"}  # 运行时读题即存
                for b in brs:
                    if "pick" not in b:
                        errs.append(f"分叉 {sid} 分支 {b.get('id')}: 缺 pick")
                    walk(b.get("then") or [], f"{sid}/{b.get('id')}")

    walk((m.get("flow") or {}).get("steps"), "flow")
    for name, p in probes.items():
        if not p.get("expect"):
            errs.append(f"探针 {name}: 缺 expect")
        if "api" not in p and name != "duplicate_submit":
            errs.append(f"探针 {name}: 非 duplicate_submit 型必须有 api 动作")

    def _has_kind(steps, kind):
        for s in steps or []:
            if kind in s:
                return True
            for b in (s.get("fork") or {}).get("branches") or []:
                if _has_kind(b.get("then"), kind):
                    return True
        return False

    # manifest-spec 声明的必填项，缺失曾 --plan-only 放行、运行时裸 KeyError 整批崩
    steps0 = (m.get("flow") or {}).get("steps") or []
    if (_has_kind(steps0, "api") or any("api" in p for p in probes.values())) \
            and not ((m.get("target") or {}).get("api_base")):
        errs.append("清单含 api 步骤/探针但 target.api_base 缺失（manifest-spec 必填项）")
    if errs:
        raise SystemExit("清单校验失败：\n  - " + "\n  - ".join(errs))


# ---------------------------------------------------------------- 路径枚举
def expand_steps(steps, trace):
    """→ [(run_trace, [step,...])]。fork 本体保留在路径中（运行时读题载体），注入 _branch。"""
    for idx, s in enumerate(steps):
        if "fork" in s:
            prefix = steps[:idx]  # 分叉之前的步骤属于每一条路径
            tail = steps[idx + 1:]
            out = []
            for b in s["fork"].get("branches") or []:
                btrace = trace + [b["id"]]
                marked = {**s, "_branch": b["id"]}
                pre = expand_steps(b.get("then") or [], btrace) or [(btrace, [])]
                post = expand_steps(tail, btrace) or [(btrace, [])]
                for bt, bs in pre:
                    for tt, ts in post:
                        full = list(bt) + tt[len(btrace):]  # 尾段可能还有更深分叉
                        out.append((full, list(prefix) + [marked] + bs + ts))
            return out
    return [(trace, list(steps))]


def enum_runs(m):
    steps0 = (m.get("flow") or {}).get("steps") or []
    normals = [{"id": "__".join(t) or "base", "kind": "normal", "trace": t, "steps": st}
               for t, st in expand_steps(steps0, [])]
    runs = list(normals)
    probes = m.get("probes") or {}
    for r in normals:
        for i, s in enumerate(r["steps"]):
            for pname in s.get("error_probes") or []:
                if pname in probes:
                    runs.append({"id": f"{r['id']}@{pname}@{s['id']}", "kind": "probe",
                                 "trace": r["trace"], "steps": r["steps"][:i + 1],
                                 "probe": pname, "probe_step": s["id"]})
    return normals, runs


# ---------------------------------------------------------------- 变量与 JSONPath
def fresh_vars(m):
    # rand4 每 run 一值（规范口径）：所有变量共享同一随机码，探测写入与探测断言
    # 才能对上；此前按出现位置各自随机，跨变量引用必然失配。
    # 空间从 token_hex(2)=65536 放宽到 48bit：同批 run 对撞（create 409 假 RED，
    # 报错误导排查方向）概率从 ~0.2% 降到可忽略——2026-09 门0 实证。
    rand = secrets.token_hex(6)
    vars_ = {k: str(tpl).replace("{rand4}", rand)
             for k, tpl in (m.get("variables") or {}).items()}
    # 与 validate 白名单同源：{api_base}/{ui_base} 校验放行，运行时也必须可得
    # （曾只进白名单不物化，照 spec 写步骤必 RED——2026-09 门0 实证）。
    t = m.get("target") or {}
    if t.get("api_base"):
        vars_.setdefault("api_base", str(t["api_base"]))
    if t.get("ui_base"):
        vars_.setdefault("ui_base", str(t["ui_base"]))
    return vars_


def subst(obj, vars_):
    if isinstance(obj, str):
        def rep(mt):
            name = mt.group(1)
            if name not in vars_:
                raise RedError(f"引用未声明变量 {{{name}}}")
            return str(vars_[name])
        return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", rep, obj)
    if isinstance(obj, dict):
        return {k: subst(v, vars_) for k, v in obj.items()}
    if isinstance(obj, list):
        return [subst(v, vars_) for v in obj]
    return obj


def jget(data, path):
    if not path.startswith("$"):
        raise RedError(f"JSONPath 必须以 $ 开头: {path}")
    cur = data
    for part in path[2:].split("."):
        # 尾索引语法：key[-1] / [-1]（负数下标，常取数组末元素如最新一条消息）
        idx = None
        if part.endswith("[-1]"):
            idx = -1
            part = part[:-4]
        if isinstance(cur, list):
            try:
                cur = cur[int(part)] if part else (cur[idx] if idx is not None else MISSING)
            except (ValueError, IndexError):
                return MISSING
        elif isinstance(cur, dict):
            if part not in cur:
                return MISSING
            cur = cur[part]
            if idx is not None:
                if not isinstance(cur, list):
                    return MISSING
                try:
                    cur = cur[idx]
                except IndexError:
                    return MISSING
        else:
            return MISSING
    return cur


# ---------------------------------------------------------------- HTTP
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁自动重定向：http() 逐跳手动跟随——每跳复跑 SSRF 守卫，跨主机剥离凭据头。
    （默认 handler 会原样跟进 302 落点且不带守卫，Authorization 也照转——实证可被
    用来把执行器引进私网/云元数据端点并带走 key。）"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # None → urllib 抛 HTTPError(3xx)，交 http() 手动逐跳


_OPENER = urllib.request.build_opener(_NoRedirect)


def http(method, url, body=None, headers=None, timeout_s=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    retries = 2 if method.upper() == "GET" else 0  # 铁律 4：写操作不自动重试
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    cur, mth, payload = url, method.upper(), data
    for _hop in range(6):
        guard_url(cur)
        last = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(cur, data=payload, method=mth, headers=hdrs)
                with _OPENER.open(req, timeout=timeout_s) as r:
                    return _resp(r.status, r.read())
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
                if not loc:
                    return _resp(e.code, e.read())  # 有响应 = 交给断言去判
                nxt = urljoin(cur, loc)
                if (urlparse(nxt).hostname or "") != (urlparse(cur).hostname or ""):
                    for h in ("Authorization", "Cookie"):
                        hdrs.pop(h, None)  # 跨主机重定向不带凭据，防 key 被带走
                if e.code in (301, 302, 303):
                    mth, payload = "GET", None  # 与浏览器语义一致
                cur = nxt
                break  # 下一跳；重定向不消耗本跳的 GET 重试次数
            except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, OSError) as e:
                last = e
                if attempt < retries:
                    time.sleep(1)
        else:
            raise ConnError(f"{mth} {cur} 连接失败: {last}")
    raise ConnError(f"重定向跳数超上限: {url}")


def _resp(status, raw):
    text = raw.decode("utf-8", "replace")
    try:
        js = json.loads(text)
    except Exception:
        js = None
    return {"status": status, "text": text, "json": js}


# ---------------------------------------------------------------- 断言
def eval_assert(a, resp):
    if "status" in a:
        want = a["status"]
        ok = resp["status"] in want if isinstance(want, list) else resp["status"] == want
        return ok, f"status={resp['status']} 期望 {want}"
    if "json" in a:
        val = jget(resp.get("json") if resp.get("json") is not None else {}, a["json"])
        if "exists" in a:
            return val is not MISSING, f"{a['json']} 存在性"
        if val is MISSING:
            return False, f"{a['json']} 不存在"
        if "eq" in a:
            return val == a["eq"], f"{a['json']}={val!r} 期望 {a['eq']!r}"
        if "contains" in a:
            ok = isinstance(val, (str, list)) and a["contains"] in val
            return ok, f"{a['json']} 包含性"
        if "not_contains" in a:
            # 内容级断言：不得含指定子串（如 LLM 幕后指令回声）
            ok = not (isinstance(val, (str, list)) and a["not_contains"] in val)
            return ok, f"{a['json']} 不包含性"
        return False, "json 断言缺 exists/eq/contains"
    if "text_contains" in a:
        return a["text_contains"] in (resp.get("text") or ""), "响应文本包含性"
    return False, f"未知断言 {a}"


# ---------------------------------------------------------------- 步骤执行
class Ui:
    """门2 的 Playwright 懒加载会话（整个 run 批次共用一个浏览器；
    每个 run 开新 context——storage 隔离，保证 run 间彼此独立）。"""

    def __init__(self):
        self._pw = self._browser = self._page = self._ctx = None

    def page(self):
        if self._page is None:
            if self._pw is None:
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(headless=True)
            self._ctx = self._browser.new_context()
            self._page = self._ctx.new_page()
        return self._page

    def new_page(self):
        """run 间隔离：关掉上一 run 的 context，开全新 context + page。"""
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:
                pass
            self._ctx = None
            self._page = None
        return self.page()

    def close(self):
        for x in (self._ctx, self._browser, self._pw):
            try:
                if x:
                    x.close()
            except Exception:
                pass


def run_step(step, ctx, manifest, gate):
    sid = step["id"]
    if "_branch" in step:
        return do_fork(step, ctx, manifest, gate, step["_branch"])
    if "wait" in step:
        time.sleep(float(step["wait"].get("seconds", 1)))
        return f"等待 {step['wait'].get('seconds', 1)}s"
    if "api" in step:
        if gate == "ui":
            gates = step.get("gates")
            if gates and "ui" not in gates:
                raise RedError(f"步骤限定 gates={gates}，UI 门跳过（GATED）", uncover=True)
            raise RedError("API 步骤在 UI 门中无 ui 定义（UI-UNCOVERED）", uncover=True)
        cfg = subst(step["api"], ctx["vars"])
        url = manifest["target"]["api_base"].rstrip("/") + cfg["path"]
        resp = http(cfg["method"], url, cfg.get("body"), cfg.get("headers"),
                    float(cfg.get("timeout_s", 30)))
        ctx["last_resp"] = resp
        ctx["last_req"] = (cfg["method"], url, cfg.get("body"), cfg.get("headers"))
        _snip(ctx, sid, resp)
        for var, jp in (step.get("save") or {}).items():
            val = jget(resp.get("json") if resp.get("json") is not None else {}, jp)
            if val is MISSING:
                raise RedError(f"save 失败：响应无 {jp}（status={resp['status']}）")
            ctx["vars"][var] = val
        for a in step.get("assert") or []:
            ok, detail = eval_assert(a, resp)
            if not ok:
                _dump_resp(ctx, sid, resp)
                raise RedError(f"断言不过: {detail}")
        return f"{cfg['method']} {cfg['path']} → {resp['status']}"
    if "cli" in step:
        gates = step.get("gates")
        if gates and gate not in gates:
            raise RedError(f"步骤限定 gates={gates}，当前门 {gate} 跳过（GATED）", uncover=True)
        cfg = subst(step["cli"], ctx["vars"])
        cmd = cfg.get("cmd")
        argv = shlex.split(cmd, posix=True) if isinstance(cmd, str) else [str(x) for x in cmd or []]
        if not argv:
            raise RedError("cli.cmd 为空")
        root = Path(manifest.get("_path", ".")).parent  # cwd 相对清单所在目录
        cwd = (root / cfg["cwd"]).resolve() if cfg.get("cwd") else None
        try:
            cp = subprocess.run(argv, shell=False, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=float(cfg.get("timeout_s", 60)),
                                cwd=cwd)
            rc, text = cp.returncode, (cp.stdout or "") + (cp.stderr or "")
        except FileNotFoundError as e:
            rc, text = 127, f"[命令不存在] {e}"
        except subprocess.TimeoutExpired as e:
            rc, text = 124, f"[超时] {cmd}: {e}"
        _mk_dump(ctx, f"{sid}.cli.txt", f"$ {cmd}\nexit={rc}\n{text[:4000]}")
        resp = {"status": rc, "text": text, "json": None}  # 伪响应：status=退出码，可复用全部断言
        for a in step.get("assert") or []:
            ok, detail = eval_assert(a, resp)
            if not ok:
                raise RedError(f"断言不过: {detail}")
        return f"cli: {cmd} → exit {rc}"
    if "ui" in step:
        if gate != "ui":
            return "门1 跳过 UI 步骤"
        detail = do_ui(step, ctx, manifest)
        # 2026-09-05 修复：ui 步骤的 assert 原本被静默忽略（假绿）——
        # ui_visible 断言现在真正执行；text_contains/status 走通用断言
        page = ctx["_ui"].page()
        resp = {"status": 200, "text": page.inner_text("body"), "json": None}
        for a in step.get("assert") or []:
            if "ui_visible" in a:
                sel = a["ui_visible"]
                try:
                    page.wait_for_selector(sel, state="visible", timeout=3000)
                except Exception:
                    raise RedError(f"断言不过: 元素不可见 {sel}")
            else:
                ok, why = eval_assert(a, resp)
                if not ok:
                    _dump_text(ctx, sid, "page", page.inner_text("body")[:4000])
                    raise RedError(f"断言不过: {why}")
        return detail
    raise RedError("步骤类型无法识别")


def do_ui(step, ctx, manifest):
    cfg = subst(step["ui"], {**ctx["vars"], "ui_base": manifest["target"].get("ui_base", "")})
    act, page = cfg.get("action"), ctx["_ui"].page()
    try:
        return _do_ui_action(act, page, cfg, ctx, step)
    except RedError:
        raise
    except Exception as e:  # playwright 超时/选择器异常 → 计失败而非崩批次
        raise RedError(f"UI 动作 {act} 异常: {type(e).__name__}: {str(e)[:200]}")


def _setup_basic_auth_route(page, url):
    """URL 内嵌凭据（http://user:pass@host）在头部导航上已不被 Chromium 自动应用，
    全新 context 也没有凭据缓存：SPA 首个 API 调用会 401 导致页面无法渲染。
    改用 route 拦截对该 origin 的全部请求注入 Authorization 头。"""
    import base64
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    if not parts.username:
        return url
    userinfo = parts.username + (":" + parts.password if parts.password else "")
    header = "Basic " + base64.b64encode(userinfo.encode()).decode()
    origin = f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")
    clean_url = urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1],
                            parts.path, parts.query, parts.fragment))

    def _auth(route):
        headers = {**route.request.headers, "Authorization": header}
        route.continue_(headers=headers)

    page.route(origin + "/**", _auth)
    return clean_url


def _do_ui_action(act, page, cfg, ctx, step):
    if act == "goto":
        url = _setup_basic_auth_route(page, cfg["url"])
        # 跨海/慢源站目标 20s 硬编码扛不住首屏资源全量加载：timeout_s 秒参数化
        page.goto(url, timeout=int(cfg.get("timeout_s", 20)) * 1000)
        try:
            # networkidle 只是尽力而为的静默等待：部分站点长轮询/慢字体永远不空闲，
            # load 事件已保证 DOM+资源就绪，这里超时不应判死步骤。
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        u = cfg["url"]
        if "@" in u:  # URL 内嵌凭据不进 detail/报告/落盘（铁律 2 同源口径）
            head, tail = u.rsplit("@", 1)
            sp = head.find("://")
            u = head[:sp + 3] + "***@" + tail if sp != -1 else u
        return f"goto {u}"
    if act == "click":
        page.click(cfg["target"], timeout=10000)
        return f"click {cfg['target']}"
    if act == "fill":
        page.fill(cfg["target"], cfg.get("value", ""), timeout=10000)
        return f"fill {cfg['target']}"
    if act == "wait":
        page.wait_for_timeout(int(cfg.get("ms", 500)))
        return f"wait {cfg.get('ms', 500)}ms"
    if act == "expect_visible":
        try:
            page.wait_for_selector(cfg["target"], state="visible", timeout=10000)
        except Exception:
            # 失败取证：落当前 URL 与页面文本首段，便于定位"等不到元素"时页面实际在哪
            try:
                _dump_text(ctx, step["id"], "page_url", page.url)
                _dump_text(ctx, step["id"], "page", page.inner_text("body")[:2000])
            except Exception:
                pass
            raise RedError(f"元素不可见: {cfg['target']}")
        return f"visible {cfg['target']}"
    if act == "text_contains":
        text = page.inner_text("body")
        if cfg.get("value") not in text:
            _dump_text(ctx, step["id"], "page", text[:4000])
            raise RedError(f"页面文本不含「{cfg.get('value')}」")
        return f"文本含「{cfg.get('value')}」"
    raise RedError(f"未知 UI 动作 {act}")


def do_fork(step, ctx, manifest, gate, branch_id):
    f, sid = step["fork"], step["id"]
    if gate == "ui" and f.get("read") == "$page":
        text = ctx["_ui"].page().inner_text("body")
    else:
        try:
            text = subst(f.get("read") or "", ctx["vars"])
        except RedError as e:
            if gate == "ui":
                # UI 门下前置 api 步骤被 SKIP，读题变量未产出 → 视为无覆盖而非失败
                raise RedError(f"fork 读题变量未就绪（{e}）", uncover=True)
            raise
    kws = f.get("expect_keywords") or []
    if kws and not any(k in text for k in kws):
        _dump_text(ctx, sid, "question", text)
        raise RedError(f"题面不含预期关键词 {kws}，题面截取：{text[:120]}")
    branch = next((b for b in f.get("branches") or [] if b["id"] == branch_id), None)
    if branch is None:
        raise RedError(f"枚举分支 {branch_id} 不在清单中（清单被改过？重跑 --plan-only）")
    pick, choice_var = branch["pick"], f.get("choice_var") or f"{sid}_choice"
    if "contains" in pick and pick["contains"] in text:
        choice, how = pick["contains"], "关键词"
    elif "llm" in pick and f.get("mode") == "fuzzy":
        llm = manifest.get("llm") or {}
        r = llm_match.pick_choice(llm.get("base_url"), llm.get("api_key_env"),
                                  llm.get("model"), text, pick["llm"])
        if not r["ok"]:
            _dump_text(ctx, sid, "question", text + f"\n\n[LLM兜底失败] {r['error']}")
            raise RedError(f"LLM 兜底失配: {r['error']}")
        choice, how = r["choice"], "LLM" + ("（非 JSON 取首行）" if r.get("note") else "")
        _dump_text(ctx, sid, "llm_raw", r.get("raw") or "")
    else:
        _dump_text(ctx, sid, "question", text)
        raise RedError(f"读题失配：题面未含「{pick.get('contains')}」"
                       + ("（exact 模式不做模糊兜底）" if f.get("mode") != "fuzzy" else ""))
    ctx["vars"][choice_var] = choice
    _dump_text(ctx, sid, "choice", f"题面：{text[:500]}\n选中：{choice}（{how}）")
    return f"分叉 {sid} → {branch_id}（{how}）: {choice[:40]}"


def _snip(ctx, sid, resp):
    # resp["json"] 已在完整响应文本上解析（_resp）。曾为省空间「截断再 parse」，
    # >2000 字符响应 parse 必败被静默吞——status+json 一起丢，diag 失去对照样本、
    # 大响应场景（LLM 长回复正是主形态）诊断静默降级。现截断只作用于随存文本预览。
    body = resp.get("text") or ""
    ctx["snips"][sid] = {"status": resp["status"], "json": resp.get("json"),
                         "text": body[:2000], "truncated": len(body) > 2000}


def _mk_dump(ctx, fname, content):
    p = ctx["artdir"] / fname
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    ctx["artifacts"].append(p.name)


def _dump_resp(ctx, sid, resp):
    _mk_dump(ctx, f"{sid}.resp.json", json.dumps(
        {"status": resp["status"], "text": resp["text"][:4000]},
        ensure_ascii=False, indent=1))


def _dump_text(ctx, sid, name, text):
    _mk_dump(ctx, f"{sid}.{name}.txt", str(text))


# ---------------------------------------------------------------- run 与探针
def execute_run(run, manifest, gate, ui, artdir):
    ctx = {"vars": fresh_vars(manifest), "last_resp": None, "last_req": None,
           "snips": {}, "artifacts": [], "artdir": artdir / run["id"], "_ui": ui}
    ctx["artdir"].mkdir(parents=True, exist_ok=True)
    out = {"id": run["id"], "kind": run["kind"], "branch_trace": run["trace"],
           "status": "PASS", "ms": 0, "error": None, "steps": [], "vars": {},
           "snips": {}, "artifacts": [], "finished_at": None}
    uncovered, conn_fail = [], False
    t0 = time.time()
    if gate == "ui":
        ui.new_page()  # run 间 storage 隔离：上一 run 的登录态不带入
    for step in run["steps"]:
        sr = {"id": step["id"], "status": "PASS", "ms": 0, "detail": ""}
        ts = time.time()
        try:
            sr["detail"] = run_step(step, ctx, manifest, gate)
        except RedError as e:
            sr["ms"] = int((time.time() - ts) * 1000)
            if e.uncover:
                uncovered.append(step["id"])
                sr.update(status="SKIP", detail=str(e))
                out["steps"].append(sr)
                continue
            sr.update(status="RED", detail=str(e))
            out.update(status="RED", error=f"步骤 {step['id']}: {e}")
            out["steps"].append(sr)
            break
        except ConnError as e:
            sr.update(status="RED", ms=int((time.time() - ts) * 1000), detail=str(e))
            out.update(status="RED", error=f"步骤 {step['id']}: {e}", conn_fail=True)
            conn_fail = True
            out["steps"].append(sr)
            break
        sr["ms"] = int((time.time() - ts) * 1000)
        out["steps"].append(sr)
    else:  # 全部步骤跑完且未被 RED 打断 → 探针注入
        if run["kind"] == "probe" and out["status"] == "PASS":
            try:
                detail = run_probe(run, ctx, manifest, gate)
                out["steps"].append({"id": f"probe:{run['probe']}", "status": "PASS",
                                     "ms": 0, "detail": detail})
            except RedError as e:
                if e.uncover and gate == "ui":
                    out.update(status="SKIPPED",
                               error=f"UI-UNCOVERED 探针 {run['probe']}: {e}")
                    out["steps"].append({"id": f"probe:{run['probe']}",
                                         "status": "SKIP", "ms": 0, "detail": str(e)})
                else:
                    out.update(status="RED", error=f"探针 {run['probe']}: {e}")
                    out["steps"].append({"id": f"probe:{run['probe']}", "status": "RED",
                                         "ms": 0, "detail": str(e)})
            except ConnError as e:
                out.update(status="RED", error=f"探针连接失败: {e}", conn_fail=True)
    if gate == "ui" and uncovered and out["status"] == "PASS":
        out["status"] = "SKIPPED"
        out["error"] = f"UI-UNCOVERED: {','.join(uncovered)} 无 ui 定义"
    out.update(ms=int((time.time() - t0) * 1000), vars=ctx["vars"],
               snips=ctx["snips"], artifacts=ctx["artifacts"], finished_at=now_iso())
    if conn_fail:
        out["conn_fail"] = True
    return out


def run_probe(run, ctx, manifest, gate):
    p = (manifest.get("probes") or {})[run["probe"]]
    if "api" in p:
        try:
            cfg = subst(p["api"], ctx["vars"])
        except RedError as e:
            # UI 门下前置 api 步骤被 SKIP，探针引用的变量未产出 → 无覆盖而非失败
            raise RedError(f"探针变量未就绪（{e}）", uncover=(gate == "ui"))
        url = manifest["target"]["api_base"].rstrip("/") + cfg["path"]
        resp = http(cfg["method"], url, cfg.get("body"), cfg.get("headers"),
                    float(cfg.get("timeout_s", 30)))
        what = f"{cfg['method']} {cfg['path']} → {resp['status']}"
    else:  # duplicate_submit：重放目标步的原始请求（含头，Basic Auth 端点否则恒 401）
        if not ctx.get("last_req"):
            # 目标步在本次 run 未实际执行（如 UI 门下 api 步骤被 SKIP）
            raise RedError("duplicate_submit 无可重放请求（目标步未实际执行）",
                           uncover=(gate == "ui"))
        method, url, body, headers = ctx["last_req"]
        resp = http(method, url, body, headers, 30)
        what = f"重放 {method} → {resp['status']}"
    _dump_resp(ctx, f"probe_{run['probe']}", resp)
    for a in p.get("expect") or []:
        ok, detail = eval_assert(a, resp)
        if not ok:
            raise RedError(f"探针断言不过: {detail}")
    return what


# ---------------------------------------------------------------- health 与 CLI
def health_check(m):
    h = (m.get("environment") or {}).get("health")
    if not h:
        print("[health] 清单未配 health，跳过复验")
        return True
    guard_url(h.get("url"))
    deadline = time.time() + float(h.get("timeout_s", 120))
    while time.time() < deadline:
        try:
            if http(h.get("method", "GET"), h["url"], timeout_s=5)["status"] == h.get("expect", 200):
                print(f"[health] 就绪：{h['url']}")
                return True
        except ConnError:
            pass
        time.sleep(2)
    print(f"[health] 超时未就绪：{h['url']}"
          f"（environment.start 由 AI 编排层负责，先起环境再跑；本地栈记得 FULLFLOW_ALLOW_PRIVATE_TARGET=1）")
    return False


def plan_only(normals, runs, m):
    n_api = sum(1 for r in runs for s in r["steps"] if "api" in s)
    n_cli = sum(1 for r in runs for s in r["steps"] if "cli" in s)
    n_llm = sum(1 for r in normals for s in r["steps"]
                if "fork" in s and any("llm" in b["pick"] for b in s["fork"]["branches"]))
    print(f"清单：{m.get('name')}")
    print(f"正常路径 {len(normals)} 条 + 探针 run {len(runs) - len(normals)} 条 = 共 {len(runs)} 条")
    print(f"API 请求约 {n_api} 次；LLM 读题兜底上限约 {n_llm} 次（关键词命中则不调）")
    if n_cli:
        print(f"CLI 命令约 {n_cli} 次（本机 shell 执行，确认命令可复现、无破坏性）")
    print("-" * 60)
    for r in runs:
        tag, extra = ("探针", f"（{r['probe']}@{r['probe_step']}）") if r["kind"] == "probe" else ("正常", "")
        print(f"[{tag}] {r['id']}{extra}  步骤数 {len(r['steps'])}")


def _latest_failed_ids(mpath):
    rroot = mpath.parent / "reports"
    for d in sorted(rroot.iterdir(), reverse=True) if rroot.exists() else []:
        f = d / "results.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("gate") == "api":
                return {r["id"] for r in data.get("runs", []) if r.get("status") == "RED"}
    return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gate", choices=["api", "ui"], default="api")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--max-paths", type=int, default=None)
    ap.add_argument("--only-gate-failed", action="store_true")
    args = ap.parse_args()

    mpath = Path(args.manifest).resolve()
    m = load_manifest(mpath)
    m["_path"] = str(mpath)  # cli 步骤的 cwd 相对清单所在目录
    validate(m)
    normals, runs = enum_runs(m)

    if args.plan_only:
        plan_only(normals, runs, m)
        return
    if args.max_paths is not None and len(runs) > args.max_paths:
        raise SystemExit(f"路径数 {len(runs)} 超过 --max-paths {args.max_paths}，已中止"
                         f"（不静默跳过）。未覆盖：{[r['id'] for r in runs[args.max_paths:]]}")
    if args.only is not None:
        want = set(args.only)
        runs = [r for r in runs if r["id"] in want]
        if want - {r["id"] for r in runs}:
            raise SystemExit(f"--only 含不存在路径（先 --plan-only 看表）：{sorted(want - {r['id'] for r in runs})}")
    if args.only_gate_failed:
        prev = _latest_failed_ids(mpath)
        runs = [r for r in runs if r["id"] in prev]
        if not runs:
            raise SystemExit("最近的门1 结果里没有 RED 路径可复测")

    if args.gate == "ui":  # 门2 通道分流：run.py 只驱动 web（Playwright）
        platform = (m.get("target") or {}).get("platform") or "web"
        if platform != "web":
            raise SystemExit(f"platform={platform} 的门2 走 AI 驱动通道"
                             f"（见 SKILL.md「门2 多平台驱动分流」），run.py 不直接驱动")
        if not (m.get("target") or {}).get("ui_base"):
            raise SystemExit("web 平台未配 target.ui_base，门2 无处可去；"
                             "App/桌面/CLI 目标请设 target.platform 走对应通道")

    if not health_check(m):
        raise SystemExit(2)

    rdir = mpath.parent / "reports" / datetime.now().strftime("%Y-%m-%d_%H%M%S_run")
    (rdir / "artifacts").mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.snapshot.yaml").write_text(mpath.read_text(encoding="utf-8"),
                                                 encoding="utf-8")
    ui = Ui() if args.gate == "ui" else None
    print(f"开跑：gate={args.gate}，共 {len(runs)} 条 run，报告目录 {rdir}")

    results, conn_streak = [], 0
    for i, r in enumerate(runs):
        if conn_streak >= 3:
            results.append({"id": r["id"], "kind": r["kind"], "branch_trace": r["trace"],
                            "status": "NOT_RUN", "error": "环境崩溃熔断（连续连接失败）",
                            "steps": [], "vars": {}, "snips": {}, "artifacts": [],
                            "ms": 0, "finished_at": now_iso()})
            continue
        print(f"[{i + 1}/{len(runs)}] {r['id']} ...", flush=True)
        rr = execute_run(r, m, args.gate, ui, rdir / "artifacts")
        conn_streak = conn_streak + 1 if rr.pop("conn_fail", False) else 0
        results.append(rr)
        print(f"    → {rr['status']}  {rr['ms']}ms  {rr['error'] or ''}", flush=True)
    if ui:
        ui.close()

    summary = {"manifest": str(mpath), "name": m.get("name"), "gate": args.gate,
               "started_at": results[0]["finished_at"] if results else now_iso(),
               "finished_at": now_iso(), "target": m.get("target"), "runs": results}
    (rdir / "results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    stat = {}
    for rr in results:
        stat[rr["status"]] = stat.get(rr["status"], 0) + 1
    print("完成：" + "  ".join(f"{k}={v}" for k, v in stat.items()) + f"  报告目录：{rdir}")


if __name__ == "__main__":
    main()

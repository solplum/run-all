"""run-all — fuzzy 分叉读题的 LLM 兜底（关键词匹配由 run.py 完成，这里只负责选支）。

SSRF 约束：仅允许 http/https；私网/环回地址需显式设置 FULLFLOW_ALLOW_PRIVATE_LLM=1
（本地 LLM 网关调试用），公网地址不受影响。
"""
import ipaddress
import json
import os
import re
import socket
import urllib.request
from urllib.parse import urlparse


def strip_think(text: str) -> str:
    """剥掉思考模型的 <think>...</think> 段（MiniMax-M3 等会带，不清掉会污染读题）。"""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I).strip()


def check_endpoint_url(url: str) -> str | None:
    """校验 LLM endpoint。返回 None=通过，否则返回拒绝原因。"""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        return f"协议不允许: {p.scheme or '(空)'}，仅 http/https"
    host = p.hostname or ""
    private = host in ("localhost",) or host.endswith(".local")
    if not private:
        try:
            addr = ipaddress.ip_address(host)
            private = (
                addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast
            )
        except ValueError:
            # 域名解析成 IP 逐一判（曾放行交出口侧管控——域名可解析到环回绕过守卫）
            try:
                infos = socket.getaddrinfo(host, None)
            except socket.gaierror:
                infos = []
            for info in infos:
                try:
                    a = ipaddress.ip_address(info[4][0])
                except (ValueError, IndexError):
                    continue
                if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved:
                    private = True
                    break
    if private and os.environ.get("FULLFLOW_ALLOW_PRIVATE_LLM") != "1":
        return f"私网/环回 LLM 地址被拒（{host}）；本地网关调试请设 FULLFLOW_ALLOW_PRIVATE_LLM=1"
    return None


def pick_choice(base_url, api_key_env, model, question, instruction, timeout_s=60):
    """把题目文本 + 分支的 pick 指令发给 LLM，要它返回 {"choice": "<选项原文>"}。

    返回 {"ok": True, "choice": str} 或 {"ok": False, "error": str}（raw 字段带原始输出便于取证）。
    """
    if not base_url or not model:
        return {"ok": False, "error": "清单缺 llm.base_url / llm.model，无法 LLM 兜底"}
    reason = check_endpoint_url(base_url)
    if reason:
        return {"ok": False, "error": reason}
    key = os.environ.get(api_key_env or "", "")
    if not key:
        return {"ok": False, "error": f"环境变量 {api_key_env} 未设置，无法 LLM 兜底"}

    prompt = (
        "以下是流程中的题目/问题文本：\n---\n"
        f"{question}\n---\n"
        f"任务：{instruction}\n"
        '只输出一个 JSON 对象：{"choice": "<选项原文>"}，不要输出任何其他内容。'
    )
    payload = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # 一律不跟随重定向：Bearer key 不得随 30x 带到任何落点

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout_s) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # 网络/超时/非 JSON 响应都算兜底失败，由调用方记 RED
        return {"ok": False, "error": f"LLM 调用失败: {e}"}

    try:
        raw = strip_think(data["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        # 网关 200 + 错误形状体（无 choices/缺 message/content 为数组）按兜底失败归位，不裸崩整批
        return {"ok": False, "error": f"LLM 响应结构异常: {e!r}",
                "raw": json.dumps(data, ensure_ascii=False)[:200]}
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if m:
        try:
            choice = json.loads(m.group(0)).get("choice")
            if choice:
                return {"ok": True, "choice": str(choice), "raw": raw}
        except Exception:
            pass
    line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    if line:
        return {"ok": True, "choice": line, "raw": raw, "note": "非 JSON 输出，取首行"}
    return {"ok": False, "error": f"无法解析 LLM 输出: {raw[:200]}", "raw": raw}

#!/usr/bin/env python3
"""run-all 自带演示服务：零依赖（纯标准库），3 步 2 叉 + 异常探针靶点。

用途：不依赖任何真实项目，回归验证执行器全链（SKILL.md「验证本 skill 自身」）。
流程：创建蓝图 → 第一题（复刻/全新）→ 简报决策（确认/修改）→ 生成 → 查档。
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

DB = {}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _bp(self):
        parts = self.path.strip("/").split("/")
        return DB.get(parts[1]) if len(parts) > 1 and parts[0] == "blueprints" else None

    def log_message(self, *a):  # 静音，避免干扰执行器输出
        pass

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path.endswith("/question"):
            return self._send(200, {"question": "你想复刻一个既有角色，还是创建一个全新人设？"})
        bp = self._bp()
        if self.path.endswith("/brief"):
            if not bp:
                return self._send(404, {"error": "blueprint not found"})
            return self._send(200, {"brief": f"{bp['name']} 的人设简报",
                                    "question": "请选择：确认这份简报，或者修改后再确认。"})
        if bp:
            return self._send(200, bp)
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        body, p = self._body(), self.path.rstrip("/")
        if p == "/blueprints":
            name = (body.get("name") or "").strip()
            if not name:
                return self._send(400, {"error": "name 必填"})
            if any(b["name"] == name for b in DB.values()):
                return self._send(409, {"error": "name 已存在（重复提交被拒）"})
            bid = f"bp{len(DB) + 1:04d}"
            DB[bid] = {"id": bid, "name": name, "status": "created"}
            return self._send(201, DB[bid])
        bp = self._bp()
        if not bp:
            return self._send(404, {"error": "blueprint not found"})
        if p.endswith("/answer"):
            choice = (body.get("choice") or "").strip()
            if "复刻" not in choice and "全新" not in choice:
                return self._send(400, {"error": "choice 必须含 复刻/全新"})
            bp["choice"] = choice
            return self._send(200, {"ok": True, "choice": choice})
        if p.endswith("/decision"):
            choice = (body.get("choice") or "").strip()
            if "确认" not in choice and "修改" not in choice:
                return self._send(400, {"error": "decision 必须含 确认/修改"})
            bp["decision"] = choice
            bp["revised"] = "修改" in choice
            return self._send(200, {"ok": True, "revised": bp["revised"]})
        if p.endswith("/generate"):
            if bp["status"] == "cancelled":
                return self._send(409, {"error": "已取消的蓝图不能生成（cancelled 为终态）"})
            if "choice" not in bp or "decision" not in bp:
                return self._send(409, {"error": "流程未走完，不能生成"})
            bp["status"] = "generated"
            bp["persona"] = {"name": bp["name"], "source": bp["choice"]}
            return self._send(200, bp)
        if p.endswith("/cancel"):
            bp["status"] = "cancelled"
            return self._send(200, {"status": "cancelled"})
        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"demo 服务：http://127.0.0.1:{args.port}（Ctrl+C 停）")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

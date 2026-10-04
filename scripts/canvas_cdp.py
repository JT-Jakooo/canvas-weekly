#!/usr/bin/env python
"""
Canvas 只读抓取工具（通过 CDP 借用用户已登录的浏览器会话）。

用法:
  python canvas_cdp.py get  <api_path> [outfile]     # 抓任意 Canvas API 路径
  python canvas_cdp.py page <course_id> <slug> [out] # 抓页面正文（去 HTML）
  python canvas_cdp.py all  <outdir>                 # 批量抓标准端点

依赖: websockets (pip install websockets)
前提: 浏览器已由用户启动并带 --remote-debugging-port=9222，且已登录 Canvas。
"""
import asyncio, json, sys, io, os, re, html, time, urllib.request

PORT = int(os.environ.get("CANVAS_CDP_PORT", "9222"))
HOST_MATCH = os.environ.get("CANVAS_HOST", "canvas.manchester.ac.uk")

# 课程 ID 需按学期核对（GET /api/v1/courses 可列出）
COURSES = {}


# 强制绕过系统代理：否则 127.0.0.1 的 CDP 端点会被代理拦截（实测返回 HTTP 502 Bad Gateway）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def page_ws():
    url = "http://127.0.0.1:%d/json/list" % PORT
    d = json.load(_OPENER.open(url, timeout=10))
    p = [t for t in d if t.get("type") == "page" and HOST_MATCH in t.get("url", "")]
    if not p:
        p = [t for t in d if t.get("type") == "page"]
    if not p:
        raise SystemExit("找不到可用标签页。请确认浏览器已打开且带 --remote-debugging-port")
    return p[0]["webSocketDebuggerUrl"]


def strip_html(body):
    t = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>|</div>", "\n", body or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


async def fetch_many(pairs):
    """pairs: list of (name, api_path). 返回 [(name, status, text)]

    ⚠ 2026-10-04：**同步 XHR 已不可用**。Edge 154 起，页面内 `xhr.open(..., false)`
    一律抛 `NetworkError`（实测 `/api/v1/users/self` 也失败，与登录状态无关）。
    改用异步 `fetch` + CDP 的 `awaitPromise: true`，已验证正常返回 200。
    """
    ws_url = page_ws()
    out = []
    expr_tpl = ("fetch(%s,{credentials:'same-origin'})"
                ".then(r=>r.text().then(t=>JSON.stringify({s:r.status,b:t})))"
                ".catch(e=>JSON.stringify({s:0,b:'FETCH THROW '+e}))")
    async with __import__("websockets").connect(ws_url, max_size=256 * 1024 * 1024) as ws:
        i = 0
        for name, path in pairs:
            i += 1
            expr = expr_tpl % json.dumps(path)
            await ws.send(json.dumps({"id": i, "method": "Runtime.evaluate",
                                      "params": {"expression": expr, "returnByValue": True,
                                                 "awaitPromise": True}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == i:
                    break
            val = msg.get("result", {}).get("result", {}).get("value")
            if val is None:
                out.append((name, 0, ""))
            else:
                d = json.loads(val)
                out.append((name, d["s"], d["b"]))
            time.sleep(0.15)
    return out


def cmd_all(outdir):
    os.makedirs(outdir, exist_ok=True)
    jobs = [("courses", "/api/v1/courses?per_page=100&enrollment_state=active"),
            ("todo", "/api/v1/users/self/todo?per_page=100"),
            ("upcoming", "/api/v1/users/self/upcoming_events"),
            ("planner", "/api/v1/planner/items?per_page=100")]
    res = asyncio.run(fetch_many(jobs))
    for name, st, body in res:
        io.open(os.path.join(outdir, name + ".json"), "w", encoding="utf-8").write(body)
        print("%-12s HTTP %s  %d bytes" % (name, st, len(body)))
    # 从 courses.json 自动推导课程 ID，再抓各科明细
    try:
        cs = json.loads([b for n, s, b in res if n == "courses"][0])
    except Exception:
        print("课程列表解析失败，跳过明细"); return
    ids = {c["course_code"].split()[0]: c["id"] for c in cs if c.get("course_code")}
    print("课程:", ids)
    jobs2 = []
    for code, cid in ids.items():
        for kind, path in [
            ("assignments", "/api/v1/courses/%d/assignments?per_page=100&order_by=due_at" % cid),
            ("modules", "/api/v1/courses/%d/modules?include[]=items&per_page=100" % cid),
            ("announcements", "/api/v1/announcements?context_codes[]=course_%d&per_page=50" % cid),
        ]:
            jobs2.append(("%s__%s" % (code, kind), path))
    for name, st, body in asyncio.run(fetch_many(jobs2)):
        io.open(os.path.join(outdir, name + ".json"), "w", encoding="utf-8").write(body)
        print("%-28s HTTP %s  %d bytes" % (name, st, len(body)))


def cmd_get(path, outfile=None):
    (name, st, body), = asyncio.run(fetch_many([("x", path)]))
    print("HTTP", st, len(body), "bytes")
    if outfile:
        io.open(outfile, "w", encoding="utf-8").write(body); print("->", outfile)
    else:
        print(body[:2000])


def cmd_page(cid, slug, outfile=None):
    path = "/api/v1/courses/%s/pages/%s" % (cid, slug)
    (name, st, body), = asyncio.run(fetch_many([("x", path)]))
    try:
        obj = json.loads(body); txt = strip_html(obj.get("body"))
    except Exception:
        txt = body
    print("HTTP", st)
    if outfile:
        io.open(outfile, "w", encoding="utf-8").write(txt); print("->", outfile)
    else:
        print(txt[:3000])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    c = sys.argv[1]
    if c == "all":
        cmd_all(sys.argv[2] if len(sys.argv) > 2 else "_canvas_data")
    elif c == "get":
        cmd_get(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif c == "page":
        cmd_page(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        print(__doc__)

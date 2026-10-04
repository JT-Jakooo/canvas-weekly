"""在指定页面里执行 JS 并打印结果（CDP Runtime.evaluate）。

用法: python cdp_eval.py <js表达式> [url子串] [port]
       python cdp_eval.py --file <js文件> [url子串] [port]
"""
import asyncio, json, sys, urllib.request

# 强制绕过系统代理：否则 127.0.0.1 的 CDP 端点会被代理拦截（实测 HTTP 502 / 连接被拒）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

args = sys.argv[1:]
if not args:
    print(__doc__); raise SystemExit(1)

if args[0] == "--file":
    EXPR = open(args[1], encoding="utf-8").read()
    rest = args[2:]
else:
    EXPR = args[0]
    rest = args[1:]

PORT = next((int(a) for a in rest if a.isdigit()), 9222)
MATCH = next((a for a in rest if not a.isdigit()), "outlook.cloud.microsoft")


async def main():
    import websockets
    d = json.load(_OPENER.open("http://127.0.0.1:%d/json/list" % PORT, timeout=10))
    pages = [t for t in d if t.get("type") == "page" and MATCH in (t.get("url") or "")]
    if not pages:
        print("找不到匹配页面:", MATCH)
        for t in d:
            if t.get("type") == "page":
                print("   候选:", (t.get("url") or "")[:100])
        raise SystemExit(1)
    pg = pages[0]
    print("page:", (pg.get("title") or "")[:50], "|", (pg.get("url") or "")[:90])
    async with websockets.connect(pg["webSocketDebuggerUrl"], max_size=256 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": EXPR, "returnByValue": True,
                                             "awaitPromise": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                break
    r = msg.get("result", {})
    if "exceptionDetails" in r:
        print("JS 异常:", json.dumps(r["exceptionDetails"])[:600]); return
    v = r.get("result", {}).get("value")
    print(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)[:6000])


asyncio.run(main())

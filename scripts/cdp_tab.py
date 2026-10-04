"""在带 --remote-debugging-port 的浏览器里新建标签页。

用法: python cdp_tab.py <url> [port]
"""
import asyncio, json, sys, urllib.request

args = sys.argv[1:]
URL = next((a for a in args if a.startswith("http")), "about:blank")
PORT = next((int(a) for a in args if a.isdigit()), 9222)


async def main():
    import websockets
    ver = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=10))
    ws_url = ver["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Target.createTarget",
                                  "params": {"url": URL}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                break
        print("新标签页已创建 targetId =", msg.get("result", {}).get("targetId"), "->", URL)


asyncio.run(main())

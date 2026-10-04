# canvas-weekly

读取曼彻斯特大学 Canvas（canvas.manchester.ac.uk）上的每周教学安排与作业截止，
生成**"本周/下周要做什么"清单**；也可以把某周需要的文件下载到本地 / OneDrive，
按规范归类改名。

这是给 AI Agent 用的 skill（Claude Skill / WorkBuddy Skill 格式）——
核心是 `SKILL.md` 里那套经过实测校准的抓取与归类规范，`scripts/` 只是执行它的工具。

## 它解决什么问题

- 每门课的作业、公告、模块页面散在 Canvas 各处，手动翻很费时间
- Canvas 的 `due_at` / Outlook 课表的 `Start` 都是 **UTC**，直接看会整体错 1 小时（夏令时）
- 老师锁定文件下载权限、文件列表接口被学校禁用（403）时，不知道还能怎么拿文件
- 用户手动下载过的文件常被改名，按文件名比对会重复下载 + 误判

这个 skill 把这些问题逐条解决：只读抓取、周次现场推导、UTC → 本地换算、
文件按 **MD5** 比对归类，且全程不对外发送数据。

## 功能

- 只读抓取 Canvas 课程 / 作业 / 模块 / 公告 / 页面正文（CDP 借用已登录的浏览器会话，绝不 POST）
- **周次现场推导**：不写死学期锚点，用课表 + Canvas 模块名的日期区间定周次
- 产出 HTML 看板：周次定位 / 最近截止时间表 / 每门课下周任务 / 固定安排 / 考核方式
- 下载某周文件到本地 / OneDrive，并按《Course Folder Organization Guide》归类改名
- **UTC → Europe/London** 换算（BST/GMT 分段处理），用课表交叉验证
- 外部课表走 Outlook OWA REST（Microsoft Graph 403 时的可用通道）

## 环境要求

- Windows + Edge（以 `--remote-debugging-port=9222` + 独立 `--user-data-dir` 启动）
- Python 3 + `websockets`（装在隔离 venv）

```bash
<venv>/Scripts/pip.exe install websockets
```

## 安装

把本目录放到 Agent 的 skill 目录下即可：

```
# WorkBuddy / Claude Code 用户级 skill
~/.workbuddy-ai/skills/canvas-weekly/
```

## 用法

```bash
# 1) 确认 CDP 通道活着
curl -s -m 10 http://127.0.0.1:9222/json/version

# 2) 批量抓取标准端点（课程/待办/日程/作业/模块/公告）
<venv>/Scripts/python.exe scripts/canvas_cdp.py all <工作区>/_canvas_data

# 3) 抓某页正文（老师的原话）
<venv>/Scripts/python.exe scripts/canvas_cdp.py page <course_id> <page_slug>

# 4) 辅助：在调试浏览器里执行 JS / 新建标签页
<venv>/Scripts/python.exe scripts/cdp_eval.py "<js表达式>" [url子串]
<venv>/Scripts/python.exe scripts/cdp_tab.py <url> [port]
```

## 文件结构

```
SKILL.md                # 权威规范：硬约束、时区换算、周次推导、踩坑清单（先读这个）
scripts/
  canvas_cdp.py         # Canvas 只读抓取工具（get / page / all 三个子命令）
  cdp_eval.py           # 在指定页面执行 JS 并打印结果（Runtime.evaluate + awaitPromise）
  cdp_tab.py            # 在调试浏览器里新建标签页（Target.createTarget）
```

## 注意事项

- 首次 SSO + MFA 登录必须用户本人操作；之后 session 存在浏览器 profile 里，Agent 可复用
- 沙箱会连带清理子进程：长驻浏览器任务要用 `run_in_background: true` 抱住
- 本机设了系统代理时，访问 `127.0.0.1:9222` 必须绕过代理（脚本已内置处理）
- 课程 ID、周次锚点、Reading week 位置每学期都会变 → 每次运行现场重新核对
- 已有例行自动化（每周六 11:00）把本 skill 的完整流程串成一条链，改流程时记得同步更新它的 prompt

## 许可

[MIT](LICENSE)

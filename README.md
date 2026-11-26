# 好策读书自动化助手（绿色版）

当前版本：**v1.1**（上一版 v1.0，见 [更新日志](#版本与更新日志)）

## 仓库内容

| 路径 | 内容 |
| --- | --- |
| 根目录 | Python 源码（`app.py` 为 GUI 入口），直接 `python app.py` 运行 |
| `bin/` | `pdftotext.exe` 及其依赖 DLL（`adb.exe` / `ffmpeg.exe` 体积大，需自行放入，见下文） |
| `release/haoce-tool-green/` | 绿色版目录，解压即用，双击 `haoce-tool.exe`（**缺 `bin/ffmpeg.exe`**，原因见 `release/README.md`） |
| `release/haoce-tool-green.zip` | 绿色版完整压缩包（约 74 MB），下载解压后同上 |

> 各版本安装包统一放在 [Releases](https://github.com/Jellyu/haoce-tool/releases)：`v1.0` 与 `v1.1` 均提供源码包和绿色版压缩包。

> 绿色版里的 `config.json` 是空白模板，Cookie 需自行点「读取登录态」获取。

免安装桌面工具，按“当前书籍”自动完成好策 App 的朗读、摘抄、讨论三项评分任务，并内置 adb 自动翻页。书不写死：哈利波特、Animal Farm 或其他有 PDF 的好策书籍都走同一套流程。

| 功能 | 好策要求（每本书不同） | 工具做法 |
| --- | --- | --- |
| 朗读 | 数量 `tag_3_config`，每段不少于 `book_opt.word_3` 词 | 书内随机段落 → edge-tts → AMR-NB → 直传 H5 接口 |
| 摘抄 | 数量 `tag_6_config`，原文不少于 `book_opt.word_6` 词，见解不少于 `word_topic` 词 | 随机原文 + 自动生成见解 |
| 讨论 | 发帖 `user_topic` 篇，回复 `user_comment` 条，字数不小于 `word_topic` / `word_comment` | 按主题自动发帖，并回复其他同学的主题 |
| 自动翻页 | 阅读进度 | adb 读取页码节点、横向滑动、确认翻页，末页切下一章 |

任务数量和字数门槛全部来自 `/app/bookOne/detail/<book_id>`，不再固定为 30/15/2/10。

## 绿色版使用

1. 解压整个 `haoce-tool` 文件夹（`_internal`、`bin` 要一起，不能只拿 exe）；
2. 启动 MuMu，打开好策 App，登录并进入要做的书（阅读页或该书的任务页都可以）；
3. 双击 `haoce-tool.exe`；
4. 首次使用点「读取登录态」，工具会通过 `bin/adb.exe` 从 App 的 WebView 读取 `_UHAO`；
5. 点「读取当前书籍」，工具会从 App 的本地存储识别 `book_id`，读取详情并自动建段落库；如果还没读取过登录态，这一步会自动从设备补读；
6. 核对顶部书籍名、任务按钮上的数量（例如「朗读 30」「摘抄 15」「讨论 2+10」）；
7. 点「一键完成」或单项按钮补齐差额；
8. 想刷阅读进度时，在 App 打开阅读页，回到工具点「开始翻页」。

所有运行数据写在 exe 同级：`config.json`、`books/`、`work/`，卸载只需删除文件夹。

## 什么时候需要 MuMu 模拟器

只有 **3 个功能**要碰 adb / 模拟器，其余全是纯 HTTPS 请求：

| 功能 | 需要 MuMu | 实现 |
| --- | --- | --- |
| 读取登录态 | 是 | `adb root` 后读取 App WebView 的 Cookies 库，取 `_UHAO`（`core.py`） |
| 读取当前书籍 | 是 | `adb pull` 设备里的 `DCStorage` 库，解析出 `book_id` / `novel_id`（`books.py`） |
| 自动翻页 | 是 | `uiautomator dump` 读页码 + `input swipe` 横向翻页（`turner.py`） |
| 刷新状态 / 朗读 / 摘抄 / 讨论 | 否 | 直接请求 `appclient.haoce.com` |
| 建书籍库（下载 PDF / 提取正文） | 否 | 下载 CDN 的 PDF，本地 `pdftotext` 提取 |

几点说明：

1. **登录态和书籍 ID 是一次性的**。拿到后写进 `config.json`（`cookie`、`book_id`、`novel_id`），之后朗读 / 摘抄 / 讨论全程不碰 adb。严格说只有「自动翻页」每次都需要模拟器。
2. **书籍 ID 可以绕过 adb**：在书籍栏手动输入 `book_id` 点「加载 ID」即可。只是没有 `novel_id` 时，阅读器接口取文会退化成走 PDF。
3. **朗读不需要模拟器，但需要本地 ffmpeg**：edge-tts 生成的 mp3 要转成 AMR-NB 再上传，绿色版已内置 `bin/ffmpeg.exe`。

所以：**已经有 `cookie` 和 `book_id`、只想补任务的话，模拟器可以完全不开**。

## 换书 / 没有 PDF 的书

- **自动识别**：在 App 打开任意一本书的阅读页或任务页，点「读取当前书籍」。工具读取 `DCStorage` 里的 `_winExtras`，支持 `readerFull` 的 `detail.book_id`，也支持 `topicNew?book_id=...` 这类任务页 URL。
- **手动 ID**：在书籍栏输入 `book_id`，点「加载 ID」。ID 可以从 App 任务页 URL 或详情接口看到。
- **自动建库（三级取文）**：不用你上传，工具自己找正文，按顺序尝试——
  1. **好策阅读器接口**：用 `novel_id` 拉全部章节正文，和 App 里看到的完全一致（最优先，多数书走这条）；
  2. **好策 CDN 的 PDF**：详情接口 `book.book_pdf` 指向的 PDF，下载后用 `bin/pdftotext.exe` 提取，失败改用 pypdf；
  3. **Gutenberg 镜像**：前两条都拿不到时，按书名在公版库检索全文（只覆盖已进入公版的经典书）。
  
  三条都失败才会提示你手动导入。段落库写入 `books/<book_id>/paragraphs.json`。
- **导入文本（最后手段）**：如果工具三条路都没找到（冷门书、教材、非公版新书），点「导入文本」自己选 TXT、Markdown 或 PDF。TXT 建议段落之间空一行。这是唯一需要你提供文件的情况。
- **每本书独立**：段落库、去重记录、音频分别放在 `books/<book_id>/` 和 `work/<book_id>/`，换书不会互相污染。

## 界面按钮

- **读取当前书籍**：从模拟器识别当前书、切换配置、自动建库；
- **构建书籍库**：对当前书重新下载/提取 PDF，已有段落库时直接复用；
- **导入文本**：给当前书导入 TXT/Markdown/PDF 并重建段落库；
- **加载 ID**：按 `book_id` 切换书籍；
- **刷新状态**：读取服务器端讨论帖/回复/朗读/摘抄/报告计数；
- **读取登录态**：从 MuMu 设备抓取好策 WebView Cookie；
- **清除登录态**：清空本机保存的 Cookie、`book_id`、`novel_id`，并作废旧书的 targets/joined 缓存；**不会退出模拟器里好策 App 的登录**，换号时先清除再「读取登录态」即可；
- **一键完成 / 朗读 / 摘抄 / 讨论**：按当前书的目标补差额，目标为 0 的按钮会自动禁用；
- **停止**：停止当前批量任务或自动翻页；
- **自动翻页**：慢速（20–30 秒/页）、正常（14–22 秒/页）、快速（8–14 秒/页），带随机波动与阅读停顿；到最后页连续确认 3 次后自动左滑切下一章。

自动翻页要求 App 当前停留在阅读页；工具读取右下角 `当前页/总页数` 无障碍节点，识别不到页码时会提示并停止。

## 技术原理

### 1. 登录态：从设备 WebView 取 Cookie

好策阅读模块是远程 H5（`appclient.haoce.com`），鉴权只靠 WebView 里的 `_UHAO` Cookie（URL 编码 JSON：uid/name/school/openid/sign）。

- `adb root` 后将 `/data/data/app.haoce.com/app_webview/Default/Cookies` 拉到本地；
- 用 sqlite 查询 `host_key='appclient.haoce.com' and name='_UHAO'`；
- 写入 `config.json`，后续所有请求携带该 Cookie。

### 2. H5 API 逆向

从 `readerFull` 页面加载的 `haoce.js` 找到真实 API 根域 `https://appclient.haoce.com/`，请求头需带 `X-Display: json`、`X-Requested-With: ''` 和含 `uni-app Html5Plus/1.0` 的 UA。

| 用途 | 接口 |
| --- | --- |
| 书籍详情 / 任务门槛 | `POST /app/bookOne/detail/<book_id>` → `book.book_pdf`、`book_opt.word_3/5/6`、`tag_3_config/tag_6_config`、`user_topic/user_comment`、`word_topic/word_comment`、`bookJoin.*_cnt` |
| 任务计数 | `bookJoin.topic_cnt/comment_cnt/tag_3_cnt/tag_5_cnt/tag_6_cnt` |
| 讨论列表 | `POST /app/bookOne/topicList/<book_id>?pageno=N`（`tag_id=0`） |
| 发帖（讨论 tag=0 / 摘抄 tag=6） | `POST /book/topicAdd` |
| 回复 | `POST /book/commentAdd/<book_id>/<topic_id>` |
| 朗读上传 | `POST /book/topicAdd/tag3`（multipart，文件字段 `file`，`attr={"path","time","ext"}`） |

写操作对 `error==113（访问频率过快）` 自动等待 20 秒重试，普通请求间隔 2–5 秒。

### 3. 当前书籍识别

好策 App 是 DCloud uni-app，`_winExtras` 存在本地 SQLite：

```text
/data/data/app.haoce.com/databases/DCStorage
表名形如 DC_<id>_storage，行 key='_winExtras'
```

值可能是 `readerFull` 页面，也可能是 `topicNew?book_id=...` 任务页。工具同时解析 `detail.book_id` 和 `detail.url` 里的 `book_id`，所以不要求一定停在阅读页。若数据库里保留多条不同书的页面记录，按 `timestamp` 取最近访问的一条；停在书架、没有进入任何书时，读到的是上次进入的页面，可用「加载 ID」手动指定。

段落库、去重记录和音频都按 `book_id` 分目录存放，换书不会混用。

### 4. 书籍库：任意书 → 段落

1. 详情接口取 `book_pdf`，拼接 `https://cdn.haoce.com` 下载到 `books/<id>/book.pdf`；
2. 优先用 bundled `pdftotext.exe -enc UTF-8`（默认阅读顺序模式，保留段落空行），失败用 pypdf；
3. `paras.py` 归一化连字（ﬁ/ﬂ/ﬀ）、软连字符、跨行断词、页眉页码，按空行切块并去掉目录/页码噪声；
4. 过长段落按句号切到约 220 词（中文约 700 字），过短段落丢弃；
5. 语言检测：CJK 占比高判为中文，否则英文；朗读自动切换中/英音色；
6. 段落库缓存在 `books/<id>/paragraphs.json`，同一本书后续直接读取。

### 5. 长度适配：阈值小也能凑够数量

好策每本书的字数门槛不同（例如 50 词、80 词）。工具不是只从段落里“碰运气”：

- 先取落在理想区间的完整段落；
- 段落太长时，按句子边界裁出一段满足 `word_3/word_6` 的连续片段；
- 段落略短但已达到最低门槛时也保留；
- 去重同时记录“片段哈希”和“原段落哈希”，同一段不会反复用。

### 6. 朗读：TTS + AMR 转码

- `edge-tts` 调用微软 Edge 在线 TTS；英文 Aria/Jenny/Guy 轮换，中文 Xiaoxiao/Yunxi/Xiaoyi/Yunjian 轮换，失败自动重试；
- 带 `libopencore_amrnb` 的 ffmpeg 转 8kHz 单声道 12.2kbps AMR-NB；
- AMR 时长按帧长计算：`(字节数-6)/32×0.02` 秒；
- multipart 直接上传音频和文本，接口校验通过即计入朗读任务。

### 7. 摘抄 / 讨论：按书生成内容

- 见解、主题帖、回复都是通用模板，使用 `{q}`（金句）、`{who}`（人物/文中人物）、`{theme}`（主题）、`{book}`（书名）、`{author}`（作者）；
- 人物名从书中“人名 + 说话动词/所有格”统计，排除书名词和常见词；中文书使用“文中的人物”；
- 主题从书中关键词统计（友谊、勇气、权力、自由、欺骗、平等、劳动等），引用里出现主题词时优先用引用中的主题；
- 见解、帖子、回复按每本书的 `word_topic` / `word_comment` 自动补足长度；
- `work/<id>/state.json` 记录已用段落哈希、主题帖标题、已回复 topic_id，重复运行只补差额；
- 中文书自动输出中文见解/帖子/回复。

### 8. 自动翻页：adb + 无障碍页码

修复版 AutoX.js 的结论：好策阅读器是横向翻页，竖滑无效；本环境 WebView 对注入触摸处理很慢，像素截图不可靠，右下角页码节点才可靠。

桌面版用 adb 复刻：

1. `uiautomator dump` 读取 `text="当前页/总页数"` 和 `Chapter ...`；
2. `input swipe` 从 90% 宽度横滑到 10% 宽度（约 0.8 屏）；
3. 轮询页码，只认前进跳变并二次确认，20 秒未变化则重试，最多 3 次；
4. 页码到达末页时连续 3 轮确认，再额外左滑切换下一章；
5. 每页之间按所选速度随机等待，偶发额外阅读停顿；停止按钮随时中断。

`auto_turner/haoce_auto.js` 是原 AutoX.js 版本，作为备用脚本保留，桌面绿色版不再依赖它。

## 目录结构（绿色版）

```
haoce-tool/
├─ haoce-tool.exe        主程序
├─ README.md             本文件
├─ config.default.json   默认配置模板
├─ config.json           首次运行生成，保存 Cookie/adb/ffmpeg/当前书籍
├─ bin/
│  ├─ adb.exe            MuMu 自带 adb
│  ├─ AdbWinApi.dll
│  ├─ AdbWinUsbApi.dll
│  ├─ ffmpeg.exe         含 libopencore_amrnb，用于 AMR 转码
│  ├─ pdftotext.exe      PDF 文本提取
│  └─ lib*.dll           pdftotext 依赖
├─ books/<book_id>/
│  ├─ meta.json          当前书的标题/作者/目标/字数门槛/语言
│  ├─ book.pdf           详情接口下载的 PDF
│  ├─ book.txt           提取出的纯文本
│  └─ paragraphs.json    段落库
├─ work/<book_id>/
│  ├─ state.json         该书去重记录
│  └─ audio/             该书生成的 mp3/amr
├─ auto_turner/
│  └─ haoce_auto.js      AutoX.js 备用翻页脚本
└─ _internal/            PyInstaller 运行时（不可删）
```

## 配置说明

`config.json` 位于 exe 同级；首次启动自动生成。一般只需点「读取登录态」和「读取当前书籍」。

| 字段 | 含义 |
| --- | --- |
| `cookie` | 好策 `_UHAO`，点「读取登录态」自动更新 |
| `adb` | adb 路径，留空时自动使用 `bin/adb.exe` |
| `serial` | 模拟器序列号，默认 `127.0.0.1:16384`；连接不上时自动取第一个设备 |
| `book_id` / `novel_id` | 当前书籍，点「读取当前书籍」或「加载 ID」自动写入；0 表示未选择 |
| `ffmpeg` | ffmpeg 路径，留空时自动使用 `bin/ffmpeg.exe` |
| `pdftotext` | pdftotext 路径，留空时自动使用 `bin/pdftotext.exe` |

## 从源码运行 / 重新构建

```bat
pip install -r requirements.txt
python app.py
python books.py current          :: 只测试当前书籍识别
python books.py build 31900      :: 只测试某本书建库
python build_green.py            :: 生成同级目录 ..\haoce-tool-green 与 ..\haoce-tool-green.zip
```

源码文件：`app.py`（GUI）、`core.py`（任务编排）、`books.py`（当前书籍/下载/建库/导入）、`haoce_api.py`（H5 API）、`content.py`（通用内容生成）、`tts.py`（edge-tts）、`paras.py` + `textutil.py`（多语言段落/计数）、`turner.py`（adb 翻页）、`runtime.py`（打包路径/依赖探测）。

构建前先确认 `bin/pdftotext.exe` 与三个 `lib*.dll` 存在；`build_green.py` 会按 `config.json` 的 `adb` / `ffmpeg` → 环境变量 `ADB_PATH` / `FFMPEG_PATH` → `bin/ffmpeg.exe`、MuMu 默认路径的顺序查找 adb 与 ffmpeg，并把 pypdf 一并打进包。产物直接落在源码目录的同级：`../haoce-tool-green/`（exe 在根目录）和 `../haoce-tool-green.zip`。

自检：`haoce-tool.exe --selftest` 会在 exe 同级生成 `selftest.json`，检查 adb/ffmpeg/pdftotext、登录态、当前书籍、任务计数、TTS/AMR 和页码读取。

## 已验证结果

- 哈利波特（31907）：历史成绩 92.84；旧段落库首次运行自动迁移到 `books/31907/`。
- Animal Farm（31900）：详情接口 167 个段落，朗读候选 153 段、摘抄候选 146 段，英文见解/帖子/回复均达到 25 词门槛；只做本地建库与内容检查，未向未加入的书籍提交任务。
- 中文/英文 edge-tts + ffmpeg AMR 转码均通过。
- 绿色版实测：登录态读取、状态查询、页码读取与单页翻页通过。

## 版本与更新日志

### v1.1（当前）

- **新增「清除登录态」**：一键清空本机保存的 Cookie、`book_id`、`novel_id`，并作废该书的 targets/joined 缓存；只清本地登录态，模拟器里好策 App 的登录不会退出。换号时先清除再「读取登录态」，避免沿用上一个账号的任务目标。
- **账号识别**：顶部显示当前账号（优先显示学号，其次 UID）；读取登录态后如果检测到 UID 变化，会提示「账号已变更」，并自动清除书籍选择。
- **模拟器连接更稳**：找不到设备时自动 `adb connect` 常见 MuMu 端口（`16384` / `7555` / `5555` / `16416`）；没有在线设备时给出明确提示，不再拿死地址空等；`adb root` 后 25 秒未重新上线会提示重启 MuMu。

### v1.0

- 首个公开版本：朗读 / 摘抄 / 讨论自动补差额、自动建书籍库、adb 自动翻页、绿色版打包。

## 注意事项

- **风险自负**：本工具属于自动化/逆向操作，平台可能判定为违规，存在封号、限制、成绩作废或纪律处罚的风险。使用即表示你已知悉并自行承担全部后果，作者概不负责；
- 本工具只操作你自己的账号与课程任务，请遵守学校与平台的使用规定；
- 如果日志提示“缺少登录态”或“自动读取登录态失败”，先点「读取登录态」，并确认好策 App 已登录、adb root 可用；
- 未加入阅读任务的书（`bookJoin` 为空）不会提交，避免无效请求；
- 自动翻页是模拟真实滑动，不修改平台数据；翻页前请先打开阅读页；
- 写操作带 113 退避重试，仍建议不要高频连续运行；
- 分享绿色版前可删除 `config.json` 中的 `cookie`，让对方自行「读取登录态」；
- 不建议二次分发或用于商业用途，由此产生的一切纠纷与作者无关。

---

## ⚠️ 风险提示 / 免责声明

本工具通过逆向平台接口、模拟设备操作来批量完成任务，**属于平台可能禁止的自动化行为**。使用前请务必知悉：

- 可能被平台检测，导致**账号被封禁、限制、限流、成绩作废**，或收到学校 / 平台的**纪律处分与处罚**；
- 可能因接口变更、数据异常导致任务失败、重复提交或数据错乱；
- 个人账号信息（Cookie 等）存在泄露风险。

**是否使用、如何使用，完全由使用者自行判断并承担全部后果。作者不对任何封号、扣分、处罚、数据丢失或其他直接 / 间接损失负责。**

本项目仅做交流学习使用，请遵守学校规定、平台用户协议及当地法律法规，不得用于代刷、交易、出租或其他牟利行为。如果你不同意以上内容，请不要使用本工具。

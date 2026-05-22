# kaoyan-vocab-memory-tracker

考研英语遗忘词汇追踪器，用来长期整理你在华为平板手写记录的考研英语遗忘词。它把华为笔记导出的 PDF 或页面图片转成可校对 CSV，人工确认后合并到总词库，并通过网页展示复习优先级。

项目不会假装手写 OCR 一开始就完全可靠。蓝色英文单词、红色“正”字计数都可能识别不稳，所以自动结果只作为初稿，最终数据以人工校对为准。

## 项目结构

```text
kaoyan-vocab-memory-tracker/
├── raw_notes/              # 原始 .hinote / PDF / 图片存档
├── extracted/pages/        # 从 PDF 或图片整理出的页面图片
├── extracted/ocr/          # OCR 初稿与人工校对 CSV
├── data/                   # 最终词库、考研考频、更新日志
├── scripts/                # 导入、合并、校验脚本
├── web/                    # Vite + React 前端
└── .github/workflows/      # GitHub Pages 自动部署
```

## 为什么 .hinote 只做存档

华为笔记的 `.hinote` 属于私有格式，长期稳定解析成本高，也容易因为 App 更新而失效。因此本项目把 `.hinote` 只作为 `raw_notes/` 中的原始档案保存；稳定处理流程使用 PDF 或页面图片。推荐做法是在华为笔记中导出 PDF，或导出/截图为图片，然后放入 `raw_notes/`。

## 安装依赖

在项目根目录运行：

```bash
npm install
```

如果 Windows PowerShell 因执行策略拦截 `npm.ps1`，可以使用同等命令：

```bash
npm.cmd install
```

Python 脚本默认只依赖标准库。若要把 PDF 自动转换成页面图片，可以任选安装一个 PDF 渲染库：

```bash
python -m pip install pypdfium2
```

如果想尝试英文 OCR，可另外安装：

```bash
python -m pip install pillow pytesseract
```

`pytesseract` 还需要系统中安装 Tesseract OCR。没有 OCR 也可以使用本项目，因为人工校对模板可以空白生成。

## 访问方式

本项目保留本地使用模式，同时支持 GitHub Pages 公网访问。公网访问不要求设备连接同一个 Wi-Fi，只要华为平板、MacBook Air、Windows 笔记本或台式电脑能访问互联网，就可以打开同一个网站地址。

### 1. 本机访问

适合在电脑本机开发调试：

```bash
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

PowerShell 执行策略拦截时可用：

```bash
npm.cmd run dev
```

### 2. 同一 Wi-Fi / 局域网访问

适合电脑运行开发服务器，华为平板在同一 Wi-Fi 下访问：

```bash
npm run dev -- --host 0.0.0.0
```

PowerShell 执行策略拦截时可用：

```bash
npm.cmd run dev -- --host 0.0.0.0
```

查看电脑局域网 IP。Windows 可以运行：

```bash
ipconfig
```

假设电脑 IPv4 地址是：

```text
192.168.1.10
```

华为平板浏览器访问：

```text
http://192.168.1.10:5173
```

如果打不开，请检查电脑防火墙是否允许 Node.js 或 5173 端口的局域网访问。

### 3. 公网访问 / 不同网络访问

适合华为平板、MacBook Air、Windows 电脑不在同一个 Wi-Fi 下访问。使用 GitHub Pages 部署后，示例访问地址是：

```text
https://你的GitHub用户名.github.io/kaoyan-vocab-memory-tracker/
```

这个地址是公网网页地址，不依赖你的电脑是否开机，也不要求设备在同一局域网。只要能访问互联网，就可以用浏览器打开。

## GitHub Pages 部署步骤

本项目已经包含 GitHub Actions 工作流：

```text
.github/workflows/deploy-pages.yml
```

部署步骤：

1. 在 GitHub 创建仓库，推荐仓库名保持为 `kaoyan-vocab-memory-tracker`。
2. 把当前项目推送到 GitHub。
3. 在 GitHub 仓库进入 `Settings -> Pages`。
4. 在 Pages 的 Build and deployment 里选择 `GitHub Actions` 作为部署来源。
5. push 到 `main` 分支后，GitHub Actions 会自动执行 `npm ci` 和 `npm run build`。
6. 构建产物会从 `web/dist` 上传并部署到 GitHub Pages。
7. 构建完成后，在 `Settings -> Pages` 查看网站地址。
8. 在华为平板、MacBook Air、Windows 电脑浏览器中打开这个地址。
9. 华为平板浏览器菜单中可以选择添加到桌面，作为 PWA 快捷入口。

项目站点通常部署在仓库名子路径下。如果仓库名是 `kaoyan-vocab-memory-tracker`，GitHub Pages 路径通常是：

```text
/kaoyan-vocab-memory-tracker/
```

工作流构建时会自动设置：

```text
VITE_BASE_PATH=/${{ github.event.repository.name }}/
```

所以资源路径会按仓库名生成。手动构建 GitHub Pages 版本时，也可以显式设置：

```bash
VITE_BASE_PATH=/kaoyan-vocab-memory-tracker/ npm run build
```

Windows PowerShell 可用：

```powershell
$env:VITE_BASE_PATH="/kaoyan-vocab-memory-tracker/"
npm.cmd run build
```

如果页面空白，优先检查 Vite `base` 路径是否正确。如果资源 404，优先检查仓库名和 `VITE_BASE_PATH` 是否一致。当前 `web/vite.config.js` 默认本地使用 `base: "./"`，GitHub Actions 构建时使用仓库名子路径。

## 构建与预览

本地构建：

```bash
npm run build
```

本地预览构建结果：

```bash
npm run preview
```

构建结果在：

```text
web/dist/
```

`web/vite.config.js` 会在构建时把 `data/*.json` 复制到 `web/dist/data/`，因此 GitHub Pages 可以直接读取词库数据。

## 数据处理流程

1. 把华为笔记导出的 PDF 或页面图片放进 `raw_notes/`。
2. 运行导入脚本，将 PDF 转成页面图片，并生成校对 CSV：

```bash
python scripts/import_pdf.py
```

3. 打开 `extracted/ocr/review_template.csv`，人工校对每一行：

```text
file,page,line_index,word,raw_count_mark,detected_count,corrected_count,confidence,notes
```

4. `corrected_count` 是最终合并依据。红色“正”字计数请手动换算：一个完整“正”字 = 5 次，每一笔 = 1 次。
5. 合并人工校对后的 CSV：

```bash
python scripts/merge_vocab.py --csv extracted/ocr/review_template.csv
```

6. 校验数据：

```bash
python scripts/validate_data.py
```

## 手动生成空白校对表

如果 OCR 不可用，或者你想直接手动录入，可以生成空白模板：

```bash
python scripts/export_template.py --rows 40 --output extracted/ocr/review_template.csv
```

每页大约 40 个单词，可以按页多次生成或复制行。

## 公网访问与数据更新的关系

网页部署后，华为平板可以随时访问当前已发布的数据。新的 PDF 仍然需要在电脑端处理：

1. 把新的 PDF 或图片放入 `raw_notes/`。
2. 运行 `python scripts/import_pdf.py`。
3. 人工校对 `extracted/ocr/review_template.csv`。
4. 运行 `python scripts/merge_vocab.py --csv extracted/ocr/review_template.csv`。
5. 运行 `python scripts/validate_data.py`。
6. `git commit` 修改后的数据和代码。
7. `git push` 到 `main`。
8. GitHub Actions 自动重新部署。
9. 平板刷新网页后看到更新后的词汇表。

平板端暂时不负责直接上传 PDF 和处理 OCR。这样可以避免把浏览器端做得过重，也能保留人工校对流程。

## 维护考研考频

考研考频只从 `data/exam_frequency.json` 读取。不要凭感觉把词标成高频；如果没有可靠来源，就保持未标注。

格式示例：

```json
{
  "acquire": {
    "score": 5,
    "label": "超高频",
    "source": "demo"
  }
}
```

没有考频数据的词会自动显示为：

```json
{
  "exam_frequency": 0,
  "exam_frequency_label": "未标注"
}
```

## 维护中文释义和易混词

最终词库在 `data/vocab.json`。每个词可以维护：

- `chinese`：中文释义
- `similar_words`：易混词、中文含义、区别说明
- `examples`：英文例句和中文翻译

网页默认不展示中文释义、易混词和例句。点击单词行后，右侧详情区才会展开这些内容。

## PWA 说明

`web/public/manifest.json` 已提供基础 PWA 信息，方便在华为平板浏览器中添加到桌面。当前 PWA 只是桌面快捷入口和独立窗口显示，不等于真正离线同步，也不会在平板端自动处理 PDF 或 OCR。

## 隐私说明

GitHub Pages 是网页部署，不是私密数据库。如果仓库或 Pages 站点是公开的，`data/vocab.json` 中的词汇数据也可能被别人访问。

不要在 `vocab.json` 里写个人隐私、账号、密码、联系方式等内容。如果你只想自己使用，可以选择：

- 本地运行；
- 使用私有仓库和支持私有 Pages 的 GitHub 计划；
- 后续改成需要登录的部署平台。

当前版本默认做成纯静态网页，不做登录系统，避免项目复杂化。

## 默认排序规则

网页默认综合排序：

```text
score = forget_count * 10 + exam_frequency * 3
```

如果分数相同：

1. `forget_count` 更高的在前；
2. `exam_frequency` 更高的在前；
3. `last_seen` 更新的在前；
4. 最后按 `word` 字母序排序。

## 注意事项

- 不要把低置信度 OCR 当成最终数据。
- 不要凭空生成“真实考研考频”。
- `raw_notes/` 默认被 `.gitignore` 忽略，适合保存个人原始笔记。
- 示例数据中的考频来源标为 `demo`，只用于演示结构和界面。

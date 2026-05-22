# AGENTS.md

本项目是一个个人长期维护的考研英语遗忘词汇追踪器。后续维护时请遵守以下规则。

## 核心原则

1. 不要伪造 OCR 结果。自动识别只能作为初稿，必须保留 `confidence`，低置信度内容不能直接进入最终词库。
2. 不要伪造考研考频。考频只允许来自 `data/exam_frequency.json`；未知词统一使用 `exam_frequency = 0` 和 `exam_frequency_label = "未标注"`。
3. 不要删除 `raw_notes/` 中的原始文件。`.hinote`、PDF、图片都可能是重要原始档案。
4. `.hinote` 只做原始存档，不要求直接解析；稳定输入以 PDF 或页面图片为主。
5. 所有自动识别结果必须能进入人工校对 CSV，由用户确认后再合并。
6. 代码保持简单、清楚、少依赖，优先适合个人长期维护。

## 数据与脚本

1. `scripts/import_pdf.py` 只负责转换页面图片和生成校对初稿，不应把低置信度 OCR 直接写入 `data/vocab.json`。
2. `scripts/merge_vocab.py` 合并时优先使用 `corrected_count`。如果 `corrected_count` 为空，只有在 `detected_count` 置信度很高且日志明确标注时才允许合并。
3. `scripts/validate_data.py` 修改后应能检查 `data/vocab.json`、`data/exam_frequency.json` 和基础字段完整性。
4. `README.md` 中出现的命令必须能在项目根目录实际执行。

## 前端

1. 使用 Vite + React，避免引入过重依赖。
2. 设计优先适配横屏笔记本、台式电脑、横屏平板；窄屏可用即可。
3. 英文单词显示使用接近试卷阅读文本的衬线字体，如 Times New Roman、Georgia 或系统 serif。
4. 默认隐藏中文释义、易混词、区别和例句，用户点击词条后再显示详情。
5. 日用/夜用模式必须用 CSS variables 实现，并保持足够可读性。
6. 夜用模式不要使用纯黑背景；日用模式要保持清爽、层次清楚。
7. 修改后至少运行：

```bash
python scripts/validate_data.py
npm run build
```

## 原始文件

`raw_notes/` 是原始笔记存档区。自动脚本可以读取，但不应移动、重命名或删除其中的文件。

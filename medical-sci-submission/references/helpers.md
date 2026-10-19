# 工具接口

脚本仅用 Python 标准库；从本技能目录执行下例，用环境配置的真实 Python 替换 `python`。每个命令支持 `--help`。过程记录由调用者保存，不写进干净材料目录，不覆盖已有记录。

```text
python scripts/submission_guard.py snapshot SOURCE.docx
python scripts/submission_guard.py compare BASELINE.json SOURCE.docx ADAPTED.docx
python scripts/submission_guard.py assess RECORD.json
python scripts/submission_guard.py package DELIVERABLE_DIR ALLOWLIST.json NEW_PACKAGE.zip
```

输出 UTF-8 JSON 到 stdout。snapshot 的 JSON 原样保存为 BASELINE；含原件 sha256、Word XML story 的有序引用（完整 citationItems、citationID）、bibliography JSON 与标准化缓存、原始 citation_displays。引用显示不参与身份比较，数字/作者年制均接受。段落/run 拆分和通常的引号/横线/空白变化不影响 bibliography 检查。本文缓存不验证科学正确性；字段模式不支持、JSON 损坏、简单/嵌套 Zotero 字段、字段结构不完整均报错，不声称部分通过。compare 检查原件 hash 与字段语义，不能证明正文数值/版面保持。

compare 通过退出 0、检测到破坏退出 1；assess 有缺口退出 1、pending_author 退出 0；解析/路径/不支持错误退出 2。package 创建新 ZIP 并输出文件清单；绝不覆盖已有 ZIP。所有检查都不读写 Zotero 库。

RECORD 的实际结构：

```json
{
  "facts": [
    {"name": "ethics", "required": true, "value": "supplied statement",
     "source": "source document and exact locator",
     "confirmation": {"by": "confirming author", "evidence": "actual response locator"}}
  ],
  "requirements": [
    {"name": "article-type rule", "url": "https://example.org/official-guide",
     "access_date": "2026-10-19", "provenance": "official",
     "verification": "current", "resolved": true}
  ],
  "conflicts": [],
  "checks": {"preservation": "pass", "visual": "pass", "word_refresh": "pending"}
}
```

这是结构示例，不是可套入稿件的声明。facts 必须枚举本稿所有适用必需事实，required=false 的真实不适用理由另存记录。value 可为字符串、数字或布尔：有来源和实际确认的 false（如无利益冲突）/0（如零资助）均为有效值；缺失、null、空白字符串或空容器产生缺口。confirmation 不能只写 true。事实来源/确认必须由实际材料和作者回复支撑；模型不得自己制造。requirements 的 verification 可为 current（实际在线核验）、supplied_official（作者提供的官方指南，注明日期/局限）或 unavailable（失败/待核）；后者产生缺口。`access_date` 填真实访问日期；指南版本/原文定位保存在配套要求表。`resolved` 表示该条已满足且有证据，不是仅取得网页。实际使用须包含 general、article-type 及适用 reporting 的要求，示例不是完整清单。

word_refresh 仅在源稿确无原生引用字段且本次不改变引用集成时可 not_applicable；否则 pending/pass/fail 取实际验收。对字段保护工具不能覆盖的合法引用样式变更保留 compare 失败及独立的字段/文献表核查和作者 Refresh 证据，不伪造 pass。记录工具不会验证这些外部事实，也不能授予就绪状态。

ALLOWLIST 是 JSON 数组：`[{"path":"adapted.docx","kind":"manuscript"}]`。path 必须为交付目录内相对路径。kind 仅接受 manuscript、title_page、statements、cover_letter、checklist、figure、attachment、changes、requirements、pending。每项必须实际核实为投稿材料，attachment 不能借作隐私文件通道。脚本拒绝越界、符号链接、过程/隐私目录、非材料扩展名和重复条目，但不是内容隐私扫描器。

流水线辅助工具位于 `medpaper-pipeline/scripts/submission_state.py`：

```text
python scripts/submission_state.py PROJECT.md
python scripts/submission_state.py PROJECT.md --changed-stage 11
```

仅输出迁移后文本，不覆盖 PROJECT。先确保第 12 行存在（按 pipeline 约定迁移），再补第 13 行“未开始”；影响主稿的 0–11 步变化使已存在的 12/13 需返工，12 步变化使 13 需返工，13 的常规排版不修改上游。`--unaffected-main` 用于经实际判断确不影响主稿/引用的修改；其他下游科学状态仍由 pipeline 依赖关系管理。脚本从不设置“已确认”。

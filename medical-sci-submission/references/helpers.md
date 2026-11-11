# 工具接口

脚本仅用 Python 标准库；从本技能目录执行下例，用环境配置的真实 Python 替换 `python`。每个命令支持 `--help`。过程记录由调用者保存，不写进干净材料目录，不覆盖已有记录。

```text
python scripts/submission_guard.py snapshot SOURCE.docx
python scripts/submission_guard.py compare BASELINE.json SOURCE.docx ADAPTED.docx
python scripts/submission_guard.py assess RECORD.json
python scripts/submission_guard.py titles TITLE_CHECK.json DELIVERABLE_DIR ALLOWLIST.json
python scripts/submission_guard.py package DELIVERABLE_DIR ALLOWLIST.json NEW_PACKAGE.zip
```

输出 UTF-8 JSON 到 stdout。snapshot 的 JSON 原样保存为 BASELINE；含原件 sha256、Word XML story 的有序引用（完整 citationItems、citationID）、bibliography JSON 与标准化缓存、原始 citation_displays。引用显示不参与身份比较，数字/作者年制均接受。段落/run 拆分和通常的引号/横线/空白变化不影响 bibliography 检查。本文缓存不验证科学正确性；字段模式不支持、JSON 损坏、简单/嵌套 Zotero 字段、字段结构不完整均报错。影响字段的修订祖先（删除/移出/插入/移入）也报错，覆盖 begin/separate/end、拆分指令和缓存，不依赖修订子树是否单独含有 ZOTERO 字样；不声称部分通过。compare 检查原件 hash 与字段语义，不能证明正文数值/版面保持。

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

这是结构示例，不是可套入稿件的声明。facts 必须枚举本稿所有适用必需事实，required=false 的真实不适用理由另存记录。value 可为字符串、数字或布尔：有来源和实际确认的 false（如无利益冲突）/0（如零资助）均为有效值；缺失、null、空白字符串或空容器产生缺口。source、confirmation.by/evidence 须为非空白文字定位，confirmation 不能只写 true。事实来源/确认必须由实际材料和作者回复支撑；模型不得自己制造。requirements 的 verification 可为 current（实际在线核验）、supplied_official（作者提供的官方指南，注明日期/局限）或 unavailable（失败/待核）；后者产生缺口。url 须为有合法主机名的 HTTP(S) URL，空主机、空白和错误端口均形成具体 url 缺口；不进行联网认证。`access_date` 填真实访问日期；指南版本/原文定位保存在配套要求表。`resolved` 表示该条已满足且有证据，不是仅取得网页。实际使用须包含 general、article-type 及适用 reporting 的要求，示例不是完整清单。

word_refresh 仅在源稿确无原生引用字段且本次不改变引用集成时可 not_applicable；否则 pending/pass/fail 取实际验收。对字段保护工具不能覆盖的合法引用样式变更保留 compare 失败及独立的字段/文献表核查和作者 Refresh 证据，不伪造 pass。记录工具不会验证这些外部事实，也不能授予就绪状态。

ALLOWLIST 是 JSON 数组：`[{"path":"adapted.docx","kind":"manuscript"}]`。path 必须为交付目录内相对路径。kind 仅接受 manuscript、title_page、statements、cover_letter、checklist、figure、attachment、changes、requirements、pending。每项必须实际核实为投稿材料，attachment 不能借作隐私文件通道。脚本拒绝越界、符号链接、过程/隐私目录、非材料扩展名和重复条目，但不是内容隐私扫描器。

## 题名的独立机械检查

`titles`读取实际交付文件，不写入文件、不联网、不改Zotero。返回`ok`、`draft/pending_author`、具体`gaps`、登记标题及实际位置的计数、已读文件SHA256。通过退出0，有未决项退出1，路径/解析/不支持错误退出2；无论哪种结果都不授予投稿或题名批准。源稿保护仍独立运行snapshot/compare，普通assess不能代替本检查。

TITLE_CHECK示例（合成数据，不代表真实期刊核验或作者选择）：

```json
{
  "original_title": "Retinal imaging in diabetes: a retrospective study",
  "full_title": "Retinal imaging in diabetes: a retrospective study",
  "decision": {
    "mode": "retain",
    "reason": "原标题与实际研究设计、主要证据及适用要求相符，证据定位另存审阅记录"
  },
  "requirements": {
    "verification": "current",
    "url": "https://example.org/author-guide",
    "access_date": "2026-11-12",
    "locator": "本例是合成条款，实际运行必须改为已读取的官方条款定位",
    "full_limits": {"max_words": 15, "max_characters": 100},
    "short_required": false
  },
  "targets": [
    {"path": "adapted.docx", "role": "full", "paragraph": 1},
    {"path": "title-page.docx", "role": "full", "paragraph": 1},
    {"path": "letter.md", "role": "full", "paragraph": 2,
      "prefix": "We submit “", "suffix": "”."}
  ]
}
```

- ALLOWLIST与打包使用同一清单，不为运行检查而另造缺少文件的精简清单；所有kind为manuscript/title_page/cover_letter的实际文件须有可见完整标题位置。没有要求的文件不新增。不能把只含元数据的位置当作可见标题位置。
- 支持DOCX指定story中的一基`w:p`序号（包括表内段落，默认`word/document.xml`；还支持`word/headerN.xml`/`word/footerN.xml`），或UTF-8 MD/TXT按空行分隔的一基段落。信中嵌入题名用prefix/suffix声明上下文；比较指定段落，不在全文搜索一个匹配就放行。确实存储论文题名的DOCX元数据可另给`location: metadata_title`，不指定paragraph。
- 如需短标题，增加`short_title`、`short_limits`（位于requirements）、对应`role: short`的实际位置。短标题是否必需未知时用`short_required: null`并保持待核。仅给出短标题字符串而未定位实际文件也不能通过。
- `full_limits/short_limits`的max_words、max_characters是正整数或null。null仅在实际已核实无明文限制时使用；未知规则用unavailable和缺口表示，不能拿null掩盖未核查。默认空白分词（连字符词为一个词），字符按Unicode码位且含空格；也检查实际位置的标题片段，防止输入中删空格后假称符合限制。期刊另有算法时须额外核算、保存证据，当前脚本不假装覆盖不同算法。
- 保留原标题时mode=retain并填写理由，完整题名必须与原标题相符。新题名选择使用author_selected或delegated，填写真实by/evidence来源；推荐本身不算选择。候选、中英语义与科学依据另存审阅记录，不由本脚本判断。`supplied_official`同原接口记录版本/来源及未在线核实的局限，unavailable产生待核项。
- 不支持的文件类型、无法定位的字段/段落和含未解决修订的题名须如实记录失败；必要时用适用文档工具补做有定位的人工检查，保留原失败和独立证据，不能修改脚本或重写输入伪造PASS。PDF等导出物还须核对实际渲染题名；脚本没有PDF题名解析能力。
- 此检查仅覆盖显式声明的位置和规则、记录完整性；仍须通读其他标题出现位置、核对稿件科学范围、实际作者选择及当前官方条款。过程输入/回执不放进干净投稿包。

## 流水线状态辅助

流水线辅助工具位于 `medpaper-pipeline/scripts/submission_state.py`：

```text
python scripts/submission_state.py PROJECT.md
python scripts/submission_state.py PROJECT.md --changed-stage 11
```

仅输出迁移后文本，不覆盖 PROJECT。先确保第 12 行存在（按 pipeline 约定迁移），再补第 13 行“未开始”；影响主稿的 0–11 步变化使已存在的 12/13 需返工，12 步变化使 13 需返工，13 的常规排版不修改上游。`--unaffected-main` 用于经实际判断确不影响主稿/引用的修改；其他下游科学状态仍由 pipeline 依赖关系管理。脚本从不设置“已确认”。

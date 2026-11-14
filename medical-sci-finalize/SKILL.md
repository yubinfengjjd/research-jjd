---
name: medical-sci-finalize
description: Use when a complete medical SCI manuscript needs final Word assembly and whole-manuscript English polishing or conservative removal of defensive writing, after Methods, Results, legends, Introduction, Discussion and Abstract are complete. Requires the installed anti-defensive-writing skill. Not for individual section drafting, research planning, or generating new results.
---

# medical-sci-finalize

流水线第 11 步，一个技能两个阶段：组装主稿与补充材料 Word；随后对全部英文作证据保留的结构润色，同步对应中文和已有双语稿，再重新组装。不用于单个章节写作、研究计划、补做分析或重绘图表。

## 跨章节定位衔接

起草或结构修订前复用[跨章节贡献与证据定位](../medpaper-pipeline/references/positioning.md)规定的唯一记录；已有作者决定沿用。只补实际缺失的定位与证据关系，不复制新规则或以固定句式制造主张。

## 必需依赖：anti-defensive-writing

**REQUIRED SUB-SKILL：必须使用 `anti-defensive-writing`。** 每次使用本技能时，先读取同一技能根目录下的 [anti-defensive-writing/SKILL.md](../anti-defensive-writing/SKILL.md)，再读取本技能的医学适配与结构审查规则；两者均读完后，在医学证据边界内应用依赖。独立技能缺失、链接失效或不可读时，报告缺失路径并停止本技能；不得仅靠本技能内的静态摘录继续，也不得宣称已经使用依赖。安装须在独立维护任务中完成，稿件流程保持离线。

依赖负责去防御性写作的叙事与语言审查；[polish-rules.md](references/polish-rules.md) 的证据保留和医学适配规则同时适用。冲突时保留数据、已定评价口径、不利结果、必要不确定性和结论相关局限，不执行上游规则中会隐藏证据、改变评价维度或将不利结果改称合理权衡的部分。允许有证据的结构重组和重复限定合并。

在 `修改记录.md` 中记录实际读取的依赖路径、版本/提交号（如 `.source.json` 提供）与 `SKILL.md` 的 SHA256，以及实际应用或因医学证据边界未采用的规则。脚本不能代替这一步审查。

## 入口与硬门槛

收到外部审查意见时，先执行 [润色规则的版本绑定与处置](references/polish-rules.md#审查意见的版本绑定与处置)，区分旧稿缺陷与当前残留后再编辑。

先读 [当前润色规则](references/polish-rules.md) 与 [结构审查契约](references/structural-review.md)；[原始要求与确认选择](references/original-finalize-prompt.md) 仅保留历史来源。确认项目根、版本及阶段；已有明确指令直接执行，不重复访谈。仅有完整的 Methods、Results、图注、Introduction、Discussion、Abstract 时开始；缺任一类停止并列缺项。“完整成稿”和“作者已确认”分开：保留 PROJECT.md 中待确认状态，不能把文件存在或脚本通过当作作者同意。读取口径表、作者决定、冲突台账，沿用所有未决事项。

全程本地离线，不联网，不派子代理，不调用 ARS 流水线或 humanizer。`anti-defensive-writing` 是须实际读取并应用的本地依赖；ARS 与 humanizer 仅使用 references 中的静态摘录。所有 Python 命令用 `python -X utf8` 运行（PATH 上的 `python` 若是 Windows 商店空壳，改用真实解释器的完整路径）。开发/盲测时先复制获准材料到隔离工作目录；绝不把开发操作指向原项目或已安装技能目录。

## 阶段一：组装

阅读 [组装规则](references/assembly-rules.md) 和 [Word 版式](references/journal-style.md)。运行 `scripts/build_manuscript.py --project-root <项目根> --kind both --version <N>`。没有 PROJECT.md 时另传 `--output-dir`；有则固定输出 `05_final/`。

运行 `scripts/check_finalize.py --project-root <项目根> --version <N> --report <过程目录>/assembly_check.json`。版本按项目当前产物递增；开发仅使用获准的隔离副本。默认单节 A4 纵向、Arial 12 pt 单倍行距，无行号及页眉页脚。主图表放在首次正文引用所属（子）节末、下一个同级或更高标题前；同节按首次引用顺序混排。图片满宽 14.6 cm 自然流式；表键优先取 Markdown 首行的显示编号，并核对同名 .source.json 的 presentation_trim.display_number；无显示标题才回退文件名，重复编号报错。同一表号可含多个 Markdown 表格区块，共用一次表题表注，区块间一个空段，各块独立布局与记录（含区块序号、N blocks）；单区块保持原输出。8→7.5→7→6.5 pt，地板仍超词宽时允许词内断行并 WARN。全部标题用 Normal 段落加直接格式，无 Heading/Title 样式及大纲级别；一级节与资产块间按规则留一个 Arial 12 pt 空段落，详见 Word 版式。

主稿不输出 References，正文引用标识原样保留。过程目录同时生成 `表格断行清单.md`（逐表字号、断词列与样例）及 `参考文献候选清单.md`（首次出现顺序、已有字段、缺口）；书目缺失与未核验只进入候选清单，不进入成品 WARN。必须实际打开两份 DOCX；可用本机 Word 或渲染器检查自然分页、图片、跨页表、公式及标题块。不得只凭 ZIP/XML 可解析宣称视觉验收通过。ERROR 阻断发布；WARN 逐条登记；组装检查 JSON 的 `style` 附全稿及逐节风格统计，含主/附图注与表注；直接复用 medpaper-pipeline 的检查函数，缺少依赖时明确报错。统计只读，不在组装时改写源稿。组装检查对列数 >10 或存在 >50 字符单元格的表追加发表形态 WARN，列出表号与列名（长单元格另报行号与长度；表注除外），提示按设计规则精简。此项只读提示，不改源表、组装、排版、原有 ERROR 或退出码语义。候选清单不证明文献已经核验，也不代表投稿就绪。无需改上游即可修复的排版问题在组装脚本中修复。

## 阶段二：润色、归档、重新组装

确认已加载必需依赖 `anti-defensive-writing`，并按其叙事、语言和交稿前自查规则开展审查；结合本地医学适配，阅读 [润色规则](references/polish-rules.md) 与 [判断示例](references/examples.md)。润色由当前代理逐段完成，脚本只执行确定性检查与归档覆盖，不会自动润色或自动删句。

1. 保存 `04_manuscript` 改前快照与 SHA256，建立保持相对路径的候选树。审阅全部 EN 正文、Abstract/Keywords/Highlights、主附图注及表题表注；结构调整后同步对应 ZH 和已有 EN_ZH。数据、源表、02_figures 和 03_outline 不变。
2. 通读全文，核对关键事实、限定、CI 归属与补充图注/表注/核查说明。按 [结构审查契约](references/structural-review.md) 建立绑定改前及候选内容的 `review.json`；精确原文用于溯源，不要求限定永远保持独立原句。允许同节合并、去重和重排，分析范围与引用支持关系不变。
3. 逐个解决实质叙事问题，记录真实修改或具体保留理由。逐块来源/候选位置、事实及双语覆盖记入 `review.json`，可读修改记录另存 Markdown；按结构契约生成绑定 review 哈希和全部叙事问题 ID 的 `changes.json`，不用旧严格模式的逐段列表。未知局部范围保留原文并继续独立编辑，作者动作按共同问题归组；核心矛盾阻断受影响交付。交叉核对审计可按 polish-rules 使用 `crosscheck.json` 与记录呈现脚本，不能用它代替结构审查。
4. 默认运行 `scripts/check_finalize.py --edit-mode structural --review-json <review.json> --before <改前04_manuscript> --after <候选树> --changes <changes.json> --report <report.json>`。ERROR 修复，WARN 逐条解释。词数变化只触发信息覆盖复核；不以 ±10% 或通用最低词数拒绝结构编辑。作者/期刊明确限制仍须满足或报告真实冲突；项目限额登记在 PROJECT 同级 `writing-limits.json`（小写节名 → `min`/`max`），具体口径见 [pipeline 项目约定](../medpaper-pipeline/references/project-layout.md)。
5. 按结构契约写入 `decisions.json`，与 `changes.json` 使用相同的 review 哈希及问题 ID 清单格式，与人读的 `作者裁决清单.md` 分开；旧 Markdown decisions 参数仅用于严格兼容模式。核验通过后在同一命令追加 `--apply --project-root <根> --decisions <decisions.json>`，归档每个变化语言组的全部现有 EN/ZH/EN_ZH 原件（含未变同组稿）后覆盖变化文件，失败回滚。记录留在 `_process/Finalize/<日期>_polish_v<N>/`，不跳过归档。
6. 依次运行 `medpaper-pipeline/scripts/consistency_check.py <项目根>`，然后逐节运行 `manuscript_check.py <methods|legends|results|introduction|discussion> <EN稿> --zh <ZH稿>`，Results 依赖按参数传入。ERROR 修复，WARN 说明；另人工核对已有 EN_ZH 的信息覆盖与摘要证据。检查通过不证明语义等价。
7. 递增版本重新组装并实际查看两份 Word；更新 PROJECT 第 11 步为“已润色，待作者验收”，记录路径/版本。只有作者明确验收才标已确认；新裁决追加而不改旧决定，候选建议不记为已决定。

兼容严格模式继续支持不带 `--edit-mode structural` 的 `--before/--after --protected-json <protected.json> --changes` 调用，按旧规则检查精确保护字符串及相对篇幅。只在明确要求逐句保护的任务使用，不作为结构编辑默认门槛，也不通过削弱保护项让旧检查放行。

机械检查不证明事实未变、临床有效性、语义等价或期刊特定投稿合规；逐段证据核对、所有不利结果及局限保留、视觉验收与作者裁决均需独立完成。

## 交付前检查

- [ ] 散文分号链 0 处（同句 ≥2 个散文分号为 ERROR，结构性分号豁免）；目标平均 18–28 词/句，一般 ≤45 词、硬上限 60 词，>45 词占比 >10% 为 WARN；无连续 ≥3 个 <8 词短句的电报体连跑；WARN 已逐条说明。连接词按逻辑需要使用，不连续三句以上以同一个连接词或短语开头；按 journal-style 的「句长、分号与衔接」复核。

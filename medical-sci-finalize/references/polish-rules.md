# 全稿润色：证据保留的结构编辑

## 优先级与范围

医学稿诚实性、作者决定、口径表和实际证据优先于任何风格规则。全文读完再逐段检查语法、句法、指代、时态、学术正式度和衔接；保留准确而自然的原句。覆盖正文四节、摘要/Keywords/Highlights、主图及附图图注、主表与附表标题/表注。默认允许同节合并、去重、重排，英文重构后同步对应 ZH 和已有 EN_ZH 并归档原件。不新增研究发现、无据解释、比较、临床获益或证据外推；引用支持关系和项目软配额保留，不为填数扩充。

数字、单位、统计口径、引文标识、图表编号、术语和公式的科学含义不变。默认按 [结构审查契约](structural-review.md) 保存来源/候选绑定、论断与事实归属、变化块、双语覆盖及叙事问题处理；精确原句作为溯源而非不可合并的保护单元。旧 `protected.json` 精确字符串机制只用于显式严格兼容模式。不得把限定从某一分析移给另一分析，数字相同也不等于科学口径相同。

## 执行步骤（对应入口阶段二第 2/3 步）

**第 2 步：建立论断/事实记录并实际交叉核对。** 在写候选稿之前，给关键限定和关键数字各建核对项 ID，保留文件/段落或标题位置、精确原句、分析对象与口径。数字项同时记录单位、分母/样本范围、统计量及其 CI 归属；关键数字包括样本量、效应量、性能值、CI、阈值、重复次数等。结构模式将这些信息绑定到 `review.json` 的来源和候选位置，限定可合并但其支配范围不能改变；严格兼容模式的 `protected.json` 仍仅放原文精确字符串，归属、证据与裁决另记。

逐项阅读相关上下文，将这些限定和数字与补充图注、主/附表标题及表注、Methods/Results/Introduction/Discussion/Abstract/Legends 各节核查说明交叉核对。材料在获准本地范围内读取，中文核查说明可作证据；与编辑对应的双语稿需同步，既有核查事实及未决状态保留。不能只查主图图注或只比原稿与清稿的词频；记录实际查阅的文件和定位，缺失或未能读取的材料也登记。相同数字但队列、分析层级、种子、CI 所属运行等不同，不判为一致，也不互相替换。

每项判为“一致”“差异有据”“来源待查”或“未执行”。差异有明确来源时摘录双方证据、说明分析口径是否不同；仅跨文档有据仍不授权本轮改事实。材料中找不到证据支持的差异，或证据相互冲突、归属无法确定，列为“来源待查”作者裁决项。某限定/数字只在一份材料出现、补充材料未重复、核查说明无对应记录、原始证据不可用或未覆盖时，写明“无法证明缺失”，不能据此断言正文漏写或补充材料错误；保留该处原文，不擅自补限定、改数字或删句；继续完成独立可判定的编辑。真正需作者动作按共同缺口归组，核心事实矛盾阻断受影响交付。

**第 3 步：写候选并记录执行结果。** 通读全节/全稿的主线、重复、比例失衡、段落依赖与结论强度；每个实质问题落实改文，或给出具体证据保留理由。仅降低词频、统计字数或填写“已复核”不算解决问题。逐段润色时核对保护项和第 2 步的分析归属，改后再检查限定的否定范围、数字及 CI 是否仍归属于原分析。将实际覆盖文件、未覆盖原因、各类结果数量和逐项证据写入 `修改记录.md` 的“交叉核对执行与结果”（格式见下）。全部审计 ID 保留于 `crosscheck.json` 和附录；“来源待查”按证据缺口分组，作者清单只列本轮真正需要动作的组，不能将单一材料出现/未复述机械升级为作者问题。未改段也要进入核对覆盖，变化位置写入 review 和可读修改记录；结构模式的 changes 只绑定 review 与叙事问题 ID，不作为逐段日志。即使 0 项差异，也记录查阅范围与核对数量；尚未执行不能写成“未发现差异”或“已完成交叉核对”。

## 事实与范围不得删除或增强

重复限定可合并到支配相关论断的句中，重复句可删除；保护的是科学范围和信息，不是独立句子数量。正文承诺、注册或结论依赖的未完成分析须公开披露；内部备选实验、审批及版本过程不要求进入正式稿。

保留单次运行、评估种子/子集范围、单双侧、分析单位、重采样层级、同目标拟合评估、描述性/探索性、非独立重复、区间跨零、结论不确定、不可估计/未执行、未建立优势、失败队列/不利结果、局限中影响结论的信息与范围，以及未决作者事项。这些保护的是信息和科学归属；结构模式可合并局限段、去重限定、将内部代号转为准确科学表述，不要求逐个英文 token 或独立原句保持不变。相反方向不利结果不能改成合理权衡；未检验不能改成“不影响”。不能为满足字数或去 AI 味删这些内容。

可以删不承载事实的 unfortunately、regrettably、we apologize、we must admit、自我贬损形容词、与研究证据无关的写作尝试流水账、同义 hedge 堆积。不能做全局字符串替换。`only`、`limited`、`may`、`not` 很可能是量/推断限定，必须读上下文；除非能证明冗余且不改证据含义，否则保留该处并记录未知点；只有真实待裁定问题才归入作者动作。

## 规则来源与适配（anti-defensive-writing 为必需依赖；其余为静态参考）

### Anti-defensive-writing：必需依赖与十二项医学适配

每次执行 `medical-sci-finalize` 均须先读取并应用同一技能根下的 [独立 anti-defensive-writing 技能](../../anti-defensive-writing/SKILL.md)。缺失或不可读时停止，不以以下摘录替代依赖。以下十二项用于限定上游规则在医学稿中的应用；ARS 与 humanizer 仍只作静态参考，不调用其技能。

来源：[Adkid-Zephyr/anti-defensive-writing-Skill 的 SKILL.md](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill/blob/main/skills/anti-defensive-writing/SKILL.md)，2026-10-15 读取；MIT，Copyright (c) 2026 Adkid-Zephyr。以下保留原有医学适配要点，不是原规则原文照搬；实际执行同时读取独立安装版本，版本与哈希记入修改记录：

1. 围绕有证据的价值组织；不得隐藏弱项。
2. 用研究逻辑替代过程流水账；结论相关失败/未执行事实公开保留；内部备用实验、审批与版本记录留在过程文件。
3. 不建立无据的全面领先主张；已定评价维度不换。
4. 准确说清贡献；不得强化证据。
5. 将比较限定在已执行范围。
6. 默认可在同节内合并、去重和重排，不更换研究问题、科学范围或选择性隐藏不利结果。
7. 删自贬情绪词；保留限制事实。
8. 客观报告不占优结果；禁止“不说输”式隐去。
9. 不把局部不利结果泛化为整体否定。
10. 解释实验对应问题；不删不利实验。
11. 摘要/引言明确问题与研究价值，不添发现。
12. 结论聚焦已有证据；仍保留必要边界。

上游“更换维度、删除结果、只围绕优势”等隐藏不利证据的规则不适用于本医学稿；以本文件的保留清单覆盖。同时必须执行以下正向主线锐度规则，防止润色后仍呈平铺防御腔：

### 主线锐度与去防御冗余准则（Headline-First & Anti-Defensive Clarity）

1. **先立发现主线，后精准附边界**：Abstract 结论、Highlights、Results 小节标题与段落首句、Discussion 首尾段，必须先用清晰直接的主动陈述给出研究真正回答的结论及具体极端/失败边界（如具体保持区间与失灵队列），禁止用含糊概括（如 `varies across cohorts and declines`）或空洞验证套话（如 `requiring validation before...`）替代明确 take-home 结论。
2. **禁用空洞过程元标签**：正文（Abstract、Introduction、Discussion）严禁使用 `"structured method"`、`"method carrier"`、`"evaluation vehicle"`、`"evaluation framework"`、`"interpretability carrier"` 及中文“结构化方法”“方法载体”作为主体标签；直接写研究评估的真实模型与机制（如 ANCHOR-OCT / concept-bottleneck model）完成了什么、在何处失效。
3. **反重复防御（单点支配，不逐句贴标签）**：单种子、样本量、探索性/描述性、未建立优势等科学范围只在支配该论断的段落/逻辑块首句或主位用最少的精确词交代一次（注意“单点支配”指避免同句连词重复，也避免在相邻两三句或同一 Discussion 段落中反复出现 `In the single evaluated seed...` 双重贴标；但**每个独立的单种子分析阶段——含 Stage-1 前段分割/校准/特征图注与副面板（即使 `.source.json` 的 `transforms` 为空，仍须核对 `inputs` 如 `learned_per_row.parquet` 与 Stage-1 表格）、子集抽样/合并图注中并列于多种子面板旁的单个单种子子图（如合并 `(c, d)` 句中将 `in the single evaluated seed` 显式贴于 `(c)` 从句）、单种子曲线面板（即使与多种子面板同图）、指标/目标拟合对照表注、案例图集与单独表注、以及讨论中首次引用的单一生物标志物分析——仍须读出对应 `.source.json` 的 `inputs`/`definitions`/`transforms` 后明确标示单种子范围**：仅当原文已含 `seed 0` / `seed-0` 时使用 `in seed 0` / `在种子0中`（清除连字符 `seed-0`），而当原文未写种子编号或只写模糊的 `in the evaluated seed` 时，**统一补充为 `in the single evaluated seed` / `在唯一接受评价的种子中`，严禁凭空向不含数字的段落插入新数字 `seed 0` 或在中文中把 `one seed / the other two` 改写成数字 `种子0 / 种子1和种子2`**，以免破坏结构验证的数值一致性；改写 Highlights 等条目时保留 `retrospective` 等研究设计范围词）；严禁在 Results/Discussion/Methods/Tables 中机械重复 `"rather than"`（Results 建议 `≤6`，Methods/Tables 亦应直陈对照而非反复 `"rather than"`）、`"descriptive"` / `"descriptively"`（可用具体样本与检验边界如 `in five subjects (P = 0.124)`、具体差值幅度或 `"is not established"` / `"without a prespecified inferential threshold"` 替代空贴标签，或在同论断单元内保留一处主限定、清理其余重复）或 `"served as..."` / `"unresolved"` / `"does not establish"` / `"remains ..."` 堆砌；**混合多种子列的表格/附图注释必须先核对源表 `02_figures/out/tables/*.md` 的逐列表头，再分列标明每一真实列名或列组**（禁止笼统写成 `"Single-seed ... with seed variability"`，也**严禁凭空合并或错配表头**把本属于独立多列的内外部点估计、pooled 差值和多种子汇总列说成“某单列即多种子 mean ± SD”）。
4. **跨队列独立性与逐类核对清单（Cross-Cohort & Classwise Audit）**：在宣称“多数外部队列（most / N of M）保持”或将某队列设为“唯一例外”前，必须在 **Abstract、Results、Discussion 以及所有图注（Figure Legends / Supplementary Figure Legends）** 中统一**优先以去重后的独立队列组数作为主分母**（例如先写 `five of six independent cohort groups`，严禁在主标题、摘要、讨论或图注首句以包含重叠样本/扫描的 `six of seven cohorts` 领起，重叠细节仅可在括号或附注补充），并逐队列、逐类别、逐主要终点指标核对源表、`*.csv` 及 `*.source.json` 全部行与字段；同时逐条审计 Results 的**所有父级 H2 标题与子节 H3 标题**是否越过子类别 AP/PR-AUC、多种子不一致、外部失灵或按类别覆盖不足证据，且**改动后的 H2/H3 标题措辞必须严格使用 `口径表.md` 中的规范术语**（例如统一使用 `transport conditions` / `无标签迁移条件`，不得自行替换为 `transport rules` / `迁移规则`）（严禁在少数类/水肿类 AP 明显偏低时保留 `"performs on par"`；也禁止 H2 标题在同节存在多个失败/未达标队列时只点名其中一个而遗漏同节另一失败队列，或在存在外部失灵与多队列按类别覆盖不足时仍以 `"Coverage point estimates exceed target..."` 正面领起，应先点明全部分布失灵/异质性边界再附保持范围）；所有满足同一缺失/未达标/例外条件的队列与类别行必须**逐一写全数值与区间**（例如扫描按类别覆盖表 `ST09.csv` 的全部队列-类别组合——包括总覆盖率本已低于名义目标的队列中按诊断分层明显低于名义值甚至最低的类别行及同队列内高/低诊断对比——凡低于名义目标值的每条队列-类别行均须在 Results 与 Discussion 写全点估计与区间，**Abstract Conclusions 所提每一关键结论词如 diagnosis-specific undercoverage 亦必须在 Abstract Results 中有明确对应数值或具体类别支撑**）；当 Results 或图注比较核心模型曲线（如 risk–coverage、ROC 等）且源数据报告了汇总指标（如 pooled AURC 及 95% CI）时，必须给出核心定量汇总值与区间，禁止仅做定性方向描述；并同步审校 `*_EN.md` 与对应 `*_ZH.md`（杜绝中文稿残留未本地化 `seed` / `logit` / `bootstrap`、`种子` 前后混用空格、术语批替换引入的中文词间多余空格如 `列出 按类别`、`0.5 像素 非劣效界值`、`的 目标样本量`、英文 `Fig.`/`Table`、英文字母 `(1−alpha)`/`px`（复合单位 `µm/px` 除外）、句号/标点前多余空格、全角逗号并列粘连、`****` / `**(a)` 加粗残损、`## 3.x` / `- ` 列表结构丢失，以及 `口径表.md` 禁用别名或未汉化术语如 `external oracle`），不可用“大纲原标题”或遗漏附表行掩盖证据偏差。
5. **全稿无死角覆盖、零可修复告警与段落切分**：阶段二整稿润色必须同时核查并收紧 **Highlights（与正文和摘要同步打磨，保留 `retrospective` 等设计范围、关键失败条件与边界，不得原封不动跳过，每条一句独立发现、不与 Abstract Conclusions 同义循环；同时检查 `Abstract_EN_ZH.md` 中每条中文 Highlight 的前导 `- ` 列表符与英文完全一致）**、**Abstract 结论与篇幅（Results 保持 4–6 个清晰短句、零散文分号（`check_abstract.py` 对 `>=1` 个分号即告警）、压缩比较从句时严禁省去被修饰名词而写成逻辑矛盾的 `"negative intervals crossing zero"`（须完整保留 `"negative differences with intervals crossing zero"`），也严禁删去 `"point estimates"` / `"点估计"`（如跨名义阈值结论仍存在跨越阈值的置信区间）或未经推断检验对比上的 `"descriptively"` / `"描述性"` 与对比限定词（如 `"same-backbone"` / `"同骨干"`），并在中译 `"with X and Y in [Cohorts]"` 时严禁前置统领修饰语造成作用域越界（须分写为“总体 X 以及 [队列] 的 Y”）；Conclusions 中的核心结论短语（如 `diagnosis-specific undercoverage`）必须在 Abstract Results 中明确给出对应类别证据而非仅写队列总覆盖率、尽量带出核心差值或低性能类对比数字，严禁以 `"Safe/clinical deployment requires prospective..."` 等空泛验证套话收尾，并保留 `<250` 词安全余量而不卡死 250/250）**、**Results 小节标题与同源引用合并（单段同一图表精确目标 `≥3` 次或同主图号 `≥4` 次时合并至单元/句末共享括号，保留首次/跨句所需唯一引用，消除 `(Fig. S8)` 与 `(Fig. S8C,D)` 同括冗余及相邻重复 `(Supplementary Fig. S6)`；清除孤立 1 句寡段与行尾多余空格；清除 `≥3` 次重复的 `supplementary data` 模板套话；Introduction/Results/Discussion 单段 `>8` 句或 `>200` 词时按单一论证单元拆分，同时保持 Discussion 平均句长 `18–28` 词/句）**、**图注语法与并列一致性（复核长句并列动词与从句一致性，如 `so ... appear ... and outline ...` 而非混用分词 `outlining`）**、以及 **Discussion 主题句与收尾段**。运行 `manuscript_check.py` 与 `check_abstract.py` 后必须清零所有 `ERROR` 及**所有可修复的 `WARN`**——其中 `legends` 校验必须**逐一对全部 `Legends/*_EN.md`（`Figure_Legends`、`Supplementary_Figure_Legends`、`Table_Titles_Notes`）及其对应 `*_ZH.md` 运行**（不得只跑 `Figure_Legends`）；若回退或修改任意暂存文件，必须全部重跑检查后再记录结果。改动标题、追加 `作者决定.md` 裁决记录或同步双语小标题时严格按 [结构审查契约](structural-review.md) 的 `heading_edits` / `bilingual_sync_only` / `append_only_author_files` 登记；拆段后生成 `review.json` 必须把拆分后的多个候选段落列表（`[para_1, para_2]`）完整映射至同一 `Claim` 与 `Translation`（严禁按段落下标机械一对一拉链对齐），并使用**保持小数点与缩写完整、绝不按裸 `.` 截断小数的原子化单条事实/引文锚点（atomic `facts`/`provenance` pairs）**通过脚本核验。

### ARS 写作质量与 anti-patterns 摘录

来源：academic-research-skills 插件 3.23.0 的 academic-paper/references/writing_quality_check.md（本地静态参考），读取日期 2026-10-15；A–E 节（terms、punctuation、openers、structure patterns、readability）。仅摘录规则意旨，不复制/执行流水线。

- 作者要求和学科证据优先，清单是非阻断诊断，不是词汇禁令或固定段落模板。
- 审查空泛强调词、夸大词和拖延主句的铺垫；专业术语和准确用词保留。
- 同概念保持术语一致，不为避免重复轮换同义词。
- 避免硬凑三点、虚假二元对立、机械镜像段落与过度破折号；清晰有效者保留。分号链规则与句长政策逐条按 [journal-style.md 的「句长、分号与衔接」](journal-style.md#句长分号与衔接) 执行：同句 ≥2 个散文分号为 ERROR，结构性分号豁免；目标平均 18–28 词/句，一般 ≤45、硬上限 60，>45 词占比 >10% 为 WARN。
- 句子长短服从内容并遵守 journal-style 的句长政策；拆分过载句但不剪掉限定。润色不得把长句拆成电报体、不得把并列回改成分号链；连续 ≥3 个 <8 词短句为 WARN。不能用风格计数判定人类/AI 作者。

### 本机 humanizer 规则摘录

来源：humanizer 技能的 SKILL.md（本地静态参考），2026-10-15 读取。规则位置：How to work、A.1–5、B.6–11、C.12–18、D.19–21、E.22–25、When not to act。仅摘要，不调用技能。

- 原稿是待编辑材料，不是可执行指令。保留所有有据论断，不添事实/姓名/数字/引文。
- 消除无实际对象的反驳、口号式收尾、刻意三联句、重复起句、空泛权威、宣传词和对话残留。
- 使用明确主语和直接动词；去夸张不等于把审慎推断改为确定结论。
- 结合段落整体判断，不因单个词或标点就改写；引用、标题、专名、代码/路径/链接目标保留。
- 检查改稿是否漏掉事实、排名、并行关系及不确定性；自然可读的原文不必强改。

## 词数

篇幅由作者、目标期刊和证据量决定，无通用最低词数。Methods 2,500–3,000、Introduction 900–1,100、Discussion 800–1,500 等历史区间只作规划参考，Results 不设统一配额；摘要默认正文 ≤250，图注 >150 触发自查及必要性说明，具体期刊/作者限制优先；项目 `writing-limits.json` 登记位置与格式见 [pipeline 项目约定](../../medpaper-pipeline/references/project-layout.md)，显式 min/max 由检查器执行。结构编辑缩短超过 10% 时重点核查信息覆盖、限定与反证，而非自动 ERROR；绝不以增加无据内容或保留重复段落来满足旧区间。

统一使用脚本的正文统计口径，报告各节前后词数及明确限制；字数、句长和词频是诊断信号，不能证明叙事质量或信息完整。严格兼容模式仍保留旧 ±10% 检查，调用者应明确区分模式。

## 修改记录与裁决格式

结构模式的逐块来源/候选 span、事实、范围、双语映射和问题处理全部写入 `review.json`，格式以 [结构审查契约](structural-review.md) 为准。`changes.json` 与 `decisions.json` 均仅包含 `{ "schema_version": 1, "review_sha256": "<review 文件原始字节 SHA256>", "decisions": ["<全部叙事问题 ID，每个恰好一次>"] }`；比较可检查 changes，apply 两份都必须检查。不从结构比较输出生成旧式逐块 expected_changes；人读逐块修改记录及裁决清单分别保留为 Markdown，不替代机器记录。

仅在旧严格兼容模式中，逐块 `changes.json` 为列表或 `{ "changes": [...] }`。每条字段：`file`（相对于原稿树，如 `Methods/Methods_EN.md`）、`before_start`、`after_start`（按 blocks 规则的一起始段号）、`before`、`after`（精确原/改段，多段用两个换行）、`reason`。该模式可用一次无 --changes 比对返回的 `expected_changes` 建立骨架，再补理由并带 --changes 检查；不得将此格式交给结构模式，不得用自动骨架充当人工润色或判断理由。

另写可读 Markdown：位置 | 原句/原段 | 改句/改段 | 理由 | 数字/限定核对。每条实际变化都需覆盖，未改段不伪造修改记录。候选改动未采用时在裁决清单保留建议，不进入清稿。

### 修改记录说明：交叉核对执行与结果

`修改记录.md` 必须另设同名部分，不能用“已核对”一句话替代实际记录：

- 执行信息：日期、原稿/候选版本、实际查阅的补充图注/表注/各节核查说明文件及定位范围；缺失、不可读或未执行的文件及原因。
- 汇总：关键限定项数、关键数字项数；一致/差异有据/来源待查/未执行各多少项。计数以唯一 ID 为单位，混合项注明类型，不能把未执行算作一致。
- 逐项表：`ID | 类型（限定/数字） | 原稿文件/位置与精确原句 | 分析归属/单位/范围/CI归属 | 已查材料文件/位置与证据摘录（或未找到/未覆盖） | 候选位置与保留情况 | 结果与依据 | 保守处理/裁决ID`。每个关键保护项都要有可追溯结果；修改段记录的“数字/限定核对”引用这些 ID。

“来源待查”项即使未改文也完整进入审计附录，写清已查材料、证据缺口、是否“无法证明缺失”及当前保留原文。例如（虚构格式示例）：正文写“single evaluated seed”，补充图注无种子记录，核查说明也无对应证据；记录“来源待查；无法证明缺失；保留原句”。仅缺少重复叙述时归结构性覆盖缺口；若另有实质范围冲突或分析归属不明，才要求相应运行证据。不能写成“漏了多种子限定”或将正文改为多种子结果。关键数字同理，不能把邻近分析的 CI 移作该数字的证据。

作者裁决清单默认三层：§1 沿用既有未决事项（不改其状态和内容）；§2 本轮需作者动作（按共同问题归组，每组写一句话问题、文件/ID、保守处理、所需证据或决定）；§3 指向附录并列简要计数。即便新增 0 组也明确写 0 组。不能将旧项重复计作本轮新问题，不将建议登记为已确认。附录按“文件 × 类型（限定/数字）× 共同证据缺口”统计全部来源待查项，明确“计数≠问题数”；材料未复述造成的结构性记录缺口不据此认定稿件问题。保留全部原判定，不因分组重判为一致。

### 记录呈现生成（默认用于新项目；也可单独修复已有记录）

`scripts/generate_polish_records.py` 只生成 `作者裁决清单.md`、`附录_交叉核对审计.md`，不会执行润色、检查器、组装或修改 changes/清稿/稿件/Word。输入为过程目录中 `before/<相对稿件路径>`、`crosscheck.json`、已有作者清单和一份当前代理审阅的呈现分组 JSON。不要重跑项目的旧 `records.py`，它可能同时重写 changes、修改记录及 crosscheck。

`crosscheck.json` 为列表，每项沿用：`id/type/file/unit_key/result/basis/original_sentences/evidence/conservative_action`；`file` 相对 before/，`unit_key` 为一基始 block 整数或图表注 `c1/cS1`。证据项为 `file/line/quote`。图表注从 `**Figure N.`、`**Supplementary Figure SN.` 或相应 Table 标题到下一个标题/文件末整体抽取，包含软换行和多个自然段；数字正文按所属完整句恢复，保留小数及 Fig. 等缩写，旧碎片无法安全匹配则展示整个单元。展示不使用 `<br>`，换行合为空格，超长明确加“…”；原始全文与证据仍在输入中。

呈现分组 JSON 顶层为 `crosscheck_sha256`（输入文件实际 SHA256）、`items`（按每一个“来源待查”ID 映射；不得漏项或额外列 ID）。每项必填 `kind` 和共同证据缺口 `gap`：

- `coverage_gap`：材料结构未逐项复述，不因该缺口要求作者动作。
- `inherited`：同一未决事项已在 §1；另填能在 §1 找到的 `reference`，不关闭或重复新增。
- `author_action`：存在需要作者回答的具体问题；另填稳定 `group`、一句话 `question`、`conservative`、`needed`。同组问法与处理必须一致，合并涉及文件和 ID。

该归类由代理读证据后完成，脚本不凭“未找到”“来源待查”等关键词自动判断是否是稿件问题；分组不充分或哈希已变即停止生成。新项目无既有清单时，可填顶层 `inherited_markdown` 保存上游未决事项，不能默认丢弃已知未决项；既有清单须能识别“沿用既有未决事项”章节。

先预览（仅写单独开发目录）：

```powershell
& '<解释器完整路径>python.exe' -X utf8 scripts/generate_polish_records.py --process-dir <过程目录> --triage-json <呈现分组.json> --preview-dir <独立预览目录>
```

在获准写入项目的环境执行：

```powershell
& '<解释器完整路径>python.exe' -X utf8 scripts/generate_polish_records.py --process-dir <项目根>/_process/Finalize/<日期>_polish_v<N> --triage-json <呈现分组.json> --write --project-root <项目根> --archive-date <YYYY-MM-DD>
```

替换前按项目相对路径将旧两份记录的实际存在版本归档到 `_archive/<日期>/_process/Finalize/.../` 并逐字节核验，再原子替换；归档路径已有不同字节时停止、不覆盖历史。相同输入重跑字节一致且不重复写入/归档。标准输出 JSON 报告全部变更路径、两份记录 SHA256、04_manuscript/05_final 保持不变；全项目文件前后哈希核对仅允许这两份记录及其归档发生变化。既有 assembly 过程文件不由该脚本修改。

先在候选树核验，再使用 --apply 归档全部变化原件后覆盖。字节归档、检查报告和逐段记录应一同留在过程目录；失败不推进状态，不在未通过时改真实成稿。

## 上游 MIT 许可保留

以下许可适用于上述 anti-defensive-writing 规则来源（不宣称本项目其他本地来源也为 MIT）：

```text
MIT License

Copyright (c) 2026 Adkid-Zephyr

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```


## 证据优先的叙事复核

发表边界复核：清除内部审批、版本历史及实验代号；科学承诺或结论依赖的未执行分析仍须披露，内部备选任务不自动进入论文。编辑验收逐项评价信息增量、文献论证角色、摘要优先级和限定支配范围；字数或词频 PASS 不得代替这些判断。尤其不得将 no clear reduction 改为 did not narrow，不得混淆 observed-class BACC 与完整三分类 BACC，或把差值为负写成种子为负。

局部编辑不得为满足摘要格式而补写背景、样本设计或方法。清理表注时逐项区分科学信息与内部管理信息：删除审批理由及 E9/E13 等无读者意义代号；独有计数（例如 24 个组合、179,505 行）不可随之消失，除非有明确依据证明其纯属内部过程且记录取舍。测试验收应包含未预告变体和反例，不能由编辑自己编写预期后全部自评 PASS。

实际手稿回归须把每条已确认审查问题映射到候选的具体修改位置或有证据的保留理由；不能仅在孤立夹具中修复问题，却遗漏正文原位置。没有重跑的案例必须标为 carried-forward，不能计入本轮独立通过数。不要只根据脚本字面匹配判定文献分组或双语语义。

最终交付新鲜度：最终一次编辑后重新生成合并稿并重跑检查，记录最终源文件SHA256及合并稿SHA256；检查副本须与最终候选逐文件一致。历史失败与当前候选失败分开报告。双语数字核对必须覆盖小于10的数字与中英文数词，不得通过忽略小数值掩盖错误；无法可靠自动对应时逐项人工核对并记录。


## 审查意见的版本绑定与处置

收到外部审查后，先记录审查所依据的提交号、手稿文件与 SHA256，再与当前候选逐条比对；没有原文件时标记“版本未核实”，不得把旧稿引文当作当前缺陷。每条意见登记为仍存在、已修复、部分成立或证据不足，并给当前定位及修改/保留理由。规则已修复但正式源稿未接入时，应处理发布落差，不重复扩写规则。词频及固定阈值仅用于发现重复线索；不得据此判定 AI 来源、全局替换近义词或把必要对比改成无比较。结论只能覆盖实际复核范围，沿用测试须注明时间与版本。候选通过复核后，归档并接入正式源稿、重建对应审查合并稿，同时把 Word 的过期状态如实登记。


## 真实候选的机械阻断

显式structural路径仍保护claim/translation词项、局部context、fact字面锚点与标题。不能仅凭narrative理由豁免，也不能在无关处塞回not、缩小事实清单或改基线取巧。先对真实候选的科学范围与对应语言人工审读，再区分信息损失与机械字面误拦；只有后一种才提出绑定源/候选SHA、准确span、事实/范围/三语及真实审读身份的局部兼容修复。联合核对各层契约，保留旧strict语义，不整体降级否定保护。

有据的小节标题修改须保留稳定身份、层级、顺序和范围，原/新标题及对应语言一一映射，不开放跨节迁移。检查通过不能证明语义等价。

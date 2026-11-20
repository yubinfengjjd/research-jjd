# 跨章节贡献与证据定位

复用既有大纲或核查说明中的一处定位记录，各写作阶段读取或链接同一记录。新项目在现有大纲阶段形成，完整手稿修订可在入口回填；不新增阶段、强制YAML字段或复制多份表格。已有作者决定直接沿用。

记录研究问题与贡献类型、关键发现及证据位置、决定性反证与必要范围、读者能判断什么、最近邻文献支持状态及章节位置。实现能力、实证认识、文献新颖性与临床作用分别判断；组合方法或阴性结果本身不自动证明新颖性。文本核对不叫科学验证通过。

Introduction对齐问题、设计区别和可评估能力，沿用其不报本研究结果的默认政策；Results给有范围的发现，Discussion说明回答了什么，Abstract/Highlights选择主要支持与会改变主结论的反证。同一事实和证据强度相容，各章不必逐字复述。短文本可省次要分析，内部记录取舍；不规定贡献或限制的条数。

限定是否必要取决于其支配的具体论断。每项删并说明：原来限制什么、候选哪处继续承担同一范围、分析切换时哪里失效。研究设计/分析/估计三类仅帮助盘点，不能规定只在某章或只说一次；摘要、亮点、图注可各需自己的范围。不按not/no/without/descriptive/unresolved等词性批量删除，也不把已有CI视为自动足够的推断说明。

复核问题—证据—贡献是否清楚；相近点估计是否被误写成等效/无代价；阴性或异质性是否被改成未检验机制/临床效用；摘要省略的反证是否改变结论。清楚自然的原文可保留。词频、篇幅和引用密度只作诊断，无通用配额。

部署与稿件分开验收：规则/代码版本、实际加载路径及依赖SHA、片段改善、三语同步、正式源稿接入、Word视觉/引文字段、作者认可分别登记。安装哈希差异先审读来源与内容，不直接当损坏覆盖；历史版本未知时不倒推写作原因。

## 共同写作与核验边界

围绕研究问题、主要发现及其意义组织正文，先写读者需要知道的结果；关键发现、限制、段落、句数和文献量不设通用条数。按证据角色连接已知问题、方法选择、直接比较、解释和反证，同一关键来源可支持不同论断，不按“一段一篇”或每段固定文献数组织文字。数字、标点、词频、句长和引用密度是审读线索；除明确作者或期刊限制外，不为清零提示凑数、加长、拆句或机械合句。

范围声明可以支配明确界定的同章节/同文件后文：记录对象、队列、终点、数据划分、种子/子集、方法和推断状态及开始/结束位置，逐项映射后继论断。在 `Results` 与 `Discussion` 中，单次运行/单种子范围在 `Methods` 和 `Results` 第一次进入单次运行分析处声明一次（以及 `Discussion` 开篇声明一次）后，**同文件后续所有 `###` 子节和段落自动继承该单次运行范围，必须删去各子节句首和段中机械重复的 `In the single evaluated seed,` / `Evaluated in the single evaluated seed,`（全稿 `single evaluated seed` 压至 ≤ 2–3 次）**；只在同段直接并列对比单种子与多种子结果时用具体运行号（如 `in seed 0` vs `in seeds 1 and 2`）区分。严禁滥用 `"instead of"` 替代 `"rather than"` / `"not"` 或拼凑稻草人免责（全稿 `"instead of"` 压至 0–1 次）：若后接未测量的稻草人（如因果驱动、真实病变标注、跨模态性能、临床工作流获益），直接删去 `instead of ...` 尾巴；若为真实对照，改用主谓否定句（`"did not hold"`）、`", not ..."` 或 `"rather than"`。删去 `Results` 与 `Discussion` 段末不提供新数据的免责总结句（如 `"These probes were representation readouts distinct from..."`、`"This algebraic decomposition quantified... instead of causal drivers"`、`"Projected distances were neither... nor..."`、`"This gallery remained descriptive without establishing..."`、`"These findings delineate specific evidence boundaries..."`），并将 `Discussion` 中段末 `"would test / would help distinguish / would clarify"` 压至全篇 1–2 处以内。打散句尾分词链 `, leaving / showing / indicating / representing / distinguishing ... (Fig. X).`，避免句句以 `(Fig. X).` 结尾；将怪异搭配与抽象名词堆叠（如 `admitted an exact decomposition`、`values indexed`、`near-magnitude reduction`、`separate evaluations assessed`）改回直接主谓宾，并主动混入 6–12 词的短句打破 ~20 词均匀句长。对超过 30–35 词的过载复合句拆成两到三个直接清楚的句子，保留段内全部数值、区间与引用。当一句比较某一终点而句末用 `, alongside ...` 挂上另一无关领域的测定时，严禁把 `alongside` 机械替换成 `with`，应拆成独立短句；句首 `Alongside [X],` 改写为 `Combined with [X],` 或 `Together with [X],`。在 `Introduction` 与 `Discussion` 连续介绍三篇及以上相关文献时，先写一句归纳性判断或比较角色引导句，再分两到三句陈述各研究及其 PMID。当具体数据、区间或检验已明确写出时，删去矛盾或叠床架屋的 `non-inferential` / `descriptive` 标签与重复对冲。数字与单位之间、名称与其编号之间加一个空格不改变证据记号，应当补上。不要把 16 改成十六，也不要把两个改成 2。侧车记录补充审计，不代替读者在当前文字附近所需的材料证据引用和科学限定。

预注册或预设、验证性或探索性设计按真实记录描述，不是内部开发史。分别核对是否预设分析、是否实际进行推断检验、是否事后分析、估计与检验结果；“未预设推断阈值”“未进行检验”“不显著”“未建立某关系”不能互换，也不能把所有次要分析自动标成探索性。保留会改变结论的异质性、阴性结果与反例，并让它们继续归属相同对象、终点及分析。

引用靠近实际支持的论断或清楚的连续论断组。合并重复引用需核对相同来源、支配范围和中间是否切换证据；不能只因出现多次便删引或换源。项目口径表、实际图面、作者确认的术语与研究设计决定具体名称及 panel 大小写；技能中的课题例子只是条件示例，不升级为通用禁词或固定表达。

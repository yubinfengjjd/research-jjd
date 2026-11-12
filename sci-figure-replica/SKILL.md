---
name: sci-figure-replica
description: Use when 用户要求复刻科研数据图、从文章或代码提取可复用图样式、按图估读或收录科研画廊；先识别去重样式并咨询，只制作确认选定的代表单 panel，整图仅保留作只读溯源。不适用于示意图、医学影像网格、论文写作或单纯统计咨询。
---

# 数据图复刻与本地画廊

适用于折线、条形、散点、箱线/小提琴、热图、误差棒、蜂群、极坐标；多面板来源先识别去重样式，选代表单 panel。示意图/流程机制图、照片/显微或医学影像、地图、3D/动画/交互图不适用。“1:1”表示尽量贴近并交作者目视签核，不能承诺像素完全一致。

输入为帖子全文（粘贴或 md/txt/html）、按出现顺序命名的 `fig01.png` 等原图、标题/公众号/作者/日期/URL 来源元数据。未知来源字段用 null；原件只读。只有 URL 时，公开页面抓取受阻就停止索取全文。先读 [输入规则](references/input-and-parsing.md)。

## 从样式咨询到复刻

1. **解析**：`scripts/parse_post.py --input <file> --out <post-dir> [--url <url>]`；只有 URL 可用 `--url <url> --out <post-dir>`。提取全文、来源、代码块与图片候选，不执行代码；验证页则停止。
2. **识别样式**：agent 查看候选图，区分数据图与封面等，配对来源与本地原件，再列去重后的样式卡：代表裁图、原图位置/重复位置、视觉编码、附属元素、已有模板及不确定点。模型/指标/颜色变化通常是参数；真正不同的结构保留可选变体。inset、色标、边缘分布与主图合成一个逻辑 panel，图片数不等于任务数。见 [读图与去重](references/image-analysis.md)。
3. **询问与计划**：每个选定样式只做一个代表单 panel；不提供整组复刻或整图收录选项。集中确认样式/代表、数据、保真重点、语言/代码和交付，复用已有答案，等关键选择明确后执行。缺原始数据先说明缺口与估读/合成的影响，询问本次选择，不默认采用任何一种。方法联想限定为有依据的方法家族推广（如 XGBoost＋SHAP → 满足条件的机器学习模型＋SHAP）：保留原实现，说明适用范围、前提、限制与未实现/未验证分支；不从画法通用性推导宽泛新分析方法。先写文字，有来源代码可按函数契约融入，不自动补算法。见 [实施流程](references/replication-workflow.md)。候选阶段可解析、裁图预览、查询模板和出计划；渲染或正式收录在计划确认后开始。
4. **建条目/记录范围**：按 [画廊布局](references/gallery-layout.md) 向 `dedupe --image` 和 `init_entry --source` 传同一选定裁图；裁图为 `source_image`，`source_image_sha256` 记录裁图哈希，完整原图另行只读归档并记独立哈希/bbox。先 dry-run，再留历史更新或建新 id；不同结构代表用不同 id。`figure.panel_map` 只声明实际选定 panel 的图型，不能要求未选 panel 全覆盖或按图型强行合并。
5. **代码与函数复用**：先核对目标对应关系，再原样运行→有限改造→归档并按授权重建。保留原语言、源字节/哈希与修改副本。分析返回表、绘图消费表，显式数据/列/参数，可独立或串联；复制到课题用其环境，独立函数与既有 render/draw 共用绘图核心。统计含义变化或补缺失分析算法先询问。见 [代码与函数契约](references/code-handling.md)。
   函数化须覆盖组数/类别数/系列/行列变化，不能仅把固定原图包成函数。 n为实际数据中的任意合法数量，由课题agent识别并编排，不为固定几个n另写分支/模板；尺寸默认系数可按课题覆盖。尺寸按结构计算（如固定留白+n×每组宽度），默认保持单panel和间距继续扩展；作者明确限宽才协商。标签、配色和附属元素随规模适配；原图比例复刻与adaptive复用分开验证。见 [规模适配](references/adaptive-sizing.md)。
6. **渲染**：用 [运行环境](references/runtime-environment.md) 的专用解释器，从可追溯数据和样式生成可运行代码，导出 PNG/PDF/SVG 与缩略图，记录实际设备、字体及运行日志。不得虚构原始数据；合成近似明确标注。
7. **对比**：`make_compare.py` 输出等高并排与可选 overlay；`qa_check.py` 生成机械检查及人工待填项，再逐项目视填写。见 [视觉 QA](references/visual-qa.md)。
8. **迭代**：读取选定单位的对比图修图，每轮记录命令、退出码、变化与 QA；自动轮次最多 `config.max_auto_rounds`（默认 3）。不得降低阈值、删掉已选元素或缩小参考图凑通过。见 [复刻流程](references/replication-workflow.md)。
9. **签核/索引**：准备阶段为 draft；可审成图用 review；只有作者明确签核才 approved。未决项记 `needs_author`。按 [场景词表](references/scenario-taxonomy.md) 标记，用 `build_index.py --gallery <dir>` 更新离线索引；draft 缺图显示“待生成”。
10. **收录进知识库**：按 research-wiki 的 SKILL.md 运行 `wiki.py ingest-figure <条目 id>`，填写适用与不适用。单 panel 可独立收录、签核及模板 ready/render，不以前置重建整组为条件；来源 layout 若也要 ready，需只覆盖已选单位的布局/preview 与 `verify-layout`（单 panel 为 1×1），不覆盖未选 panel。关联方法先沉淀文字笔记；已确认的作者源码可按契约函数化，不要求每篇笔记有代码。实际运行/换数据验证、作者签核分别记录，不自动 approved/ready。

## 环境、工具与例子

路径集中在 `config.json`：Python 为 `C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe`，R 为 `D:\R-4.5.0\bin\Rscript.exe`。不要使用 PATH 上的 Windows 商店 Python，不改其他 venv。`bootstrap_env.py --check-r` 检查现有环境；缺包先报告，不自动联网安装。运行器是有界执行器，不是安全沙箱，只运行已审阅且获授权的代码。

```powershell
$py = 'C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe'
& $py -X utf8 <skill>\scripts\run_code.py --language python --code <entry>\code\replica.py --cwd <entry>
& $py -X utf8 <skill>\scripts\run_code.py --language r --code <entry>\code\replica.R --cwd <entry>
```

脚本还包括 `crop_figure.py`、`sample_palette.py`、`estimate_data.py`；参数见各脚本 `--help`。模板为 `python_style.py`、`panel_layout.py`、`shap_bar.py`、`beeswarm.py`、`radial_bar.py`、`r_style.R`。Python 中文用 `register_cjk_font(text=...)` 验证字符映射并记录 family/file；R 中文用 `register_cjk_font()` 检查字体文件并注册 `windowsFonts`。R 的 `svglite` 缺失可降级 `grDevices::svg`，但文字可能是路径，必须 WARN，不能宣称文字可编辑。

例子：`examples/single-panel/{bar_inset,beeswarm,radial}` 为 A/B/C 单图；`examples/post01-fig4` 为六面板复刻；`examples/r-simple` 为 synthetic 柱形误差棒运行时演示。前两者含估读/合成近似，不是原始观测；R 演示不代表任何帖子已完成 1:1 复刻。例子自带 README、数据、代码、导出、并排与 QA，运行方法读各自 README。T3 六面板仍有 WARN，作者签核待定。

## 画廊与交付

画廊根有 `index.html/index.json`；每图为 `POST/figures/figNN/`，包括 `meta.json`、README、`source/` 原图、`original_code/`、`code/`、`data/`、`output/`、`compare/`、`thumb.png`、`qa_report.md`、`run.log`、`history/`。帖子全文和来源在 POST 层。draft 允许缺 output/compare，索引只链接已有文件并列出 pending“待生成”，不能伪造占位成图。完成渲染后交付三格式、并排图、运行方法、数据/代码来源、假设和未决项。

所有画廊写 CLI 显式要求 `--gallery`；正式路径取 `config.gallery_root`，开发测试指定独立测试画廊，不得写真实画廊。去重保留 `source/` 与原代码，旧 meta/code/data/output/compare/README 等进入 `history/<UTC timestamp>/`，version 加 1，索引只保留当前条目。

## 停止条件

缺原图、配对不明、关键元素不可读、运行/导出失败原因不明、缺必需包或字体、需要联网安装、权限受限或旧版本不能安全保留时，保存现场并报告。原代码无法改造可归档，是否重建按已有授权办理；不能静默换语言、补造原始数据/统计结论、把文件存在当视觉验收，或把未运行/未通过写成通过。严格遵守全局 AGENTS.md 对外部工作流目录的隔离要求，不读取、调用或引用被禁止的资源。

## 每次收录的知识关联

新复刻图/模板/方法收录前，agent检索已有知识并核对方法、数据含义与接口；有依据才补来源/参考/互补方法链接或复用接口，将检查结果和未关联原因写进Wiki。不能为连通网络伪造可串联关系。方法卡片可以配明确关联的参考图样并标状态，单panel图样与可调用模板分开展示，历史整图来源归档并隐藏。见 [知识关联检查](references/knowledge-linking.md)。


## 交接 Wiki 的验收

正式收录与实质更新同时遵守research-wiki读取的正式库AGENTS.md“入库与展示验收”：来源/单panel范围、覆盖关系下的配图去重、方法家族与双向关联、数据适配、原生/复用代码、前端实查及状态交接。单panel图样包含已有单panel函数模板，两栏可重叠；按明示覆盖去重，不按页面存储类型排除。历史整图只保留溯源，但已拆出的单panel必须在图样入口可见；使用既有记录，不重复入库、虚构来源或新增待办。方法页面先呈现用途、输入/输出、配图和适配要求；不得借画法相似把需要适配改成直接可接。


### Wiki 入库验收交接

按 research-wiki `check-entry <id>` 核查和记录适用/不适用及知识关联检查；拆出函数后用当前代码/示例完成带输入与输出哈希的 verify-template。只有预览、旧版无哈希记录或修改前回放都不能替代当前验证，仍需作者确认。来源签核绑定版本，重复入库不自动签核新版本。处理待办读 `pending --json`，继续真实缺项，避免遗漏方法或重复新建。

图样/可调用模板是重叠视图；共享同一函数且明示完整覆盖的多个来源可合为一个图样入口并保留来源链接，不靠图型同名合并结构变体。不得为新的验收规则补分析算法、伪造科学关联、改变作者区块或把既有 SHAP 图样隐藏。

模板 ready 后，方法主关系指向模板，来源 layout 只作 evidence；方法页关系卡显示有效 workflow（如“模板已就绪”），不把来源 `pending_template` 当未完成。声明输出与模板输入不一致时标 `adaptable`，在方法页单列需适配模板。

方法页链条同时展示结构匹配与需适配模板；每个模板标出读取接口，不能只留“暂无”。


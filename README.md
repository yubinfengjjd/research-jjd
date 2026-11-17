# research-jjd

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release 2026-11-17](https://img.shields.io/badge/release-2026--11--17-2ea44f.svg)](https://github.com/yubinfengjjd/research-jjd/releases/tag/2026-11-17)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](requirements.txt)

**23 个技能，一条命令装进 Claude Code 和 Codex。**

医学与临床 AI 的课题设计、受控实验、期刊图表、论文写作、Zotero 引文和投稿材料。Medical AI research skills for reproducible experiments, figures, and manuscripts.

```
课题   medical-research-plan → medimg-experiment
图表   medfig-suite → plan → render / orchestrate → outline
写作   medpaper-pipeline → 各节正文 → finalize → references → submission
```

`medical-sci-references` 和 `medical-sci-submission` 也可以直接处理一份独立主稿。

## 安装

```bash
git clone https://github.com/yubinfengjjd/research-jjd.git
cd research-jjd
pip install -r requirements.txt
python install.py
```

以后更新：`git pull && python install.py --update`。

`install.py` 只用标准库。默认装到 `~/.claude/skills` 和 `~/.codex/skills`，已有同名技能先备份，复制后逐文件做 SHA-256 校验。

```bash
python install.py --dry-run          # 只打印计划，不改动文件
python install.py                    # 安装全部 23 个技能
python install.py --update           # 只重装清单哈希有变化的技能
python install.py --verify           # 对比源与已安装文件的 SHA-256
python install.py --uninstall        # 把已安装技能移到备份目录，从不删除
python install.py --target D:/x/skills --target D:/y/skills
```

同时使用 `.agents/skills` 时，用 `--target` 指明实际加载的技能根，先 `--dry-run` 再安装或 `--verify`。0.10 的结构编辑、双语同步和旧记录见[迁移说明](docs/evidence-aware-writing.md)。

备份在 `~/skill_backups/medfig_<时间戳>/<目标名>/<技能名>`，可用 `--backup-root` 修改。安装戳 `<目标>/<技能>/.medfig_install.json` 记下源仓库短 SHA、时间、文件数和清单哈希。校验失败时退出码非零。安装器只读写清单中的技能，目标根里的其他技能不动。

## 换一台电脑

克隆、安装依赖、运行 `python install.py` 之后，23 个技能的规则、脚本、模板和示例都在。下面这些随机器变化，仓库里留的是空位和检查，不是某一台电脑的路径。

| 要做的事 | 本机准备 |
|---|---|
| 出图、稿件检查、Word 组装 | Python ≥ 3.11，且不是 Windows 商店占位程序。`pip install -r requirements.txt` |
| Excel 表、参考文献 XML、矢量几何 | 已锁定：`openpyxl`、`lxml`、`fonttools` |
| 数据图复刻 | 在 `sci-figure-replica/config.json` 填写 `python_exe`、`rscript_exe`、`gallery_root` 三个绝对路径。同目录的 `config.local.json` 可覆盖它们，且不进入版本库。R 渲染需要 `ggplot2`、`patchwork`、`scales` |
| 可见参考文献 | Zotero 10（建议 ≥ 10.0.5，本地 API 写入）、Word 里的 Zotero 插件、用于重放 CSL 的 Node |
| 参考图重画成可编辑矢量 | Windows，已打开目标文档的 Adobe Illustrator CC 2019（23.x）或更新版本 |
| 自动实验 | Windows、Git，以及一次真实调用核验过的 Codex 或 Claude Code。PyTorch / CUDA 按课题环境准备 |

可选增强缺了会降级并报告：Arial（否则 matplotlib 使用 DejaVu Sans）、SciencePlots、PyMuPDF、kaleido。`svglite` 和 `ggbeeswarm` 对 R 复刻是可选的。

`medfig-illustrator` 的 PowerShell 按 `CELL_LCT_PYTHON` → `py` 启动器 → PATH 上的 `python.exe` 找解释器，这个解释器要能导入 Pillow 和 fontTools。PATH 上只有商店占位程序时：

```powershell
[Environment]::SetEnvironmentVariable("CELL_LCT_PYTHON", "<python.exe 的完整路径>", "User")
```

显式设置的解释器不存在或缺少这两个包时，脚本报 `PYTHON_OVERRIDE_UNUSABLE`，不会静默换一个。

`medical-sci-references` 在 Zotero 未开着或未允许本机程序通信时，停在就绪检查，不自行启动或修改 Zotero。Node 用来按选定 CSL 重放可见编号和文献表。

## 技能

图表 9 个，写作 11 个，课题与实验 3 个。

| 技能 | 作用 |
|---|---|
| `medfig-suite` | 入口与路由：判定任务交给哪个技能，列出下游需要的输入，本身不画图 |
| `medfig-plan` | 规划整套图表：panel 选型、图型多样性、表格规划，产出 `docs/<date>-figure-set-design.md` |
| `medfig-render` | 按规格渲染单张图；自带 `lib/figkit`（配置、样式、QA、导出与各类 panel） |
| `medfig-orchestrate` | 批量出多张图：并行 worktree、审查清单、台账与交付模板 |
| `medfig-outline` | 图表定稿后写 Methods / Results 写作大纲（docx + md），数字对照 `source.json` 回核，并按小节归档图、表、图注与代码 |
| `medfig-schematic` | 研究设计图 / 网络架构图：写生图模型的英文提示词，检查、打包、评估，逐轮迭代到定稿 |
| `medfig-illustrator` | 把已有参考图复刻成可编辑矢量；在已打开的 Illustrator 文档里原生重画，文字保持可编辑 |
| `scipilot-medimg-figure-skill` | `medfig-render` 调用的期刊样式、导出、文件自检，以及医学影像 panel。派生自 [Haojae/scipilot-figure-skill](https://github.com/Haojae/scipilot-figure-skill)（MIT），差异见其 `NOTICE.md` |
| `sci-figure-replica` | 科研数据图的代表单 panel 复刻、样式去重、对比 QA 与画廊。脚本、模板和示例在技能目录内，详见其 [README](sci-figure-replica/README.md) |

### 写作

| 技能 | 作用 |
|---|---|
| `medpaper-pipeline` | 写作侧入口：从图表规划到成品、Zotero 参考文献和第 13 步期刊适配，逐阶段调用并等作者确认；管理 `PROJECT.md` |
| `medical-sci-methods` | Methods 正文（英文成稿附中文对照与核查说明） |
| `medical-sci-legends` | 主图 / 附图图注与表题表注 |
| `medical-sci-results` | Results 正文 |
| `medical-sci-introduction` | Introduction（引用逐条核验 PMID） |
| `medical-sci-discussion` | Discussion（方法、结果、图注、引言齐备后才动笔） |
| `medical-sci-abstract` | 摘要（中英对照、关键词、Highlights；默认英文正文 ≤250 词） |
| `medical-sci-finalize` | 成品 Word（主稿 + 补充材料）、保留证据的全稿结构编辑，以及对应中文 / 已有双语稿同步 |
| `anti-defensive-writing` | `medical-sci-finalize` 每次都要实际读到的依赖，也可以单独使用。医学稿仍保留不利结果、必要限定和不确定性 |
| `medical-sci-references` | 从主稿抽取 PMID / DOI / arXiv，补入 Zotero，注入 Word 原生引文字段和文献表，并核对插入不变式 |
| `medical-sci-submission` | 按目标期刊和文章类型准备作者信息、声明、cover letter 和清单。可以处理独立 DOCX。准备材料不等于允许投稿 |

### 课题与实验

| 技能 | 作用 |
|---|---|
| `medical-research-plan` | 逐轮访谈、文献锚点、数据与伦理可行性、假设反证，产出可交给编程 agent 的研究与工程计划 |
| `medimg-experiment` | Windows 本地 2D/3D 分类与分割。在首次授权和固定数据 / 评价边界内，真实调用所选 Codex 或 Claude Code，按结果修订方法、代码和当前计划，并完成比较、冻结测试与归档 |
| `socratic-project-manager` | 用苏格拉底式问答把开发项目、研究或复杂想法推进到需求、设计与可执行交接 |

## 从哪里开始

- 一张纯影像网格（已导出的 PNG/JPG/TIF，加上掩膜、轮廓、热力图、放大框或比例尺）用 `scipilot-medimg-figure-skill`。
- 还没有图表规格用 `medfig-plan`。已有规格、画一张用 `medfig-render`。整套图用 `medfig-orchestrate`。定稿后的写作大纲用 `medfig-outline`。示意图用 `medfig-schematic`。参考图重画成矢量用 `medfig-illustrator`。
- 从出图写到投稿材料用 `medpaper-pipeline`。只写或修一节，直接用对应的 `medical-sci-*`。
- 分不清入口时用 `medfig-suite`。

非医学图表，以及用代码直接画的示意图，不在这套技能的范围内。

## 研究计划到自动实验

`medical-research-plan` 先形成可实施计划并完成 G1/G2/G3。作者首次确认具体效果规则、数据与科学边界、累计训练预算、修订和故障上限、整体截止、正式复核预留，再授予自动委托。`medimg-experiment` 负责代码实现、新上下文审查、可信基线、初筛、正式至少 3 个 seed、比较与贡献消融。负结果可以在授权内推动方法、代码和计划修订，不重新划分数据，也不降低贡献目标。

正式门全部通过即冻结并执行预定测试。测试成绩只报告，不用于继续搜索。当前计划、总索引和 PROJECT 在关键事件后更新，旧文档唯一归档，study 原始运行证据留在原位。依赖变化后，下游图表、正文、引用和投稿材料需要返工。投稿第 13 步和独立稿件入口继续可用。准备材料不代表允许实际投稿。`auto-optimize` 不是依赖。

首次委托用 `agent_backend` 选择 `codex` 或 `claude`。旧委托默认 Codex。选 Claude 时可以不安装 Codex，并使用本机 Claude Code 已有的连接配置。CLI 名称不是实际模型身份，实际模型另行记录。调用失败不自动换后端。详见[后端选择](medimg-experiment/references/agent-backends.md)。

自动模式见[实验执行协议](medimg-experiment/references/adaptive-execution.md)。模板空值要按具体课题确认后再填。合成 GPU 流程验收只证明执行协议，不能代替真实患者数据、科学或临床有效性、外部泛化。本仓库不发布本机后端验收记录。

## 只装其中几个

重复 `--skill` 即可，例如 `python install.py --update --skill medical-sci-finalize --skill medpaper-pipeline`。安装和核验会先装上运行依赖；只卸载所选技能时，仍可独立使用的依赖留在原地。依赖环和未知技能会拦住安装。

| 所选技能 | 一并装上 |
|---|---|
| 各节写作技能 | `medpaper-pipeline` |
| `medical-sci-finalize` | `anti-defensive-writing`、`medpaper-pipeline` |
| `medfig-outline`、`medfig-schematic`、`medfig-orchestrate` | `medfig-render`，render 再带上 `scipilot-medimg-figure-skill` |
| `medfig-plan` | `medpaper-pipeline`、`medfig-render`（含 scipilot） |
| `medfig-render` | `scipilot-medimg-figure-skill` |

`medfig-outline` 的检查脚本直接导入 figkit。`medfig-schematic` 用同一套禁用词表。`medfig-plan` 要读 render 的配方索引 `examples/gallery/INDEX.md`，有论文项目时还要读 pipeline 的口径表格式。

安装包排除缓存、技能根下的 `tests/`、`evals/`、`validation/`、直接位于 `scripts/` 的 `test_*.py` 与 `*_test.py`，以及 `examples/**/out`、`examples/**/data`。运行所需的 `evaluate_test.py` 和其他目录里文件名含 test 的运行资产保留。开发测试和验证记录在本机开发归档，不进入产品仓库或运行包。

## Codex：设置 FIGKIT_LIB

图脚本模板默认从 `~/.claude/skills/medfig-render/lib` 导入 figkit。技能只装在 Codex 时：

```bash
export FIGKIT_LIB=~/.codex/skills/medfig-render/lib          # bash / Git Bash
```

```powershell
$env:FIGKIT_LIB = "$HOME\.codex\skills\medfig-render\lib"  # 当前会话
[Environment]::SetEnvironmentVariable("FIGKIT_LIB", "$HOME\.codex\skills\medfig-render\lib", "User")
```

`scipilot_scripts` 默认指向 `~/.claude/skills/scipilot-medimg-figure-skill/scripts`。只装在 Codex 时，写进项目的 `figkit.toml`：

```toml
scipilot_scripts = "~/.codex/skills/scipilot-medimg-figure-skill/scripts"
```

`FIGKIT_TOML` 指向项目的 `figkit.toml`。figkit 从这份配置读路径。

## 运行诊断

完整手稿修订可以运行只读的跨版本文风诊断：

```bash
python medpaper-pipeline/scripts/lint_manuscript.py candidate/04_manuscript --previous before/04_manuscript --report process/prose-comparison.json
```

它列出重复短语、词族密度、句长和图表括号。这些是线索。词频变化不判定写作失败，诊断也不代替稿件审查。

## 主线、来源与版本

图表和大纲按科学问题组织。预注册、探索性分析、训练和重新拟合按实际情况保留。清理开发术语时，研究设计和不利结果仍写在稿件里。细则见 `medfig-plan/references/mainline_rules.md`。

各技能的规则来自真实论文出图里积累的缺陷，整理成通用规则并按编号引用（`medfig-plan/references/lessons.md`）。第三方思路和代码见 [`NOTICE.md`](NOTICE.md)。

当前发布标签是 [2026-11-17](https://github.com/yubinfengjjd/research-jjd/releases/tag/2026-11-17)。标签之后的依赖和介绍修订见 [`CHANGELOG.md`](CHANGELOG.md)。

---
name: medical-research-plan
description: "Use throughout a medical or medical-AI research project to anchor the initial study plan (Step 1 + conditional branches), evolve the plan after each experiment round from real validation evidence, and converge to a clean final route for figures and manuscript writing. Supports both medical-imaging AI and retrospective clinical data analysis."
metadata:
  version: "1.0.0"
---

# 医学科研滚动规划伙伴

这是一个**贯穿课题全程的活计划伙伴**，而不是第 0 天写完就束之高阁的一次性开题生成器。

真实科研几乎不可能在第 0 天就预设好完美的终局模型和全部消融。本技能陪伴课题走完 **立项定锚 → 跑第一步并诊断 → 按真实实验反馈迭代延展/换路线 → 收敛唯一终局** 的完整滚动周期，同时兼顾**医学影像 AI** 与**回顾性临床数据分析**。

## 三种工作模式（按课题当前进度自动进入）

每次唤起先读已有项目材料（如 `00_plan/project-plan.md`、`01_analysis/<study>/report.md` 或用户贴出的实验结果），再用一句话说明将进入哪种模式：

1. **`start`（开题定锚 · 做好第一步 + 条件分支）**：
   - 适用于空白想法、已有数据或初版设想。
   - **绝不在第 0 天硬编“三层创新终局”**：只把**当前第一步**写实到立刻可跑（临床问题、数据与防泄漏划分、主指标、强基线 + 错例诊断或最小核心验证），其余潜在创新写成 **2–3 条条件触发的延伸分支**（“若第一步观察到现象 X → 往分支 A 延展；若观察到 Y → 往分支 B 延展”）。
   - 文献只做**轻量摸底**（3–5 篇最核心基线与最近竞争论文，确认没撞车、基线选对即可开工）。
2. **`evolve`（实验后迭代延展 · 课题进行中持续唤起）**：
   - 适用于跑完一步实验（基线完成、错例分析出来、或某轮探索不理想）后重新唤起。
   - 读入当前 `00_plan/project-plan.md` 与最新实验报告/指标，先做**实证复盘**（已证实什么、瓶颈在哪、为什么失效），给出 **2–3 个具体下一步方向**（深化机制、换至候选分支、补充消融/外部验证或收窄主张）并附审稿人视角质疑。
   - 用户拍板后，先把旧计划归档至 `_archive/`，原地更新 `00_plan/project-plan.md`（已跑通的成果浓缩为“既定实证基础”，淘汰分支移出主文），按需针对新机制**滚动补检 3–5 篇精准锚点论文**，并同步生成给 `medimg-experiment` 的下一轮条目配置。
3. **`converge`（收敛定稿 · 衔接出图与写论文）**：
   - 适用于关键实验与锁定测试全部完成后。
   - 剥离探索期备选分支，把 `00_plan/project-plan.md` 收口为**唯一清晰主线的最终研究计划**，更新 `PROJECT.md` 备注，直接衔接 `medfig-plan` 与 `medpaper-pipeline`。

## 精简两段式开题节奏（`start` 模式）

详细规则见 [访谈与滚动演进](references/interview-and-evolution.md)：

- **灵活补齐缺口**：材料还比较粗时，每轮合并问 **2–3 个高信息量问题**（优先使用交互弹窗或编号选项卡，带推荐项与代价说明）；材料已充分时直接一步出草案，不再强行拖成 10 轮问答。
- **仅两处明确拍板点**：
  1. **拍板 1（方向与任务定位）**：临床问题、目标人群与使用情景、任务输入/输出、标签与参考标准、数据与防泄漏划分单位、核心基线。
  2. **拍板 2（当前阶段方案与下一步）**：第一步实验设计、主指标与统计口径、当前步骤滚动算力估算、条件延伸分支及执行前待办。
- **不因正常在办事项卡死定稿**：伦理审批、数据权限申请、待测算力等统记入 **“执行前待办”**，不阻断方案定稿。只用三种清晰中文状态标注：**已确认 / 待核实 / 执行前待办**。
- **可选独立审查**：用户主动要求或在复杂/高风险节点时，再调用独立只读子代理做审稿人模拟核查；常规迭代不强设审查卡点。

## 按需加载参考

- 访谈节奏、滚动演进（`evolve`/`converge`）与目录归档：[interview-and-evolution.md](references/interview-and-evolution.md)
- 动机因果链、假设与反证、审稿人模拟、样本量与临床统计：[research-design.md](references/research-design.md)
- 分阶段文献锚点、数据与伦理核查、独立划分防泄漏：[evidence-and-data.md](references/evidence-and-data.md)
- 医学影像深度学习专章（仅影像 DL 课题加载）：[imaging-dl.md](references/imaging-dl.md)
- 与 `medimg-experiment` v3 双向协同与 `study-config.json` 交接：[experiment-handoff.md](references/experiment-handoff.md)

## 落盘约定与质量检查

- **极简目录，零冗余污染**：
  - 检测到 `PROJECT.md` 时，写入 `00_plan/project-plan.md`（使用 [主文模板](assets/project-plan-template.md) 精炼 7 节结构，不写空栏、不写免责套话、不塞 12 列官僚大表）；仅在跨会话续接或需留存完整检索式时附带 1 份轻量 `00_plan/notes.md`。
  - 没有 `PROJECT.md` 时写入用户指定目录，不擅自新建 `PROJECT.md`。
  - 每次 `evolve` / `converge` 更新前，先将旧版 `project-plan.md` 归档至 `_archive/<日期>_plan_v<旧版>/00_plan/project-plan.md`（独立课题放 `history/`），确保 `00_plan/` 永远只有当前这一份干净计划书。
- **轻量校验脚本**：定稿或交接 `medimg-experiment` 前，可运行零依赖检查器：
  ```bash
  python -X utf8 scripts/validate_plan.py 00_plan/project-plan.md [--study-config 01_analysis/study-config.json]
  ```
  检查 7 项核心要素（主线章节、患者划分防泄漏说明、主指标与强基线、当前步骤可执行任务、无残留模板占位与防御性 JSON/折叠垃圾，以及可选与 `study-config.json` 口径一致）。

## 权限边界

本技能只负责规划、实证复盘、文献检索（仅发送公开术语，绝不外发私人数据或未公开完整方案）与计划书/配置草案维护；不自行发起训练、下载未授权数据或提交伦理审批。实际训练与锁定测试交接给 `medimg-experiment`。

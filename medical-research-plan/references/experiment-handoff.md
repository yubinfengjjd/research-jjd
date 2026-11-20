# 与 medimg-experiment v3 的双向协同交接

本参考用于医学影像 AI 课题将计划书交接给 `medimg-experiment`（v3 轻量协同版）执行，以及在实验反馈后回到本技能演进计划书。

## 1. 从计划书生成 `study-config.json` 草案（`start` → 实验）

在 `start` 模式拍板 2 完成后，可直接从 `00_plan/project-plan.md` 提炼一份开箱可用的 `study-config.json` 草案（对应 `medimg-experiment/assets/study-config-template.json`，`schema_version: 3`），帮助用户一步启动：

| 计划书内容 | 映射到 `study-config.json` | 探索期是否锁死 |
|---|---|---|
| 课题名称 / 任务类型 | `study_id`、`task`（任意任务名，如 `multiclass_classification`、`3d_segmentation`） | `study_id` 固定 |
| 当前核心假设 | `hypothesis` | 可随 `revise` 更新 |
| 计划书路径与代码目录 | `plan_path`、`project_root`、`code_dir` | 固定 |
| 主指标与辅助指标 | `primary_metric`（`name` / `direction` / 可选 `target`）、`secondary_metrics` | **主指标定义锁死** |
| 数据与防泄漏划分 | `data.*` + `split_audit.command` | **审计通过后锁死 `split_hash`** |
| 锁定测试集策略 | `test.policy`（`locked` + `command`，或 `none` + `rationale`） | **探索期严格禁止运行** |
| 本阶段实验矩阵 | `reference`（参照基线）+ `entries`（支持 `screening_command` 与 `command`） | **可随 `revise` 自由增删改** |
| 本步滚动探索预算 | `budgets`（`max_routes`、`max_training_seconds`、`run_timeout_seconds`、可选 `deadline_utc`） | 跨轮累计不重置 |
| 本机运行环境 | `environment`（真实 Python 绝对路径，拒绝 WindowsApps 占位；`device`；`inherit_cache: true`） | 不强制锁全量包版本 |

> 交接仅生成配置草案与计划书，不擅自开始训练、下载大型未授权权重或覆盖已有实验目录。

## 2. 实验反馈回流到计划书（实验 → `evolve` → 实验）

- **小幅调参或通宵预算内换模块**：可直接在 `medimg-experiment` 内调用 `revise` 推进（自动归档旧计划书并复用未受影响的 Baseline）。
- **需要重新思考研究方向、增补新机制、补充文献锚点或重构主张**：回到 `medical-research-plan` 进入 `evolve` 模式，读取 `01_analysis/<study-id>/report.md` 与错例分析，与用户共同拍板下一阶段路线，更新 `00_plan/project-plan.md` 并输出下一轮 `entries_vN.json`，再交回 `medimg-experiment` 调用 `revise` 继续执行（已跑完的强基线无需重训）。

## 3. 最终定稿衔接下游写作（实验完成 → `converge` → `medfig-plan` / `medpaper-pipeline`）

在 `medimg-experiment` 完成 `pretest-check`、`freeze`、`test` 与 `finalize` 后，确保 `00_plan/project-plan.md` 已收口为唯一最终路线（可通过 `validate_plan.py 00_plan/project-plan.md --mode converged` 核验），随即交接给 `medfig-plan` 规划论文图表与 `medpaper-pipeline` 撰写各节正文。

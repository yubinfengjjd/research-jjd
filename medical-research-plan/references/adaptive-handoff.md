# 计划书与实验协同交接（v3 轻量模式）

当医学影像 AI 课题准备交给 `medimg-experiment` 执行有界探索（含半自动通宵探索）时加载本参考。适用通用医学影像 AI 任务（分类、多分类、多标签、2D/3D 分割、回归等）。

## 1. 开跑前首次对齐（轻量清单）

保留 G1/G2/G3 真实科学确认后，与作者一次性确认以下核心边界，并填入 `medimg-experiment/assets/study-config-template.json`：

| 交接项 | 首次必须明确 | 探索期是否锁死 |
|---|---|---|
| 核心问题与主指标 | 研究问题、`primary_metric.name` 与方向（`higher`/`lower`），确保跨路线横向可比 | **锁死** |
| 数据与患者划分 | 只读数据路径、分组单位（如 `patient_id`）、标签来源、划分防泄漏审计脚本 | **审计通过后锁死 `split_hash`** |
| 锁定测试集 | 测试集策略（`locked` + 冻结测试脚本，或 `none` + 理由） | **探索期严禁触碰** |
| 探索预算 | `max_routes`（路线修订轮数上限）、`max_training_seconds`（总训练时长）、`run_timeout_seconds`、可选 `deadline_utc` | 全局累计不重置 |
| 运行环境 | 真实 Python 绝对路径（拒绝 WindowsApps 占位）、设备（`cuda`/`cpu`/`mps`）、是否复用本机预训练缓存（默认 `true`） | 不强制锁死全量包版本 |
| 初始路线与条目 | 强 Baseline 参照条目、初版 Proposed 与消融/对比命令（支持任意 PyTorch/timm/MONAI/nnU-Net 最小侵入脚本） | **可随验证结果自由调整** |

## 2. 授权内可变 vs 必须停下交作者

- **授权内自动协同（可通宵连续推进）**：验证集结果不理想时，宿主 Agent 可直接诊断日志、调整模型架构/核心模块/损失/数据预处理，以及**增删改 Proposed、Ablation 与 Comparison 条目**，并同步更新 `00_plan/project-plan.md`；未受影响的 Baseline 结果自动复用，避免重复浪费算力。
- **必须停下汇报由作者拍板**：
  1. 划分防泄漏审计失败，或需要变更患者划分/主指标定义；
  2. 达到验证预期、耗尽 `max_routes` / `max_training_seconds` 或到达 `deadline_utc` —— 此时导出完整报告向作者总汇报，**由作者从各轮路线中选定最终路线**；
  3. 冻结与锁定测试前：执行一次独立只读核查（`pretest-check`），再由作者确认 `freeze` 并运行 `test`；
  4. 需要下载新的大型未授权预训练权重或外部代码仓库。

## 3. 计划书协同与最终收口原则

- **`00_plan/` 永远只保留一份干净的 `00_plan/project-plan.md`**：不留 `draft` 草案，不往正文注入裸 JSON 块或 `<details>` 历史折叠块，也不对 `00_plan/project-plan.md` 施加字节哈希互锁（作者随时可手动编辑）。
- **先归档、再更新**：每次 `revise` 或 `finalize` 替换计划书前，`medimg-experiment` 自动将旧版 `00_plan/project-plan.md` 完整归档到 `_archive/<日期>_plan_v<N>/00_plan/project-plan.md`，淘汰路线与所有失败运行明细保留在 `01_analysis/<study-id>/routes.jsonl` 与 `report.md` 中。
- **最终定稿**：`finalize` 后，`00_plan/project-plan.md` 收口为**唯一干净的最终选定路线**，同步 `01_analysis/README.md` 与 `PROJECT.md`，直接衔接 `medfig-plan` 与 `medpaper-pipeline`。

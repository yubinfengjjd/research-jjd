# 计划书与实验协同及最终路线收口

本技能的核心目标是让 `00_plan/project-plan.md` 与当前实验进度始终保持一致，同时保证项目目录干净整洁。

## 1. 零污染与零互锁原则

- **`00_plan/` 永远只有一份活跃计划书**：不生成 `project-plan.draft.md` 等并存草案，避免错误版本或旧计划污染项目目录。
- **正文保持纯人类可读 Markdown**：控制器绝不向 `00_plan/project-plan.md` 注入裸 JSON 块、机器投影标签或 `<details>` 历史折叠块。
- **取消字节哈希互锁**：作者本人或 `medical-research-plan` 随时可以直接手动编辑 `00_plan/project-plan.md` 或 `PROJECT.md`，控制器不会因文件被外部编辑而报错停机。
- **替换前必归档**：调用 `revise --plan-file <新版.md>` 或 `finalize --plan-file <终版.md>` 时，控制器会先把当前的 `00_plan/project-plan.md` 完整复制到 `_archive/<YYYY-MM-DD>_plan_v<旧版本>/00_plan/project-plan.md`（独立 study 归档至 `<STUDY>/plans/history/`），再用新版原子替换。

## 2. 实验不理想时的路线修订（`revise`）

当某轮验证集表现不佳或诊断发现模块无效时：

1. 先按最新有效实验证据更新计划书文本（写清新的技术路线、架构/损失/预处理变动与当前实验矩阵，移除已淘汰路线的主文描述）；
2. 若实验条目变化（新增/删除/修改 Proposed、Ablation 或 Comparison），准备新的 `entries_vN.json`；
3. 调用 `controller.py revise`：
   ```powershell
   & $PY -X utf8 $CTRL revise --root $STUDY `
     --summary "v1 注意力模块验证集无增益，切换为多尺度特征融合 v2 并更新消融" `
     --entries-json entries_v2.json `
     --plan-file updated_project_plan.md
   ```
4. **自动基线复用**：只要 `baseline` / `comparison` 条目的训练命令未变且未被显式列入 `--invalidate-entries`，控制器自动保留其上一轮已完成的多 seed 验证结果，无需重复消耗 GPU；若修改了全局预处理导致旧基线不可比，传入 `--invalidate-entries baseline` 显式重跑。

## 3. 实验定稿收口（`finalize`）

作者选定最终路线并完成锁定测试后：

1. 将 `00_plan/project-plan.md` 整理为**唯一最终路线定稿版**（只呈现最终保留方案与冻结实证结果；淘汰路线和失败运行明细安静留在 `01_analysis/<study-id>/routes.jsonl`、`report.md` 与 `_archive/` 中）；
2. 运行：
   ```powershell
   & $PY -X utf8 $CTRL finalize --root $STUDY --plan-file final_clean_plan.md
   ```
3. 控制器自动归档前一版计划书、原子写入终版 `00_plan/project-plan.md`、更新 `01_analysis/README.md` 汇总表与 `PROJECT.md` 变更记录，并导出终版 `report.md` / `report.json` 供下游 `medfig-plan` 与 `medpaper-pipeline` 直接读取。

---
name: medimg-experiment
description: Use when running a local medical-imaging AI experiment that co-evolves with the research plan (including bounded overnight exploration, route revision with baseline reuse, split-leakage audit, pre-test independent check, locked test evaluation, and clean final plan convergence). Supports classification (binary/multi-class/multi-label), 2D/3D segmentation, and regression.
---

# 医学影像实验（计划书协同版）

本技能让 **研究计划书（`00_plan/project-plan.md`）与实验执行双向协同**：按计划跑基线和初版方案，若验证集结果不理想，在授权预算内诊断问题、调整架构/损失/预处理/消融条目并同步更新计划书，最后由作者选定胜出路线、经一次独立测试前核查后跑锁定测试集，并将计划书收口为**唯一干净的最终路线**。

支持通用医学影像 AI 任务（二分类、多分类、多标签、2D/3D 分割、回归等）与任意主指标（BACC、Macro-F1、Macro-AUROC、Dice、HD95、AUPRC 等）；最小侵入接入自写 PyTorch、timm、MONAI、nnU-Net 等代码，默认继承本机预训练权重缓存。

## 三条不可妥协的科学红线

其余流程保持轻量化，但以下三条由控制器硬性守住：

1. **患者/分组划分零泄漏**：任何训练开始前必须通过 `audit`，确保 `train / val / test` 的 `group_ids` 严格互斥并锁定 `split_hash`。发现泄漏立即停止，不得为了提分重划数据。
2. **锁定测试集严格隔离**：探索期禁止触碰测试集；仅在作者选定最终路线、完成一次独立只读核查（`pretest-check`）并执行 `freeze` 后，才能运行 `test`。测试成绩只报告、不回流选型。
3. **证据真实与目录干净**：所有运行日志、原始指标、失败记录和路线演变完整保存在 `01_analysis/<study-id>/`（不编造或篡改数字）；`00_plan/project-plan.md` 永远只保留当前唯一可读计划书，旧版整份归档至 `_archive/`，**绝不在 `00_plan/` 留草案、裸 JSON 块或折叠历史残骸**。

## 协作节奏：半自动有界探索

本技能由**当前宿主 Agent 长会话直接驱动**（如 Claude Code / Codex / Antigravity `/goal`），不再拉起易崩溃的后台多 CLI 守护进程。

1. **首次确认（开跑前一次对齐）**：
   - 与作者确认：数据路径与只读权限、患者划分脚本、主指标与方向（固定用于跨路线公平对比）、锁定测试策略、本机真实 Python 解释器（拒绝 WindowsApps 占位程序）与 GPU 设备，以及**探索预算**（例如最多 `max_routes: 3` 轮路线尝试、`max_training_seconds: 28800` 总训练时长、可选 `deadline_utc`）。
   - 填写轻量配置 [study-config-template.json](assets/study-config-template.json)（字段说明见 [config-and-protocol.md](references/config-and-protocol.md)）。
2. **初始化与划分审计**：
   ```powershell
   & $PY -X utf8 $CTRL init --root $STUDY --config $CFG --authorization "作者确认的预算与探索范围"
   & $PY -X utf8 $CTRL audit --root $STUDY
   ```
3. **授权内自主探索循环（可通宵连续推进，绝不碰测试集）**：
   - 先跑强 `baseline` 建立可靠参照，再跑 `proposed` / `ablation` / `comparison`（可先用 `screening` 快速验证，有希望再补全多 seed `formal`）：
     ```powershell
     & $PY -X utf8 $CTRL run --root $STUDY --entry baseline --seed 0 --phase formal
     ```
   - 遇到 OOM/报错/非零退出时，读取 `runs/<run-id>/train.log` 诊断修复代码后继续重跑（失败耗时自动计入总预算，不触发死锁停机）。
   - **结果不理想 → 修订路线并协同更新计划书**：在固定患者划分、测试集与主指标定义的前提下，允许自由调整模型架构、损失函数、预处理/增强，以及**增删改消融条目与对比方法**。同步将 `00_plan/project-plan.md` 更新为最新可读版本后，调用 `revise`（控制器先归档旧计划书再更新，并自动复用未受影响的 Baseline 结果）：
     ```powershell
     & $PY -X utf8 $CTRL revise --root $STUDY --summary "v1 未优于基线，改为方案 v2 并调整消融矩阵" --entries-json entries_v2.json --plan-file new_plan_v2.md
     ```
   - 达到预期目标、耗尽 `max_routes` / `max_training_seconds` 或到达 `deadline_utc` 时，调用 `export` 生成 [report.md](references/plan-sync.md) 并向作者总汇报各路线验证结果，**停下来等待作者选定最终路线**。
4. **独立测试前核查 → 冻结 → 锁定测试 → 定稿收口**：
   - 作者选定最终路线后，启动一次独立只读核查（详见 [verification-and-testing.md](references/verification-and-testing.md)），核验无测试泄漏、划分一致、代码与计划书声明相符，登记 `pretest-check`；
   - 执行 `freeze` 锁定最终条目，再逐条目运行 `test`（仅报告）；
   - 最后执行 `finalize`，将 `00_plan/project-plan.md` 收口为**唯一干净的最终定稿路线**，同步 `01_analysis/README.md` 与 `PROJECT.md`，交给 `medfig-plan` / `medpaper-pipeline` 进入出图与写作阶段。

## 重要边界

- **外部编辑零互锁**：作者或其他技能随时可以直接编辑 `00_plan/project-plan.md` 与 `PROJECT.md`，控制器不再因字节哈希变动而报错停机；每次替换前都会先将现有版本完整归档到 `_archive/`。
- **不自动安装全局驱动或私自联网下载未授权权重**：默认继承本机已有 `TORCH_HOME` / `HF_HOME` / `TIMM_CACHE_DIR` 缓存；需要下载新的大型预训练权重或外部研究代码仓库时，先向作者确认。
- **无 `PROJECT.md` 时保持独立 study**：所有历史计划快照存于 `<STUDY>/plans/history/`，不擅自新建论文项目目录。

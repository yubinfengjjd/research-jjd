# 测试前独立核查与锁定测试集保护

为了兼顾研发效率与科学严谨性，本技能在探索期不做每轮小改动的繁琐双代理审查，而是把审核力集中到**冻结方案、首次触碰锁定测试集前的唯一硬关口**。

## 1. 测试前独立核查（`pretest-check`）

当探索收敛、作者从 `report.md` 中选定拟冻结的最终路线后，在运行 `freeze` 与 `test` 之前，安排一次**独立只读核查**（可由新上下文只读子代理或独立人工审阅完成），重点只查 4 件事：

1. **无测试集泄漏**：训练/预处理/调参脚本全程只读取 train/val，未触碰锁定测试集路径或标签；
2. **划分一致性**：当前代码读取的划分与 `audit` 锁定的 `split_hash` 一致；
3. **代码与最终路线一致**：`00_plan/project-plan.md` 描述的最终方法、对比基线、消融设计与实际运行代码吻合；
4. **基线公平性与指标真实性**：主方法与基线使用相同评价口径与充分训练，原始日志与 `result.json` 无异常篡改。

核查通过后登记：

```powershell
& $PY -X utf8 $CTRL pretest-check --root $STUDY `
  --reviewer "independent-readonly-reviewer" `
  --verdict pass `
  --summary "已核对 split_hash、训练脚本无测试读取、代码与 v2 路线一致" `
  --checked-files "train.py,audit_split.py,evaluate_test.py"
```

若核查返回 `block`，修复问题并在当前路线补跑受影响验证条目后重新执行 `pretest-check`。任何 `revise` 都会清空旧的 `pretest_check` 记录。

## 2. 冻结与锁定测试（`freeze` → `test`）

1. **作者确认冻结**：
   ```powershell
   & $PY -X utf8 $CTRL freeze --root $STUDY `
     --entries "baseline,proposed_v2,ablation_no_aux" `
     --statement "作者审阅 v1/v2 验证集报告，确认冻结 v2 路线并执行锁定测试"
   ```
   冻结后，控制器拒绝任何进一步的 `run` 与 `revise`。
2. **执行锁定测试集评估**：
   ```powershell
   & $PY -X utf8 $CTRL test --root $STUDY --entry baseline
   & $PY -X utf8 $CTRL test --root $STUDY --entry proposed_v2
   ```
   - 控制器依次对每个冻结条目的各 seed 运行目录调用 `test.command`；
   - 若测试脚本生成 `cases.jsonl`，自动校验其 `case_id` 集合与 `audit` 登记的 `test` 分组完全一致；
   - 每次调用累加 `test_looks`，测试成绩仅写入 `tests/` 与 `report.md`，绝不回流用于继续搜索。若测试表现低于预期，如实报告并记录原因。

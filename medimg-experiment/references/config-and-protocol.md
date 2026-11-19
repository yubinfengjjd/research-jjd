# 轻量配置与最小侵入训练协议

## 1. 配置文件（`schema_version: 3`）

复制 `assets/study-config-template.json` 并按实际课题填写。控制器只锁定与科学公平性直接相关的字段，不再要求预填全量 Python 包版本、静态依赖清单或硬编码方差上限。

| 字段 | 说明 | 是否探索期锁死 |
|---|---|---|
| `study_id` / `task` | 课题标识与任务描述（任意任务，如 `multiclass_classification`、`3d_segmentation`、`regression`） | `study_id` 固定 |
| `hypothesis` | 当前研究假设 | 可随 `revise` 更新 |
| `plan_path` / `project_root` | 初始计划书绝对路径；可选论文项目根目录（省略时自动向上查找 `PROJECT.md`） | 固定 |
| `code_dir` | 实验代码目录绝对路径（控制器直接以此为工作目录运行，不强制拷贝白名单） | 固定 |
| `primary_metric` | `{name, direction ("higher"\|"lower"), target (可选)}`；保证多轮路线横向可比 | **`name` 与 `direction` 锁死** |
| `secondary_metrics` | 可选辅助指标列表 `[{name, direction}]` | 可扩展 |
| `data` / `split_audit` | 只读数据路径、分组单位（如 `patient_id`）及防泄漏审计命令 | **审计通过后锁死 `split_hash`** |
| `test` | `policy: "locked"`（附冻结测试命令）或 `"none"`（附理由） | **探索期严格禁止运行** |
| `reference` / `entries` | 参照基线 ID 与实验条目列表（`baseline` / `proposed` / `ablation` / `comparison`） | **可随 `revise` 自由增删改** |
| `seeds` | 正式评估推荐 `>= 3` 个不重复整数 seed | 可按需跑指定 seed |
| `budgets` | `max_training_seconds`（跨轮总训练秒数）、`run_timeout_seconds`（单次超时）、`max_routes`（路线修订上限）、可选 `deadline_utc` | 全局累计不重置 |
| `environment` | `python`（真实绝对路径，拒绝 WindowsApps 占位）、`device`（`cuda`/`cpu`/`mps`）、`inherit_cache`（默认 `true`，复用本机 `TORCH_HOME`/`HF_HOME`） | 不强制包版本全等 |
| `ci` | 可选 `null` 或 `{statistic: "mean_per_case"\|"binary_auroc", resamples, level, seed}` | 可选增强，不阻断训练 |

## 2. 最小侵入命令与输出约定

命令支持任意 `argv` 字符串数组（支持自写 PyTorch、`python -m`、MONAI、timm 或包装 nnU-Net CLI），控制器在启动前替换以下占位符，同时通过环境变量传给子进程：

- 占位符：`{python}`、`{seed}`、`{output_dir}`、`{entry}`、`{phase}`
- 环境变量：`ME_RUN_ID`、`ME_ENTRY`、`ME_PHASE`、`ME_SEED`、`ME_OUTPUT_DIR`、`ME_STUDY_ROOT`、`ME_DEVICE`、`ME_SPLIT_HASH`、`TMP`、`TEMP`

**训练脚本唯一硬要求**：退出码为 `0`，并在 `{output_dir}/result.json` 写入 JSON：

```json
{
  "metrics": {
    "bacc": 0.8612,
    "macro_f1": 0.8490
  },
  "artifacts": ["best.pt"],
  "notes": "可选：关键超参或诊断备注"
}
```

- 不再强制实时逐行写带时区 `metrics.jsonl`；
- 不再强制 `worktree` 结束时零未跟踪文件；
- 若课题使用逐病例标量均值或二分类 AUROC，可额外写入 `{output_dir}/cases.jsonl`（每行 `{"case_id": "...", "value": ...}` 或 `{"case_id": "...", "label": 0/1, "score": ...}`），`export` 时自动计算相对基线的配对 bootstrap 区间；多分类/多标签/全局指标直接忽略即可。

## 3. 划分审计脚本输出约定

`split_audit.command` 将 JSON 写入 `{output}`：

```json
{
  "group_unit": "patient_id",
  "splits": {
    "train": {"group_ids": ["P001", "P002"], "class_counts": {"c0": 1, "c1": 1}},
    "val": {"group_ids": ["P003"], "class_counts": {"c0": 1, "c1": 0}},
    "test": {"group_ids": ["P004"], "class_counts": {"c0": 0, "c1": 1}}
  }
}
```

控制器校验 `group_unit` 一致、各划分内部无重复且跨划分零重叠，生成不可变 `split_hash`。

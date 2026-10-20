---
name: medimg-experiment
description: Use when implementing or running an authorized Windows-local medical-imaging AI experiment from a confirmed research plan, including bounded autonomous method, code and plan revision, fresh-context review, actual training, multi-seed comparisons, freezing and final testing. Supports 2D/3D classification and segmentation.
---

# 医学影像实验

先读取作者实际计划与数据、代码和环境证据。仅解释计划或检查环境时只做对应工作；执行训练须有真实的契约确认和授权。训练本地运行，数据只读，保留原计划和失败结果。

## 选择执行方式

- **授权内自动闭环**：作者希望无人值守地读结果、诊断、换方法和重训时，读取 [adaptive-execution.md](references/adaptive-execution.md)。使用 schema-v2 `matrix` 契约加单独的 `AdaptiveDelegation@1` 委托、首次委托选定的真实本地 Codex 或 Claude Code CLI 和后台 supervisor。首次确认后，授权内不反复要求作者确认；遇到固定边界、下载资源、预算或测试后纠错等关口停下。不要将单候选 worker 当作完整闭环。
- **人工逐步执行**：作者要逐候选决定，或没有可用的自动调用后端时，使用原有 `matrix`（基线/主方法/消融/比较）或 `search`（基线→探索→正式复核）。读取 [setup-contracts.md](references/setup-contracts.md)、[execution-protocol.md](references/execution-protocol.md) 和 [recovery.md](references/recovery.md)。此方式异常仍走汇报→回退→等待新方向，不冒充自动闭环。

自动闭环支持显式 `matrix`；后端选择、原生程序和只读工具边界见 [agent-backends.md](references/agent-backends.md)。未指定后端的旧委托仍用 Codex，失败不自动换后端。`auto-optimize` 不是依赖；它的通用优化循环不能替代本技能的数据、统计、测试和证据门。

## 固定的科学边界

1. 先核验患者等分组 ID、标签来源与 train/val/test。已有划分冻结；缺划分时按作者确认的分组规则生成、审计、首次确认后冻结。缺 ID、泄漏或标签定义不清时停止，不能猜测或重新划分以提高成绩。
2. 任务、标签、分组划分、主指标及计算单位、checkpoint 规则、正式 seed、对照与贡献目标固定。网络、核心模块和损失可以在委托范围内替换。整体效果好但模块没有贡献时继续核验/改方法；不能删掉贡献目标来宣布达标。
3. 合理基线先成立。文献数字只在条件可比时辅助设定预期；不能用未核验的偏弱本地基线宣布优势。低于预期先查数据适配、训练和评价，再讨论方法。
4. 开发只看训练/验证。初筛不能当论文证据；有希望或难判断的候选再充分训练、≥3 seed、正式比较与消融，按预先确认的患者级统计规则判断。
5. 正式规则全部达到即停止探索、冻结方案、统一测试。测试低分保留并报告，不再回流搜索。已见测试后发现评价错误，须新上下文审查和作者具体确认修复/复算，保留全部测试历史。

## 开始与推进

先核实真实 Python、Git、设备、精确依赖版本、磁盘与可读数据。使用宿主指定解释器（使用已确认的真实解释器绝对路径，并启用 UTF-8），拒绝 WindowsApps 的占位程序；不把 CUDA 不可用静默改为 CPU。

由 `medical-research-plan` 提供可实施计划。提出完整契约和自动委托供作者首次确认：科学规则、允许修改文件/参数、训练总时长、方法修订轮数、故障重试次数、整体截止时间、正式复核预留和当前环境。每课题设数值，不编通用门槛。普通依赖可按已经批准的隔离安装范围处理；研究代码、预训练权重下载必须具体确认，不能借依赖安装绕过。

候选代码改变后，先用新上下文只读审查实际源码和命令，审查通过才允许受管训练。同代码仅换 seed 可复用绑定的审查。自动执行由控制器真实调用所选后端的独立 CLI 会话，保存真实会话标识和日志；不能伪造审查记录，也不把同模型家族审查等同独立科学验证。人工模式见 [independent-review.md](references/independent-review.md)。

训练错误、OOM、NaN 和“训练正常但无优势”分别记录。授权内排查、修复、重新审查并重跑，所有失败和预算累计保留。可靠完整 checkpoint 经协议核验后续训；否则以新 run 重跑当前 seed。主动暂停必须等作者明确恢复。对未覆盖的外部环境故障，不宣称已可靠恢复。

## 项目计划与资产

检测到 `PROJECT.md` 时，study 默认 `01_analysis/<study-id>/`，保持受管目录原位。关键事件后实质更新 `00_plan/project-plan.md` 的当前方法/技术路线、真实状态、有效结果、预算和下一步；不能只在末尾追加“改过了”。旧文档按 `medpaper-pipeline` 规则存入 `_archive/<日期或日期_2>/<原相对路径>`，原始 runs、权重和失败证据不搬家。

同时同步 `01_analysis/README.md` 和 `PROJECT.md` 目录说明/变更记录，不新增实验阶段行；区分最新尝试、当前有效结果和最终冻结。条件不变的旧结果可沿用并标来源，受代码、评价、预处理或环境影响的结果失效/重算。影响下游时标需返工，不自动改写正文或图表。自动投影有事件回执，重复/中断重入先核对并补全。没有 `PROJECT.md` 则保持独立 study，不擅自新建论文项目。

所有操作从实际安装目录的 `scripts/controller.py` 进入，不直接运行 worker。资源见 [contract-template.json](assets/contract-template.json) 和 [adaptive-contract-template.json](assets/adaptive-contract-template.json)。演示验证见 [真实合成 GPU fixture](assets/gpu_synthetic/README.md)，只证明执行能力。控制器不是操作系统安全沙箱，不能独立认证人类确认或审查质量。原始数据和测试结果不进入模型提示；源码和必要脱敏元数据经用户配置的所选 CLI 服务处理。禁止调用其他模型 API、上传研究数据，或读取被明确隔离的工程资源。

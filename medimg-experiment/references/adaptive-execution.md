# 授权内自动闭环

本页适用于用户已选择的自动执行模式。旧的 setup/execution/recovery/independent-review 文档描述人工逐步模式；激活自动委托后禁止混用旧命令绕过累计预算或测试门。自动流程通过首次委托选定且已实际核验的本机 Codex 或 Claude Code CLI 调用提案者与新上下文只读审查者，训练始终由受管 worker 执行。

## 两份确认材料

1. `assets/contract-template.json`：schema-v2 的显式 `matrix` 契约，至少含 baseline 和唯一 proposed，以及计划要求的 ablation/comparison。包含原计划路径、数据与冻结评价、正式 seed、输出协议、设备/精确依赖和单次训练限制。
2. `assets/adaptive-contract-template.json`：独立委托，填入真实作者授权和每课题门槛/预算。模板空值不可运行，不为校验通过编造数值。它不会把自动修改记录伪装成作者新确认。

`schema_version:1` 为 `AdaptiveDelegation@1`；字段如下。完整输出接口以模板与控制器为准。

| 字段 | 约定 |
| --- | --- |
| `authorization` | 实际首次授权的范围与来源文字。 |
| `deadline_utc` | 含时区的整体最晚时间；编码、审查、等待、训练均受约束。 |
| `budgets.training_seconds` | 跨修订累计训练墙钟上限，不能超过基础契约。部分/失败运行也累计；不是精确 GPU 占用时长。 |
| `budgets.max_method_revisions` / `max_fault_retries` | 初始方案之后的方法修订上限、故障修复重试上限；分别累计，不因改版清零。 |
| `budgets.formal_reserve_seconds` | 初筛/新探索不能占用的正式复核预留；由估算或测时支持，不保证错误估算下仍能跑完。 |
| `budgets.step_timeout_seconds` / `poll_seconds` | 单次模型调用时限、后台轮询间隔；实际调用应按课题批准充分时间。 |
| `rules.baseline_floor` / `target` / `screening_floor` | 本地基线合理水平、正式主方法门槛、初筛下限；依主要指标方向解释。初筛分数不会写成正式结果。 |
| `rules.min_effect` / `ci_lower_bound` | 主方法相对本地基线的患者配对效应与区间门槛。CI 是按 seed 聚合后的患者配对区间；seed 波动另报，不冒充联合层级不确定性。 |
| `rules.required_contributions` | `{id, ablation, claim, falsification, boundary, min_effect, ci_lower_bound}` 列表；固定科学命题、反证、边界与指定消融/统计要求。与初始贡献卡可读对应，方法换了也持续有效；空列表须确有已确认理由。 |
| `rules.comparisons` | `{entry, min_effect, ci_lower_bound}` 列表；对正式比较条目的要求。 |
| `entry_dependencies` | 每个矩阵条目完整的相关源码清单；与固定数据、环境、评价、命令一起指纹化判断复用。不得少列共享模型、预处理等依赖。 |
| `agent_backend` | `codex` 或 `claude`；省略时兼容旧委托使用 Codex。首次确认后固定，不因调用失败自动切换。 |
| `codex.executable` | 选 Codex 时提供实际本地原生可执行文件绝对路径，先核验真实调用。 |
| `claude.executable` / `claude.max_turns` | 选 Claude 时提供原生可执行文件绝对路径和 1–100 的单调用轮数上限，不要求安装 Codex。详见 [后端协议](agent-backends.md)。 |
| `project_root` | 可选已有论文项目绝对路径；初次绑定，不能由模型提案任意更换。 |
| `downstream_stages` | 可选初次确认的受影响下游阶段名；未提供时识别已有论文阶段，排除入口检查。只在实质变更事件使相应下游需返工，后续普通事件不重复撤销新的作者验收。 |
| `evaluator_implementation_paths` | 可选明确列出的原冻结评价实现文件；仅开发期恢复原指标定义时可走专用纠错审查，不能修改划分审计。 |
| `recovery` | 可选 `{checkpoint, validator_command, timeout_seconds}`：checkpoint 为原 run 内相对路径，命令含 `{python}`、冻结核验脚本、`{checkpoint}` 和 `{output}`。核验 model、optimizer、scheduler、Python/NumPy/CPU/CUDA RNG、sampler、progress、selection 和 configuration 的真实完整状态及 run/seed/哈希，通过后才续训；否则保留故障并新 run 重跑该 seed。 |

## 启动与持久推进

PowerShell 示例（`$pythonExe` 必须设为本课题已核验的真实 Python 绝对路径；其余变量必须指向本次已审阅且已确认材料，`$controller` 从实际安装位置解析）：

```powershell
& $pythonExe -X utf8 $controller adaptive-init --root $study --contract $contract --delegation $delegation --statement $actualUserAuthorization
& $pythonExe -X utf8 $controller adaptive-start --root $study
& $pythonExe -X utf8 $controller adaptive-status --root $study
```

`adaptive-init` 创建全新 study 并登记首次契约/委托，尚不启动训练。`adaptive-start` 启动单实例后台 supervisor；父聊天离开后仍可读结果、真实调用已选后端、修订、审查和启动下个受管候选，直到终止条件。计算机必须保持运行、联网且账户调用能力可用；锁屏不需要聊天持续发送消息。`adaptive-step` 只推进一步，适合排错和受控验收，不能把它当后台运行证明。重复启动不应产生重复训练。

没有现成代码时，受管工程先进入初始实现窗口：根据原确认定义提出训练器、划分审计和评价实现，只能写明确允许的初始源码；新上下文审查覆盖全部固定实现和条目依赖，通过才执行审计。首次审查/审计后窗口永久关闭，后续不得借“重新初始化”修改划分或评价。审查发现明确实现问题时，在故障重试上限内修复再用新会话审，不把 block 改成 pass。

模型只返回结构化文件/命令提案，由控制器核验和应用。提案必须列出完整矩阵、明确失败依据和当前方法技术路线；不可删除贡献目标、放宽门槛、改划分或覆盖失败证据。资源请求进入人工关口。研究代码/预训练权重下载需作者具体确认；模型不能自行执行安装、下载或训练。

基线先充分核验，再初筛主方法/消融/比较；主方法的筛选下限不套给正常完成的消融或比较条目，较低消融分数可以是有效贡献证据。通过筛选后使用正式命令重新跑完整 seed，不把小预算结果混入正式配对。若基线未可信先诊断基线；模块无贡献继续有依据的修订，不以“总体较好”跳过。每次修改后新上下文审查，记录真实会话 ID、绑定提交与实际读取文件；失败保留并在约定边界内处理。正式门全部满足后立即冻结，测试成绩只交付。

## 关键事件、停止与恢复

事件保存在 `adaptive/events.jsonl`；提案、模型调用、门判断和累计账本均在 study 下。同步时更新计划的方法章节及状态，并通过 `evidence/projections/` 回执按 pipeline 归档旧文档。先保存事实再投影；文档被外部改动或部分事务未完成时先协调，不能覆盖冲突。受影响下游标需返工，旧结果仍按原 run 路径可追踪。

```powershell
& $pythonExe -X utf8 $controller adaptive-pause --root $study --statement $actualPauseInstruction
& $pythonExe -X utf8 $controller adaptive-resume --root $study --statement $actualResumeInstruction
& $pythonExe -X utf8 $controller adaptive-start --root $study
& $pythonExe -X utf8 $controller adaptive-export --root $study
```

主动暂停只接受明确恢复，不因重启/轮询解除；原截止时间和累计预算保留。异常重入先 status 核验进程归属、提交、划分/环境和 checkpoint，不仅检查有没有权重文件。可靠恢复写入新的 run，原失败 run 不覆盖；无可靠 checkpoint 则从头重跑当前 seed，已有效 seed 按指纹核验后保留。达到任一预算/截止、正式预留不足、不能解决的审查或资源问题时，保留证据并报告实际终止原因。

Windows 状态 JSON 原子替换遇到临时共享冲突时，仅对 WinError 5/32/33 短退避重试，最多两秒且受剩余整体截止约束；持续失败仍保留原文件与 durable 临时文件并停止。已停止工程的 `adaptive-status`/导出仍按真实 run 幂等累计耗时，不因此重新派发训练；不要把记录补账当作恢复授权。

开发期明确评价实现错误用 `adaptive-correct --root ... --record ...` 提交恢复原定义的方案，先独立审查；受影响记录失效、重新计算，训练选择受影响则重训，预算不重置。冻结或看过最终测试后该入口会阻断自动修复；先提供具体修复/复算方案与独立审查，取得作者新确认，再由明确批准的维护流程执行并登记测试历史。不得用普通 resume 重开搜索。

若真实只读审查已完成，但源码路径与控制元数据格式不一致等登记故障使流程停止，可用 `adaptive-reconcile --root ... --record <该次调用的 invocation.json>` 核验并登记原审查。控制器必须绑定原真实会话、输入、候选提交和因果事件，源码与明确允许的项目控制材料分列；原始模型响应保留。此入口仅修复这一类技术登记故障，不解除资源、预算、截止、主动暂停、科学判断不明或测试后的人工关口，也不重新调用模型代写通过意见。核验成功后再运行 `adaptive-start`，所有累计数保留。

当前导出区分“实现/运行/契约达标”及未验证医学有效性。总迭代数、负结果、验证集反复选择、seed 波动、患者配对区间与测试次数如实报告；达到门槛不保证论文创新或临床价值。

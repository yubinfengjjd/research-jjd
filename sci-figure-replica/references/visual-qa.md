# 对比、QA 与签核

## 本轮验收单位

只对作者选定的代表单 panel 验收，参考图用选定裁图，完整原图与原图 bbox 映射单独保留。inset、色标、边缘分布及理解 panel 必要的共享标注随主图检查，多 axes 仍为一个逻辑 panel。记录裁图与原图位置、选定范围和适配的标签，不要求覆盖未选 panel；整图仅作只读溯源，不作为本轮验收目标。不得在迭代中缩小已选范围以凑通过。

## 工具边界

`make_compare.py --original PNG --replica PNG --out PNG [--overlay PNG] [--footer TEXT]` 保持两图比例缩放至相同高度（最大输入高度），白底、24 px 间隔、Original/Replica 标签。overlay 把复刻缩放到原图尺寸并 50% 混合，仅辅助定位，拉伸不作为比例一致证据。输入打不开或输出指向输入时拒绝；先生成全部字节再替换输出，不修改原图，保持解压炸弹保护开启。

`qa_check.py --entry DIR --original PNG --replica PNG --out MD` 检查 meta/README、数据/spec、代码、三格式、并排、thumb、run.log；非空与图片可打开分别记录，PNG 记录尺寸。宽高比相对误差 `abs((replica_w/replica_h)/(original_w/original_h)-1) <= 2%`。机械 FAIL 退出 1 并保存报告；人工项目保持待填，不自动判断“像不像”，也不自动 approved。

选定单 panel 时向 `--original` 传该裁图，不能拿完整组图宽高比评判单 panel。核对 init/dedupe 使用同一裁图、`source_image_sha256` 对应该裁图，以及完整原图单独归档的哈希/bbox；具体协议见 [画廊布局](gallery-layout.md)。代码函数化的数值等价、换数据/不同工作目录复用及 render 共用核心检查按 [代码契约](code-handling.md) 单独记录；视觉相似不能替代数值或统计核验。

知识库模板的 `verify-template`/作者确认/`mark-ready` 与 layout ready 分开检查：模板可独立 ready/render，不要求 layout 回放，layout 可仍为 `pending_template`。若还要将 layout 标为 ready，则检查它自己的 layout.json、preview 与已选范围覆盖，并运行 `verify-layout` 后交作者确认；单 panel 是只含已选单位的 1×1 回放，不要求未选 panel 或原始整组重建。

## 人工十项清单

逐项填 PASS/WARN/FAIL、证据与限制：画布/布局、panel 标签、颜色、字体/中文缺字、坐标轴范围/刻度、图例/colorbar、数据形状、注释、导出；画布与布局可分列为固定十项。检查主色板 ΔE00 中位数≤10、发散方向正确；不能独立量化时保留 WARN 和观察依据。PNG 长边≥2000 px 或≥300 dpi；PDF/SVG 要可打开，文字可编辑需单独检查，文件非空不证明渲染或字体正确。无法满足原检查标准时标 WARN/FAIL，不改阈值。

| 结论 | 含义 |
|---|---|
| PASS | 对该项已有明确证据，只覆盖写明的检查范围 |
| WARN | 存在近似、缺失证据或可审差异，明确影响并交作者 |
| FAIL | 不符合标准、缺产物或阻塞，修复或报告 |
| 待填 | 人工检查未做，不等于 PASS |

R 使用 `grDevices::svg` fallback 时文字可能为路径，即使图看起来正常也必须记录导出 WARN，不能写文字可编辑通过。Python 的 SVG text 节点/ PDF 字体结构检查也不替代独立查看器逐页视觉。中文同时记录实际字体文件、文本字符映射检查与缺字警告；只找到字体或 PNG 无异常不证明其他格式无 tofu。

## A/B/C 单面板例子

`examples/single-panel/{bar_inset,beeswarm,radial}/qa_report.md` 展示固定清单。A 的条形/inset/色标共享其已记录归一化，C 的环形色标用自己的数据域；源图内颜色校准不是独立验证。B 为固定种子合成视觉近似，其点数/密度无原始样本证据，数据形状保持相应 WARN。三例导出、并排和结构检查与作者视觉签核分别记录；status=review，不能因示例能运行就 approved。

## T3 六面板 QA 例子

`examples/post01-fig4/qa_report.md` 及 T3 终审记录了以下证据与限制，供填写 QA 时参考，不是新一轮测试结论：

| 项 | T3 证据/结论边界 |
|---|---|
| 画布 | PNG 7200×4104，相对 893×509 绘图区宽高比误差 0.001965%，满足≤2% |
| 布局/标签 | 2×3、A–F、A/B 与 D/E 共享名；A/D inset 开口略大、短扇形偏短，C/F 略小略低，布局 WARN |
| 颜色 | 蓝低红高；A/D 为源图内部校准，非独立留出验证，未宣称独立 ΔE00 通过 |
| 字体 | 实际 Arial 文件已记录，源字体文件未知；相同族名不证明同源，WARN |
| 数据/注释 | A/D 候选转录及 C/F 百分比 uncertain；A2、D1、F1 等末位待确认；B/E 各 2700 合成近似点，WARN |
| 色标 | B/E 为 Feature value；C/F 中心为 SHAP 绝对值，范围与方向分别核对 |
| 导出 | 三格式、SVG text 及 PDF 结构有证据；页级 PDF 独立查看器视觉当时待 T4，不借文件存在宣称已完成 |

T3 结论是“实现通过（带 WARN，作者视觉签核待完成）”。后续若没有针对上述项的新证据，继续保留 WARN；不能把阶段通过、pytest 通过或进入下一阶段写成作者 approved。合成数据不支持统计/科学有效性结论。

## 迭代与最终状态

修数据估读、布局、字体、颜色，不修阈值来凑通过。每轮保留并排和 QA，默认最多 3 轮；上限后列 needs_author。needs_author 记录在报告中，metadata 仍用 draft/review/blocked/approved 的合法状态。只有作者明确给出姓名/日期/结论才能 approved；pending 签核与未运行检查如实列出。

## 复刻与自适应复用的不同验收

原图复刻继续使用原宽高比≤2%等既有标准；adaptive换数据示例不强制原图比例。由agent选择不同的n或相应行列规模，检查实际宽高、物理间距、文字/图例/色标裁切、配色数量和覆盖；测试样例不构成支持数量的白名单。字体不因组数增加而自动缩小；默认单panel继续扩展，显式上限不足时询问。新规则不修改历史条目状态，也不以自动测试代替作者签核。

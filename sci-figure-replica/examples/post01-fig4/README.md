# post01 Fig. 4：六面板本地复刻

状态 **review**，待作者签核。只完成 T3，未写真实画廊、未全局安装、未运行 R 渲染。

原图：开发根 `samples/post01/source/fig01.png`，893×579（含图注）。
复用 T2 `crop_figure.py` 得到 `[0,0,893,509]`，图注区 `[6,519,880,579]`。
原始文件只读；输出保存在本示例内。参考附件为原图、T2 裁图与 A–F 4× 放大图。

## 运行

在开发根 PowerShell 执行：

```powershell
$py = 'C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe'
& $py -m pytest staged\sci-figure-replica\tests -q
& $py -X utf8 staged\sci-figure-replica\examples\post01-fig4\replica.py
```

`--out <路径>` 可指定测试输出；拒绝向 samples 与配置中的真实画廊写入。
`prepare_inputs.py` 是显式、可重复的输入准备脚本（固定种子 20261020）；
绘图脚本只读取 CSV，不会重新抽样、训练模型或执行原帖代码。
测试输出目录及完整实测 stdout、stderr、退出码见开发根 `codex/T3-validation.json`。

## 结构与复用

复用 T2 的 `python_style.py`、`shap_bar.py`、`beeswarm.py`、`radial_bar.py`，
并通过 `make_compare.py` 生成 [并排图](compare/side_by_side.png)。T2 模板未修改。
采用显式 axes，画布 12×6.84 in，600 dpi，输出 PNG 7200×4104、PDF、可编辑文字 SVG。

- A/D：逆向横条、右侧共享特征名、左侧 High/Low 色标、逆时针由低向高阅读的开放环形 inset。
  inset 实际 theta 方向为 clockwise：从高值开始顺时针向低值排列，反向即低→高逆时针；
  这是按附件红色右侧、蓝色左上方的视觉排列做的调整。
- B/E：隐藏 y 标签，与 A/D 每一特征的 y 坐标一致；各 15×180 合成点，0 线、水平虚线、右侧 Feature value 色标。
- C/F：顺时针极坐标条、外圈特征名与百分比、内部三位小数值、中心绝对 SHAP 色标。
  与 A/D inset 按 feature 键共享百分比，不把模糊百分比自动归一化成精确值。

figure_spec.json 保存每个 panel 的范围、实际 axes bounds、letter、insets、字体文件、色域、ticks、数据哈希及来源。
bar 的 bbox_figure 含共享标签；B/E 的 bbox 不重复计入这块共享区。
极坐标图属于同一列，按原图向下偏移；严格等大等中心的网格会改变原图布局。

## 转录、修正与不确定性

任务书 §2 及 design.md §11 的初录数值存在明显冲突；依任务书“放大图优先”逐项修正。
下表左列是任务书候选，右列是本次对附件的转录候选。它们都不是原始观测。

| 行 | 任务书 feature / A 或 D 值 | 附件 feature / 本次 A 或 D 值 |
|---|---|---|
| A1 | Complexity_per_MW / .1534 | Complexity_per_MW / .1534 |
| A2 | Ch3v / .1179 或 .1379 | Chi3v / .1178（末位 .1179 也可能） |
| A3 | SMR_VSA10 / .1171 | SMR_VSA10 / .1171 |
| A4 | MfR_per_MW / .0653 | MR_per_MW / .0835 |
| A5 | AromaticRing_Ratio / .0663 | AromaticRing_Ratio / .0811 |
| A6 | XlogP / .0633 | Ketone / .0767 |
| A7 | Kappa3 / .0777 | Kappa3 / .0735 |
| A8 | MinPartialCharge / .0715 | MinPartialCharge / .0729 |
| A9 | Charge_Span / .0723 | Charge_Span / .0589 |
| A10 | MolLogP / .0559 | MolLogP / .0507 |
| A11 | SlogP_VSA2 / .0507 | SlogP_VSA2 / .0501 |
| A12 | BalabanJ / .0508 | BalabanJ / .0492 |
| A13 | TPSA_x_LogP / .0433 | TPSA_x_LogP / .0471 |
| A14 | MinAbsPartialCharge / .0401 | MinAbsPartialCharge / .0403 |
| A15 | FractionCSP3 / .0603 | FractionCSP3 / .0402 |
| D1 | Complexity_per_MW / .0951 | Complexity_per_MW / .0965（数字仍需作者确认） |
| D2 | BerzCT / .0900 | BertzCT / .0908 |
| D3 | Jpc / .0842 | Ipc / .0682 |
| D4 | Ch4v / .0747 | Chi4v / .0628 |
| D5 | Kappa3_Anisotropy / .0705 | Kappa_Anisotropy / .0442 |
| D6 | NChargeValenceElectrons / .0586 | NumValenceElectrons / .0406 |
| D7 | Ch3v / .0484 | Chi3v / .0388 |
| D8 | HallKierAlpha / .0341 | HallKierAlpha / .0284 |
| D9 | MolWt / .0327 | MolWt / .0279 |
| D10 | SlogP_VSA5 / .0219 | SlogP_VSA5 / .0241 |
| D11 | BalabanJ / .0204 | BalabanJ / .0199 |
| D12 | TPSA_x_LogP / .0180 | TPSA_x_LogP / .0174 |
| D13 | LogP_TPSA / .0177 | LogP_TPSA / .0173 |
| D14 | HalogenRatio / .0176 | HalogenRatio / .0169 |
| D15 | SMR_VSA7 / .0111 | SMR_VSA7 / .0161 |

C/F 外圈数字小、旋转且有压缩伪影，**全体百分比均保留 uncertain**。
由于 CSV 每行同时含 shap 和 percent，60 行的 provenance 统一为 uncertain，
uncertain_reason 指明主要是百分比而非宣称每一清楚的条形数字都不可辨认。
特别需要确认 A2 的末位、D1 的数字、F1 的 15.8%（16.3% 也可能）。
未用百分比反算所谓原始 SHAP，也未强制总和等于 100%。
百分比按同一 feature 在 A/C、D/F 成对保存：

| feature（顶行顺序） | 初录 C % | 本次 A-inset / C 候选 % |
|---|---:|---:|
| Complexity_per_MW | 13.5 | 13.8 |
| Chi3v | 10.6 或 10.4 | 10.6 |
| SMR_VSA10 | 10.3 | 10.5 |
| MR_per_MW | 7.5 | 7.5 |
| AromaticRing_Ratio | 7.3 | 7.3 |
| Ketone（初录 XlogP） | 6.9 | 6.9 |
| Kappa3 | 6.9 | 6.6 |
| MinPartialCharge | 5.9 | 6.6 |
| Charge_Span | 5.4 | 5.3 |
| MolLogP | 4.6 | 4.6 |
| SlogP_VSA2 | 4.5 | 4.5 |
| BalabanJ | 4.4 | 4.4 |
| TPSA_x_LogP | 4.2 | 4.2 |
| MinAbsPartialCharge | 3.8 | 3.6 |
| FractionCSP3 | 3.8 | 3.6 |

| feature（底行顺序） | 初录 F % | 本次 D-inset / F 候选 % |
|---|---:|---:|
| Complexity_per_MW | 13.5 | 15.8 |
| BertzCT | 14.9 | 14.9 |
| Ipc | 11.2 | 11.2 |
| Chi4v | 10.5 | 10.3 |
| Kappa_Anisotropy | 7.2 | 7.2 |
| NumValenceElectrons | 6.7 | 6.7 |
| Chi3v | 6.4 | 6.4 |
| HallKierAlpha | 4.9 | 4.7 |
| MolWt | 4.9 | 4.6 |
| SlogP_VSA5 | 3.9 | 4.0 |
| BalabanJ | 3.1 | 3.3 |
| TPSA_x_LogP | 2.8 | 2.9 |
| LogP_TPSA | 2.8 | 2.8 |
| HalogenRatio | 2.8 | 2.8 |
| SMR_VSA7 | 2.6 | 2.6 |

B/E 分布为 **estimated**，固定种子的正态混合簇仅近似可见位置、范围和颜色方向；
不能据此推断真实样本量、相关性、模型性能或机制。
E 按附件坐标刻度 −.1/0/.1/.2，采用 −.17～.21，替代任务书初录的 −1～1。
B 范围 −.64～.55；二者均逐行固定点数 180，不是从模型导出的 SHAP 矩阵。

## QA、日志与代码来源

见 [qa_report.md](qa_report.md)、color_audit.json、figure_spec.json、render.log、追加式 run.log。
stdout.txt / stderr.txt / exit_code.txt 是该次命令的实际流与退出码。
颜色阈值仍为 ΔE00 中位数≤10；A/D 仅测量校准点内拟合，不当成独立配色验收。
Arial 实际文件已记录，源字体文件未知。PNG 已解码、SVG XML与可编辑 text、PDF结构另见开发根审计；
PDF 独立查看器逐页视觉检查仍待 T4。作者签核前不进入 accepted 状态。

`code_provenance=reconstructed`；`original_code_provenance=example_not_target`。
四段帖子代码见 [original_code/README.md](original_code/README.md)；字节与 fence 内文完全一致，
只有归档状态 archived_only，没有执行、补全缺失函数或安装 XGBoost 等依赖。

图注（视觉复刻说明）：A/B/C 展示 pLC50 的 LightGBM SHAP 解释，D/E/F 展示 AR–DBP 的 CatBoost SHAP 解释。
A/D 为平均绝对 SHAP 值及贡献 inset，B/E 为合成近似蜂群，C/F 为相对贡献环形图。
所有转录均来自提供的图像，模糊数字为 uncertain；本产物用于视觉示例，不构成原研究的数据或模型复现。

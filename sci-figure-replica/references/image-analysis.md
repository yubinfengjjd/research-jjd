# 读图、裁剪与数据估读

## 先识别逻辑 panel 与样式

agent 查看原图后按图元、视觉映射、坐标/布局、颜色语义和附属结构列样式卡。每卡给代表裁图、来源及原图 bbox、重复位置、编码描述、已有模板/差异和不确定点。默认每个选定样式只复刻一个清晰代表；模型名、指标名、单位、值或配色通常参数化，不自动增加模板。新增编码、不同坐标结构或实质不同的画法保留可选变体并说明理由。

inset、色标、共享标注和边缘分布依附于主 panel，不机械拆成新样式。例如密度散点＋边缘直方图为一个逻辑 panel（可含多个 axes），六个模型通常重复使用它；箱线＋散点＋均值菱形在 RMSE/R²/MAE 间通常是指标参数变化。多 panel 原图只作溯源，识别去重后询问代表单 panel，不规划整组复刻。

每个代表独立建条目；不同结构变体使用不同条目 id，沿用既有模板 id 规则，不将同图型变体强合并。保留完整原图与哈希，另存选定裁图及原图坐标 bbox；原图位置与复刻范围在 spec/README 对应。未选 panel 仅作来源背景，不纳入 QA 覆盖要求。

## 裁图与低质量边界

`scripts/crop_figure.py --image PNG --out DIR [--spec JSON] [--bottom-crop PX] [--panel A --bbox x0,y0,x1,y1]` 另存 `original_figure.png` 和 `crop.json`。bbox 为原图坐标、右/下端点不含；`--spec` 输出/更新分析 JSON，已有 `caption_bbox`（含 null）和 `quality_flags` 可人工覆盖。原图保持字节不变。

内容检测采用相对背景低阈值（RGB 最大差 >10）与 8 px 留边，保留浅色柱、色条和文字。图注检测独立使用较高阈值（>25）的留白、宽度、行密度及非彩色文字带几何线索，不识别语义；不能让浅色绘图区桥接图注留白。分离底部图注后保留**整个原始横向宽度**，不按深色墨迹收窄复合图左右边距。不要硬编码某张图的 bbox，也不要为匹配宽高比裁掉外圈标签。

先查看原图尺寸、模糊、截断、水印和关键文字。图注可能与灰色表格/图例混淆：对照原图确认后用 `caption_bbox` 或 `--bottom-crop` 显式覆盖；`caption_bbox: null` 可禁用自动图注判断。记录 original_size、crop_bbox、caption_bbox、裁后尺寸和 quality_flags。panel bbox 仍以原图坐标记录，不把裁后坐标混用。

`low_resolution`、`possible_blur_or_low_contrast`、`possible_truncation_at_image_edge` 是启发式提示；水印由人工检查，可写入 `quality_flags`（如 `watermark`）并说明。未触发标志不代表质量已通过。README/metadata 列出不可读部位和影响；轴刻度、特征名、数字或图例等关键内容不可读时停止索取更清晰原图，不靠猜测补齐。

## 结构、颜色与字体

按选定单位记录 panel 标签、bbox、inset、边缘分布、共享标签，再记录画布比例、背景、字体族/实际文件/fallback、字号粗细、颜色、坐标范围/刻度/单位、图例/colorbar、数值与注释。选单 panel 时把理解它所需的共享标签保留或显式适配并记录；不要借适配删掉已选结构。完整行列仅在原图溯源记录中保留，不作为交付范围。图注与绘图区分开保存，检查浅色元素、轴名、长标签和外圈百分比均保留。

`sample_palette.py --image PNG --out JSON [--probes JSON] [--k 8]` 输出 data/ink/background 主色、占比和 RGB/hex 探针。probes 为 `[{"name":"high","x":60,"y":100}]`；蓝/红端点仅是近似色板，不是恢复原始 colormap。记录色标方向与归一化；源图内部校准不等于独立验证。中文调用模板字体注册并检查实际文本的字符映射，记录实际字体文件；PDF/SVG 可编辑性另行核查。

## 数据与不确定性

原始数据缺失时先列缺口和影响，询问作者本次使用估读还是合成；选择明确后才执行下述步骤。估读/合成数据均不能支持原始样本或统计复现结论。

先转录图上已印数字，无法确定末位也保留 `uncertain_reason`。无标注时用至少两个轴刻度校准像素→数值，说明轴类型；当前 `estimate_data.py` 只支持**线性轴**，对数轴需另行明确实现和验证，不能套用线性估读。误差棒 SD/SE/CI 未知则不猜。

`estimate_data.py --mode bars|points|color --spec JSON --out CSV` 字段见脚本 `--help`/docstring：bars spans 为 [起点x,端点x]，支持反向轴/非零基线；points 独立校准 x/y。`colorbar_bbox` 必须含 bbox、位置/RGB samples、orientation、high_at，仅空间 bbox 不能反查颜色。RGB 最近投影默认距离上限 25，修改需在 spec 的 max_rgb_distance 显式记录；歧义/不匹配输出 NA 和原因。

`estimated_data.csv` 保存 panel、series/feature、value、unit、provenance、uncertain_reason 等适用字段；无法可靠辨读写 NA，不补造。工具输出均为 estimated，不是原始观测。蜂群遮挡无法恢复逐点数据；按可见范围/密度/颜色构造点集时，明确记录 synthetic visual approximation、生成方法与固定种子，数据分类按实际为 synthetic/mixed；若历史 CSV 保留 estimated，也必须另有逐行合成标志与 README 说明，不能据此称原始样本。

post01 的 A/D 数字与 C/F 百分比来自低清图候选转录，全部保留 uncertain；B/E 为各 2700 个合成近似点，点数不代表样本量。不得由百分比反算原始 SHAP、强制总和 100%、重训模型或推断显著性。参考单面板及六面板例子的 spec、CSV 和 QA，不能把视觉近似升格为统计复现。

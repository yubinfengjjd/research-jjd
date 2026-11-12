# 按代表单 panel 执行与签核

帖子级来源先解析，agent 读图并列去重样式卡，确认来源配对与计划后按选定样式串行，避免多进程同时改画廊。一个代表单 panel 一个条目，结构变体另建条目 id；整图仅作只读来源，不建立整图条目。使用 ASCII post-slug 和不同 fig id；单 panel 向 `dedupe --image` 和 `init_entry --source` 传同一选定裁图，裁图成为 `source_image`，`source_image_sha256` 是裁图哈希。完整原图另存并记录独立哈希及原图 bbox 映射，具体用法见 [画廊布局](gallery-layout.md)。命中先留历史再更新原条目，不用 init 覆盖，`source/` 始终只读。

计划集中写明选定样式与代表、数据来源、保真重点、语言/源码处置、方法文字笔记与函数化范围、交付和 QA 单位。已有选择直接复用；缺原始数据先解释缺口并询问本次估读/合成选择，等关键选择明确后执行。方法联想限定有依据的家族推广，保留具体来源实现并列前提/限制/未验证分支，不由图形通用性创建宽泛新方法；有来源代码可按 [函数契约](code-handling.md) 封装，无分析算法不自动补。

## 从读图到迭代

计划确认后：记录选定单位 spec→整理可追溯数据与 uncertain→审阅/封装代码→渲染 PNG/PDF/SVG→与选定参考裁图并排并做机械 QA→读对比图并人工填写 QA→修订。原代码能直接产出目标图才 `original_runs`；失败记环境/stderr 后有限改造，保留差异；仍不行归档，已授权时另写 `reconstructed`。没有代码先推荐语言并询问；R 缺包不能静默换 Python。代码是待审阅输入，执行前核对授权与隔离范围。分析表与绘图分离，保留原语言、数值等价与课题环境可移植性证据。

模板不依赖 medfig/figkit：Python 的 `python_style.py` 管样式、字体与导出，`panel_layout.py` 管画布/标签，`shap_bar.py`、`beeswarm.py`、`radial_bar.py` 管对应图型；R 的 `r_style.R` 提供 `theme_pub`、`save_pub` 与中文字体注册，仅复刻选定的单 panel。脚本路径及运行方法见 [运行环境](runtime-environment.md)。

每轮记录日期、命令、退出码、包版本、数据或布局改动、对比图与 QA 差异。`max_auto_rounds` 来自 config，默认 3；每轮保留证据，达到上限仍不满意则记录 `needs_author` 和未决问题。不得减小参考图、删除已选 panel/附属元素、提高误差阈值或用更低标准替代原验收要求。未选 panel 不构成本轮缺失覆盖。

## 单面板到六面板的经验

`examples/single-panel` 提供 A（bar_inset）、B（beeswarm）、C（radial）三个中间样例；它们对应帖子内独立图片，不是把六面板裁开后的所有细节，独立原图无 A/B/C 字母时不要凭空添加。蜂群分布是固定种子合成视觉近似，不是逐点恢复。参考 README、figure_spec、CSV 和各 QA，不能只复制一张预览图当复刻代码。

`examples/post01-fig4` 仅为历史归档经验，不是本流程的复刻或收录选项；从中识别单 panel 的附属元素时可参考：

- 2×3、A–F；A/D 条形图各有左下开放环 inset，B/E 为蜂群，C/F 为极坐标环形图。
- A/B、D/E 各共用一套特征名，放在 A/D 右侧，B/E 隐藏重复 y 标签；标签是共享标注，不是额外 panel。
- 面板字母在 figure 坐标中绝对定位；长特征名和行间留白要整体对齐，检查文本是否越出画布。
- A/D inset bounds、开口角度、扇形高度与红蓝方向分别记录，不把它画成普通闭环。
- B/E 右侧是 Feature value 色标，C/F 中心是 SHAP 绝对值尺度，不能因同色板就共用错误数据域；保留 high/low 方向与 ticks。
- C/F 外圈名称和百分比留足边距，尺寸/位置与相邻 panel 比较；裁图注后保留原图全宽和浅色内容，避免错误画布比例驱动后续布局。

T3 终审为“通过（带 WARN，作者视觉签核待完成）”。已确认整体结构与三格式产物；A/D inset 开口/短扇形、C/F 略小略低、末位转录/百分比、B/E 合成分布、源字体与页级 PDF 查看、颜色内部校准仍是 WARN。不可把任务书初录当唯一数字真值：候选转录可依据放大原图修正，但必须保留 uncertain_reason 与证据；不能把修正写成已获原始数据。

## 状态与交付

`draft` 是准备中，可缺 output/compare；`review` 是待作者目视；`blocked` 附具体阻塞；`approved` 必须有作者、日期、签核结论。needs_author 是未决事项记录，不是 schema 的新 status。脚本成功、测试通过、文件齐全或 T3 实现审查均不会自动 approved。

交付包括完整原图/选定裁图与 bbox、代码/数据/spec、来源与估读限制、三格式、选定单位并排、QA、日志、运行方法和剩余问题。单 panel 可独立收录、回放与交作者签核，不以重建整组为前置条件。作者反馈后迭代；重做旧图先去重留版本，再更新索引。若没有新签核证据，post01 保持 review，不因进入 T4 自动消除 WARN。

知识库有两个就绪单位：模板在 `verify-template`、作者确认及 `mark-ready <模板 id>` 后即可独立 `render`，来源 layout 可保持 `pending_template`。若要同时完成 layout 的 ready，须为选定单位准备 layout.json、自己的 preview 和完整已选覆盖，运行 `verify-layout` 后交作者确认并 `mark-ready <版式 id>`；单 panel 使用仅含该 panel 的 1×1 布局。不再提供整组回放选项，不能把未选 panel 加进覆盖门槛。

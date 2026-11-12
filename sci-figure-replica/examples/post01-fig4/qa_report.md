# post01 Fig.4 QA

状态：review；作者未签核。阈值保持宽高比≤2%、颜色ΔE00中位数≤10。

| 项目 | 结论 | 证据与限制 |
|---|---|---|
| 画布/宽高比 | PASS | PNG 7200×4104；相对误差 0.001965% ≤2%。 |
| panel 布局 | WARN | 2×3，A/B、D/E共享标签；行间对齐有artist测试；并排图待作者签核。 |
| 面板标签 | PASS | A–F粗体；figure_spec记录位置，测试检查实际文本。 |
| 颜色 | WARN | 蓝低红高；A/D色彩按原图条内部校准，非独立验证；未宣称ΔE00通过，见color_audit.json。 |
| 字体 | WARN | 实际 Arial；文件 C:\Windows\Fonts\arial.ttf；源字体文件未知。 |
| 坐标轴/刻度 | PASS | A 0.16→0、D 0.10→0；B −0.64～0.55、E −0.17～0.21；覆盖源图可见范围。 |
| 图例/colorbar | PASS | A/D左侧High/Low；B/E右侧Feature value；C/F中心SHAP绝对值尺度与ticks已记录。 |
| 数据形状 | WARN | A/D印刷值逐条候选转录；C/F低分辨率百分比uncertain；B/E各15×180合成点，非原始样本。 |
| 注释 | WARN | 数值、环形百分比齐全；uncertain_reason逐项保存。画布外文字：[]。 |
| 导出 | WARN | PNG/PDF/SVG已生成；SVG文字可编辑；PDF页级独立查看器视觉保留待T4。 |

未执行帖子示例训练；未写真实画廊、samples或全局安装。作者/日期/结论：待填。

# 运行环境、设备与字体

## 解释器与环境检查

本机路径集中 `config.json`，以实际任务书指定路径优先：

| 项 | 路径/规则 |
|---|---|
| 专用 Python | `C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe` |
| Rscript | `D:\R-4.5.0\bin\Rscript.exe`，读取 `rscript_exe` |
| 正式画廊 | `config.gallery_root`；写入仍必须显式传 `--gallery` |
| 测试画廊 | 独立 `test-gallery-t4`，禁止写正式画廊 |

不用 PATH 的 Windows 商店 Python；专用 venv 不复用 `figure-skills` site-packages，不改其他环境。`bootstrap_env.py --config CONFIG [--python-exe PATH] [--check-r] [--rscript-exe PATH]` 检查已有解释器。专用环境不存在时，只有提供 `--base-python` 才能创建；普通环境检查不自动联网安装。缺包列清单、停止报告；未经作者决定不安装。

Python 检查 `matplotlib/numpy/pandas/seaborn/scipy/Pillow/fonttools/pytest` 导入与版本；`scikit-image/openpyxl` 仅在需要时检查。开发根可执行 `<专用python> -m pytest staged/sci-figure-replica/tests -q`。默认测试临时根唯一；显式 basetemp 保持原值，pytest 禁用 cache provider。旧 ACL 受限目录保留，不清理/接管。

R 检查一次 `installed.packages()` 清单（30s）和独立 cairo 能力探测（10s），不逐包加载 namespace；超时清理进程树，清理被拒绝也记录错误并有界返回。**必需包为 `ggplot2`、`patchwork`、`scales`**；`svglite`、`ggbeeswarm` 可选。`cairo_pdf` 是 R 设备而非待装包，需检查 `capabilities("cairo")`；cairo 不可用时报告 PDF 导出阻塞，不能把缺设备当通过。缺必需包正常非零，不等于检查器挂死。

## 执行器与日志

```powershell
$py = 'C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe'
& $py -X utf8 <skill>\scripts\run_code.py --language python --code <entry>\code\replica.py --cwd <entry> --timeout 300
& $py -X utf8 <skill>\scripts\run_code.py --language r --code <entry>\code\replica.R --cwd <entry> --timeout 300
```

`run_code.py` 用 config 的 `python_exe` 或 `rscript_exe`，参数列表调用；R 使用 `Rscript --vanilla`，不拼 shell。有效 cwd 下探测失败、运行失败和超时都保留日志。记录 UTC 时间、命令、cwd、解释器/版本、包版本、退出码、stdout/stderr 尾部与清理错误；完整输出另存 `stdout.txt/stderr.txt`。R 同时记录 `sessionInfo()`。这不是安全沙箱：先审阅来源、确认绘图执行授权及隔离运行范围，不运行帖子中的安装、训练、网络或破坏性操作。日志不保存 key/令牌。

## 模板与导出

Python：`python_style.apply_style()`、`save_figure(fig, stem)`；PNG 600 dpi，保持显式画布比例；PDF fonttype 42，SVG fonttype none。不能由这些设置或文件非空推断所有字体已正确嵌入、文字均可编辑或视觉一致。

R：`r_style.R` 提供 `theme_pub(base_size=7, base_family="Arial")`、`save_pub(plot, stem, width, height)`。主题为 classic、黑色细轴线、无网格/主标题；尺寸单位按模板接口为英寸。PNG 600 dpi；PDF 使用 `grDevices::cairo_pdf`，先检查 cairo；SVG 优先 `svglite::svglite`，缺失时降级 `grDevices::svg()`，记录实际设备。**base SVG fallback 的文字可能转为路径，导出 QA 必须 WARN，不能宣称文字可编辑。** 可选包缺失不触发联网安装。没有 `ggbeeswarm` 时可以用固定种子的合成 jitter，但必须标为合成视觉近似，不能叫真实蜂群观测。

## 中文字体

Python 调用 `register_cjk_font(text="示例图 分组")`，优先 Microsoft YaHei/SimHei，返回实际 `family` 与 `file`；检查传入文本的字符映射后再用于标题/轴标签。把 family/file 和缺字检查结果写进 spec/日志；不能只确认字体名称存在就宣称无 tofu。检查应覆盖实际中文文本；字体或字符缺失时明确报告并停止受影响渲染，不能静默用 DejaVu Sans 代替中文。

R 调用 `register_cjk_font()`，检查 Microsoft YaHei/SimHei 字体文件并通过 `windowsFonts` 注册；保存实际路径/字体族。`windowsFonts` 注册本身不证明 cairo/SVG 设备使用了同一个字体，仍检查各格式输出及缺字警告；缺字体或出现 tofu 时停止报告，不作成功结论。PNG 正常不等于 PDF/SVG 同样正常。

示例入口见 `examples/single-panel/README.md`、`examples/post01-fig4/README.md` 和 `examples/r-simple/README.md`。R 示例仅为 synthetic 运行时演示，三格式或 exit=0 不证明目标图复刻通过。
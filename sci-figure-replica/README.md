# sci-figure-replica

科研数据图的样式咨询、代表单 panel 复刻与画廊维护技能。使用规则见 [SKILL.md](SKILL.md)。脚本、模板、参考文档与已有示例随目录分发；历史六面板例子仅作证据，不能据此恢复整图默认复刻规则。

在仓库根运行 `python install.py --skill sci-figure-replica --target <技能根> --dry-run`，核对后去掉 `--dry-run` 安装，再用同样参数加 `--verify` 核验。Windows 本机使用作者指定的实际 Python 解释器。

`config.json` 只放工具与目录路径，不含凭据。发布副本的 Python、Rscript 与画廊路径为空；换电脑后把本机绝对路径写入该文件，或写入同目录、不提交的 `config.local.json`。空路径会停下，不会沿用别的机器。不要使用 Windows 商店占位 Python。缺包只报告，安装依赖仍需作者授权。

`samples/` 提供原始材料的只读输入；独立安装器保留为本目录的 `install.py`。复制技能后，脚本从技能目录定位示例输入。运行产生的文件应写入独立临时目录。

运行示例前先按 `references/runtime-environment.md` 核对解释器、Rscript、字体和可选依赖；缺失项只报告，不自动安装。

`samples/post01/source/` 的帖子和图片来自其 `meta.json` 所记载的公开文章，原始材料只读，权利归原作者；仓库的 MIT 许可不重新许可这些第三方材料及其派生图片。`examples/` 中的数据近似、估读、合成标识与 QA 警告原样保留，已有成图和测试通过不代表作者签核或科学验证。

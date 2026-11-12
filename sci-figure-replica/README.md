# sci-figure-replica

科研数据图的样式咨询、代表单 panel 复刻与画廊维护技能。使用规则见 [SKILL.md](SKILL.md)。脚本、模板、参考文档、评估题、测试与全部已有示例随目录分发；历史六面板例子仅作证据，不能据此恢复整图默认复刻规则。

在仓库根运行 `python install.py --skill sci-figure-replica --target <技能根> --dry-run`，核对后去掉 `--dry-run` 安装，再用同样参数加 `--verify` 核验。Windows 本机使用作者指定的实际 Python 解释器。

`config.json` 保留原本机的路径设置，仅包含工具与目录路径，不含凭据。换电脑后先按实际环境修改它，尤其是 Python、Rscript 与画廊路径；不要直接运行指向原作者机器的默认值。不要使用 Windows 商店占位 Python。缺包只报告，安装依赖仍需作者授权。

`samples/` 补齐原开发目录的只读测试输入；独立安装器保留为本目录的 `install.py`。测试与示例的开发根定位已改为技能目录，使复制后的目录可以自行找到这些文件。原始技能源文件的 SHA256 与打包改动列在 `source-manifest.json`。测试产生的文件应写入独立临时目录。

单独运行本技能测试，避免与仓库其他测试的同名模块及 conftest 混合：`python -X utf8 -m pytest sci-figure-replica/tests -q`。完整历史测试含 Windows、R、字体及本机解释器依赖；未具备时不能声称全量测试通过。仓库的通用 pytest 入口将它分开，原始测试文件全部保留。

`samples/post01/source/` 的帖子和图片来自其 `meta.json` 所记载的公开文章，原始材料只读，权利归原作者；仓库的 MIT 许可不重新许可这些第三方材料及其派生图片。`examples/` 中的数据近似、估读、合成标识与 QA 警告原样保留，已有成图和测试通过不代表作者签核或科学验证。

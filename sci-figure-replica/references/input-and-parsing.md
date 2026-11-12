# 输入、解析与配对

本地 md/txt/html 优先；parse_post.py --input FILE --out POST_DIR [--url URL] 中 URL 只作来源，不发请求。仅 --url 时用浏览器 UA 与 Accept-Language: zh-CN，验证/环境异常页 stdout 提示“请粘贴全文”并退出2。网络/TLS失败保存错误，不循环抓取或绕过验证。

微信识别 activity-name、js_name、js_author_name_text、publish_time；时间空时 var ct 按 UTC+8 转换。用 HTMLParser 栈追踪 js_content 的平衡 div；不靠首个 </div> 截取正文。缺失或不闭合即拒绝，不猜正文范围。pre 的 data-lang 为语言，每个 code 元素一行，nbsp 转空格，保留缩进/空行；正文外脚本不执行，HTML 中 pre 不作为可执行输入。img 优先 data-src，去除 #imgIndex 后保留出现顺序；去重后的 URL 只是候选，不等于目标图。

输出 source.md（六个来源 frontmatter 字段）、meta.json（来源、代码lang/code/index、image_urls、figure_candidates、local_figures、待确认配对状态）；HTML 输入另存 article.html 原始字节。已有 frontmatter 的 Markdown 原字节保留，解析元数据单独写 meta；--url 覆盖的是 meta 的来源注记，原文不重写。source_html 指向本次 HTML 存档；纯文本未知为 null。无 fence 不强拆代码；支持反引号/波浪号 fence，不完整 fence 报错。解析后不运行任何代码。

解析器只产生候选；agent 实际查看原图，区分正文数据图、头图、二维码、封面、屏幕截图、示意图或不确定，再把来源与本地 figNN 配对。记录候选序号/URL/本地名/描述。配对不明则询问，不能把16个图片 URL 和1张目标图自动判为输入错误。T1 不自动做视觉分类或代替作者确认。下载图片并非 T1；如后续授权下载，微信图片带 Referer: https://mp.weixin.qq.com/。

配对后按 [图像分析](image-analysis.md) 列去重样式卡，不把候选数、图片数或 panel 数直接变成复刻任务数。卡片包含代表裁图、原图/面板位置、重复位置、编码与附属结构、已有模板、结构变体和不确定点。原图哈希去重只判断同源文件，不能代替视觉样式去重。

候选阶段只解析、预览、查模板和出计划。确认本次选定样式/代表、数据、保真重点、语言/代码、交付范围后才渲染或建正式条目；已有答案直接复用。无原始数据先说明缺什么，以及估读保留可见数值但有辨读误差、合成只示意形状且不保留原始观测/推断的区别，询问本次选择并等待答案。不能因旧示例使用估读/合成就替作者选。

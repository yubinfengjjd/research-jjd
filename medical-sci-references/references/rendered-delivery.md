# 可见引用交付

原生域构造和可见结果是两道独立关口。旧检查器I1–I9保护原文、位置、条目身份与格式；它的原标识结果及空文献表只适用于中间件。不得修改其断言来放行完成稿。

## 本地CSL生成

使用已安装软件中的citeproc-js、实际选定的CSL文件及对应语言文件；显式传入路径，记录SHA256。可以从已安装Zotero的app/omni.ja提取citeproc.js与CSL locale至本轮显式`_tmp/`，样式通常在数据目录styles中。不要自动安装依赖、修改Zotero设置或从第三方技能复制格式化代码。本仓库只提供调用及检查逻辑，不分发第三方处理器。

从已经通过旧核对器的未渲染原生域DOCX生成INPUT.json：`source_sha256`为该DOCX哈希；`items`按真实itemData.id的字符串索引保存原itemData；`citations`按文档顺序保存全部原生citation JSON。保留所有条目、URI、citationID和原有合并引用顺序，不用少量示例代替整稿。每条本地CSL输入必须与原字段中的元数据完全一致。

```text
node make_csl_plan.cjs INPUT.json CITEPROC.js STYLE.csl LOCALE.xml PLAN.json
python -X utf8 render_zotero_fields.py render NATIVE.docx CACHED.docx --plan PLAN.json --report rendered-check.json
python -X utf8 render_zotero_fields.py check NATIVE.docx CACHED.docx --plan PLAN.json --report final-check.json
```

INPUT/PLAN及输出候选均留在本轮过程目录。调用项目指定真实Python；Node使用明确可用的运行时。所用样式必须与原生域文档偏好一致；当前实现支持方括号数字制，遇其他样式应明确报不支持，不能手写编号仿造CSL输出。元数据仅在本地处理，不发送私稿。

## 可见交付关口

- 原生引用域及文献表域保留，全部citationID、citationItems、URI、真实整数ID与元数据不变，只更新formattedCitation/plainCitation及可见缓存。
- 每处可见编号由实际CSL生成，与该处条目集合相符；重复引用复用编号，连续编号区间正确展开。
- 书目条数等于实际引用的唯一条目数，条目ID集合精确一致且无重复，书目顺序、编号和题名与CSL及字段元数据相符。不得硬编码课题条数。
- References之前无残留PMID/DOI/URL/arXiv标识。未解决来源应标为部分完成并保留原因，不能宣称全部替换。
- 还原字段缓存后，其他正文、表格、公式、分节、段落属性及非document.xml包成员逐字节/规范XML一致。拒绝字段锁定或外壳变化。
- CSL计划绑定源文件及本地输入、处理器、样式、locale哈希。资源变动或源哈希过期须重生成，不沿用旧PASS。

完成稿先检查，再归档、原子发布、校验输出哈希和更新跟踪；保留原生域中间件，方便复查。检查只证明已验证的CSL缓存及文档保护，不证明Word插件实际刷新成功、图文分页完全正确或科学引用支持关系。

## 修复反馈与回归

当作者反馈“仍是原标识”“只出现部分文献”，优先留存文件及哈希，对比可见文字、字段缓存、唯一item/URI与原清单；未拿到刷新后的实际文件时，不能把某种插件故障当成已确认根因。禁止Computer Use时使用文件/API，不把界面点击作为必需条件。

回归至少覆盖：未渲染中间稿不能当完成稿；多来源却仅少数书目；错误编号；错误书目/题名；正文篡改；字段锁定；计划过期。`tests/test_rendered_references.py`含53来源却只保留4条书目的反例；这是合成工程回归，不是某篇私稿或Word Refresh实测。

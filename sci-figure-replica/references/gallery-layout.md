# 画廊、元数据与历史

## 目录与状态

正式路径由 `config.gallery_root` 提供；开发显式 `--gallery <独立测试画廊>`，不得写真实画廊。写画廊的三个 CLI（init_entry/build_index/dedupe）均要求 `--gallery`，不隐式读真实路径写入。

```text
GALLERY/
  index.html
  index.json
  POST/
    source.md                 # 帖子全文
    meta.json                 # 帖子级来源，非图条目
    article.html              # 有 HTML 输入时
    figures/figNN/
      meta.json
      README.md
      source/figNN.png        # 选定的单 panel 裁图；完整整图另存只读溯源
      source/full_original.png # 单 panel 来自组图时，完整原图另存
      original_code/
      code/replica.py|replica.R
      data/estimated_data.csv
      data/figure_spec.json
      output/replica.png|pdf|svg
      compare/side_by_side.png
      thumb.png
      qa_report.md
      run.log
      history/<UTC timestamp>/
```

这是完成条目的结构；`draft` 允许 output/compare 等待生成，不伪造成图。init 默认 draft/unknown/estimated/reconstructed 是计划分类，README 明示，不能据此声称已估读或重建。`review` 待作者目视，`approved` 必须有作者签核；`blocked` 记录阻塞。原图始终只读，全文/原代码保持来源可追溯。

## 选定来源单位

一个去重样式的代表单 panel 对应一个条目，实质结构变体用不同条目 id；历史整组条目仅作溯源保留，不再新增整组或收录进 Wiki。先生成所选逻辑 panel 的裁图 `CROPPED.png`，`dedupe.py --gallery DIR --image CROPPED.png --post-url URL --dry-run`，无匹配再 `init_entry.py --gallery DIR --post-slug SLUG --fig-id FIG_ID --source CROPPED.png`。不同代表用不同 FIG_ID；无 URL 时按 CLI 传标题与 account 代替 URL。

`source_image` 指向 init 保存的选定裁图，`source_image_sha256` 记录该裁图的 SHA-256。完整原图按原字节另存如 `source/full_original.png`，在 spec/README 明确记录它自己的路径、独立 SHA-256、所选 bbox（完整原图坐标，右/下端点不含）、来源 panel/重复位置及附属元素。裁图哈希和完整原图哈希都要记录，不能用一个代替另一个，不能用完整原图覆盖 `source_image`。同一完整原图的不同代表裁图可分别建条目；无需新增 schema/API。

复刻、compare、canvas 与 QA 指向选定裁图；完整原图保留供溯源，不能用裁图覆盖。`figure.panel_map` 与 `panels` 只描述本条目实际选定单位，inset/色标/边缘分布不单独计 panel。单 panel 可由内部 layout 页面表示，不要求先完成未选 panel。知识库沿用现有 `<条目 id>--<图型>` 模板 id；不同条目的结构变体不会同名。

## Metadata 与索引

`metadata.schema.json` 为 Draft2020-12 schema：post 含 title/account/author/publish_date/url，未知 null；figure 含 index/label/caption/panels/chart_types/canvas_px；scenarios 含 1–2 个主场景及 secondary/free；另含 language、data_provenance、code_provenance、original_code_provenance、files、status、version、source_image_sha256、created_at/updated_at。files 相对条目、用 /，不能有上跳或绝对路径。单 panel 的 source_image_sha256 是裁图哈希，完整来源哈希另记如上；数据与代码来源分别标注，不能混用。

索引扫描当前 `POST/figures/FIG/meta.json`，跳过帖子级、history 和嵌套测试目录。缩略图依次从 thumb.png、output/replica.png、source_image 所指原图获取；不存在的图不伪造链接。index.json 为数组；HTML 内联 CSS/JS，不依赖 CDN/服务器，UTF-8 离线可用，按主场景/语言/状态筛选。标题用 textContent、JSON 做 HTML 转义。

卡片 `links` 只含实际存在的 replica、compare、README；缺失项按顺序放进 `pending`（key、中文 label），显示“待生成”。例如 draft 只有原图和 README 时，README 可点，复刻图/并排图标为待生成，不能链接到尚不存在的 output/compare。build_index 不替代渲染，也不因文件缺失把 draft 伪标 approved。

## 去重与版本更新

`dedupe.py --gallery DIR --image PNG --post-url URL --dry-run` 先只读检查；单 panel 的 PNG 必须是与 init 相同的选定裁图。无 URL 时传 post-title/account。post_key 为规范 URL SHA-256 前 12 位（scheme/host 小写、去默认端口/fragment、query 排序、去常见追踪参数，保留微信文章身份参数），无 URL 则用标题+公众号；figure_key 为所传 source image SHA-256 前 12 位，匹配时比较其完整哈希。单 panel 因而按裁图去重；历史整图条目仅保留旧记录，不再新增。多重命中拒绝自动处理，视觉样式是否重复仍需 agent 判断。

再次传相同裁图会匹配各自条目；不要用 init 覆盖已有条目，init 对重复 id 会拒绝。需要更新时先 dedupe 留历史再修改当前版。完整原图来源相同不会把不同裁图强合并，完整来源哈希和 bbox 则保留它们之间的出处关系。

同源同图命中后非 dry-run 更新**原条目**：

1. 旧 meta.json、code、data、output、compare、README 进入 `history/<UTC timestamp>/`；若存在，thumb、qa_report、run.log 也留历史，避免当前索引显示旧产物。
2. source 和 original_code 保持不变；当前 version 加 1（如 1→2），回到 draft，重建空产物目录。
3. 填写新版本并重新渲染；README 记录历史入口，重建索引。索引只显示当前条目一次，不扫描历史版本。

## 失败与写入边界

新条目先在同目录临时目录完成再 rename；文件先写同目录临时文件再 replace；多文件先全部 stage，Python 异常恢复旧字节；dedupe 异常逆向恢复迁移。只支持单写者，跨多文件无操作系统级整体事务。断电或回滚本身失败需人工恢复，保留 history/.pending-* 或 backup 现场，不假称完整事务。不沿 symlink/junction 写出目标；权限/占用失败保留旧版并报告，不删除 ACL 受限目录。

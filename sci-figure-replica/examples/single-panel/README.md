# T2 single-panel examples

Three dev-local reconstructions from read-only `samples/post01/source/article_images/img06.png`, `img07.png`, `img08.png`. These images differ from the six-panel `fig01.png`; this folder does not implement T3. Do not execute article code. The examples import sibling `_example.py`, staged templates/scripts, and their own CSVs; keep that tree intact. No gallery/index/global installation is performed.

Run each `replica.py` with the configured dedicated Python interpreter. Optional `--out <directory>` directs generated files elsewhere. Each exports `output/replica.png|pdf|svg`, `compare/side_by_side.png`, `figure_spec.json`, `render.log`, and `run.log`. A runner may replace `run.log` with its captured runtime record; `render.log` retains visual iteration history. Image comparison uses equal content height, 24 px gap, 36 px header and 24 px figure/date footer. Sources are never overwritten.

From the development root in PowerShell:

```powershell
$py = 'C:\Users\86186\.codex\venvs\sci-figure-replica\Scripts\python.exe'
& $py -X utf8 staged\sci-figure-replica\examples\single-panel\bar_inset\replica.py
& $py -X utf8 staged\sci-figure-replica\examples\single-panel\beeswarm\replica.py
& $py -X utf8 staged\sci-figure-replica\examples\single-panel\radial\replica.py
```

All CSVs have `provenance=estimated`. A/C transcribe printed numbers; B is a synthetic visual approximation with 192 constructed points per feature after T2 F2. None contains original observations, fitted SHAP results or evidence for statistical inference. The development helper `codex/build_t2_example_data.py` records the initial transcription/fixtures; B's current deterministic generator is `beeswarm/generate_estimated.py`. Renderers only read the committed CSVs. Standalone B matches img07 without an extra colorbar and uses the full plotting width; density remains a visual approximation.

Style: Arial when available, then Microsoft YaHei / SimHei / DejaVu Sans; 600 dpi PNG; PDF TrueType type 42; SVG live text. Exact actual font, source SHA-256, canvas bounds, inset bounds, palette and domains are in each figure spec. Standalone sources have no A/B/C letter, so examples do not add one; `panel_label` is available for future composition. `volume` is the canonical CSV key; the source spelling `volumn` is retained in visible A/C labels.

A and C share the same five-stop blue→white→red colormap, [0,17.4089] value domain and red-high direction. A uses an empirical continuous monotone value→color calibration from visible bar colors (`bar_inset/color_calibration.json`); its bars, inset and colorbar share that exact normalization. C uses linear normalization. This models their observed visual difference; it does not recover or claim the original plotting normalization. Applying the same linear function to A failed the unchanged ΔE00 criterion, as recorded in the delivery evidence.

Reports use the fixed ten-item visual checklist, with PASS/WARN/FAIL plus concrete reasons. `status=review`; author visual acceptance remains pending. Format structure and font streams are checked mechanically; PDF opening/rendering in a separate viewer is not established by nonempty files.

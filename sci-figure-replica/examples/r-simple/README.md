# Synthetic R runtime example

Six synthetic group/condition means and SD values demonstrate ggplot2 bars with error bars. These values are invented demonstration data (`provenance=synthetic`), not experimental measurements or a 1:1 reconstruction of any post.

Run from any working directory with `D:/R-4.5.0/bin/Rscript.exe --vanilla <absolute-path>/replica.R`, or use `scripts/run_code.py --language r --code <path>/replica.R --cwd <path>`. Data and the theme resolve relative to this script. Optional `SCI_FIGURE_R_CJK=1` exercises an installed Microsoft YaHei/SimHei subtitle and records the actual font path.

`reference/synthetic.png` is the fixed, same-data synthetic reference, initialized once and left unchanged on reruns. `output/` contains 600 dpi PNG, cairo PDF and SVG. See `output/replica-devices.txt` for actual devices: base R SVG fallback can outline glyphs and therefore carries an editable-text WARN. `sessionInfo.txt`, `run.log`, stdout/stderr retain execution evidence. `compare/side_by_side.png` and `qa_report.md` record the comparison. Same-data agreement only verifies the export pipeline, not target-image fidelity, statistical validity or author approval.

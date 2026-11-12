# Synthetic runtime/export demonstration, not a reconstruction of a real post.
file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(file_arg) != 1) stop("Run with Rscript --vanilla replica.R")
here <- dirname(normalizePath(sub("^--file=", "", file_arg), winslash = "/", mustWork = TRUE))
source(file.path(here, "../../templates/r_style.R"), encoding = "UTF-8")
data <- read.csv(file.path(here, "data.csv"), stringsAsFactors = FALSE)
stopifnot(nrow(data) == 6, all(data$provenance == "synthetic"))
data$group <- factor(data$group, levels = c("A", "B", "C"))
data$condition <- factor(data$condition, levels = c("Control", "Treatment"))
font <- "Arial"
subtitle <- NULL
if (identical(Sys.getenv("SCI_FIGURE_R_CJK"), "1")) {
  registered <- register_cjk_font()
  font <- registered$family
  subtitle <- "合成示例"
  writeLines(c(registered$family, registered$file), file.path(here, "cjk-font.txt"), useBytes = TRUE)
}
plot <- ggplot2::ggplot(data, ggplot2::aes(group, mean, fill = condition)) +
  ggplot2::geom_col(position = ggplot2::position_dodge(width = 0.75), width = 0.65) +
  ggplot2::geom_errorbar(ggplot2::aes(ymin = mean - sd, ymax = mean + sd),
                       position = ggplot2::position_dodge(width = 0.75), width = 0.18, linewidth = 0.3) +
  ggplot2::scale_fill_manual(values = c("#2f84b1", "#f6b08a")) +
  ggplot2::scale_y_continuous(limits = c(0, 6.5), expand = ggplot2::expansion(mult = c(0, 0))) +
  ggplot2::labs(x = "Group", y = "Synthetic value (mean +/- SD)", subtitle = subtitle) +
  theme_pub(base_family = font) + ggplot2::theme(legend.position = "top")
save_pub(plot, file.path(here, "output/replica"), width = 4, height = 3)
# The fixed reference is created once from this same synthetic dataset; reruns never replace it.
reference <- file.path(here, "reference/synthetic.png")
if (!file.exists(reference)) {
  dir.create(dirname(reference), recursive = TRUE, showWarnings = FALSE)
  if (!file.copy(file.path(here, "output/replica.png"), reference)) stop("Cannot create fixed synthetic reference")
}
writeLines(capture.output(sessionInfo()), file.path(here, "sessionInfo.txt"), useBytes = TRUE)
cat("Synthetic R example: 3 groups x 2 conditions; mean +/- SD; PNG/PDF/SVG exported\n")
cat(R.version.string, "\n")

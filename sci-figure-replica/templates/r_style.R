# Standalone publication theme. No medfig/figkit dependencies or package installs.
if (!requireNamespace("ggplot2", quietly = TRUE)) {
  stop("Missing R package ggplot2. Ask the author to provision the local user library; no automatic installation.")
}

theme_pub <- function(base_size = 7, base_family = "Arial") {
  ggplot2::theme_classic(base_size = base_size, base_family = base_family) +
    ggplot2::theme(axis.line = ggplot2::element_line(colour = "black", linewidth = 0.3),
                   axis.ticks = ggplot2::element_line(colour = "black", linewidth = 0.3),
                   panel.grid = ggplot2::element_blank(),
                   plot.title = ggplot2::element_blank(),
                   legend.title = ggplot2::element_blank())
}

register_cjk_font <- function() {
  if (.Platform$OS.type != "windows") {
    stop("CJK registration requires a verified local font. Supply a local CJK font on this platform; rendering stopped to avoid tofu.")
  }
  candidates <- c("Microsoft YaHei" = "msyh.ttc", "SimHei" = "simhei.ttf")
  for (family in names(candidates)) {
    font_file <- file.path(Sys.getenv("WINDIR", "C:/Windows"), "Fonts", candidates[[family]])
    if (file.exists(font_file)) {
      attempt <- try(do.call(grDevices::windowsFonts,
                            setNames(list(grDevices::windowsFont(family)), family)), silent = TRUE)
      if (!inherits(attempt, "try-error")) {
        message("CJK font: ", family, "; file=", normalizePath(font_file, winslash = "/"))
        return(list(family = family, file = normalizePath(font_file, winslash = "/")))
      }
    }
  }
  stop("Microsoft YaHei/SimHei not found or windowsFonts registration failed. Supply a local installed CJK font; rendering stopped to avoid tofu.")
}

save_pub <- function(plot, stem, width, height) {
  if (!isTRUE(capabilities("cairo"))) stop("cairo unavailable: PDF/SVG export cannot proceed. Check local R build; no packages installed.")
  dir.create(dirname(stem), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(paste0(stem, ".png"), plot = plot, width = width, height = height,
                  units = "in", dpi = 600, bg = "white")
  ggplot2::ggsave(paste0(stem, ".pdf"), plot = plot, width = width, height = height,
                  units = "in", device = grDevices::cairo_pdf, bg = "white")
  has_svglite <- requireNamespace("svglite", quietly = TRUE)
  svg_device <- if (has_svglite) svglite::svglite else grDevices::svg
  ggplot2::ggsave(paste0(stem, ".svg"), plot = plot, width = width, height = height,
                  units = "in", device = svg_device, bg = "white")
  devices <- c("PNG: ggsave png, 600 dpi", "PDF: grDevices::cairo_pdf",
               if (has_svglite) "SVG: svglite::svglite" else
                 "SVG: grDevices::svg (cairo fallback); WARN: glyph outlines, editable text not guaranteed")
  writeLines(devices, paste0(stem, "-devices.txt"), useBytes = TRUE)
  message(paste(devices, collapse = "\n"))
  invisible(devices)
}

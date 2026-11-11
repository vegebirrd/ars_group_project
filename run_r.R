#!/usr/bin/env Rscript
# Run from repository root: Rscript run_r.R --stage all
args <- commandArgs(trailingOnly = TRUE)
if (!file.exists("R/helpers.R")) stop("Run from the ars_group_project repository root")
source("R/helpers.R")
check_dependencies()
ensure_dirs()

stage <- "all"
if ("--stage" %in% args) {
  idx <- match("--stage", args)
  if (idx == length(args)) stop("Give a value after --stage")
  stage <- args[idx + 1L]
}
valid <- c("all", "prepare", "attention", "consumption", "figures", "text")
if (!stage %in% valid) stop("--stage must be one of: ", paste(valid, collapse=", "))

run_module <- function(name) {
  cat("\n[ARS] ", name, "\n", sep="")
  source(file.path("R", name), local = new.env(parent = globalenv()))
}

if (stage %in% c("all", "prepare", "attention") ||
    (stage %in% c("consumption", "text") && !file.exists("outputs/r/events_model_data.csv"))) {
  run_module("01_prepare.R")
}
if (stage %in% c("all", "attention")) {
  for (name in c("02_rq1_attention.R", "04_rq2_heterogeneity.R",
                 "05_matching.R", "06_robustness.R")) run_module(name)
}
if (stage %in% c("all", "consumption")) run_module("03_rq1_consumption.R")
if (stage %in% c("all", "attention", "figures")) run_module("07_figures.R")
if (stage %in% c("all", "attention")) run_module("08_summary.R")
if (stage %in% c("all", "text")) run_module("09_text_analysis.R")
cat("\nDone. Tables: outputs/r/ | Figures: outputs/r/figures/\n")

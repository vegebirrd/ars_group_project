# Run from the repository root: Rscript scripts/install_r_packages.R
packages <- c("ggplot2", "fixest", "dplyr", "readr", "tidyr", "MatchIt", "cobalt")
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) install.packages(missing, repos = "https://cloud.r-project.org")
cat("R package prerequisites available: ", paste(packages, collapse = ", "), "\n", sep = "")

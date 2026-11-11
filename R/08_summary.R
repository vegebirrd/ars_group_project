# Generate a compact, result-linked research memo from *computed* tables.
source("R/helpers.R")
ensure_dirs()
coverage <- read_csv_checked("outputs/r/coverage.csv", c("n_complete", "n_pages", "n_daily"))
coefs <- read_csv_checked("outputs/r/RQ1_regressions.csv", c("model", "term", "estimate", "se", "p_value"))
row <- coefs[coefs$model == "M3L_pretrend" & coefs$term == "x", , drop = FALSE]
fmt <- function(z) if (length(z) && is.finite(z[1])) sprintf("%.3f", z[1]) else "NA"

lines <- c(
  "# Empirical findings — generated from local R outputs",
  "",
  sprintf("- Complete attention events in the locally supplied analysis input: **%s**.", coverage$n_complete[1]),
  sprintf("- Distinct artist Wikipedia page clusters: **%s**.", coverage$n_pages[1]),
  sprintf("- Daily event records: **%s**.", coverage$n_daily[1]),
  sprintf("- Primary M3L association per 1-point increase in rating: **%s log points** (SE **%s**, p **%s**).",
          fmt(row$estimate), fmt(row$se), fmt(row$p_value)),
  "",
  "## Files to cite in the preliminary presentation",
  "",
  "- `RQ1_regressions.csv`: main regressions, pre-review placebo, persistence and abnormal attention.",
  "- `RQ1_window_group_cluster_ci.csv`: uncertainty for pre-review, short and long windows.",
  "- `RQ1_weekly_score_coefficients.csv`: event-time profile of conditional rating slopes.",
  "- `RQ1_persistence_tests.csv`: direct tests of short-versus-long association.",
  "- `RQ1_same_sample_release_models.csv`: release confounding on identical dated samples.",
  "- `RQ1_U_shape_diagnostic.csv`: sample-support endpoint slopes and U-shaped joint test.",
  "- `RQ1_robustness.csv`: release and baseline-window sensitivity.",
  "- `RQ2_heterogeneity.csv`: prior popularity and genre interactions.",
  "- `RQ2_popularity_marginal_score_slopes.csv`: score slopes at popularity quantiles.",
  "- `RQ2_distribution_by_popularity_score.csv`: relative and absolute gains with cluster CIs.",
  "- `RQ2_genre_interaction_joint_test.csv`: joint test of genre-related differences.",
  "- `RQ2_matching_contrasts.csv`: matched score comparison, interpreted descriptively.",
  "- `RQ1_consumption_regressions.csv`: observed Spotify chart visibility only, if chart data are available.",
  "- `figures/`: R-generated figure source in `R/07_figures.R`.",
  "",
  "## Substantive interpretation",
  "",
  "Compare score associations across short, medium, long and abnormal-attention outcomes.",
  "Release timing and pre-publication trajectories are reported beside post-publication estimates.",
  "RQ2 compares proportional attention change and additional daily visits across prior-popularity levels.",
  ""
)
writeLines(lines, "outputs/r/RESEARCH_FINDINGS.md")
cat("Research memo written to outputs/r/RESEARCH_FINDINGS.md\n")

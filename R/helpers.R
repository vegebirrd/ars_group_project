# Shared conventions for the ARS empirical modules.
required_packages <- c("ggplot2", "fixest", "dplyr", "readr", "tidyr", "MatchIt", "cobalt")

check_dependencies <- function(packages = required_packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", "),
                            "\nRun: Rscript scripts/install_r_packages.R")
}

ensure_dirs <- function() {
  dir.create("outputs/r", recursive = TRUE, showWarnings = FALSE)
  dir.create("outputs/r/figures", recursive = TRUE, showWarnings = FALSE)
  dir.create("data/processed", recursive = TRUE, showWarnings = FALSE)
}

read_csv_checked <- function(path, columns) {
  if (!file.exists(path)) stop("Missing input: ", path,
                              "\nSee QUICKSTART.md to build local data using the Python data pipeline.")
  x <- readr::read_csv(path, show_col_types = FALSE, progress = FALSE)
  absent <- setdiff(columns, names(x))
  if (length(absent)) stop("Input ", path, " lacks columns: ", paste(absent, collapse = ", "))
  as.data.frame(x)
}

score_group <- function(x) {
  factor(cut(x, breaks = c(-Inf, 5, 8, Inf), right = FALSE,
             labels = c("Low (<5)", "Middle (5–<8)", "High (>=8)")),
         levels = c("Low (<5)", "Middle (5–<8)", "High (>=8)"))
}

main_events <- function(events) {
  # A modern cohort is the principal extension. An explicit environment setting
  # can select the historical cohort for strict reproducibility.
  mode <- Sys.getenv("ARS_COHORT", unset="auto")
  if (!mode %in% c("auto", "modern", "historical", "all"))
    stop("ARS_COHORT must be auto, modern, historical or all")
  year <- as.integer(events$year)
  if (mode == "auto") mode <- if (any(year %in% 2020:2025)) "modern" else "historical"
  period <- switch(mode,
    modern=events[year %in% 2020:2025,,drop=FALSE],
    historical=events[year %in% 2018:2019,,drop=FALSE],
    all=events[year %in% 2018:2025,,drop=FALSE])
  if (!nrow(period)) stop(paste("No events for",mode,"cohort"))
  period$baseline_centered <- period$baseline - stats::median(period$baseline,na.rm=TRUE)
  period$lowpop <- as.integer(period$baseline < stats::median(period$baseline,na.rm=TRUE))
  period
}

safe_feols <- function(formula, data, cluster = "page_key", min_n = 15L, min_groups = 8L) {
  vars <- all.vars(formula)
  needed <- unique(c(vars, cluster))
  absent <- setdiff(needed, names(data))
  if (length(absent)) {warning("Regression input missing: ", paste(absent, collapse = ", ")); return(NULL)}
  df <- data[stats::complete.cases(data[, needed, drop = FALSE]), , drop = FALSE]
  if (nrow(df) < min_n || length(unique(df[[cluster]])) < min_groups) return(NULL)
  cluster_formula <- stats::as.formula(paste("~", cluster))
  tryCatch(fixest::feols(formula, data = df, vcov = cluster_formula),
           error = function(e) {
             warning("Regression skipped: ", conditionMessage(e))
             NULL
           })
}

tidy_feols <- function(model, model_name, outcome, sample_name = "primary") {
  if (is.null(model)) return(data.frame())
  ct <- as.matrix(fixest::coeftable(model))
  if (nrow(ct) == 0) return(data.frame())
  est <- as.numeric(ct[, 1]); se <- as.numeric(ct[, 2])
  stat <- as.numeric(ct[, 3]); p <- as.numeric(ct[, 4])
  data.frame(sample = sample_name, outcome = outcome, model = model_name,
             term = rownames(ct), estimate = est, se = se, statistic = stat,
             p_value = p, ci_low_approx = est - 1.96 * se,
             ci_high_approx = est + 1.96 * se, n = stats::nobs(model),
             row.names = NULL)
}

bind_rows_safe <- function(...) {
  d <- list(...)
  d <- Filter(function(z) !is.null(z) && NROW(z) > 0, d)
  if (!length(d)) return(data.frame())
  dplyr::bind_rows(d)
}

write_csv_safe <- function(x, file) {
  dir.create(dirname(file), recursive = TRUE, showWarnings = FALSE)
  if (!ncol(x)) {
    writeLines("# No eligible observations for this analysis", file)
  } else readr::write_csv(x, file, na = "")
}

write_model_table <- function(models, path) {
  models <- Filter(Negate(is.null), models)
  if (!length(models)) return(invisible(NULL))
  lines <- capture.output(do.call(fixest::etable, c(models, list(digits = 3))))
  writeLines(lines, path)
  invisible(path)
}

save_plot <- function(plot, filename, width = 8, height = 5) {
  ggplot2::ggsave(file.path("outputs/r/figures", filename), plot = plot,
                  width = width, height = height, dpi = 200, units = "in")
}

research_theme <- function() {
  ggplot2::theme_minimal(base_size = 12) +
    ggplot2::theme(plot.title = ggplot2::element_text(face = "bold"),
                   legend.position = "bottom",
                   panel.grid.minor = ggplot2::element_blank())
}

get_release_subset <- function(df) {
  df[is.finite(df$release_lag), , drop = FALSE]
}

u_shape_diagnostic <- function(model, scores, page_count) {
  if (is.null(model)) return(data.frame())
  b <- stats::coef(model)
  V <- stats::vcov(model)
  if (!all(c("x", "I(x^2)") %in% names(b))) return(data.frame())
  beta1 <- unname(b[["x"]]); beta2 <- unname(b[["I(x^2)"]])
  low <- min(scores, na.rm = TRUE) - 7
  high <- max(scores, na.rm = TRUE) - 7
  deriv <- function(z) {
    slope <- beta1 + 2 * z * beta2
    v <- V["x", "x"] + (2 * z)^2 * V["I(x^2)", "I(x^2)"] +
      4 * z * V["x", "I(x^2)"]
    c(slope = slope, se = sqrt(max(v, 0)))
  }
  left <- deriv(low); right <- deriv(high)
  df <- max(page_count - 1L, 1L)
  p_left <- if (left[["se"]] > 0) stats::pt(left[["slope"]] / left[["se"]], df) else NA_real_
  p_right <- if (right[["se"]] > 0) stats::pt(-right[["slope"]] / right[["se"]], df) else NA_real_
  data.frame(score_min = low + 7, score_max = high + 7,
             curvature = beta2, turning_score = if (abs(beta2) > 1e-12) 7 - beta1 / (2 * beta2) else NA_real_,
             slope_at_low_score = left[["slope"]], slope_at_high_score = right[["slope"]],
             p_one_sided_left = p_left, p_one_sided_right = p_right,
             p_joint_U = max(p_left, p_right, na.rm = TRUE))
}

# Cluster-aware descriptive confidence intervals for equally weighted events.
# K=1 CR1 correction G/(G-1); cluster sums retain multiple events on a page.
cluster_mean_ci <- function(df, outcome, cluster = "page_key") {
  d <- df[is.finite(df[[outcome]]) & !is.na(df[[cluster]]), , drop = FALSE]
  n <- nrow(d); G <- length(unique(d[[cluster]]))
  if (n == 0L) return(data.frame(n=0L, clusters=0L, mean=NA_real_, se=NA_real_, ci_low=NA_real_, ci_high=NA_real_))
  mu <- mean(d[[outcome]])
  if (G < 3L) return(data.frame(n=n, clusters=G, mean=mu, se=NA_real_, ci_low=NA_real_, ci_high=NA_real_))
  sums <- tapply(d[[outcome]] - mu, d[[cluster]], sum)
  se <- sqrt((G/(G-1)) * sum(sums^2)/n^2)
  half <- stats::qt(.975, G-1L) * se
  data.frame(n=n, clusters=G, mean=mu, se=se, ci_low=mu-half, ci_high=mu+half)
}

# t-reference for one linear combination of coefficients, using the CR1
# covariance stored by fixest and the number of distinct page clusters.
linear_contrast <- function(model, weights, clusters, label) {
  if (is.null(model)) return(data.frame())
  b <- stats::coef(model); V <- stats::vcov(model)
  if (!all(names(weights) %in% names(b))) return(data.frame())
  w <- setNames(rep(0, length(b)), names(b)); w[names(weights)] <- weights
  est <- sum(w*b)
  se <- sqrt(max(0, as.numeric(t(w) %*% V %*% w)))
  dof <- max(1L, as.integer(clusters)-1L)
  critical <- stats::qt(.975, dof)
  data.frame(contrast=label, estimate=est, se=se, df=dof,
             ci_low=est-critical*se, ci_high=est+critical*se,
             p_value=if (se>0) 2*stats::pt(-abs(est/se),dof) else NA_real_)
}

# Small-sample approximate joint Wald F for score-by-group interactions.
# Cluster count should be measured on the estimation sample, not the input.
cluster_wald <- function(model, terms, clusters, label) {
  if (is.null(model)) return(data.frame())
  b <- stats::coef(model); V <- stats::vcov(model)
  if (!length(terms) || !all(terms %in% names(b))) return(data.frame())
  q <- length(terms)
  tryCatch({
    z <- unname(b[terms]); W <- unname(V[terms,terms,drop=FALSE])
    F_stat <- as.numeric(t(z) %*% solve(W, z))/q
    data.frame(test=label, q=q, cluster_df=max(clusters-1,1),
               F=F_stat, p_value=stats::pf(F_stat,q,max(clusters-1,1),lower.tail=FALSE))
  }, error=function(e) data.frame(test=label,q=q,cluster_df=clusters-1,F=NA_real_,p_value=NA_real_))
}

# RQ1 | Review valence, short-run attention, persistence, abnormal attention.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
                                  c("score", "short_delta", "mid_delta", "long_delta", "x", "baseline", "trend_week", "page_key")))
ev$score_group <- score_group(ev$score)

fits <- list(
  M1_score_only = safe_feols(short_delta ~ x, ev),
  M2_quadratic = safe_feols(short_delta ~ x + I(x^2), ev),
  M3L_pretrend = safe_feols(short_delta ~ x + baseline + trend_week, ev),
  M3_quadratic_controlled = safe_feols(short_delta ~ x + I(x^2) + baseline + trend_week, ev),
  M4_increment = safe_feols(increment ~ x + baseline + trend_week, ev),
  M5_day1to7 = safe_feols(short_no_day0_delta ~ x + baseline + trend_week, ev),
  M6_preweek_placebo = safe_feols(preweek_delta ~ x + baseline + trend_week, ev),
  M7_abnormal = safe_feols(abnormal_post7 ~ x + baseline + trend_week, ev),
  M8_abnormal_increment = safe_feols(abnormal_increment ~ x + baseline + trend_week, ev),
  M9_medium = safe_feols(mid_delta ~ x + baseline + trend_week, ev),
  M10_long = safe_feols(long_delta ~ x + baseline + trend_week, ev)
)

coef_table <- dplyr::bind_rows(lapply(names(fits), function(label) {
  k <- fits[[label]]
  dep <- if (is.null(k)) "unknown" else all.vars(stats::formula(k))[1]
  tidy_feols(k, label, dep)
}))
write_csv_safe(coef_table, "outputs/r/RQ1_regressions.csv")
write_model_table(fits[c("M1_score_only", "M2_quadratic", "M3L_pretrend", "M3_quadratic_controlled")],
                  "outputs/r/RQ1_main_models.txt")
write_model_table(fits[c("M4_increment", "M6_preweek_placebo", "M7_abnormal", "M8_abnormal_increment", "M9_medium", "M10_long")],
                  "outputs/r/RQ1_dynamics.txt")

shape <- u_shape_diagnostic(fits$M3_quadratic_controlled, ev$score, length(unique(ev$page_key)))
write_csv_safe(shape, "outputs/r/RQ1_U_shape_diagnostic.csv")

long_desc <- dplyr::bind_rows(lapply(c("preweek_delta", "short_delta", "mid_delta", "long_delta", "increment",
                                      "abnormal_pre7", "abnormal_post7"), function(outcome) {
  x <- ev[[outcome]]
  data.frame(outcome = outcome, n = sum(is.finite(x)), mean = mean(x, na.rm = TRUE),
             median = stats::median(x, na.rm = TRUE), sd = stats::sd(x, na.rm = TRUE))
}))
write_csv_safe(long_desc, "outputs/r/RQ1_time_windows.csv")

by_score <- ev |>
  dplyr::group_by(score_group) |>
  dplyr::summarise(n = dplyr::n(), preweek = mean(preweek_delta),
                   short = mean(short_delta), medium = mean(mid_delta),
                   long = mean(long_delta), abnormal = mean(abnormal_post7), .groups = "drop")
write_csv_safe(by_score, "outputs/r/RQ1_score_groups.csv")
cat("RQ1 complete:", nrow(ev), "events;", length(unique(ev$page_key)), "pages\n")


# --- 10 RQ1 CORE INFERENCE ---
# RQ1 | Formal descriptive inference, dynamics, persistence and release confounding.
# Run after R/01_prepare.R. All estimation uses review events, page-clustered CR1.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
              c("reviewid", "score", "short_delta", "preweek_delta", "mid_delta",
                "long_delta", "increment", "baseline", "trend_week", "page_key")))
ev$score_group <- score_group(ev$score)
ev$score_group_ref <- stats::relevel(ev$score_group, ref = "Middle (5–<8)")
ev$short_minus_long <- ev$short_delta - ev$long_delta

# Transparent denominator and identity/overlap audit.
audit <- data.frame(
  estimand = paste0(min(ev$year),"–",max(ev$year)," scored Wikipedia complete events"),
  n_events = nrow(ev), n_pages = length(unique(ev$page_key)),
  n_low = sum(ev$score < 5), n_middle = sum(ev$score >= 5 & ev$score < 8),
  n_high = sum(ev$score >= 8),
  n_release_dated = sum(is.finite(ev$release_lag)),
  n_release_near7 = sum(is.finite(ev$release_lag) & abs(ev$release_lag) <= 7),
  n_overlapping_page_windows = sum(ev$overlapping_page_event == 1, na.rm=TRUE),
  n_missing_genre = sum(is.na(ev$genre_group) | ev$genre_group == "Unknown")
)
write_csv_safe(audit, "outputs/r/RQ1_sample_audit.csv")

windows <- c(preweek_delta="Pre-review days −7:−1",
             short_delta="Post-review days 0:6",
             mid_delta="Post-review days 7:27",
             long_delta="Post-review days 28:55",
             increment="Post minus pre-adjacent week")
window_ci <- bind_rows_safe(lapply(names(windows), function(v) {
  bind_rows_safe(lapply(levels(ev$score_group), function(g) {
    z <- ev[ev$score_group == g, , drop=FALSE]
    cbind(data.frame(outcome=v, window=unname(windows[[v]]), score_group=g),
          cluster_mean_ci(z, v))
  }))
}))
write_csv_safe(window_ci, "outputs/r/RQ1_window_group_cluster_ci.csv")

# Middle-score reference. This tests conditional group contrasts; not an
# interpretation of score strata as objectively positive/negative language.
group_models <- list(
  PostWeek = safe_feols(short_delta ~ score_group_ref + baseline + trend_week, ev),
  AdjacentWeekIncrement = safe_feols(increment ~ score_group_ref + baseline + trend_week, ev),
  LongRun = safe_feols(long_delta ~ score_group_ref + baseline + trend_week, ev),
  Decay = safe_feols(short_minus_long ~ score_group_ref + baseline + trend_week, ev)
)
write_csv_safe(bind_rows_safe(lapply(names(group_models), function(nm)
  if (is.null(group_models[[nm]])) data.frame() else tidy_feols(group_models[[nm]],nm,all.vars(stats::formula(group_models[[nm]]))[1]))),
  "outputs/r/RQ1_group_contrasts.csv")
write_model_table(group_models, "outputs/r/RQ1_group_contrasts.txt")

# Directly test whether the score association is transitory. A positive score
# slope in the short-minus-long model means a larger short-vs-long association.
persistence <- list(
  AdjacentWeek = safe_feols(increment ~ x + baseline + trend_week, ev),
  ShortMinusMedium = safe_feols(I(short_delta-mid_delta) ~ x + baseline + trend_week, ev),
  ShortMinusLong = safe_feols(short_minus_long ~ x + baseline + trend_week, ev),
  PreReviewPlacebo = safe_feols(preweek_delta ~ x + baseline + trend_week, ev)
)
write_csv_safe(bind_rows_safe(lapply(names(persistence),function(nm)
  if (is.null(persistence[[nm]])) data.frame() else tidy_feols(persistence[[nm]],nm,all.vars(stats::formula(persistence[[nm]]))[1]))),
  "outputs/r/RQ1_persistence_tests.csv")

# Group-average event-time paths: CR1 cluster interval at each weekly point.
daily <- read_csv_checked("outputs/r/pageview_event_daily.csv",
                          c("reviewid","event_day","log_views"))
daily$reviewid <- as.character(daily$reviewid)
ev$reviewid <- as.character(ev$reviewid)
daily <- dplyr::inner_join(daily,ev[,c("reviewid","score_group","x","baseline","trend_week","page_key")],
                            by="reviewid",relationship="many-to-one")
daily$event_week <- floor(daily$event_day / 7)
weekly <- daily |>
  dplyr::filter(event_week >= -8 & event_week <= 7) |>
  dplyr::group_by(reviewid, event_week, score_group, x, baseline, trend_week, page_key) |>
  dplyr::summarise(relative_log=mean(log_views)-dplyr::first(baseline),
                   n_days=dplyr::n(), .groups="drop") |>
  dplyr::filter(n_days == 7)
write_csv_safe(weekly,"outputs/r/RQ1_weekly_event_outcomes.csv")
weekly_ci <- weekly |>
  dplyr::group_by(event_week,score_group) |>
  dplyr::group_modify(~cluster_mean_ci(.x,"relative_log","page_key")) |>
  dplyr::ungroup()
write_csv_safe(weekly_ci,"outputs/r/RQ1_weekly_group_cluster_ci.csv")

weekly_models <- lapply(sort(unique(weekly$event_week)),function(w) {
  z <- weekly[weekly$event_week == w,,drop=FALSE]
  m <- safe_feols(relative_log ~ x + baseline + trend_week, z)
  ans <- tidy_feols(m,paste0("week_",w),"relative_log")
  if (!nrow(ans)) return(data.frame())
  ans$event_week <- w
  ans$n_pages <- length(unique(z$page_key))
  ans
})
write_csv_safe(bind_rows_safe(weekly_models),"outputs/r/RQ1_weekly_score_coefficients.csv")

# Exactly the same dated-release subsample in all columns, so the effect of
# adding release controls is not confounded with a changing denominator.
dated <- ev[is.finite(ev$release_lag),,drop=FALSE]
if (nrow(dated) >= 30L) {
  models <- list(
    Dated_linear = safe_feols(short_delta ~ x + baseline + trend_week, dated),
    Dated_quadratic = safe_feols(short_delta ~ x + I(x^2) + baseline + trend_week, dated),
    Dated_release_linear = safe_feols(short_delta ~ x + baseline + trend_week + release_log_days + release_near7, dated),
    Dated_release_quadratic = safe_feols(short_delta ~ x + I(x^2) + baseline + trend_week + release_log_days + release_near7, dated)
  )
  recent <- dated[dated$release_lag >= -28 & dated$release_lag <= 365,,drop=FALSE]
  if (nrow(recent) >= 30L) {
    models$Recent_linear <- safe_feols(short_delta ~ x + baseline + trend_week + release_log_days + release_near7,recent)
    models$Recent_quadratic <- safe_feols(short_delta ~ x + I(x^2) + baseline + trend_week + release_log_days + release_near7,recent)
  }
  release_table <- bind_rows_safe(lapply(names(models),function(nm) {
    dd <- if (startsWith(nm,"Recent")) recent else dated
    v <- tidy_feols(models[[nm]],nm,"short_delta",nm)
    if (!nrow(v)) return(data.frame())
    v$n_pages <- length(unique(dd$page_key));v
  }))
  write_csv_safe(release_table,"outputs/r/RQ1_same_sample_release_models.csv")
  shape <- bind_rows_safe(lapply(names(models)[grepl("quadratic",names(models))],function(nm) {
    dd <- if (startsWith(nm,"Recent")) recent else dated
    z <- u_shape_diagnostic(models[[nm]],dd$score,length(unique(dd$page_key)))
    if (nrow(z))z$specification <- nm
    z
  }))
  write_csv_safe(shape,"outputs/r/RQ1_release_Ushape_tests.csv")
}
cat("RQ1 inference audit, grouped intervals, dynamic score profiles, persistence and release sensitivity complete\n")


# --- 15 MODERN RQ1 YEAR CONTROLLED ---
# Extended-cohort RQ1: review score and attention with review-year controls.
# This is the main econometric specification for 2020–2025.
source("R/helpers.R")
check_dependencies();ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
    c("score","year","short_delta","preweek_delta","long_delta","baseline","trend_week","page_key")))
ev$x <- ev$score-7
ev$year_factor <- factor(ev$year)
models <- list(
 Year_adjusted = safe_feols(short_delta ~ x+baseline+trend_week+year_factor,ev),
 Year_adjusted_quadratic = safe_feols(short_delta ~ x+I(x^2)+baseline+trend_week+year_factor,ev),
 Year_adjusted_preweek_placebo = safe_feols(preweek_delta ~ x+baseline+trend_week+year_factor,ev),
 Year_adjusted_persistence = safe_feols(I(short_delta-long_delta) ~ x+baseline+trend_week+year_factor,ev)
)
if ("release_lag" %in% names(ev)) {
 dated <- ev[is.finite(ev$release_lag),,drop=FALSE]
 if (nrow(dated)>30L) {
   models$Release_adjusted <- safe_feols(short_delta ~ x+baseline+trend_week+
                     release_log_days+release_near7+year_factor,dated)
   models$Release_adjusted_quadratic <- safe_feols(short_delta ~ x+I(x^2)+baseline+trend_week+
                     release_log_days+release_near7+year_factor,dated)
 }
}
write_csv_safe(bind_rows_safe(lapply(names(models),function(nm){
 if (is.null(models[[nm]])) return(data.frame())
 tidy_feols(models[[nm]],nm,all.vars(stats::formula(models[[nm]]))[1],"year_adjusted")
})),"outputs/r/RQ1_year_adjusted_regressions.csv")
write_model_table(models,"outputs/r/RQ1_year_adjusted_models.txt")

# Survey-style design weights correct known intentional score oversampling,
# but do NOT correct for Wikipedia match/complete-page selection.
if ("selection_probability" %in% names(ev)) {
 wt <- ev[is.finite(ev$selection_probability) & ev$selection_probability>0,,drop=FALSE]
 wt$design_weight <- 1/wt$selection_probability
 if (nrow(wt)>=30 && length(unique(wt$page_key))>=10) {
  m <- tryCatch(fixest::feols(short_delta ~ x+baseline+trend_week+year_factor,
     data=wt,vcov=~page_key,weights=~design_weight),error=function(e)NULL)
  write_csv_safe(tidy_feols(m,"Known_design_probabilities","short_delta","year_score_strata"),
                 "outputs/r/RQ1_known_sampling_weights.csv")
 }
}
cat("Modern year-adjusted RQ1 models complete\n")

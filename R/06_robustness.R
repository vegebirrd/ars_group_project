# Sensitivity to event windows, release timing, time effects, and baseline choice.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
                                  c("reviewid", "score", "x", "short_delta", "baseline", "trend_week", "page_key")))
day <- read_csv_checked("outputs/r/pageview_event_daily.csv",
                        c("reviewid", "event_day", "views", "log_views"))

specifications <- list(
  Main_0to6 = list(data = ev, form = short_delta ~ x + baseline + trend_week),
  Exclude_Day_Zero = list(data = ev, form = short_no_day0_delta ~ x + baseline + trend_week),
  Adjacent_Weeks = list(data = ev, form = increment ~ x + baseline + trend_week),
  Preweek_Placebo = list(data = ev, form = preweek_delta ~ x + baseline + trend_week),
  Year_FE = list(data = ev, form = short_delta ~ x + baseline + trend_week | year)
)

# Distinct baseline definitions change the estimand: keep them separately labeled.
main_daily <- day[day$reviewid %in% ev$reviewid, , drop = FALSE]
alt <- lapply(split(main_daily, main_daily$reviewid), function(g) {
  g <- g[order(g$event_day), , drop = FALSE]
  pre49 <- g[g$event_day >= -56 & g$event_day <= -8, , drop = FALSE]
  pre7 <- g[g$event_day >= -7 & g$event_day <= -1, , drop = FALSE]
  post <- g[g$event_day >= 0 & g$event_day <= 6, , drop = FALSE]
  if (nrow(pre49) != 49 || nrow(pre7) != 7 || nrow(post) != 7) return(NULL)
  data.frame(reviewid = g$reviewid[1],
             baseline_49 = mean(pre49$log_views),
             trend_week_49 = unname(stats::coef(stats::lm(log_views ~ event_day, pre49))["event_day"]) * 7,
             short_delta_49 = mean(post$log_views) - mean(pre49$log_views),
             baseline_7 = mean(pre7$log_views),
             trend_week_7 = unname(stats::coef(stats::lm(log_views ~ event_day, pre7))["event_day"]) * 7,
             short_delta_7 = mean(post$log_views) - mean(pre7$log_views))
})
alt <- dplyr::bind_rows(Filter(Negate(is.null), alt))
ev_alt <- dplyr::left_join(ev, alt, by = "reviewid", relationship = "one-to-one")
specifications$Baseline_49_Days <- list(data = ev_alt, form = short_delta_49 ~ x + baseline_49 + trend_week_49)
specifications$Baseline_Last_7_Days <- list(data = ev_alt, form = short_delta_7 ~ x + baseline_7 + trend_week_7)

releases <- get_release_subset(ev)
if (nrow(releases) >= 20) {
  specifications$Release_Controls <- list(data = releases,
    form = short_delta ~ x + baseline + trend_week + release_log_days + release_near7)
  recent <- releases[releases$release_lag >= -28 & releases$release_lag <= 365, , drop = FALSE]
  specifications$Recent_Releases <- list(data = recent,
    form = short_delta ~ x + baseline + trend_week + release_log_days + release_near7)
  away <- releases[abs(releases$release_lag) > 7, , drop = FALSE]
  specifications$Exclude_Release_Week <- list(data = away,
    form = short_delta ~ x + baseline + trend_week + release_log_days)
}

output <- lapply(names(specifications), function(label) {
  spec <- specifications[[label]]
  mod <- safe_feols(spec$form, spec$data)
  dep <- all.vars(spec$form)[1]
  tidy_feols(mod, label, dep, sample_name = label)
})
write_csv_safe(dplyr::bind_rows(output), "outputs/r/RQ1_robustness.csv")
cat("Robustness checks complete:", length(specifications), "specifications\n")

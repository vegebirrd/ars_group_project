# All RQ figures are generated here. The plot source, rather than static images,
# is committed to GitHub; figures are written to the git-ignored outputs folder.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
library(ggplot2)
library(dplyr)

ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
                                  c("reviewid", "score", "score_group", "short_delta", "baseline", "page_key")))
raw <- read_csv_checked("outputs/r/pageview_event_daily.csv",
                        c("reviewid", "event_day", "views", "log_views", "abnormal_log"))
ev$score_group <- score_group(ev$score)
raw <- raw[raw$reviewid %in% ev$reviewid, , drop = FALSE]
raw <- left_join(raw, ev[, c("reviewid", "score_group", "baseline")], by = "reviewid", relationship = "many-to-one")
raw$relative_log <- raw$log_views - raw$baseline
raw$event_week <- raw$event_day %/% 7L

p1 <- ggplot(ev, aes(score)) + geom_histogram(binwidth = 0.5, boundary = 0, color = "white") +
  labs(title = "Figure 1 | Distribution of Pitchfork review scores", x = "Pitchfork score", y = "Reviews") + research_theme()
save_plot(p1, "01_score_distribution.png")

# Two-stage aggregation first within event/week, then equally across events.
weeks <- raw |>
  filter(event_day <= 55) |>
  group_by(reviewid, score_group, event_week) |>
  summarise(relative_log = mean(relative_log), abnormal_log = mean(abnormal_log), .groups = "drop")
write_csv_safe(weeks, "outputs/r/RQ1_weekly_trajectories.csv")
weekly_means <- weeks |>
  group_by(score_group, event_week) |>
  summarise(mean_attention = mean(relative_log), mean_abnormal = mean(abnormal_log),
            n = n(), .groups = "drop")
p2 <- ggplot(weekly_means, aes(event_week, mean_attention, color = score_group)) +
  geom_line(linewidth = 0.9) + geom_point(size = 1.7) +
  geom_vline(xintercept = 0, linetype = "dashed") + geom_hline(yintercept = 0, linewidth = 0.4) +
  labs(title = "Figure 2 | Wikipedia attention around review date", subtitle = "Baseline: days −28 to −8; event-equal mean",
       x = "Weeks relative to review", y = "Mean log-attention change", color = "Score group") + research_theme()
save_plot(p2, "02_event_time_attention.png", 9, 5)

p3 <- ggplot(weekly_means[weekly_means$event_week %in% -3:4, ],
             aes(event_week, mean_abnormal, color = score_group)) +
  geom_line(linewidth = 0.9) + geom_point(size = 1.7) +
  geom_hline(yintercept = 0, linewidth = 0.4) + geom_vline(xintercept = 0, linetype = "dashed") +
  labs(title = "Figure 3 | Abnormal attention relative to pre-review forecast",
       subtitle = "Forecast trained on days −56 to −8, linear trend + weekday effects",
       x = "Weeks relative to review", y = "Observed minus forecast log views", color = "Score group") + research_theme()
save_plot(p3, "03_abnormal_attention.png", 9, 5)

m_curve <- safe_feols(short_delta ~ x + I(x^2) + baseline + trend_week, ev)
p4 <- ggplot(ev, aes(score, short_delta)) + geom_point(alpha = 0.5, size = 1.6) +
  labs(title = "Figure 4 | Rating and short-run attention", x = "Pitchfork score",
       y = "Change in mean log pageviews, days 0–6") + research_theme()
if (!is.null(m_curve)) {
  z <- seq(min(ev$score), max(ev$score), length.out = 120)
  pred <- data.frame(x = z - 7, baseline = stats::median(ev$baseline),
                     trend_week = stats::median(ev$trend_week))
  pred$score <- z
  pred$fit <- as.numeric(stats::predict(m_curve, newdata = pred))
  p4 <- p4 + geom_line(data = pred, aes(score, fit), inherit.aes = FALSE, linewidth = 1.05)
}
save_plot(p4, "04_score_quadratic.png")

trends <- ev |>
  group_by(score_group) |>
  summarise(preweek = mean(preweek_delta), postweek = mean(short_delta),
            long = mean(long_delta), .groups = "drop") |>
  tidyr::pivot_longer(cols = c(preweek, postweek, long), names_to = "period", values_to = "change")
p5 <- ggplot(trends, aes(period, change, fill = score_group)) +
  geom_col(position = "dodge") + geom_hline(yintercept = 0, linewidth = 0.4) +
  labs(title = "Figure 5 | Attention before and after review publication",
       x = "Event-time window", y = "Average log-attention change", fill = "Score group") + research_theme()
save_plot(p5, "05_attention_persistence.png")

pop <- ev |>
  mutate(tercile = factor(c("Low", "Middle", "High")[pmin(3L, ceiling(rank(baseline, ties.method = "first") * 3 / dplyr::n()))],
                          levels = c("Low", "Middle", "High"))) |>
  group_by(tercile) |>
  summarise(relative = mean(short_delta), absolute = mean(short_abs_delta), .groups = "drop")
write_csv_safe(pop, "outputs/r/RQ2_popularity_figures.csv")
p6 <- ggplot(pop, aes(tercile, relative)) + geom_col() +
  labs(title = "Figure 6 | Relative attention by pre-review popularity", x = "Prior popularity tercile",
       y = "Mean log-attention change") + research_theme()
save_plot(p6, "06_relative_attention_by_popularity.png")
p7 <- ggplot(pop, aes(tercile, absolute)) + geom_col() + geom_hline(yintercept = 0, linewidth = 0.3) +
  labs(title = "Figure 7 | Absolute attention by prior popularity", x = "Prior popularity tercile",
       y = "Mean additional daily Wikipedia visits") + research_theme()
save_plot(p7, "07_absolute_attention_by_popularity.png")

release <- ev[is.finite(ev$release_lag), , drop = FALSE]
if (nrow(release)) {
  p8 <- ggplot(release, aes(release_lag)) + geom_histogram(binwidth = 7, boundary = 0, color = "white") +
    coord_cartesian(xlim = c(-60, 120)) + geom_vline(xintercept = 0, linetype = "dashed") +
    labs(title = "Figure 8 | Release-to-review lag", subtitle = "Review date minus earliest matched release date",
         x = "Days from release to review", y = "Review events") + research_theme()
  save_plot(p8, "08_release_review_timing.png")
}

if (file.exists("outputs/r/RQ1_consumption_weekly.csv")) {
  w <- read_csv_checked("outputs/r/RQ1_consumption_weekly.csv",
                        c("event_week", "artist_visible_share", "album_visible_share"))
  w <- tidyr::pivot_longer(w, c(artist_visible_share, album_visible_share), names_to = "series", values_to = "share")
  p9 <- ggplot(w, aes(event_week, share, color = series)) + geom_line(linewidth = 0.95) + geom_point() +
    geom_vline(xintercept = 0, linetype = "dashed") +
    scale_y_continuous(limits = c(0, 1)) +
    labs(title = "Figure 9 | Spotify Global Top 200 chart visibility",
         subtitle = "Visible chart share, not total streams or album unit sales",
         x = "Chart weeks relative to review", y = "Share of chart-visible events", color = "Outcome") + research_theme()
  save_plot(p9, "09_spotify_chart_visibility.png")
}
if (file.exists("outputs/r/RQ1_consumption_summary.csv")) {
  a <- read_csv_checked("outputs/r/RQ1_consumption_summary.csv", c("score_group", "pre_album", "post_album"))
  a <- tidyr::pivot_longer(a, c(pre_album, post_album), names_to = "period", values_to = "share")
  p10 <- ggplot(a, aes(score_group, share, fill = period)) + geom_col(position = "dodge") +
    labs(title = "Figure 10 | Reviewed album chart visibility by score group",
         x = "Score group", y = "Share of calendar weeks with charted album tracks", fill = "Period") + research_theme()
  save_plot(p10, "10_spotify_album_by_score.png")
}
cat("Figures completed; inspect outputs/r/figures/\n")


# --- 12 RQ1 RQ2 FIGURES ---
# Inferential figures for the central social-science research questions.
# The earlier descriptive plots remain in R/07_figures.R; no figure is hard-coded.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
library(ggplot2)
library(dplyr)

p <- "outputs/r/RQ1_weekly_group_cluster_ci.csv"
if (file.exists(p)) {
  d <- read_csv_checked(p,c("event_week","score_group","mean","ci_low","ci_high"))
  g <- ggplot(d,aes(event_week,mean,color=score_group,fill=score_group)) +
    geom_ribbon(aes(ymin=ci_low,ymax=ci_high),alpha=.10,colour=NA) +
    geom_line(linewidth=.85) + geom_point(size=1) +
    geom_vline(xintercept=-.5,linetype="dashed") + geom_hline(yintercept=0,linewidth=.3) +
    labs(title="RQ1 | Review-period Wikipedia attention",subtitle="Event-weighted means; 95% page-cluster confidence intervals",
         x="Weeks relative to publication",y="Change in mean log(1 + daily views)",color="Score",fill="Score") + research_theme()
  save_plot(g,"16_RQ1_event_time_cluster_CI.png",9.5,5.5)
}

p <- "outputs/r/RQ1_weekly_score_coefficients.csv"
if(file.exists(p)) {
  d <- read_csv_checked(p,c("event_week","term","estimate","se"))
  d <- d[d$term=="x",,drop=FALSE]
  if(nrow(d)){
    d$lower <- d$estimate - stats::qt(.975,pmax(d$n_pages-1,1))*d$se
    d$upper <- d$estimate + stats::qt(.975,pmax(d$n_pages-1,1))*d$se
    g <- ggplot(d,aes(event_week,estimate)) +
      geom_ribbon(aes(ymin=lower,ymax=upper),alpha=.15) +
      geom_line(linewidth=.9) + geom_point(size=1.5) +
      geom_vline(xintercept=-.5,linetype="dashed") + geom_hline(yintercept=0,linewidth=.35) +
      labs(title="RQ1 | Weekly conditional score–attention association",
           subtitle="Separate page-clustered regressions by event week; not DID treatment effects",
           x="Weeks relative to review",y="Log points per 1-point Pitchfork score") + research_theme()
    save_plot(g,"17_RQ1_weekly_score_slope.png",9,5)
  }
}

p <- "outputs/r/RQ1_window_group_cluster_ci.csv"
if(file.exists(p)) {
  d <- read_csv_checked(p,c("outcome","score_group","mean","ci_low","ci_high"))
  d <- d[d$outcome %in% c("preweek_delta","short_delta","mid_delta","long_delta"),,drop=FALSE]
  d$outcome <- factor(d$outcome,levels=c("preweek_delta","short_delta","mid_delta","long_delta"),
                      labels=c("Pre 7 days","Post 0–6","Post 7–27","Post 28–55"))
  g <- ggplot(d,aes(outcome,mean,color=score_group,group=score_group)) +
    geom_hline(yintercept=0,linewidth=.3) + geom_line(linewidth=.8) +
    geom_point(position=position_dodge(width=.08),size=2) +
    geom_errorbar(aes(ymin=ci_low,ymax=ci_high),width=.1,alpha=.75) +
    labs(title="RQ1 | Attention and persistence by review-score stratum",
         subtitle="Descriptive level shifts relative to the earlier baseline",
         x="Window",y="Average log-attention change",color="Score group") + research_theme()
  save_plot(g,"18_RQ1_window_persistence_CI.png",9,5)
}

p <- "outputs/r/RQ2_popularity_marginal_score_slopes.csv"
if(file.exists(p)) {
  d <- read_csv_checked(p,c("contrast","model","estimate","ci_low","ci_high"))
  d <- d[d$model %in% c("Relative_short","Absolute_short","Relative_long"),,drop=FALSE]
  if(nrow(d)) {
    d$contrast <- factor(d$contrast,levels=c("p10","p25","p50","p75","p90"))
    g <- ggplot(d,aes(contrast,estimate)) +
      geom_hline(yintercept=0,linewidth=.3) + geom_pointrange(aes(ymin=ci_low,ymax=ci_high)) +
      facet_wrap(~model,scales="free_y") +
      labs(title="RQ2 | Score association across prior-popularity percentiles",
           subtitle="Delta-method 95% cluster intervals; absolute outcome uses asinh(daily visit change)",
           x="Percentile of pre-review Wikipedia popularity",y="Estimated score slope") + research_theme()
    save_plot(g,"19_RQ2_marginal_score_effects.png",11,5)
  }
}

p <- "outputs/r/RQ2_distribution_by_popularity_score.csv"
if(file.exists(p)) {
  d <- read_csv_checked(p,c("pop_tercile","score_group","outcome","mean","ci_low","ci_high"))
  d <- d[d$outcome %in% c("short_delta","short_abs_delta"),,drop=FALSE]
  if(nrow(d)){
    g <- ggplot(d,aes(pop_tercile,mean,color=score_group)) +
      geom_hline(yintercept=0,linewidth=.3) +
      geom_pointrange(aes(ymin=ci_low,ymax=ci_high),position=position_dodge(width=.5)) +
      facet_wrap(~outcome,scales="free_y",labeller=as_labeller(c(short_delta="Relative log attention",
                                                                 short_abs_delta="Absolute daily pageviews"))) +
      labs(title="RQ2 | Relative discovery versus absolute attention capture",
           subtitle="Each point represents equally weighted review events; page-cluster confidence intervals",
           x="Pre-review popularity tercile",y="Mean attention change",color="Review score") + research_theme()
    save_plot(g,"20_RQ2_relative_vs_absolute_CI.png",11,5)
  }
}

p <- "outputs/r/RQ2_genre_score_slopes.csv"
if(file.exists(p)) {
  d <- read_csv_checked(p,c("contrast","estimate","ci_low","ci_high"))
  if(nrow(d)) {
    g <- ggplot(d,aes(contrast,estimate)) + geom_hline(yintercept=0,linewidth=.3) +
      geom_pointrange(aes(ymin=ci_low,ymax=ci_high)) +
      labs(title="RQ2 | Conditional score slope by broad genre",
           subtitle="Genre interactions are exploratory; see the joint F-test and cell counts",
           x="Broad source genre",y="Log-attention change per score point") + research_theme()
    save_plot(g,"21_RQ2_genre_marginal_scores.png",8,5)
  }
}

p <- "outputs/r/RQ2_matching_balance_baseline_trend.csv"
if(file.exists(p)) {
  d <- tryCatch(read_csv_checked(p,c("variable","Diff.Un","Diff.Adj")),error=function(e)NULL)
  if(!is.null(d) && nrow(d)) {
    z <- tidyr::pivot_longer(d,c("Diff.Un","Diff.Adj"),names_to="stage",values_to="smd")
    g <- ggplot(z,aes(smd,variable,color=stage)) + geom_vline(xintercept=c(-.1,.1),linetype="dashed") +
      geom_point(size=2) + labs(title="Matched high/low reviews | Covariate balance",
            x="Standardized mean difference",y="Covariate",color="Stage") + research_theme()
    save_plot(g,"22_RQ2_matching_loveplot.png",8,5)
  }
}
cat("RQ1/RQ2 inferential figures written to outputs/r/figures\n")

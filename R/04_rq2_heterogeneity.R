# RQ2 | Attention and prior popularity, absolute exposure, and genre.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
                                  c("short_delta", "short_abs_delta", "score", "x", "baseline", "baseline_centered",
                                    "lowpop", "trend_week", "genre_group", "page_key")))
ev$score_group <- score_group(ev$score)

models <- list(
  ContinuousPopularity = safe_feols(short_delta ~ x * baseline_centered + trend_week, ev),
  LowVsHighPopularity = safe_feols(short_delta ~ x * lowpop + baseline + trend_week, ev),
  AbsoluteVisits = safe_feols(asinh_abs_delta ~ x * lowpop + baseline + trend_week, ev)
)
if (length(unique(stats::na.omit(ev$genre_group))) >= 2L) {
  # Pool low-frequency genres to preserve cell size.
  counts <- table(ev$genre_group)
  valid <- names(counts)[counts >= 10L]
  ev$genre_analysis <- as.character(ev$genre_group)
  ev$genre_analysis[!ev$genre_analysis %in% valid] <- "Other"
  ev$genre_analysis <- factor(ev$genre_analysis)
  if (length(unique(ev$genre_analysis)) > 1L) {
    models$GenreInteractions <- safe_feols(short_delta ~ x * genre_analysis + baseline + trend_week, ev)
  }
}
coefs <- dplyr::bind_rows(lapply(names(models), function(n) {
  m <- models[[n]]
  if (is.null(m)) return(data.frame())
  tidy_feols(m, n, all.vars(stats::formula(m))[1])
}))
write_csv_safe(coefs, "outputs/r/RQ2_heterogeneity.csv")
write_model_table(models, "outputs/r/RQ2_heterogeneity_models.txt")

# Baseline terciles based on empirical ranks, not hand-picked threshold values.
ev$pop_tercile <- factor(c("Low", "Middle", "High")[pmin(3L, pmax(1L, ceiling(rank(ev$baseline, ties.method = "first") * 3 / nrow(ev))))],
                        levels = c("Low", "Middle", "High"))
summary <- ev |>
  dplyr::group_by(pop_tercile, score_group) |>
  dplyr::summarise(n = dplyr::n(), mean_baseline_visits = mean(baseline_abs_views),
                   mean_relative_change = mean(short_delta),
                   median_absolute_daily_change = stats::median(short_abs_delta),
                   mean_absolute_daily_change = mean(short_abs_delta), .groups = "drop")
write_csv_safe(summary, "outputs/r/RQ2_popularity_descriptives.csv")
cat("RQ2 complete: heterogeneous score associations by pre-review popularity and genre\n")


# --- 11 RQ2 CORE INFERENCE ---
# RQ2 | Inferential distributional analysis, not just subgroup bar charts.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
               c("reviewid","score","x","baseline","trend_week","page_key",
                 "short_delta","long_delta","preweek_delta","short_abs_delta")))
ev$score_group <- score_group(ev$score)
ev$pop_tercile <- factor(c("Low","Middle","High")[pmin(3L,pmax(1L,ceiling(rank(ev$baseline,ties.method="first") * 3/nrow(ev))))],
  levels=c("Low","Middle","High"))
ev$pop_c <- ev$baseline-stats::median(ev$baseline)
ev$abs_asinh <- asinh(ev$short_abs_delta)

# Same score-by-baseline specification, on different substantive outcomes.
core <- list(
  Relative_short = safe_feols(short_delta ~ x*pop_c + trend_week,ev),
  Absolute_short = safe_feols(abs_asinh ~ x*pop_c + trend_week,ev),
  Relative_long = safe_feols(long_delta ~ x*pop_c + trend_week,ev),
  Pre_review_placebo = safe_feols(preweek_delta ~ x*pop_c + trend_week,ev)
)

# Date-verified robustness on fixed selected observations.
dated <- ev[is.finite(ev$release_lag),,drop=FALSE]
if (nrow(dated) >= 30L) {
  core$Relative_release_adjusted <- safe_feols(
    short_delta ~ x*pop_c + trend_week + release_log_days + release_near7,dated)
  core$Absolute_release_adjusted <- safe_feols(
    abs_asinh ~ x*pop_c + trend_week + release_log_days + release_near7,dated)
}
write_csv_safe(bind_rows_safe(lapply(names(core),function(nm) {
  if (is.null(core[[nm]])) return(data.frame())
  z <- tidy_feols(core[[nm]],nm,all.vars(stats::formula(core[[nm]]))[1])
  if (!nrow(z)) return(data.frame())
  z$n_pages <- length(unique(if (grepl("release_adjusted",nm))dated$page_key else ev$page_key));z
})), "outputs/r/RQ2_interaction_models.csv")
write_model_table(core,"outputs/r/RQ2_interaction_models.txt")

# Derive score slopes at observed popularity quantiles. Delta-method uncertainty
# comes from the full (page-clustered) variance matrix, including covariance.
q <- stats::quantile(ev$baseline,c(.1,.25,.5,.75,.9),na.rm=TRUE)
base_mid <- stats::median(ev$baseline)
slopes <- bind_rows_safe(lapply(names(core),function(nm) {
  m <- core[[nm]]
  if (is.null(m)) return(data.frame())
  z <- bind_rows_safe(lapply(seq_along(q),function(i) {
    v <- linear_contrast(m,c(x=1,"x:pop_c"=unname(q[i]-base_mid)),
                       if (grepl("release_adjusted",nm))length(unique(dated$page_key)) else length(unique(ev$page_key)),
                       paste0("p",c(10,25,50,75,90)[i]))
    if(nrow(v))v$baseline_log_views<-unname(q[i])
    v
  }))
  if(nrow(z))z$model<-nm
  z
}))
write_csv_safe(slopes,"outputs/r/RQ2_popularity_marginal_score_slopes.csv")
qcontrast <- bind_rows_safe(lapply(names(core),function(nm) {
  nG <- if (grepl("release_adjusted",nm))length(unique(dated$page_key)) else length(unique(ev$page_key))
  z <- linear_contrast(core[[nm]],c("x:pop_c"=unname(q[5]-q[1])),nG,"p90_minus_p10_score_slope")
  if(nrow(z))z$model<-nm
  z
}))
write_csv_safe(qcontrast,"outputs/r/RQ2_high_low_popularity_slope_differences.csv")

# Absolute vs proportional exposure, with cluster-robust uncertainty for
# equally weighted event averages and *median* for outlier robustness.
desc <- bind_rows_safe(lapply(levels(ev$pop_tercile),function(pop){
  bind_rows_safe(lapply(levels(ev$score_group),function(sc){
    z <- ev[ev$pop_tercile==pop & ev$score_group==sc,,drop=FALSE]
    if(!nrow(z))return(data.frame())
    bind_rows_safe(lapply(c("short_delta","short_abs_delta","long_delta"),function(out){
      a <- cluster_mean_ci(z,out)
      a$median <- stats::median(z[[out]],na.rm=TRUE)
      a$pop_tercile<-pop;a$score_group<-sc;a$outcome<-out
      a
    }))
  }))
}))
write_csv_safe(desc,"outputs/r/RQ2_distribution_by_popularity_score.csv")

# Sparse groups are not fed into interaction tests. Explicit genre means and
# joint tests use the same sample and controls as the genre interaction.
genre_audit <- as.data.frame(table(ev$genre_group,useNA="ifany"))
names(genre_audit) <- c("genre_group","n_events")
write_csv_safe(genre_audit,"outputs/r/RQ2_genre_coverage.csv")
valid_genres <- names(which(table(ev$genre_group) >= 10L))
valid_genres <- intersect(c("Other","Rock","Hip-Hop"), valid_genres)
gdat <- ev[as.character(ev$genre_group) %in% valid_genres,,drop=FALSE]
if (length(valid_genres) >= 2L && nrow(gdat) >= 35L) {
  gdat$genre_model <- factor(as.character(gdat$genre_group),levels=valid_genres)
  gm <- safe_feols(short_delta ~ x*genre_model + baseline + trend_week,gdat)
  write_csv_safe(tidy_feols(gm,"GenreInteraction","short_delta","genre_observed"),
                 "outputs/r/RQ2_genre_interaction_coefficients.csv")
  if (!is.null(gm)) {
    interaction_terms <- grep("^x:genre_model",names(stats::coef(gm)),value=TRUE)
    j <- cluster_wald(gm,interaction_terms,length(unique(gdat$page_key)),"Joint score-by-genre interactions")
    write_csv_safe(j,"outputs/r/RQ2_genre_interaction_joint_test.csv")
    gmargins <- bind_rows_safe(lapply(valid_genres,function(gr){
      ww <- c(x=1)
      term <- paste0("x:genre_model",gr)
      if(gr != valid_genres[1])ww[term] <- 1
      z <- linear_contrast(gm,ww,length(unique(gdat$page_key)),gr)
      if(nrow(z))z$n_events_genre <- sum(gdat$genre_model == gr)
      z
    }))
    write_csv_safe(gmargins,"outputs/r/RQ2_genre_score_slopes.csv")
  }
}
cat("RQ2 marginal score effects, distributional outcomes, and genre inference complete\n")


# --- 13 RQ2 PRIOR POPULARITY ---
# RQ2: pre-determined measures of artist visibility, with distinct estimands.
# Wiki prehistory: t-180 ... t-61; professional review career: older than t-57.
# Current Spotify popularity/followers are NOT valid historical covariates.
source("R/helpers.R")
check_dependencies();ensure_dirs()
d <- read_csv_checked("outputs/r/events_model_data.csv",
                      c("reviewid","score","year","short_delta","short_abs_delta","page_key","baseline","trend_week"))
d <- main_events(d)
d$x <- d$score - 7
d$abs_asinh <- asinh(d$short_abs_delta)

metrics <- c("prior_wiki_log_mean", "prior_pitchfork_reviews", "prior_pitchfork_career_years",
             "prior_chart_visible_weeks_share",
             "spotify_prior_chart_visible_share", "youtube_prior_chart_visible_share")
audit <- data.frame(metric=metrics,n_available=sapply(metrics,function(k){
  if (!k %in% names(d)) return(0L)
  sum(is.finite(suppressWarnings(as.numeric(d[[k]]))))
}),n_total=nrow(d))
write_csv_safe(audit,"outputs/r/RQ2_prior_popularity_coverage.csv")

fits <- list();quantiles <- list()
for (v in metrics) {
  if (!v %in% names(d)) next
  tmp <- d
  tmp$prior <- suppressWarnings(as.numeric(tmp[[v]]))
  tmp <- tmp[is.finite(tmp$prior),,drop=FALSE]
  if (nrow(tmp) < 30L || length(unique(tmp$page_key)) < 15L || sd(tmp$prior)==0) next
  # The scale of every metric is standardized only WITHIN the estimation sample.
  tmp$prior_z <- as.numeric(scale(if (v %in% c("prior_pitchfork_reviews","prior_pitchfork_career_years")) log1p(tmp$prior) else tmp$prior))
  tmp$year_factor <- factor(tmp$year)
  f1 <- safe_feols(short_delta ~ x*prior_z + baseline + trend_week + year_factor,tmp)
  f2 <- safe_feols(abs_asinh ~ x*prior_z + baseline + trend_week + year_factor,tmp)
  # Compare with a pre-event placebo outcome on identical coverage.
  f3 <- if ("preweek_delta" %in% names(tmp))
      safe_feols(preweek_delta ~ x*prior_z + baseline + trend_week + year_factor,tmp) else NULL
  fits[[paste0(v,"_relative")]] <- f1
  fits[[paste0(v,"_absolute")]] <- f2
  fits[[paste0(v,"_placebo")]] <- f3
  # Three groups constructed within year to avoid compositional confounding.
  tmp$prior_tercile <- NA_character_
  for (yy in unique(tmp$year)) {
    ids <- which(tmp$year==yy)
    n <- length(ids)
    tmp$prior_tercile[ids] <- c("Low","Middle","High")[
      pmax(1L,pmin(3L,ceiling(rank(tmp$prior[ids],ties.method="average")*3/n))]
  }
  qu <- tmp |>
    dplyr::group_by(year,prior_tercile) |>
    dplyr::summarise(n=dplyr::n(),mean_log_change=mean(short_delta),
       median_log_change=median(short_delta),mean_abs_change=mean(short_abs_delta),
       median_abs_change=median(short_abs_delta),.groups="drop")
  qu$metric <- v;quantiles[[v]] <- qu
}
coef <- bind_rows_safe(lapply(names(fits),function(nm) {
  mdl <- fits[[nm]]
  if (is.null(mdl)) return(data.frame())
  tidy_feols(mdl,nm,all.vars(stats::formula(mdl))[1],"strict_pre_review_popularity")
}))
write_csv_safe(coef,"outputs/r/RQ2_strict_prior_popularity_regressions.csv")
write_csv_safe(bind_rows_safe(quantiles),"outputs/r/RQ2_strict_prior_popularity_distributions.csv")
write_model_table(fits,"outputs/r/RQ2_strict_prior_popularity_models.txt")
if (nrow(coef)) {
 ggplot2::ggsave("outputs/r/figures/RQ2_prior_popularity_interactions.png",
    ggplot2::ggplot(coef[grepl("x:prior_z",coef$term,fixed=TRUE),],
       ggplot2::aes(x=model,y=estimate,ymin=ci_low_approx,ymax=ci_high_approx)) +
      ggplot2::geom_hline(yintercept=0,color="grey60") +
      ggplot2::geom_pointrange() + ggplot2::coord_flip() +
      ggplot2::labs(x=NULL,y="Score × prior popularity (95% CI)",title="RQ2: heterogeneity across pre-review popularity measures") +
      research_theme(), width=9,height=5,dpi=180)
}
cat("RQ2 strict historical visibility: coverage and estimable regressions saved.\n")

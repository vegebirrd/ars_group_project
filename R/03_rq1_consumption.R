# RQ1 extension | Spotify Global Top 200 visibility and chart-visible streams.
# Requires: python scripts/run_pipeline.py --cohort historical --stage charts
source("R/helpers.R")
check_dependencies(); ensure_dirs()
path <- "outputs/spotify_review_summary.csv"
week_path <- "outputs/spotify_chart_week_panel.csv"
if (!file.exists(path)) {
  message("Spotify summaries missing. Run: python scripts/run_pipeline.py --cohort historical --stage charts")
} else {
  s <- read_csv_checked(path, c("reviewid", "score", "artist_id", "pre_artist_visible",
                                "presence_delta", "pre_album_visible", "album_presence_delta"))
  s <- s[!is.na(s$artist_id), , drop = FALSE]
  s$x <- s$score - 7
  s$score_group <- score_group(s$score)
  s$album_streams_change <- log1p(pmax(s$post_album_visible_streams, 0)) -
    log1p(pmax(s$pre_album_visible_streams, 0))
  # OLS of chart-visibility fractions is a descriptive linear conditional contrast.
  a <- safe_feols(presence_delta ~ x + pre_artist_visible, s,
                  cluster = "artist_id", min_n = 20L)
  b <- safe_feols(album_presence_delta ~ x + pre_album_visible, s,
                  cluster = "artist_id", min_n = 20L)
  c <- safe_feols(album_streams_change ~ x + pre_album_visible, s,
                  cluster = "artist_id", min_n = 20L)
  results <- bind_rows_safe(tidy_feols(a, "ArtistTop200", "presence_delta"),
                            tidy_feols(b, "ReviewedAlbumTop200", "album_presence_delta"),
                            tidy_feols(c, "AlbumChartVisibleStreams", "album_streams_change"))
  write_csv_safe(results, "outputs/r/RQ1_consumption_regressions.csv")
  write_model_table(list(Artist = a, Album = b, Album_Streams = c), "outputs/r/RQ1_consumption_models.txt")
  desc <- s |>
    dplyr::group_by(score_group) |>
    dplyr::summarise(n = dplyr::n(), pre_artist = mean(pre_artist_visible),
                     post_artist = mean(post_artist_visible),
                     pre_album = mean(pre_album_visible), post_album = mean(post_album_visible),
                     .groups = "drop")
  write_csv_safe(desc, "outputs/r/RQ1_consumption_summary.csv")
  if (file.exists(week_path)) {
    w <- read_csv_checked(week_path,
                          c("reviewid", "event_week", "artist_top200_visible", "album_top200_visible"))
    weekly <- w |>
      dplyr::group_by(event_week) |>
      dplyr::summarise(n_reviews = dplyr::n_distinct(reviewid),
                       artist_visible_share = mean(artist_top200_visible),
                       album_visible_share = mean(album_top200_visible), .groups = "drop")
    write_csv_safe(weekly, "outputs/r/RQ1_consumption_weekly.csv")
  }
  cat("Spotify analysis complete:", nrow(s), "candidate events\n")
}


# --- 14 MODERN CONSUMPTION ---
# RQ1 modern global Top 200/Top 100 conditional chart visibility, not album sales.
source("R/helpers.R")
check_dependencies();ensure_dirs()
d <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
          c("reviewid","year","score","baseline","trend_week","page_key")))
d$x <- d$score-7
fits <- list();audits <- list()
for (platform in c("spotify","youtube")) {
  p <- paste0(platform,"_")
  pre <- paste0(p,"pre_chart_visible_share")
  post <- paste0(p,"post_chart_visible_share")
  old <- paste0(p,"prior_chart_visible_share")
  if (!all(c(pre,post) %in% names(d))) next
  sub <- d[is.finite(d[[pre]]) & is.finite(d[[post]]),,drop=FALSE]
  audits[[platform]] <- data.frame(platform=platform,n_total=nrow(d),n_calendar_complete=nrow(sub),
              n_prior_chart_observed=if(old %in% names(sub))sum(is.finite(sub[[old]])) else 0)
  if (nrow(sub)<30) next
  sub$delta_chart <- sub[[post]]-sub[[pre]]
  sub$prior_chart <- if(old %in% names(sub))sub[[old]] else NA_real_
  sub$year_factor <- factor(sub$year)
  fits[[paste0(platform,"_share")]] <- safe_feols(delta_chart ~ x + baseline + trend_week + year_factor,sub)
  prior_sub <- sub[is.finite(sub$prior_chart),,drop=FALSE]
  if (nrow(prior_sub)>30) {
    prior_sub$pop_chart_z <- as.numeric(scale(prior_sub$prior_chart))
    if (is.finite(sd(prior_sub$pop_chart_z)) && sd(prior_sub$pop_chart_z)>0)
      fits[[paste0(platform,"_pop_interaction")]] <-
        safe_feols(delta_chart ~ x*pop_chart_z + baseline + trend_week + year_factor,prior_sub)
  }
}
write_csv_safe(bind_rows_safe(audits),"outputs/r/RQ1_modern_chart_coverage.csv")
write_csv_safe(bind_rows_safe(lapply(names(fits),function(nm){
  m <- fits[[nm]];if(is.null(m))return(data.frame())
  tidy_feols(m,nm,"post_minus_pre_global_chart_visible_share","modern_charts")
})),"outputs/r/RQ1_modern_chart_coefficients.csv")
write_model_table(fits,"outputs/r/RQ1_modern_chart_models.txt")
cat("Modern chart visibility regressions complete\n")

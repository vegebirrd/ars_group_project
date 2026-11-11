# RQ2 matched comparison of high vs low *scored* reviews.
# All events have Pitchfork reviews; treatment denotes a high score, NOT
# review exposure. This is a matched difference-in-changes comparison.
source("R/helpers.R")
check_dependencies(); ensure_dirs()
ev <- main_events(read_csv_checked("outputs/r/events_model_data.csv",
              c("reviewid","score","baseline","trend_week","increment","page_key","year")))
ev <- ev[ev$score < 5 | ev$score >= 8,,drop=FALSE]
ev$high_review <- as.integer(ev$score >= 8)
if (min(table(factor(ev$high_review,levels=0:1))) < 6L) stop("Too few high/low reviewed events")

run_match <- function(dat,label,include_release=FALSE) {
  variables <- c("high_review","baseline","trend_week","increment","preweek_delta","year")
  if(include_release) variables <- c(variables,"release_log_days","release_near7")
  dat <- dat[stats::complete.cases(dat[,variables,drop=FALSE]),,drop=FALSE]
  if(nrow(dat)<12L || min(table(factor(dat$high_review,levels=0:1)))<5L)return(data.frame())
  f <- if(include_release) high_review ~ baseline + trend_week + release_log_days + release_near7
        else high_review ~ baseline + trend_week
  m <- tryCatch(MatchIt::matchit(f,data=dat,method="nearest",distance="glm",
             ratio=1,replace=FALSE,caliper=.2,std.caliper=TRUE,exact=~year),
             error=function(e){warning(conditionMessage(e));NULL})
  if(is.null(m))return(data.frame())
  out <- MatchIt::match.data(m)
  if(!nrow(out) || length(unique(out$high_review))<2)return(data.frame())
  out$matched_pair <- as.character(out$subclass)
  n_pairs <- length(unique(out$matched_pair))
  if(n_pairs<4L)return(data.frame())

  # Always publish achieved balance (not just the requested caliper).
  balance <- cobalt::bal.tab(m,un=TRUE,binary="std",continuous="std",m.threshold=.1)
  capture.output(print(balance),file=paste0("outputs/r/RQ2_matching_balance_",label,".txt"))
  b <- as.data.frame(balance$Balance)
  b$variable <- rownames(b);rownames(b)<-NULL
  write_csv_safe(b,paste0("outputs/r/RQ2_matching_balance_",label,".csv"))
  worst <- if("Diff.Adj" %in% names(b)) max(abs(b$Diff.Adj),na.rm=TRUE) else NA_real_

  keep <- intersect(c("reviewid","score","high_review","baseline","trend_week",
       "release_log_days","release_near7","preweek_delta","increment","year","page_key",
       "matched_pair","weights"),names(out))
  write_csv_safe(out[,keep,drop=FALSE],paste0("outputs/r/RQ2_matched_events_",label,".csv"))

  # Analogy to a two-period DID: post-minus-pre adjacent weeks by event,
  # then compare the differences of high and low reviews within matched sets.
  # Pair-clustered SEs reflect matched set dependence; no causal ATT claim.
  post <- safe_feols(increment ~ high_review, out,cluster="matched_pair",min_n=8L,min_groups=4L)
  placebo <- safe_feols(preweek_delta ~ high_review, out,cluster="matched_pair",min_n=8L,min_groups=4L)
  unmatched <- safe_feols(increment ~ high_review, dat,cluster="page_key",min_n=12L,min_groups=8L)
  tab <- bind_rows_safe(tidy_feols(unmatched,paste0(label,"_unmatched"),"increment",label),
                        tidy_feols(post,paste0(label,"_matched"),"increment",label),
                        tidy_feols(placebo,paste0(label,"_preweek_placebo"),"preweek_delta",label))
  if(nrow(tab)){
    tab$n_pairs <- n_pairs
    tab$max_absolute_adjusted_SMD <- worst
    tab$matching_rule <- "1:1 nearest PS; 0.2 SD caliper; exact year"
  }
  tab
}

result <- bind_rows_safe(run_match(ev,"baseline_trend",FALSE),run_match(ev,"release_adjusted",TRUE))
write_csv_safe(result,"outputs/r/RQ2_matching_contrasts.csv")
cat("Matching audit and descriptive matched comparisons complete\n")

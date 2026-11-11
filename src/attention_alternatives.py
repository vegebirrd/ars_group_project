#!/usr/bin/env python3
"""Additional *observed-data* analyses of artist attention. No remote data requests.

Run: python code/attention_alternatives.py --base .
Source: processed/{daily_panel_196,attention_events_196}.csv (from actual data.zip)
"""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats


def fit_expected_log(d: pd.DataFrame, train_end: int=-8):
    """Fit calendar-weekday fixed effects and linear pretrend on [-56, train_end].

    The forecast is an observational counterfactual-style *benchmark*, not an
    untreated counterfactual. The 49-day training window has seven full weeks.
    """
    days = d['event_day'].to_numpy(dtype=int)
    weekday = pd.to_datetime(d['date']).dt.dayofweek.to_numpy()
    x = np.column_stack([np.ones(len(d)), days, *(weekday==w for w in range(1, 7))]).astype(float)
    y = np.log1p(d['views'].to_numpy(dtype=float))
    tr=(days>=-56)&(days<=train_end)
    beta=np.linalg.lstsq(x[tr], y[tr], rcond=None)[0]
    pred=x@beta
    fit_rmse=float(np.sqrt(np.mean((y[tr]-pred[tr])**2)))
    return y,pred,fit_rmse,beta


def windows_average(y,t,a,b):
    return float(np.mean(y[(t>=a)&(t<=b)]))


def make(base):
    p=pd.read_csv(base/'processed/daily_panel_196.csv',parse_dates=['date'])
    ev=pd.read_csv(base/'processed/attention_events_196.csv')
    p=p[p['observed'].eq(1)].copy()
    assert len(p)==196*113
    out=[];rows=[]
    for rid,d in p.groupby('reviewid', sort=False):
        d=d.sort_values('event_day')
        assert d.event_day.tolist()==list(range(-56,57))
        tt=d.event_day.to_numpy(dtype=int)
        y,pred,rmse,beta=fit_expected_log(d)
        residual=y-pred
        raw=d.views.to_numpy(dtype=float)
        post_7=windows_average(residual,tt,0,6)
        pre_7=windows_average(residual,tt,-7,-1)
        post_7_excl=windows_average(residual,tt,1,7)
        # Use comparable 7-day windows, so raw sum and arithmetic mean are the same ratio.
        rawpost=np.sum(raw[(tt>=0)&(tt<=6)]);rawpre=np.sum(raw[(tt>=-7)&(tt<=-1)])
        # EPS=7 corresponds to adding 1 pageview per day, reducing low-count volatility.
        ratio=np.log((rawpost+7)/(rawpre+7))
        abs_gap=(rawpost-rawpre)/7
        # Placebo: 42-day training, hold out days -14..-8 as historical evaluation week.
        y_place,pred_place,rmse_place,beta_place=fit_expected_log(d,train_end=-15)
        placebo=windows_average(y_place-pred_place,tt,-14,-8)
        out.append(dict(reviewid=rid,abnormal_post7=post_7,
                        abnormal_pre7=pre_7,abnormal_post7_excl_day0=post_7_excl,
                        abnormal_increment=post_7-pre_7,
                        mean_post7_log_prediction=float(np.mean(pred[(tt>=0)&(tt<=6)])),
                        placebo_prev_week=placebo,
                        total_week_log_ratio=ratio,mean_daily_views_post_vs_pre=abs_gap,
                        pre_model_rmse=rmse,pre_model_weekly_slope=float(beta[1]*7)))
        for day, obs, ex in zip(tt, y,pred):
            if -14<=day<=27:
                rows.append(dict(reviewid=rid,event_day=int(day),abnormal_log=float(obs-ex)))
    z=ev.merge(pd.DataFrame(out),on='reviewid',validate='one_to_one')
    daily=pd.DataFrame(rows).merge(ev[['reviewid','era','group']],on='reviewid',validate='many_to_one')
    return z,daily


def clustered_table(d,target,cols):
    a=d[[target,'page_key']+cols].dropna().copy()
    X=sm.add_constant(a[cols].astype(float),has_constant='add')
    m=sm.OLS(a[target].astype(float),X).fit(cov_type='cluster',cov_kwds={'groups':a.page_key,'use_correction':True},use_t=True)
    G=int(a.page_key.nunique()); df=max(G-1,1)
    rows=[]
    for nm in m.params.index:
        b,se=m.params[nm],m.bse[nm]
        rows.append(dict(target=target,term=nm,coef=float(b),se=float(se),p=float(2*stats.t.sf(abs(b/se),df)),ci_low=float(b-stats.t.ppf(.975,df)*se),ci_high=float(b+stats.t.ppf(.975,df)*se),n=len(a),clusters=G))
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base',type=Path,default=Path('.'))
    args=ap.parse_args(); base=args.base
    results=base/'results'/'new_metrics'; figs=results/'figures';figs.mkdir(parents=True,exist_ok=True)
    z,daily=make(base)
    z.to_csv(results/'attention_new_metrics_196.csv',index=False)
    daily.to_csv(results/'abnormal_attention_daily_-14_27.csv',index=False)
    dd=z[z.era=='2018-19'].copy()
    metrics=['short_delta','increment','abnormal_post7','abnormal_pre7','abnormal_increment','total_week_log_ratio','mean_daily_views_post_vs_pre','placebo_prev_week']
    summary=dd.groupby('group',observed=True)[metrics].agg(['mean','median','std','count'])
    summary.to_csv(results/'main_group_summary.csv')
    rr=[]
    for era in ['2015-17','2018-19']:
        d=z[z.era==era]
        for target in ['short_delta','increment','abnormal_post7','abnormal_pre7','abnormal_increment','total_week_log_ratio','placebo_prev_week']:
            rr.append(clustered_table(d,target,['x','baseline','trend_week']))
    rr=pd.concat(rr,ignore_index=True)
    rr.insert(0,'era',np.repeat([ '2015-17','2018-19'], 7*4))
    rr.to_csv(results/'alternative_outcome_models.csv',index=False)
    # Event trajectory with pre-fitted residual benchmark.
    week=daily[daily.era=='2018-19'].copy()
    week['week']=np.floor_divide(week.event_day,7)
    means=week.groupby(['reviewid','week'],as_index=False).abnormal_log.mean()
    means=means.merge(z[['reviewid','group']],on='reviewid')
    tab=means.groupby(['group','week'],observed=True).abnormal_log.agg(['mean','count','std']).reset_index()
    tab['se']=tab['std']/np.sqrt(tab['count'])
    tab.to_csv(results/'weekly_abnormal_attention.csv',index=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(9.2,4.6))
    styles={'Low':'o','Middle':'s','High':'^'}
    for name,g in tab.groupby('group',observed=True):
        g=g.sort_values('week');ax.plot(g.week,g['mean'],marker=styles[str(name)],lw=1.7,label=f'{name} (n={int(g["count"].max())})')
    ax.axvline(0,color='gray',ls=':',lw=1);ax.axhline(0,color='#888',lw=.8)
    ax.set(xlabel='Week relative to review',ylabel='Observed minus forecast log pageviews',title='Out-of-window Wikipedia attention surprise (49-day trend + weekday forecast)')
    ax.legend(frameon=False);fig.tight_layout();fig.savefig(figs/'abnormal_attention_event_2018_19.png',dpi=200);plt.close(fig)
    # Coefficient comparison preserving clustering and controls.
    q=rr[(rr.era=='2018-19')&(rr.term=='x')].copy()
    vals=['short_delta','increment','abnormal_post7','abnormal_increment','total_week_log_ratio']
    q=q.set_index('target').loc[vals].reset_index()
    fig,ax=plt.subplots(figsize=(9.0,4.6))
    idx=np.arange(len(q));ci=stats.t.ppf(.975,140)
    ax.errorbar(q.coef,idx,xerr=np.vstack((q.coef-q.ci_low,q.ci_high-q.coef)),fmt='o',capsize=4,color='#234a70')
    ax.axvline(0,color='gray',lw=.8,ls=':')
    ax.set(yticks=idx,yticklabels=['Baseline delta [0,6]','Post minus previous week','Trend/weekday forecast residual','Forecast-residual acceleration','Raw weekly view-count log ratio'],xlabel='Score coefficient per one Pitchfork point (with 95% clustered CI)',title='Sensitivity to definitions of attention (2018-2019, n=143)');ax.invert_yaxis();fig.tight_layout();fig.savefig(figs/'alternative_attention_coefficients.png',dpi=200);plt.close(fig)
    summary2={'main_events':len(dd),'all_events':len(z),'mean_post_abnormal':float(dd.abnormal_post7.mean()),'mean_pre_abnormal':float(dd.abnormal_pre7.mean()),'mean_abnormal_increment':float(dd.abnormal_increment.mean()),'mean_placebo':float(dd.placebo_prev_week.mean()),'median_log_ratio':float(dd.total_week_log_ratio.median()),'median_abs_increment':float(dd.mean_daily_views_post_vs_pre.median())}
    for target in ['short_delta','increment','abnormal_post7','abnormal_pre7','abnormal_increment','total_week_log_ratio']:
        row=q[q.target==target]
        if row.empty: row=rr[(rr.era=='2018-19')&(rr.target==target)&(rr.term=='x')]
        summary2[target+'_score_coef']=float(row.coef.iloc[0]);summary2[target+'_score_p']=float(row.p.iloc[0])
    (results/'summary.json').write_text(json.dumps(summary2,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary2,indent=2,ensure_ascii=False))
if __name__=='__main__':main()

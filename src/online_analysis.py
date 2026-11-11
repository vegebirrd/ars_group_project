#!/usr/bin/env python3
"""Event-time attention estimation for freshly downloaded review/Wikimedia data.

Primary sampling unit is the review event; cluster robust inference is grouped
by resolved Wikipedia page. Results and plotting code are generated together.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

WINS={'baseline':(-28,-8),'preweek':(-7,-1),'short':(0,6),'short_no_day0':(1,7),'mid':(7,27),'long':(28,55)}
MODELS={'M0':[],'M1':['x'],'M2':['x','x2'],'M3L':['x','baseline','trend_week'],'M3':['x','x2','baseline','trend_week']}

def clean_group(s):
    return pd.cut(s,[-.00001,5,8,10.000001],right=False,labels=['Low','Middle','High'])

def data_transform(reviews:pd.DataFrame,panel:pd.DataFrame):
    if reviews.reviewid.duplicated().any():raise ValueError('reviewid must be unique in sample')
    if panel[['reviewid','event_day']].duplicated().any():raise ValueError('duplicate event-day records')
    review_ids=set(reviews.reviewid)
    d=panel[panel.reviewid.isin(review_ids)].copy()
    d['views']=pd.to_numeric(d.views,errors='coerce')
    d['observed']=pd.to_numeric(d.observed,errors='coerce').fillna(0).astype(int)
    counts=d.groupby('reviewid').agg(rows=('event_day','size'),observed=('observed','sum'))
    complete=counts[(counts.rows==113)&(counts.observed==113)].index
    d=d[d.reviewid.isin(complete)].copy()
    if d.empty:raise ValueError('No complete 113-day Wikipedia events. See pageview_coverage.csv')
    if d.views.isna().any() or (d.views<0).any():raise ValueError('All observed views must be nonnegative numeric')
    d['log_views']=np.log1p(d.views)
    rows=[];surprises=[]
    for rid,g in d.groupby('reviewid',sort=False):
        g=g.sort_values('event_day')
        base=g[g.event_day.between(-28,-8)]
        x=base.event_day.to_numpy(dtype=float);y=base.log_views.to_numpy(dtype=float)
        r={'reviewid':rid,'baseline':y.mean(),'baseline_abs_views':base.views.mean(),'trend_week':7*np.polyfit(x,y,1)[0]}
        for name,(lo,hi) in WINS.items():
            tmp=g[g.event_day.between(lo,hi)]
            r[name+'_log_mean']=tmp.log_views.mean()
            r[name+'_views_mean']=tmp.views.mean()
            r[name+'_delta']=tmp.log_views.mean()-r['baseline']
            r[name+'_abs_delta']=tmp.views.mean()-r['baseline_abs_views']
        r['increment']=r['short_log_mean']-r['preweek_log_mean']
        r['relative_week_log_ratio']=np.log1p(r['short_views_mean']*7)-np.log1p(r['preweek_views_mean']*7)
        # Pre-review fixed forecast, with linear trend + weekday effects.
        ref=g[g.event_day.between(-56,-8)].copy()
        ref['weekday']=pd.to_datetime(ref.date).dt.weekday
        X=pd.get_dummies(ref.weekday.astype(str),prefix='wd',drop_first=True,dtype=float)
        X.insert(0,'time',ref.event_day.to_numpy(dtype=float))
        full=g.copy();full['weekday']=pd.to_datetime(full.date).dt.weekday
        Q=pd.get_dummies(full.weekday.astype(str),prefix='wd',drop_first=True,dtype=float)
        Q.insert(0,'time',full.event_day.to_numpy(dtype=float))
        Q=Q.reindex(columns=X.columns,fill_value=0)
        f=sm.OLS(ref.log_views,sm.add_constant(X,has_constant='add')).fit()
        full['abnormal_log']=full.log_views.to_numpy(dtype=float)-f.predict(sm.add_constant(Q,has_constant='add')).to_numpy()
        for lo,hi,name in [(-7,-1,'abnormal_pre7'),(0,6,'abnormal_post7'),(28,55,'abnormal_long')]:
            r[name]=full.loc[full.event_day.between(lo,hi),'abnormal_log'].mean()
        r['abnormal_increment']=r['abnormal_post7']-r['abnormal_pre7']
        rows.append(r)
        surprises.append(full[['reviewid','event_day','date','abnormal_log']])
    ev=reviews[reviews.reviewid.isin(complete)].merge(pd.DataFrame(rows),on='reviewid',validate='one_to_one').copy()
    ev['score']=pd.to_numeric(ev.score)
    ev['x']=ev.score-7;ev['x2']=ev.x**2
    ev['group']=clean_group(ev.score)
    ev['year']=pd.to_datetime(ev.pub_date).dt.year
    ev['page_key']=ev.wiki_wikipedia_title.fillna(ev.artist).astype(str).str.casefold()
    ev['lowpop']=(ev.baseline<=ev.baseline.median()).astype(int)
    ev['x_lowpop']=ev.x*ev.lowpop
    ev['release_lag']=pd.to_numeric(ev.get('musicbrainz_release_to_review_days',np.nan),errors='coerce')
    ev['release_near7']=(ev.release_lag.abs()<=7).astype(float)
    ev.loc[ev.release_lag.isna(),'release_near7']=np.nan
    ev['release_log_days']=np.sign(ev.release_lag)*np.log1p(ev.release_lag.abs())
    ev['genre_group']=ev['genre'].fillna('Unknown').astype(str) if 'genre' in ev.columns else 'Unknown'
    return ev,d,pd.concat(surprises,ignore_index=True)

def fit_cluster(d:pd.DataFrame,y:str,cols:list[str]):
    v=d.dropna(subset=[y,'page_key']+cols).copy()
    if len(v)<max(12,len(cols)+4) or v.page_key.nunique()<6:return None,None
    X=sm.add_constant(v[cols].astype(float),has_constant='add')
    res=sm.OLS(v[y].astype(float),X).fit(cov_type='cluster',cov_kwds={'groups':v.page_key.astype(str),'use_correction':True},use_t=True)
    C=[];num_groups=v.page_key.nunique();degree=num_groups-1;tval=stats.t.ppf(.975,degree)
    for k in res.params.index:
        b=float(res.params[k]);se=float(res.bse[k]);pval=float(2*stats.t.sf(abs(b/se),degree)) if se>0 else np.nan
        C.append(dict(term=k,coef=b,se=se,p=pval,ci_low=b-tval*se,ci_high=b+tval*se,n=len(v),clusters=num_groups))
    return res,pd.DataFrame(C)

def u_shape(res,ev):
    if res is None or 'x2' not in res.params:return {}
    b=res.params;cov=res.cov_params();l,h=float(ev.x.min()),float(ev.x.max());df=max(ev.page_key.nunique()-1,1)
    def slope(x):
        v=float(b['x']+2*x*b['x2']);se=math.sqrt(max(float(cov.loc['x','x']+4*x*x*cov.loc['x2','x2']+4*x*cov.loc['x','x2']),0))
        return v,se
    lo,ls=slope(l);hi,hs=slope(h)
    return {'turning_score':float(7-b['x']/(2*b['x2'])) if b['x2'] else np.nan,'slope_low':lo,'slope_high':hi,
            'p_joint_U':max(stats.t.cdf(lo/ls,df),stats.t.sf(hi/hs,df)) if ls and hs else np.nan}

def cv_by_page(df,y,models):
    data=df.dropna(subset=[y,'page_key']+sorted(set(sum(models.values(),[])))).copy()
    z=data[y].to_numpy(dtype=float);groups=data.page_key.astype(str).to_numpy();out=[]
    for name,cols in models.items():
        X=data[cols].to_numpy(dtype=float) if cols else np.empty((len(data),0));pred=np.zeros(len(z))
        for g in np.unique(groups):
            tr=groups!=g;te=~tr
            pred[te]=np.c_[np.ones(te.sum()),X[te]]@np.linalg.lstsq(np.c_[np.ones(tr.sum()),X[tr]],z[tr],rcond=None)[0]
        out.append(dict(model=name,rmse=float(np.sqrt(np.mean((z-pred)**2))),mae=float(np.mean(np.abs(z-pred))),n=len(data),pages=len(np.unique(groups))))
    return pd.DataFrame(out)

def make_figures(ev,day,ab,results):
    figdir=results/'figures';figdir.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':175})
    def save(fig,name):fig.tight_layout();fig.savefig(figdir/name);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4));ax.hist(ev.score,bins=np.arange(0,10.51,.5));ax.set(xlabel='Pitchfork score',ylabel='Review events',title='Rating distribution in valid Wikipedia sample');save(fig,'01_score_distribution.png')
    fig,ax=plt.subplots(figsize=(7,4));ev.year.value_counts().sort_index().plot.bar(ax=ax);ax.set(xlabel='Year of review',ylabel='Review events',title='Coverage by year');save(fig,'02_review_years.png')
    fig,ax=plt.subplots(figsize=(7,4));ev.genre_group.value_counts().head(8).sort_values().plot.barh(ax=ax);ax.set(xlabel='Review events',ylabel='Genre',title='Genre composition');save(fig,'03_genres.png')
    data=day.merge(ev[['reviewid','group','baseline']],on='reviewid')
    data['relative_log']=data.log_views-data.baseline
    data['event_week']=data.event_day//7
    weekly=data[data.event_day<=55].groupby(['reviewid','event_week'],as_index=False).relative_log.mean().merge(ev[['reviewid','group']],on='reviewid')
    curves=weekly.groupby(['group','event_week'],observed=True).relative_log.agg(['mean','count','std']).reset_index()
    curves.to_csv(results/'RQ1_weekly_attention.csv',index=False)
    fig,ax=plt.subplots(figsize=(9,4.5))
    for name,g in curves.groupby('group',observed=True):ax.plot(g.event_week,g['mean'],marker='o',label=f'{name} (n={ev.group.eq(name).sum()})')
    ax.axvline(0,color='gray',ls=':');ax.axhline(0,color='gray',lw=.6);ax.set(xlabel='Weeks relative to review',ylabel='Mean log pageviews relative to baseline',title='RQ1 | Attention around review');ax.legend(frameon=False);save(fig,'04_attention_event_study.png')
    fig,ax=plt.subplots(figsize=(8,4.5));ax.scatter(ev.score,ev.short_delta,alpha=.55,s=21)
    res,_=fit_cluster(ev,'short_delta',['x','x2','baseline','trend_week'])
    if res is not None:
        r=np.linspace(ev.score.min(),ev.score.max(),200);Xp=pd.DataFrame({'const':1,'x':r-7,'x2':(r-7)**2,'baseline':ev.baseline.median(),'trend_week':ev.trend_week.median()})
        ax.plot(r,res.predict(Xp),label='Quadratic conditional fit');ax.legend(frameon=False)
    ax.set(xlabel='Pitchfork score',ylabel='Short-run log attention change',title='RQ1 | Review score and attention');save(fig,'05_score_curve.png')
    ab=ab.merge(ev[['reviewid','group']],on='reviewid');ab['week']=ab.event_day//7
    abnormal=ab[ab.event_day.between(-14,27)].groupby(['reviewid','week'],as_index=False).abnormal_log.mean().merge(ev[['reviewid','group']],on='reviewid')
    abnormal=abnormal.groupby(['group','week'],observed=True).abnormal_log.mean().reset_index()
    abnormal.to_csv(results/'RQ1_weekly_abnormal.csv',index=False)
    fig,ax=plt.subplots(figsize=(8,4))
    for name,g in abnormal.groupby('group',observed=True):ax.plot(g.week,g.abnormal_log,marker='o',label=str(name))
    ax.axhline(0,color='gray',lw=.6);ax.axvline(0,color='gray',ls=':');ax.set(title='RQ1 | Abnormal attention after pre-trend forecast',xlabel='Week relative to review',ylabel='Observed minus predicted log views');ax.legend(frameon=False);save(fig,'06_abnormal_attention.png')
    med=ev.baseline.median();ev['pop_split']=np.where(ev.baseline<=med,'Lower initial attention','Higher initial attention')
    grouped=ev.groupby('pop_split')[['short_delta','short_abs_delta']].mean()
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    grouped.short_delta.plot.bar(ax=axs[0],title='Relative: log change');grouped.short_abs_delta.plot.bar(ax=axs[1],title='Absolute: daily visits difference')
    for ax in axs:ax.set_xlabel('');ax.tick_params(axis='x',rotation=12)
    save(fig,'07_popularity_relative_absolute.png')
    release=ev.release_lag.dropna();
    if len(release):
        fig,ax=plt.subplots(figsize=(7,4));ax.hist(release.clip(-60,365),bins=25);ax.axvline(0,color='gray',ls=':');ax.set(xlabel='Review date minus first release date (days, clipped)',ylabel='Events',title='Release chronology');save(fig,'08_release_timing.png')
    return curves

def matching(df):
    # Matched high/low difference in outcomes; descriptive weighted comparison.
    d=df[df.group.isin(['Low','High'])].copy().reset_index(drop=True)
    d['high']=(d.group=='High').astype(int)
    if d.high.nunique()!=2 or min(d.high.value_counts())<3:return pd.DataFrame(),{'pairs':0}
    feats=['baseline','trend_week'];z=StandardScaler().fit_transform(d[feats]);m=LogisticRegression(max_iter=500).fit(z,d.high)
    p=np.clip(m.predict_proba(z)[:,1],.0001,.9999);logit=np.log(p/(1-p));cal=.2*np.std(logit)
    pairs=sorted((abs(logit[i]-logit[j]),i,j) for i in d.index[d.high==1] for j in d.index[d.high==0] if abs(logit[i]-logit[j])<=cal)
    matches=[];used_i=set();used_j=set()
    for dist,i,j in pairs:
        if i in used_i or j in used_j:continue
        matches.append({'high_reviewid':d.loc[i,'reviewid'],'low_reviewid':d.loc[j,'reviewid'],
                        'short_delta_difference':d.loc[i,'short_delta']-d.loc[j,'short_delta'],
                        'distance':dist});used_i.add(i);used_j.add(j)
    return pd.DataFrame(matches),{'pairs':len(matches),'mean_short_difference':float(np.mean([t['short_delta_difference'] for t in matches])) if matches else None,
                                  'caliper':float(cal)}

def run(sample,panel,out):
    out.mkdir(parents=True,exist_ok=True)
    ev,day,ab=data_transform(sample,panel)
    ev.to_csv(out/'events_model_data.csv',index=False)
    ab.to_csv(out/'abnormal_attention_daily.csv',index=False)
    make_figures(ev,day,ab,out)
    summaries=ev.groupby('group',observed=True)[['score','preweek_delta','short_delta','mid_delta','long_delta','short_abs_delta','abnormal_post7','abnormal_increment']].agg(['mean','std','count'])
    summaries.to_csv(out/'RQ1_group_summary.csv')
    reg_rows=[];fits={}
    for outcome in ['short_delta','short_no_day0_delta','mid_delta','long_delta','increment','abnormal_post7','abnormal_increment','relative_week_log_ratio']:
        for name,terms in MODELS.items():
            fit,table=fit_cluster(ev,outcome,terms)
            if table is None:continue
            table.insert(0,'model',name);table.insert(0,'outcome',outcome);reg_rows.append(table)
            if outcome=='short_delta':fits[name]=u_shape(fit,ev) if name in ('M2','M3') else {}
    pd.concat(reg_rows,ignore_index=True).to_csv(out/'RQ1_regressions.csv',index=False)
    cv=cv_by_page(ev,'short_delta',MODELS);cv.to_csv(out/'RQ1_pagewise_cv.csv',index=False)
    extra=[]
    for label,formula in [('score_x_small_artist',['x','lowpop','x_lowpop','baseline','trend_week']),
                          ('score_genre_year',['x','baseline','trend_week'])]:
        e=ev.copy();terms=formula[:]
        if label=='score_genre_year':
            genre=e.genre_group.where(e.genre_group.map(e.genre_group.value_counts())>=10,'Other')
            dummy=pd.get_dummies(pd.DataFrame({'genre':genre,'year':e.year.astype(str)}),drop_first=True,dtype=float)
            for nm in dummy.columns:e[nm]=dummy[nm]
            terms+=list(dummy.columns)
        fit,tab=fit_cluster(e,'short_delta',terms)
        if tab is not None:tab.insert(0,'spec',label);extra.append(tab)
    if extra:pd.concat(extra,ignore_index=True).to_csv(out/'RQ2_heterogeneity.csv',index=False)
    matched,info=matching(ev);matched.to_csv(out/'RQ2_matching_pairs.csv',index=False)
    subset=ev.dropna(subset=['release_lag'])
    if len(subset)>=12:
        fit,table=fit_cluster(subset,'short_delta',['x','baseline','trend_week','release_log_days','release_near7'])
        if table is not None:table.to_csv(out/'RQ1_release_controls.csv',index=False)
    audit={'n_events':int(len(ev)),'n_pages':int(ev.page_key.nunique()),'n_daily_records':int(len(day)),
           'n_day_precision_release':int(ev.release_lag.notna().sum()),'review_years':sorted(ev.year.unique().tolist()),
           'score_counts':ev.group.value_counts().to_dict(),'matching':info,'quadratic_diagnostics':fits}
    (out/'analysis_manifest.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,default=float),encoding='utf8')
    return audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',type=Path,default=Path('data/processed/attention_complete_sample.csv'))
    p.add_argument('--panel',type=Path,default=Path('data/processed/pageview_panel.csv'))
    p.add_argument('--out',type=Path,default=Path('outputs'))
    a=p.parse_args();result=run(pd.read_csv(a.reviews),pd.read_csv(a.panel),a.out)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=float))
if __name__=='__main__':main()

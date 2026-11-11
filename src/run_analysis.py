#!/usr/bin/env python3
"""Reproducible exploratory analysis of ARS music reviews.
Reads ONLY user-supplied data.zip extracted as data/...; no synthetic observations.
Run: python code/run_analysis.py --data /path/to/data --out /path/to/output
"""
from __future__ import annotations
import argparse, json, warnings, math, hashlib, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore',category=FutureWarning)

WINS={'baseline':(-28,-8),'preweek':(-7,-1),'short':(0,6),'short_no_day0':(1,7),'mid':(7,27),'long':(28,55),'earlier':(-56,-8)}
MODELS={'M0':[], 'M1':['x'],'M2':['x','x2'], 'M3L':['x','baseline','trend_week'],'M3':['x','x2','baseline','trend_week']}

def js(v):
    try:
        a=json.loads(v) if pd.notna(v) and isinstance(v,str) else []
        return a if isinstance(a,list) else []
    except Exception:return []

def genre(v):
    vals=js(v)
    if not vals:return 'Unknown'
    t=str(vals[0]).lower()
    return {'pop/r&b':'Pop/R&B','rap':'Hip-hop','electronic':'Electronic','rock':'Rock','jazz':'Jazz','metal':'Metal','experimental':'Experimental'}.get(t,t.title())

def make_event(ev_path,pan_path,era):
    ev=pd.read_csv(ev_path,low_memory=False)
    p=pd.read_csv(pan_path,low_memory=False)
    assert ev.reviewid.is_unique and p[['reviewid','event_day']].duplicated().sum()==0
    p=p.loc[p.reviewid.isin(ev.reviewid)].copy()
    p['observed']=pd.to_numeric(p.observed,errors='coerce').fillna(0)
    p['views']=pd.to_numeric(p.views,errors='coerce')
    assert (p.groupby('reviewid').size()==113).all() and (p.groupby('reviewid')['observed'].sum()==113).all()
    assert p.loc[p.observed==1,'views'].notna().all() and (p.views.dropna()>=0).all()
    p['log_views']=np.log1p(p.views)
    rows=[]
    for rid,d in p.groupby('reviewid',sort=False):
        b=d[(d.event_day>=-28)&(d.event_day<=-8)]
        x=b.event_day.to_numpy(dtype=float)
        y=b.log_views.to_numpy(dtype=float)
        q={'reviewid':rid,'era':era, 'baseline':y.mean(),
           'trend_week':7*np.polyfit(x,y,1)[0],
           'baseline_abs_views':b.views.mean()}
        for name,(a,z) in WINS.items():
            w=d[(d.event_day>=a)&(d.event_day<=z)]
            q[name+'_log_mean']=w.log_views.mean()
            q[name+'_views_mean']=w.views.mean()
            q[name+'_delta']=w.log_views.mean()-q['baseline']
            q[name+'_abs_delta']=w.views.mean()-q['baseline_abs_views']
        q['increment']=q['short_log_mean']-q['preweek_log_mean']
        q['increment_abs']=q['short_views_mean']-q['preweek_views_mean']
        q['long_minus_short']=q['long_log_mean']-q['short_log_mean']
        rows.append(q)
    met=pd.DataFrame(rows)
    ev=ev.merge(met,on='reviewid',validate='one_to_one')
    assert len(ev)==len(met)
    ev['score']=pd.to_numeric(ev.score)
    ev['x']=ev.score-7
    ev['x2']=ev.x**2
    ev['year']=pd.to_datetime(ev.pub_date).dt.year
    ev['genre_main']=ev.genres_json.map(genre)
    ev['group']=pd.cut(ev.score,[-.001,5,8,10.001],labels=['Low','Middle','High'],right=False)
    ev['pop_low']= (ev.baseline<ev.baseline.median()).astype(int)
    ev['b_c']=ev.baseline-ev.baseline.mean()
    ev['x_pop']=ev.x*ev.b_c
    ev['release_lag']=pd.to_numeric(ev.musicbrainz_release_to_review_days,errors='coerce')
    precision=ev.get('musicbrainz_first_release_date_precision',pd.Series('',index=ev.index)).astype(str).str.lower()
    valid=ev.get('release_date_matched_to_day',pd.Series(False,index=ev.index))
    valid=valid.fillna(False).astype(str).str.lower().isin(['1','true','yes']) | precision.isin(['day','day_precision','day-precision','yyyy-mm-dd'])
    # Earlier-v2 release lag values are only trusted if original field claims day precision.
    ev['release_day_known']=valid & ev.release_lag.notna()
    ev['release_trans']=np.where(ev.release_day_known,np.sign(ev.release_lag)*np.log1p(np.abs(ev.release_lag)),np.nan)
    ev['release_within_7']=np.where(ev.release_day_known,(ev.release_lag.abs()<=7).astype(int),np.nan)
    ev['release_recent']=ev.release_day_known & ev.release_lag.between(-28,365)
    ev['page_key']=ev.wiki_wikipedia_title.astype(str).str.strip().str.casefold().str.replace('_',' ',regex=False)
    # Use the textual Wikipedia page identity to unify first- and second-period clusters.
    return ev,p

def reg(d,y,cols,cluster='page_key'):
    a=d[[y,cluster]+cols].replace([np.inf,-np.inf],np.nan).dropna().copy()
    X=sm.add_constant(a[cols],has_constant='add').astype(float)
    result=sm.OLS(a[y].astype(float),X).fit(cov_type='cluster',cov_kwds={'groups':a[cluster], 'use_correction':True, 'df_correction':True},use_t=True)
    G=a[cluster].nunique()
    coeff=[]
    for j,k in enumerate(result.params.index):
        val=result.params[k];se=result.bse[k];pval=2*stats.t.sf(abs(val/se),max(G-1,1))
        tcrit=stats.t.ppf(.975,max(G-1,1))
        coeff.append(dict(term=k,coef=float(val),se=float(se),ci_low=float(val-tcrit*se),ci_high=float(val+tcrit*se),p=float(pval),n=len(a),clusters=G))
    info={'n':len(a),'clusters':G,'r2':result.rsquared,'r2_adj':result.rsquared_adj,'y':y,'columns':cols}
    return result,pd.DataFrame(coeff),info

def grouped_cv(d,y,models,group='page_key'):
    output={}; d=d.dropna(subset=[y,group]+sorted(set(sum(models.values(),[])))).copy()
    groups=d[group].astype(str).to_numpy()
    valy=d[y].to_numpy(dtype=float)
    for model,cols in models.items():
        X=d[cols].astype(float).to_numpy() if cols else np.empty((len(d),0))
        pred=np.full(len(d),np.nan)
        for g in np.unique(groups):
            tr=groups!=g;te=~tr
            xtr=np.column_stack([np.ones(tr.sum()),X[tr]])
            xte=np.column_stack([np.ones(te.sum()),X[te]])
            pred[te]=xte@np.linalg.lstsq(xtr,valy[tr],rcond=None)[0]
        output[model]={'n':len(d),'groups':len(np.unique(groups)),
            'rmse':float(np.sqrt(np.mean((valy-pred)**2))),
            'mae':float(np.mean(np.abs(valy-pred)))}
    b=output.get('M0',{}).get('rmse')
    for k in output:output[k]['improvement_over_M0_pct']=100*(1-output[k]['rmse']/b) if b else np.nan
    return pd.DataFrame.from_dict(output,orient='index').rename_axis('model').reset_index()

def u_shape(res,d):
    if 'x2' not in res.params:return {}
    lo,hi=d.x.min(),d.x.max(); b=res.params;V=res.cov_params()
    def sl(x):
        est=b['x']+2*x*b['x2']
        var=V.loc['x','x']+4*x**2*V.loc['x2','x2']+4*x*V.loc['x','x2']
        return float(est),float(np.sqrt(max(var,0)))
    lv,ls=sl(lo);hv,hs=sl(hi)
    df=max(d.page_key.nunique()-1,1)
    # H1: slope at lower observed score <0 and at upper observed score >0
    pl=float(stats.t.cdf(lv/ls,df)) if ls>0 else np.nan
    ph=float(stats.t.sf(hv/hs,df)) if hs>0 else np.nan
    turn=float(7-b['x']/(2*b['x2'])) if b['x2']!=0 else np.nan
    return {'score_min':float(d.score.min()),'score_max':float(d.score.max()),
        'slope_low':lv,'slope_high':hv,'slope_low_se':ls,'slope_high_se':hs,
        'turning_score':turn,'p_joint_U':max(pl,ph),'p_quadratic':float(res.pvalues['x2'])}

def save_reg(d,nam,y,models,out):
    rows=[];infos=[];fitted={}
    for name,cols in models.items():
        try:
            res,c,info=reg(d,y,cols)
            c.insert(0,'model',name); c.insert(0,'spec',nam)
            rows.append(c);info['spec']=nam;info['model']=name
            info.update({'ushape':u_shape(res,d) if 'x2' in cols else None});infos.append(info)
            fitted[name]=res
        except Exception as e:print('REG FAILED',nam,name,str(e))
    if rows:pd.concat(rows).to_csv(out/f'{nam}_coefficients.csv',index=False)
    (out/f'{nam}_models.json').write_text(json.dumps(infos,ensure_ascii=False,indent=2),encoding='utf-8')
    return fitted,infos

def group_describe(df,era):
    out=[]
    for key,g in df.groupby('group',observed=True):
        v={'era':era,'group':str(key),'n':len(g),'pages':g.page_key.nunique(), 'score_mean':g.score.mean(),'baseline_views':g.baseline_abs_views.mean()}
        for col in ['preweek_delta','short_delta','mid_delta','long_delta','increment','short_abs_delta','long_abs_delta','increment_abs']:
            v[col]=g[col].mean()
            v[col+'_median']=g[col].median()
        out.append(v)
    return pd.DataFrame(out)

def plot_setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130,'savefig.dpi':180})

def event_curves(ev,p,era,figdir):
    ix=ev[['reviewid','baseline','group','page_key']].copy()
    a=p.merge(ix,on='reviewid',validate='many_to_one')
    a['relative_log']=a.log_views-a.baseline
    a=a[a.event_day<=55].copy()
    a['week']=np.where(a.event_day<0,(a.event_day//7).astype(int),(a.event_day//7).astype(int))
    # e.g -56..-50 map -8; -7..-1 map -1
    g=a.groupby(['reviewid','week'],as_index=False).agg(rel=('relative_log','mean'))
    z=g.merge(ev[['reviewid','group']],on='reviewid')
    stats_tbl=z.groupby(['group','week'],observed=True).agg(mean=('rel','mean'),se=('rel',lambda x:x.std(ddof=1)/np.sqrt(len(x))),n=('rel','size')).reset_index()
    stats_tbl.to_csv(figdir.parent/f'{era}_weekly_trajectory.csv',index=False)
    fig,ax=plt.subplots(figsize=(8.5,4.2))
    for grp,tab in stats_tbl.groupby('group',observed=True):
        ax.plot(tab.week,tab['mean'],marker='o',markersize=3,label=f'{grp} (n={int(tab.n.iloc[0])})')
    ax.axvline(0,linestyle=':',color='gray',lw=1)
    ax.axhline(0,linestyle='-',color='#999999',lw=.6)
    ax.set(title=f'{era}: Wikipedia attention around Pitchfork review',xlabel='Weeks relative to review',ylabel='Mean log(1+views) relative to pre-review baseline',xticks=range(-8,8))
    ax.legend(frameon=False,ncol=3,loc='upper left')
    fig.tight_layout();fig.savefig(figdir/f'{era}_event_weekly.png');plt.close(fig)
    return stats_tbl

def score_scatter(df,era,figdir):
    fig,ax=plt.subplots(figsize=(8,4.4))
    ax.scatter(df.score,df.short_delta,alpha=.55,s=28,label='Events')
    fitted,_=save_reg(df,era+'_temporary','short_delta',{'quadratic':['x','x2','baseline','trend_week']},figdir.parent) # later remove temp
    res=fitted['quadratic'];v=np.linspace(df.score.min(),df.score.max(),200)
    x=v-7;Xp=pd.DataFrame({'const':np.ones(len(x)),'x':x,'x2':x**2,'baseline':np.repeat(df.baseline.median(),len(x)),'trend_week':np.repeat(df.trend_week.median(),len(x))})
    ax.plot(v,np.asarray(res.predict(Xp)),lw=2,label='Conditional quadratic fit')
    ax.set(xlabel='Pitchfork rating',ylabel='0–6-day log-attention change',title=f'{era}: Score versus short-run attention')
    ax.legend(frameon=False);fig.tight_layout();fig.savefig(figdir/f'{era}_score_scatter.png');plt.close(fig)
    for f in [figdir.parent/f'{era}_temporary_coefficients.csv',figdir.parent/f'{era}_temporary_models.json']:
        f.unlink(missing_ok=True)

def matched_high_low(df,out,figdir):
    # Deliberately simple and fully audited overlap diagnostic, not a causal estimate.
    a=df[df.group.isin(['High','Low'])].copy().reset_index(drop=True)
    a['high']=(a.group.astype(str)=='High').astype(int)
    features=['baseline','trend_week']
    Z=StandardScaler().fit_transform(a[features])
    logit=LogisticRegression(max_iter=500,C=1).fit(Z,a.high.to_numpy())
    p=logit.predict_proba(Z)[:,1]
    a['ps']=p
    log_odds=np.log(p/(1-p));caliper=.2*np.std(log_odds)
    # Greedy optimal-ish without replacement: sort all feasible pairs by absolute logit difference.
    hi=a.index[a.high==1].to_numpy();lo=a.index[a.high==0].to_numpy()
    pairs=sorted((abs(log_odds[i]-log_odds[j]),int(i),int(j)) for i in hi for j in lo if abs(log_odds[i]-log_odds[j])<=caliper)
    usedH=set();usedL=set();ret=[]
    for dist,i,j in pairs:
        if i in usedH or j in usedL:continue
        usedH.add(i);usedL.add(j);ret.append((i,j,dist))
    def smd(x,maskh,maskl):
        h=x[maskh];l=x[maskl]
        return float((np.mean(h)-np.mean(l))/np.sqrt(.5*(np.var(h,ddof=1)+np.var(l,ddof=1)))) if len(h)>1 and len(l)>1 else np.nan
    details={'n_low':len(lo),'n_high':len(hi),'n_pairs':len(ret),'caliper_logit':float(caliper)}
    for k in features:
        details[f'{k}_SMD_before']=smd(a[k],a.high==1,a.high==0)
    # fix SMD on pair indices
    for k in features:
        details[f'{k}_SMD_after']=smd(a[k].to_numpy(),[i for i,j,dt in ret],[j for i,j,dt in ret])
    if ret:
        d=pd.DataFrame([{'high_id':a.loc[i,'reviewid'],'low_id':a.loc[j,'reviewid'],'score_high':a.loc[i,'score'],'score_low':a.loc[j,'score'],
                         'baseline_high':a.loc[i,'baseline'],'baseline_low':a.loc[j,'baseline'],
                         'short_difference':a.loc[i,'short_delta']-a.loc[j,'short_delta'],
                         'increment_difference':a.loc[i,'increment']-a.loc[j,'increment'],
                         'preweek_difference':a.loc[i,'preweek_delta']-a.loc[j,'preweek_delta'],
                         'propensity_logit_distance':dist} for i,j,dist in ret])
        d.to_csv(out/'matching_pairs.csv',index=False)
        for k in ['short_difference','increment_difference','preweek_difference']:
            v=d[k].to_numpy();ci=stats.t.interval(.95,len(v)-1,loc=v.mean(),scale=stats.sem(v)) if len(v)>1 else (np.nan,np.nan)
            details[k+'_mean']=float(v.mean());details[k+'_ci95']=list(map(float,ci))
    (out/'matching_diagnostics.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    return details

def release_matched_diagnostic(df,out):
    # Second stricter sensitivity attempt includes release timing; reject causal interpretation if SMD >0.1.
    a=df[df.release_recent & df.group.isin(['Low','High'])].copy().reset_index(drop=True)
    y=(a.group=='High').to_numpy().astype(int)
    cols=['baseline','trend_week','release_trans']
    z=StandardScaler().fit_transform(a[cols])
    ps=LogisticRegression(max_iter=500,C=1).fit(z,y).predict_proba(z)[:,1]
    ll=np.log(ps/(1-ps));cal=.2*np.std(ll)
    can=sorted((abs(ll[i]-ll[j]),int(i),int(j)) for i in np.where(y==1)[0] for j in np.where(y==0)[0]
               if abs(ll[i]-ll[j])<=cal)
    ui=set();uj=set();pairs=[]
    for distance,i,j in can:
        if i in ui or j in uj:continue
        ui.add(i);uj.add(j);pairs.append((i,j))
    res={'n_release_recent_low':int(sum(y==0)),'n_release_recent_high':int(sum(y==1)),
         'n_pairs':len(pairs),'caliper':float(cal),'covariates':cols}
    for col in cols:
        high=a.loc[[i for i,j in pairs],col].to_numpy()
        low=a.loc[[j for i,j in pairs],col].to_numpy()
        sd=np.sqrt(.5*(np.var(high,ddof=1)+np.var(low,ddof=1))) if len(pairs)>1 else np.nan
        res['smd_'+col]=float((high.mean()-low.mean())/sd) if sd and np.isfinite(sd) else np.nan
    if pairs:
        v=np.array([a.loc[i,'increment']-a.loc[j,'increment'] for i,j in pairs]);
        res['increment_high_minus_low']=float(v.mean())
        res['increment_ci95']=list(map(float,stats.t.interval(.95,len(v)-1,loc=v.mean(),scale=stats.sem(v)))) if len(v)>1 else []
    res['adequate_balance_all_smd_lt_0_1']=all(abs(res['smd_'+c])<.1 for c in cols)
    (out/'release_matched_diagnostic.json').write_text(json.dumps(res,indent=2,ensure_ascii=False),encoding='utf-8')
    return res

def weighted_reg(d,y,cols,w,cluster='page_key'):
    a=d[[y,cluster,w]+cols].replace([np.inf,-np.inf],np.nan).dropna().copy()
    X=sm.add_constant(a[cols],has_constant='add').astype(float)
    weights=pd.to_numeric(a[w]).astype(float)
    res=sm.WLS(a[y].astype(float),X,weights=weights).fit(cov_type='cluster',cov_kwds={'groups':a[cluster], 'use_correction':True, 'df_correction':True},use_t=True)
    tdf=a[cluster].nunique()-1;tcrit=stats.t.ppf(.975,tdf)
    rows=[]
    for term in res.params.index:
        b,se=res.params[term],res.bse[term]
        rows.append({'term':term,'coef':b,'se':se,'ci_low':b-tcrit*se,'ci_high':b+tcrit*se,'p':2*stats.t.sf(abs(b/se),tdf),
                     'n':len(a),'clusters':a[cluster].nunique()})
    return res,pd.DataFrame(rows)

def extra_analyses(base,ev1,ev2,out,figdir):
    # Probes of score-category sampling and descriptive population transport.
    eold=pd.read_csv(base/'processed/pitchfork/eligible_reviews.csv',low_memory=False)
    enew=pd.read_csv(base/'extension_20261022/processed/pitchfork/eligible_reviews.csv',low_memory=False)
    v2pilot=pd.read_csv(base/'extension_20261022/processed/pitchfork/pilot_reviews.csv',low_memory=False)
    v2status=pd.read_csv(base/'extension_20261022/processed/wikipedia/fetch_status.csv')
    stages=[]
    for name,t in [('2015–17 candidate',eold),('2018–19 candidate',enew),('2018–19 sampled',v2pilot),('2018–19 complete',ev2)]:
        s=pd.to_numeric(t.score,errors='coerce').dropna()
        for label,mask in [('Low',s<5),('Middle',(s>=5)&(s<8)),('High',s>=8)]:
            stages.append({'stage':name,'group':label,'n':int(mask.sum()),'percent':float(100*mask.mean())})
    pd.DataFrame(stages).to_csv(out/'sampling_stages.csv',index=False)
    fig,axs=plt.subplots(1,2,figsize=(10,3.8),sharey=True)
    for i,(name,frame,ev) in enumerate([('2015–17',eold,ev1),('2018–19',enew,ev2)]):
        axs[i].hist(pd.to_numeric(frame.score),bins=np.arange(0,10.6,.5),alpha=.6,density=True,label='Candidate pool')
        axs[i].hist(ev.score,bins=np.arange(0,10.6,.5),histtype='step',linewidth=2,density=True,label='Complete panel')
        axs[i].set(title=f'{name}: score distributions',xlabel='Pitchfork score',ylabel='Density')
        axs[i].legend(frameon=False,fontsize=8)
    fig.tight_layout();fig.savefig(figdir/'score_selection.png');plt.close(fig)
    # Weight known score-stratum sampling probabilities only: no fix for API nonresponse.
    stratp={'Low':66/66,'Middle':66/1619,'High':66/429}
    dd=ev2.copy();dd['inv_select_prob']=dd.group.astype(str).map({k:1/v for k,v in stratp.items()}).astype(float)
    weighted=[]
    for y in ['short_delta','increment']:
        fit,co=weighted_reg(dd,y,['x','baseline','trend_week'],'inv_select_prob')
        co['outcome']=y;weighted.append(co)
    pd.concat(weighted).to_csv(out/'2018-19_sampling_weight_sensitivity.csv',index=False)
    # Pre-review lead association: groups may be on different trajectories already.
    lead=reg(ev2,'preweek_delta',['x','baseline','trend_week'])[1]
    lead.to_csv(out/'2018-19_preweek_score_reg.csv',index=False)
    # Coarse genre interaction; sparse detailed classes combined instead of 7+ interactions.
    dd=ev2.copy()
    dd['grp3']=dd.genre_main.where(dd.genre_main.isin(['Rock','Hip-hop']),'Other')
    dummies=pd.get_dummies(dd.grp3,prefix='genre',drop_first=False,dtype=float)
    for k in ['genre_Hip-hop','genre_Rock']:
        dd[k]=dummies[k]
        dd[k+'_score']=dd[k]*dd.x
    cols=['x','baseline','trend_week','genre_Hip-hop','genre_Rock','genre_Hip-hop_score','genre_Rock_score']
    res,co,info=reg(dd,'short_delta',cols)
    co.to_csv(out/'2018-19_genre_interactions.csv',index=False)
    # Omnibus Wald for the two conditional interaction terms.
    vv=res.params[['genre_Hip-hop_score','genre_Rock_score']].to_numpy()
    cov=res.cov_params().loc[['genre_Hip-hop_score','genre_Rock_score'],['genre_Hip-hop_score','genre_Rock_score']].to_numpy()
    chis=float(vv@np.linalg.pinv(cov)@vv)
    details={'chi2_2df':chis,'p_chi2_reference':float(stats.chi2.sf(chis,2)),
             'groups':dd.grp3.value_counts().to_dict(),'caution':'Exploratory omnibus test; no adjustment for multiple probes'}
    (out/'genre_interactions_wald.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    # Attention vs Spotify is linked for only a handful of events, not a mediation design.
    s=pd.read_csv(base/'extension_20261022/processed/spotify/consumption_prechart_cohort.csv',low_memory=False)
    inter=ev2.merge(s[['reviewid','spotify_artist_id','identity_status','post_presence_delta','pre_presence_mean']],on='reviewid',how='inner')
    inter[['reviewid','artist','score','short_delta','increment','post_presence_delta','identity_status']].to_csv(out/'linked_attention_spotify_20.csv',index=False)
    cor=stats.pearsonr(inter.short_delta,inter.post_presence_delta)
    (out/'linked_correlation.json').write_text(json.dumps({'n':len(inter),'pearson_r':cor.statistic,'pearson_p':cor.pvalue,'warnings':'n=20, selected overlap; no evidence of mediation or causal conversion'},indent=2),encoding='utf-8')
    # Quantify absolute vs relative/ baseline heterogeneity across popularity terciles.
    dd=ev2.copy();dd['pop_tercile']=pd.qcut(dd.baseline,3,labels=['Less known','Middle','More known'])
    r=dd.groupby('pop_tercile',observed=True).agg(n=('reviewid','size'),baseline_daily_views=('baseline_abs_views','median'),
         relative_short_delta=('short_delta','mean'),absolute_short_delta=('short_abs_delta','mean'),absolute_short_delta_median=('short_abs_delta','median'),increment=('increment','mean')).reset_index()
    r.to_csv(out/'popularity_tercile.csv',index=False)
    fig,ax=plt.subplots(figsize=(7.4,4))
    ax.bar(r.pop_tercile.astype(str),r.absolute_short_delta_median)
    ax.axhline(0,color='gray',linewidth=.7)
    ax.set(title='Absolute view changes by prior-popularity tercile',ylabel='Median daily pageviews change (post 0–6 vs baseline)',xlabel='Pre-review Wikipedia popularity')
    fig.tight_layout();fig.savefig(figdir/'popularity_absolute.png');plt.close(fig)
    return details

def figure_coefs(table,era,figdir):
    tbl=table[(table.spec==era+'_short')&(table.model.isin(['M1','M3L','M3']))&(table.term=='x')].copy()
    if tbl.empty:return
    fig,ax=plt.subplots(figsize=(6.5,3.6));yy=np.arange(len(tbl))
    ax.errorbar(tbl.coef,yy,xerr=[tbl.coef-tbl.ci_low,tbl.ci_high-tbl.coef],fmt='o',capsize=4)
    ax.axvline(0,color='gray',linestyle=':');ax.set_yticks(yy,tbl.model)
    ax.set(xlabel='Coefficient on review score (s-7), with 95% CI',title=f'{era}: Linear-score associations across models')
    fig.tight_layout();fig.savefig(figdir/f'{era}_coefficients.png');plt.close(fig)

def spotify_analysis(path,weeklypath,out,figdir):
    sp=pd.read_csv(path,low_memory=False)
    w=pd.read_csv(weeklypath,low_memory=False)
    assert len(sp)==132 and sp.reviewid.is_unique
    sp['score']=pd.to_numeric(sp.score)
    sp['x']=sp.score-7;sp['x2']=sp.x**2
    sp['page_key']=sp.spotify_artist_id.astype(str)
    sp['b_c']=sp.pre_presence_mean-sp.pre_presence_mean.mean()
    sp['x_pop']=sp.x*sp.b_c
    sp['pop_low']=(sp.pre_presence_mean<sp.pre_presence_mean.median()).astype(int)
    sp['week_alignment']='boundary_friday'
    summary={
        'n_reviews':len(sp),'artists':sp.spotify_artist_id.nunique(),
        'pre_presence_mean':sp.pre_presence_mean.mean(),
        'post_presence_mean':sp.post_presence_mean.mean(),
        'post_presence_change_mean':sp.post_presence_delta.mean(),
        'post_presence_change_median':sp.post_presence_delta.median(),
        'pre_presence_at_ceiling':int((sp.pre_presence_mean==1).sum()),
        'pretrend_lead_mean':sp.lead_presence_delta.mean(),
        'post_short_change_mean':sp.short_presence_delta.mean(),
        'post_long_change_mean':sp.long_presence_delta.mean(),
        'id_corroborated':int(pd.to_numeric(sp.mb_spotify_corroborated).sum()),
        'id_only_name':int(len(sp)-pd.to_numeric(sp.mb_spotify_corroborated).sum()),
    }
    for key,dd in [('overall',sp),('mb_corroborated',sp[pd.to_numeric(sp.mb_spotify_corroborated)==1]),('pre_not_full_ceiling',sp[sp.pre_presence_mean<1]),('pre_atleast4',sp[pd.to_numeric(sp.pre_charted_weeks)>=4])]:
        if len(dd)<5:continue
        summary[key]={'n':len(dd),'artists':dd.spotify_artist_id.nunique(), 'post_change':dd.post_presence_delta.mean(),'short_change':dd.short_presence_delta.mean(), 'long_change':dd.long_presence_delta.mean(),'lead_change':dd.lead_presence_delta.mean()}
    models={'S0':[], 'S1':['x'], 'S2':['x','pre_presence_mean','pre_presence_slope_week'], 'S3':['x','x2','pre_presence_mean','pre_presence_slope_week']}
    fits,infos=save_reg(sp,'spotify_presence','post_presence_delta',models,out)
    cv=grouped_cv(sp,'post_presence_delta',{'M0':[],**models})
    cv.to_csv(out/'spotify_cv.csv',index=False)
    # Separate timing outcomes and authority of corroborated identities
    more=[]
    for nam,dd in [('all',sp),('corroborated',sp[sp.mb_spotify_corroborated==1]),('not_at_ceiling',sp[sp.pre_presence_mean<1])]:
        for y in ['short_presence_delta','long_presence_delta','post_presence_delta','lead_presence_delta']:
            if len(dd)<10:continue
            z,c,_=reg(dd,y,['x','pre_presence_mean','pre_presence_slope_week'],cluster='page_key')
            c['sample']=nam;c['outcome']=y;more.append(c)
    if more:pd.concat(more).to_csv(out/'spotify_sensitivity.csv',index=False)
    (out/'spotify_descriptive.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=float),encoding='utf-8')
    sp.to_csv(out.parent/'processed/spotify_cohort_analysis.csv',index=False)
    # Date-alignment sensitivity on exact same cohort
    align=pd.read_csv(path.parent/'event_metrics_all_alignments.csv',low_memory=False)
    same=align[align.reviewid.isin(sp.reviewid)].copy()
    sens=same.groupby('alignment',as_index=False).agg(n=('reviewid','nunique'),delta=('post_presence_delta','mean'),lead=('lead_presence_delta','mean'),short=('short_presence_delta','mean'),long=('long_presence_delta','mean'))
    sens.to_csv(out/'spotify_alignment_sensitivity.csv',index=False)
    # observed weekly chart trajectory; NO zero-imputation for streams
    w=w[(w.reviewid.isin(sp.reviewid))&(w.alignment=='boundary_friday')].copy()
    a=w.groupby('event_week',as_index=False).agg(presence=('artist_chart_presence','mean'),tracks=('charted_track_count','mean'),n=('reviewid','nunique'))
    a.to_csv(out/'spotify_weekly_trajectory.csv',index=False)
    fig,ax=plt.subplots(figsize=(8.5,4))
    a=a[a.event_week!=0]
    ax.plot(a.event_week,a.presence,marker='o',label='Artist in Top 200 (fraction)')
    ax.axvline(0,color='gray',linestyle=':');ax.set(xlabel='Chart weeks relative to review',ylabel='Share of pre-charted artists in global Top 200',title='Spotify Top 200: pre-charted artist cohort (n=132)',ylim=(0,1.05));ax.legend(frameon=False)
    fig.tight_layout();fig.savefig(figdir/'spotify_chart_presence.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.4))
    statsr=sp.groupby('score_stratum')['post_presence_delta'].agg(['mean','count','std']).reset_index()
    ax.bar(statsr.score_stratum,statsr['mean'],yerr=1.96*statsr['std']/np.sqrt(statsr['count']),capsize=5)
    ax.axhline(0,color='gray',lw=.8);ax.set(ylabel='Post-minus-pre Top 200 presence fraction',title='Spotify descriptive change by score category')
    plt.xticks(rotation=12,ha='right');fig.tight_layout();fig.savefig(figdir/'spotify_score_groups.png');plt.close(fig)
    return sp,summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();base=a.data;out=a.out;out.mkdir(parents=True,exist_ok=True)
    figs=out/'figures';figs.mkdir(exist_ok=True)
    processed=out.parent/'processed';processed.mkdir(exist_ok=True)
    plot_setup()
    ev1,p1=make_event(base/'processed/research/attention_complete_sample.csv',base/'processed/wikipedia/event_panel.csv','2015-17')
    ev2,p2=make_event(base/'extension_20261022/processed/research/attention_complete_sample.csv',base/'extension_20261022/processed/wikipedia/event_panel.csv','2018-19')
    ev=pd.concat([ev1,ev2],ignore_index=True)
    ev.to_csv(processed/'attention_events_196.csv',index=False)
    assert len(ev)==196 and ev.reviewid.is_unique
    pd.concat([p1.assign(era='2015-17'),p2.assign(era='2018-19')],ignore_index=True).to_csv(processed/'daily_panel_196.csv',index=False)
    # Descriptive statistics independent of any previously published output
    group=pd.concat([group_describe(d,era) for era,d in [('2015-17',ev1),('2018-19',ev2)]],ignore_index=True)
    group.to_csv(out/'group_descriptive.csv',index=False)
    for era,d,p in [('2015-17',ev1,p1),('2018-19',ev2,p2)]:
        event_curves(d,p,era,figs)
        score_scatter(d,era,figs)
    regs=[]
    allinfos={}
    for era,d in [('2015-17',ev1),('2018-19',ev2)]:
        for suffix,y in [('short','short_delta'),('increment','increment'),('long','long_delta')]:
            spec=f'{era}_{suffix}'
            fits,info=save_reg(d,spec,y,MODELS,out)
            allinfos[spec]=info
            c=pd.read_csv(out/f'{spec}_coefficients.csv');regs.append(c)
            if suffix=='short':
                cv=grouped_cv(d,y,MODELS)
                cv.to_csv(out/f'{era}_cv.csv',index=False)
        # release-vetted subsample: compare M3L/M3 with release controls
        sub=d[d.release_day_known].copy()
        rmods={'R0':['x','baseline','trend_week'], 'R1':['x','x2','baseline','trend_week'],
               'R2':['x','baseline','trend_week','release_trans','release_within_7'],
               'R3':['x','x2','baseline','trend_week','release_trans','release_within_7']}
        fit,info=save_reg(sub,f'{era}_release','short_delta',rmods,out)
        allinfos[f'{era}_release']=info
        regs.append(pd.read_csv(out/f'{era}_release_coefficients.csv'))
        if era=='2018-19':
            sub=d[d.release_recent].copy()
            fit,info=save_reg(sub,'2018-19_recent','short_delta',rmods,out)
            allinfos['2018-19_recent']=info
            regs.append(pd.read_csv(out/'2018-19_recent_coefficients.csv'))
            cv=grouped_cv(sub,'short_delta',{'M0':[],**rmods})
            cv.to_csv(out/'2018-19_recent_cv.csv',index=False)
        # simple score-baseline interactions
        if era=='2018-19':
            models={'H0':['x','baseline','trend_week'],'H1':['x','b_c','x_pop','trend_week'],
                    'H2':['x','x2','b_c','x_pop','trend_week']}
            fits,info=save_reg(d,'2018-19_heterogeneity','short_delta',models,out)
            allinfos['2018-19_heterogeneity']=info
            regs.append(pd.read_csv(out/'2018-19_heterogeneity_coefficients.csv'))
            # genre and year FE controls (descriptive; group rare categories)
            d2=d.copy();d2['genre_coarse']=d2.genre_main.where(d2.genre_main.map(d2.genre_main.value_counts())>=12,'Other')
            dum=pd.get_dummies(d2[['genre_coarse','year']].astype(str),drop_first=True,dtype=float)
            for k in dum:d2[k]=dum[k].astype(float)
            m={'G0':['x','baseline','trend_week'],'G1':['x','baseline','trend_week']+list(dum.columns)}
            fits,info=save_reg(d2,'2018-19_genre_year','short_delta',m,out)
            allinfos['2018-19_genre_year']=info
            regs.append(pd.read_csv(out/'2018-19_genre_year_coefficients.csv'))
            matched_high_low(d,out,figs)
            release_matched_diagnostic(d,out)
            # Identify overlapping reviews of the same normalized source artist within +/-56 days.
            all_review=pd.read_csv(base/'extension_20261022/processed/pitchfork/eligible_reviews.csv',low_memory=False)
            normalize=lambda q:unicodedata.normalize('NFKC',str(q)).strip().casefold()
            all_review['artist_norm']=all_review.artist.map(normalize)
            all_review['review_day']=pd.to_datetime(all_review.pub_date)
            d=d.copy()
            d['artist_norm']=d.artist.map(normalize)
            d['review_day']=pd.to_datetime(d.pub_date)
            counts=[]
            for _,r in d.iterrows():
                rr=all_review[(all_review.artist_norm==r.artist_norm)&(all_review.reviewid!=r.reviewid)]
                counts.append(int(((rr.review_day-r.review_day).dt.days.abs()<=56).sum()))
            d['other_same_artist_reviews_56d']=counts
            d[['reviewid','artist','title','other_same_artist_reviews_56d']].to_csv(out/'other_nearby_review_flags.csv',index=False)
            # leave extremes / outcome windows / alternative baseline
            rob=[]
            for name,dd,yy in [
              ('main',d,'short_delta'),('exclude_day0',d,'short_no_day0_delta'),('early_baseline',d,'short_delta'),
              ('increment_post_vs_preweek',d,'increment'),('drop_top_abs',d.drop(d.short_delta.abs().idxmax()),'short_delta'),
              ('recent_release',d[d.release_recent],'short_delta'),
              ('exclude_other_reviews_56d',d[d.other_same_artist_reviews_56d==0],'short_delta')]:
                dd=dd.copy();cols=['x','baseline','trend_week']
                if name=='early_baseline':
                    # Adjust dependent variable and appropriate trend separately; same old slope for comparability only.
                    dd['early_y']=dd['short_log_mean']-dd['earlier_log_mean'];dd['early_b']=dd['earlier_log_mean'];
                    cols=['x','early_b','trend_week'];yy='early_y'
                if len(dd)<10:continue
                res,c,_=reg(dd,yy,cols)
                row=c[c.term=='x'].iloc[0].to_dict();row['spec']=name;rob.append(row)
            pd.DataFrame(rob).to_csv(out/'2018-19_robustness.csv',index=False)
    # Pooled model with period fixed intercept; new page-cluster groups unify same page across periods
    combined=ev.copy();combined['v2']=(combined.era=='2018-19').astype(int)
    fits,info=save_reg(combined,'pooled_era_fixed','short_delta',{'P1':['x','v2','baseline','trend_week'],'P2':['x','x2','v2','baseline','trend_week'],'P3':['x','v2','baseline','trend_week','x_pop']},out)
    allinfos['pooled_era_fixed']=info
    regs.append(pd.read_csv(out/'pooled_era_fixed_coefficients.csv'))
    co=pd.concat(regs,ignore_index=True);co.to_csv(out/'all_regression_coefficients.csv',index=False)
    figure_coefs(co,'2018-19',figs)
    extra_analyses(base,ev1,ev2,out,figs)
    sp,summ=spotify_analysis(base/'extension_20261022/processed/spotify/consumption_prechart_cohort.csv',base/'extension_20261022/processed/spotify/review_weekly_panel.csv',out,figs)
    # determine intersection of attention and spotify sample, for transparency
    inter=set(ev2.reviewid)&set(sp.reviewid)
    # source/selection audit
    fs=pd.read_csv(base/'extension_20261022/processed/wikipedia/fetch_status.csv')
    an={'source':'data.zip, user-uploaded local dataset; no download performed in this run',
        'events_2015_17':len(ev1),'events_2018_19':len(ev2),'events_total':len(ev),
        'daily_rows_included':int(len(p1)+len(p2)),
        'unique_artist_names_v2':int(ev2.artist.nunique()),
        'wiki_pages_v1':int(ev1.page_key.nunique()),'wiki_pages_v2':int(ev2.page_key.nunique()),
        'wiki_pages_pooled':int(ev.page_key.nunique()),
        'score_groups_v1':ev1.group.value_counts().to_dict(),
        'score_groups_v2':ev2.group.value_counts().to_dict(),
        'release_day_v1':int(ev1.release_day_known.sum()), 'release_day_v2':int(ev2.release_day_known.sum()),
        'release_recent_v2':int(ev2.release_recent.sum()),
        'spotify_n':len(sp),'spotify_artists':sp.spotify_artist_id.nunique(),
        'overlap_attention_spotify_v2':len(inter),
        'overlap_ids':sorted(inter),
        'wiki_v2_statuses':fs.status.value_counts(dropna=False).to_dict(),
        'v2_preweek_mean':float(ev2.preweek_delta.mean()),'v2_short_mean':float(ev2.short_delta.mean()),'v2_increment_mean':float(ev2.increment.mean()),
        'v2_long_mean':float(ev2.long_delta.mean()),
        'v2_post_abs_delta_mean':float(ev2.short_abs_delta.mean()),'v2_post_abs_delta_median':float(ev2.short_abs_delta.median())}
    (out/'sample_audit.json').write_text(json.dumps(an,ensure_ascii=False,indent=2,default=int),encoding='utf-8')
    # data provenance input hashes for selected tables
    source=[base/'processed/research/attention_complete_sample.csv',base/'processed/wikipedia/event_panel.csv',base/'extension_20261022/processed/research/attention_complete_sample.csv',base/'extension_20261022/processed/wikipedia/event_panel.csv',base/'extension_20261022/processed/spotify/consumption_prechart_cohort.csv']
    sha={str(f.relative_to(base)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source}
    (out/'input_sha256.json').write_text(json.dumps(sha,indent=2),encoding='utf-8')
    print('COMPLETE',json.dumps({k:an[k] for k in ['events_total','daily_rows_included','v2_preweek_mean','v2_short_mean','v2_increment_mean','overlap_attention_spotify_v2','spotify_n']},ensure_ascii=False))

if __name__=='__main__':main()

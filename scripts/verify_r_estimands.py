#!/usr/bin/env python3
"""Independent Python cross-check of the R event-variable assembly.

Run after importing the user's original archive and running `Rscript run_r.R --stage prepare`:
    python scripts/verify_r_estimands.py

Zero changes to the dataset; raises an error if window definitions disagree.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
WINDOWS = {'preweek':(-7,-1),'short':(0,6),'short_no_day0':(1,7),
           'mid':(7,27),'long':(28,55)}

def calculate(daily):
    daily=daily.copy()
    daily['logv']=np.log1p(pd.to_numeric(daily['views'],errors='raise'))
    if daily[['reviewid','event_day']].duplicated().any():raise ValueError('Duplicate review/event day')
    rows=[]
    for rid,g in daily.groupby('reviewid',sort=False):
        z=g.set_index('event_day').sort_index()
        if len(z)!=113 or set(z.index)!=set(range(-56,57)) or z.logv.isna().any():
            raise ValueError(f'Incomplete day window for {rid}')
        base=z.loc[-28:-8]
        b=float(base.logv.mean())
        v={'reviewid':str(rid),'baseline':b,
           'baseline_abs_views':float(base.views.mean())}
        # Straight line is slope per day; the R variable reports per week.
        v['trend_week']=float(np.polyfit(base.index.to_numpy(dtype=float),base.logv.to_numpy(),1)[0]*7)
        for label,(a,bound) in WINDOWS.items():
            sub=z.loc[a:bound]
            v[label+'_delta']=float(sub.logv.mean()-b)
            v[label+'_abs_delta']=float(sub.views.mean()-v['baseline_abs_views'])
        v['increment']=v['short_delta']-v['preweek_delta']
        rows.append(v)
    return pd.DataFrame(rows).set_index('reviewid')


def verify(daily,r_events,tolerance=1e-8):
    exp=calculate(daily)
    have=r_events.copy(); have['reviewid']=have['reviewid'].astype(str)
    if have.reviewid.duplicated().any():raise ValueError('Duplicate R event IDs')
    have=have.set_index('reviewid')
    if set(have.index)!=set(exp.index):raise ValueError('Different R/Python event IDs')
    for col in exp:
        np.testing.assert_allclose(have.loc[exp.index,col].to_numpy(dtype=float),exp[col].to_numpy(dtype=float),
                                   rtol=0,atol=tolerance,err_msg=f'R/Python mismatch for {col}')
    return {'events_verified':len(exp),'verified_variables':list(exp.columns),
            'short_mean':float(exp.short_delta.mean()), 'preweek_mean':float(exp.preweek_delta.mean())}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--daily',type=Path,default=ROOT/'data/processed/pageview_panel.csv')
    p.add_argument('--r-events',type=Path,default=ROOT/'outputs/r/events_model_data.csv')
    a=p.parse_args()
    out=verify(pd.read_csv(a.daily,dtype={'reviewid':'string'}),
               pd.read_csv(a.r_events,dtype={'reviewid':'string'}))
    print('PASS: independent Python/R estimand consistency:',out)

if __name__=='__main__':main()

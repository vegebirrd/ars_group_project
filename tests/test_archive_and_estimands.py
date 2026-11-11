import io
import sys
import zipfile
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_project_archive import load_archive, MEMBERS
from verify_r_estimands import calculate, verify


def make_fixture(tmp_path):
    ids=['abc','def']
    reviews=pd.DataFrame({'reviewid':ids,'score':[3.2,8.5],
                          'pub_date':['2018-03-08','2018-04-12'],'artist':['A','B'],
                          'wiki_wikipedia_title':['A','B']})
    panel=pd.concat([pd.DataFrame({'reviewid':i,'event_day':range(-56,57),
                     'date':pd.date_range(pd.Timestamp(dt)-pd.Timedelta(days=56),periods=113),
                     'views':np.arange(113)+10,'observed':1})
                     for i,dt in zip(ids,reviews.pub_date)],ignore_index=True)
    extra=panel.iloc[:8].copy(); extra['reviewid']='not_selected'
    panel=pd.concat([panel,extra],ignore_index=True)
    filename=tmp_path/'fixture.zip'
    with zipfile.ZipFile(filename,'w') as z:
        z.writestr(MEMBERS['2018-2019'][0],reviews.to_csv(index=False))
        z.writestr(MEMBERS['2018-2019'][1],panel.to_csv(index=False))
    return filename


def test_archive_filters_non_analysis_pilot_rows(tmp_path):
    reviews,panel,audit=load_archive(make_fixture(tmp_path),'2018-2019')
    assert len(reviews)==2
    assert len(panel)==226
    assert audit['extra_api_events_excluded']==1
    assert audit['all_windows_complete']


def test_window_math_python_crosscheck(tmp_path):
    _,panel,_=load_archive(make_fixture(tmp_path),'2018-2019')
    out=calculate(panel)
    assert np.isclose(out['increment'].iloc[0],out['short_delta'].iloc[0]-out['preweek_delta'].iloc[0])
    reference=out.reset_index().copy()
    assert verify(panel,reference)['events_verified']==2
    reference.loc[0,'short_delta']+=0.05
    with pytest.raises(AssertionError):verify(panel,reference)

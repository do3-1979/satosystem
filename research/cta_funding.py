"""
CTA改良検証: 実funding適用 + carry tilt（trend×carry融合）
BTC+ETH（実funding取得済）でフルサイクル2021-2026を検証。

carry tilt: トレンド方向がfundingに対して不利（ロングで高正funding=支払い）なら減配、
有利（ショートで正funding=受取 / ロングで負funding=受取）なら維持/微増。
funding ドラッグを構造的に削減できるか。
"""
import sqlite3, numpy as np, datetime as dt, pickle

BPY = 6*365
DB='/home/satoshi/work/satosystem/ohlcv_data/ohlcv_cache.db'

def load_close(sym):
    con=sqlite3.connect(DB);cur=con.cursor()
    cur.execute("SELECT close_time,close_price FROM candles WHERE symbol=? AND time_frame=240 ORDER BY close_time",(sym,))
    r=cur.fetchall();con.close()
    return np.array([x[0] for x in r]), np.array([x[1] for x in r],float)

def ewma(x,span):
    a=2/(span+1);o=np.empty_like(x);o[0]=x[0]
    for i in range(1,len(x)):o[i]=a*x[i]+(1-a)*o[i-1]
    return o

def trend(close,horizons):
    s=np.zeros(len(close))
    for f,sl in horizons: s+=np.sign(ewma(close,f)-ewma(close,sl))
    return s/len(horizons)

def rvol(r,w):
    # vectorized rolling std via cumulative sums
    T=len(r); v=np.full(T,np.nan)
    cs=np.concatenate([[0],np.cumsum(r)]); cs2=np.concatenate([[0],np.cumsum(r*r)])
    i=np.arange(w,T)
    mean=(cs[i]-cs[i-w])/w
    var=(cs2[i]-cs2[i-w])/w-mean*mean
    v[i]=np.sqrt(np.maximum(var,0))*np.sqrt(BPY)
    return v

def funding_per_bar(times, fund_recs):
    """8h funding を 4h bar 各時点の『そのbarで発生する funding cost率』へマップ。
       funding は8h毎(=4hバー2本に1回)。各funding時刻に最も近いbarに rate を割当。"""
    fb=np.zeros(len(times))
    if not fund_recs: return fb
    ft=np.array([x[0] for x in fund_recs]); fr=np.array([x[1] for x in fund_recs])
    j=0
    for i,t in enumerate(times):
        # funding events within (t-4h, t]
        while j<len(ft) and ft[j]<=t:
            if ft[j]>t-4*3600: fb[i]+=fr[j]
            j+=1
    return fb

def backtest(symbols, start, end, horizons_days=((20,80),(60,240),(120,480)),
             vol_window_days=30, target_vol=0.15, max_gross=3.0, rebalance_days=2,
             cost_rate=0.0011, carry_tilt=0.0, use_real_funding=True, init=100.0):
    fund=pickle.load(open('/home/satoshi/work/satosystem/research/funding_data.pkl','rb'))
    series=[load_close(s) for s in symbols]
    common=None
    for t,c in series: common=t if common is None else np.intersect1d(common,t)
    cols=[]
    for t,c in series:
        idx={tt:i for i,tt in enumerate(t)}            # build once per symbol
        cols.append(np.array([c[idx[x]] for x in common]))
    closes=np.column_stack(cols)
    T,N=closes.shape; logc=np.log(closes)
    rets=np.vstack([np.zeros((1,N)),np.diff(logc,axis=0)])
    bpd=6; horizons=[(int(f*bpd),int(s*bpd)) for f,s in horizons_days]
    sig=np.column_stack([trend(logc[:,j],horizons) for j in range(N)])
    vol=np.column_stack([rvol(rets[:,j],vol_window_days*bpd) for j in range(N)])
    fund_bar=np.column_stack([funding_per_bar(common, fund.get(s,[])) for s in symbols])

    reb=max(1,rebalance_days*bpd); warmup=max(max(h) for h in horizons)+vol_window_days*bpd+2
    w=np.zeros((T,N)); cw=np.zeros(N)
    for t in range(T):
        if t>=warmup and t%reb==0:
            v=np.where(np.isfinite(vol[t])&(vol[t]>1e-6),vol[t],np.nan)
            s=sig[t].copy()
            if carry_tilt>0:
                # carry favorability: long好む=負funding, short好む=正funding
                # トレンド方向 s と funding の符号関係で減配/増配
                recent_fund=fund_bar[max(0,t-6):t].sum(axis=0)  # 直近~1日funding
                # position direction
                disfavor = (np.sign(s) * np.sign(recent_fund)) > 0  # ロングで正funding(支払) or ショートで負funding(支払)
                damp=np.where(disfavor, 1.0-carry_tilt, 1.0)
                s=s*damp
            raw=np.nan_to_num(s/v,nan=0.0)
            pv=np.sum((raw*v)**2); scale=(target_vol/np.sqrt(pv)) if pv>1e-12 else 0
            tw=raw*scale; g=np.sum(np.abs(tw))
            if g>max_gross: tw*=max_gross/g
            cw=tw
        w[t]=cw
    wp=np.vstack([np.zeros((1,N)),w[:-1]])
    gr=np.sum(wp*rets,axis=1)
    turn=np.sum(np.abs(w-wp),axis=1); cost=turn*cost_rate
    # 実funding cost: longはfunding正で支払 → cost = w * funding_rate (符号: +w*+f = 支払)
    fcost=np.sum(wp*fund_bar,axis=1) if use_real_funding else np.zeros(T)
    net=gr-cost-fcost
    def epoch(d):return int(dt.datetime.strptime(d,"%Y-%m-%d").timestamp())
    mask=np.ones(T,bool)
    if start:mask&=(common>=epoch(start))
    if end:mask&=(common<=epoch(end))
    idx=np.where(mask)[0]; idx=idx[idx>=warmup]
    if len(idx)==0: return None
    nr=net[idx]; eq=init*np.cumprod(1+nr)
    ann=(eq[-1]/init)**(BPY/len(nr))-1
    sh=(nr.mean()/nr.std()*np.sqrt(BPY)) if nr.std()>0 else 0
    peak=np.maximum.accumulate(eq); dd=((peak-eq)/peak).max()*100
    # gross funding drag for reporting
    fdrag=fcost[idx].sum()*init  # approx in $ on init (rough)
    return dict(pnl=eq[-1]-init, ann=ann, sharpe=sh, maxdd=dd, n=len(nr),
                avg_fund_ann=np.mean(fund_bar[idx])*3*365*100)

if __name__=="__main__":
    syms=['BTC/USDT:USDT','ETH/USDT:USDT']
    print("=== BTC+ETH full-cycle 2021-2026, slower horizons, target_vol=15%, reb=2d ===")
    for label,rf,ct in [("no funding (ref)",False,0.0),
                        ("REAL funding, no tilt",True,0.0),
                        ("REAL funding + carry tilt 0.5",True,0.5),
                        ("REAL funding + carry tilt 1.0",True,1.0)]:
        r=backtest(syms,'2021-06-01','2026-06-28',use_real_funding=rf,carry_tilt=ct)
        print(f"  {label:32s}: PnL=${r['pnl']:.0f} ann={r['ann']*100:.1f}% Sharpe={r['sharpe']:.2f} DD={r['maxdd']:.1f}%")
    print(f"  (avg funding ~{backtest(syms,'2021-06-01','2026-06-28')['avg_fund_ann']:.1f}%/yr)")
    print("=== sub-periods (REAL funding + carry tilt 0.5) ===")
    for lab,s,e in [("2022 bear","2022-01-01","2022-12-31"),("2023","2023-01-01","2023-12-31"),
                    ("2024","2024-01-01","2024-12-31"),("2025","2025-01-01","2025-12-31"),
                    ("2026H1","2026-01-01","2026-06-28")]:
        r=backtest(syms,s,e,use_real_funding=True,carry_tilt=0.5)
        print(f"  {lab:10s}: PnL=${r['pnl']:.0f} ann={r['ann']*100:.1f}% Sharpe={r['sharpe']:.2f} DD={r['maxdd']:.1f}%")

"""Phase 4: HTMLレポート生成。

エクイティ/DD・年次PnL・資産別寄与・walk-forward・感応度ヒートマップ・
コストストレス・取引ログサンプルを単一の自己完結HTMLに出力する。
チャートはmatplotlib→inline SVG。配色は一貫したパレット（下記PALETTE）。
"""
import datetime as dt
import html
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

# 一貫デザイン: 検証済みライトモードパレット
P = {
    "surface": "#fcfcfb", "page": "#f9f9f7",
    "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7",
    "blue": "#2a78d6", "aqua": "#1baf7a", "yellow": "#eda100",
    "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
    "magenta": "#e87ba4", "orange": "#eb6834",
    "div_mid": "#f0efec", "critical": "#d03b3b",
}
SERIES = [P["blue"], P["aqua"], P["yellow"], P["green"], P["violet"],
          P["red"], P["magenta"], P["orange"]]

DIVERGING = LinearSegmentedColormap.from_list(
    "bwr_brand", [P["critical"], P["div_mid"], P["blue"]])


def _style(ax):
    ax.set_facecolor(P["surface"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(P["axis"])
    ax.tick_params(colors=P["muted"], labelsize=9)
    ax.grid(True, color=P["grid"], linewidth=0.6)
    ax.set_axisbelow(True)


def _svg(fig):
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight",
                facecolor=P["surface"])
    plt.close(fig)
    return buf.getvalue()[buf.getvalue().find("<svg"):]


def _dates(times):
    return [dt.datetime.utcfromtimestamp(t) for t in times]


def equity_chart(res):
    d = _dates(res.times)
    eq = res.equity
    peak = np.maximum.accumulate(eq)
    dd = (1 - eq / peak) * 100
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.6, 4.6), sharex=True,
        gridspec_kw={"height_ratios": [2.4, 1]})
    fig.patch.set_facecolor(P["surface"])
    ax1.plot(d, eq, color=P["blue"], linewidth=2)
    ax1.set_ylabel("Equity (USD)", color=P["ink2"], fontsize=9)
    if res.halted_at:
        h = dt.datetime.utcfromtimestamp(res.halted_at)
        ax1.axvline(h, color=P["critical"], linewidth=1, linestyle="--")
        ax1.annotate("circuit breaker", xy=(h, eq.max()),
                     color=P["critical"], fontsize=8, ha="left")
    ax2.fill_between(d, 0, -dd, color=P["red"], alpha=0.55, linewidth=0)
    ax2.set_ylabel("Drawdown (%)", color=P["ink2"], fontsize=9)
    for ax in (ax1, ax2):
        _style(ax)
    return _svg(fig)


def yearly_bar(yearly):
    ys = [y for y, m in yearly.items() if m.get("valid")]
    pnl = [yearly[y]["total_pnl"] for y in ys]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    fig.patch.set_facecolor(P["surface"])
    colors = [P["blue"] if v >= 0 else P["red"] for v in pnl]
    bars = ax.bar([str(y) for y in ys], pnl, color=colors, width=0.55)
    for b, v in zip(bars, pnl):
        ax.annotate(f"{v:+.0f}", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom" if v >= 0 else "top",
                    fontsize=9, color=P["ink2"])
    ax.axhline(0, color=P["axis"], linewidth=1)
    ax.set_ylabel("PnL (USD)", color=P["ink2"], fontsize=9)
    _style(ax)
    return _svg(fig)


def asset_bar(m):
    items = sorted(m["asset_pnl"].items(), key=lambda x: x[1])
    names = [k.split("/")[0] for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    fig.patch.set_facecolor(P["surface"])
    colors = [P["blue"] if v >= 0 else P["red"] for v in vals]
    bars = ax.barh(names, vals, color=colors, height=0.55)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:+.0f}", (v, b.get_y() + b.get_height() / 2),
                    ha="left" if v >= 0 else "right", va="center",
                    fontsize=9, color=P["ink2"])
    ax.axvline(0, color=P["axis"], linewidth=1)
    ax.set_xlabel("PnL (USD)", color=P["ink2"], fontsize=9)
    _style(ax)
    return _svg(fig)


def sensitivity_heatmap(sens, grid_key, col_key, col_label):
    axes = sens["axes"]
    tvs = axes["target_vols"]
    cols = axes[col_key]
    grid = sens[grid_key]
    tag = "hs" if col_key == "horizon_scales" else "vw"
    S = np.array([[grid[f"tv={tv:g}|{tag}={c:g}"]["sharpe"]
                   for c in cols] for tv in tvs])
    H = np.array([[grid[f"tv={tv:g}|{tag}={c:g}"]["halted"]
                   for c in cols] for tv in tvs])
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    fig.patch.set_facecolor(P["surface"])
    vmax = max(abs(S).max(), 0.1)
    im = ax.imshow(S, cmap=DIVERGING, aspect="auto",
                   norm=TwoSlopeNorm(vcenter=0, vmin=-vmax, vmax=vmax))
    for i in range(len(tvs)):
        for j in range(len(cols)):
            label = f"{S[i, j]:.2f}" + ("\nHALT" if H[i, j] else "")
            ax.text(j, i, label, ha="center", va="center", fontsize=8,
                    color=P["ink"])
    ax.set_xticks(range(len(cols)), [f"{c:g}" for c in cols])
    ax.set_yticks(range(len(tvs)), [f"{tv:.0%}" for tv in tvs])
    ax.set_xlabel(col_label, color=P["ink2"], fontsize=9)
    ax.set_ylabel("target vol", color=P["ink2"], fontsize=9)
    ax.grid(False)
    ax.tick_params(colors=P["muted"], labelsize=9)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("Sharpe", color=P["ink2"], fontsize=9)
    cb.ax.tick_params(colors=P["muted"], labelsize=8)
    return _svg(fig)


def _table(rows, headers):
    th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return (f"<table><thead><tr>{th}</tr></thead>"
            f"<tbody>{''.join(trs)}</tbody></table>")


def write_report(path, cfg, res, m, yearly, commit, validation=None):
    pct = lambda v: f"{v*100:.1f}%"
    summary_rows = [
        ("期間", f"{m['start']} 〜 {m['end']} ({m['years']:.2f}年)"),
        ("最終資産", f"${m['final_equity']:.2f} (初期 ${cfg.init_capital_usd:.0f})"),
        ("年率リターン / vol", f"{m['ann_return']*100:+.1f}% / {pct(m['ann_vol'])}"),
        ("Sharpe / Sortino", f"{m['sharpe']:.2f} / {m['sortino']:.2f}"),
        ("最大DD / 継続", f"{pct(m['maxdd'])} / {m['maxdd_days']:.0f}日"),
        ("取引数 / turnover", f"{m['n_trades']} / {m['turnover_x']:.1f}x/yr"),
        ("コスト負担率", f"{m['cost_drag_pct']:.1f}%/yr "
         f"(fee ${m['fees_usd']:.0f} + funding ${m['funding_usd']:.0f} "
         f"+ slip ${m['slippage_usd']:.0f})"),
        ("signal→fill乖離合計", f"${m['signal_deviation_usd']:.2f}"),
        ("利益集中度", f"上位四半期 {pct(m['top_quarter_share'])} / "
         f"上位資産 {pct(m['top_asset_share'])}"),
        ("グロスレバレッジ", f"平均 {m['avg_gross']:.2f}x / 最大 {m['max_gross']:.2f}x"),
        ("サーキットブレーカー", "発動 (halted)" if m["halted"] else "未発動"),
    ]

    fills = res.fills[:15]
    fill_rows = [(dt.datetime.utcfromtimestamp(f.ts).strftime("%Y-%m-%d %H:%M"),
                  f.symbol.split("/")[0], f"{f.qty:+.6f}",
                  f"{f.signal_price:.2f}", f"{f.ref_price:.2f}",
                  f"{f.fill_price:.2f}", f"{f.fee_usd:.4f}",
                  f"{f.slippage_usd:+.4f}") for f in fills]

    yearly_rows = [(y, f"{ym['ann_return']*100:+.1f}%", f"{ym['sharpe']:.2f}",
                    pct(ym["maxdd"]), f"{ym['total_pnl']:+.2f}",
                    "HALT" if ym.get("halted") else "")
                   for y, ym in yearly.items() if ym.get("valid")]

    val_html = ""
    if validation:
        wf = validation.get("walk_forward", {})
        gates = validation.get("wf_gates", {})
        wf_rows = [(y, f"{w['total_pnl']:+.2f}", f"{w['sharpe']:.2f}",
                    pct(w["maxdd"]), "HALT" if w["halted"] else "")
                   for y, w in wf.items()]
        cs = validation.get("cost_stress", {})
        cs_rows = [(k, f"{c['ann_return']*100:+.1f}%", f"{c['sharpe']:.2f}",
                    pct(c["maxdd"]), "HALT" if c["halted"] else "")
                   for k, c in cs.items()]
        sens = validation.get("sensitivity")
        heat = ""
        if sens:
            heat = ("<div class='row'><figure><figcaption>感応度: target vol × "
                    "トレンドホライズン倍率（Sharpe）</figcaption>"
                    + sensitivity_heatmap(sens, "vol_x_horizon",
                                          "horizon_scales", "horizon scale")
                    + "</figure><figure><figcaption>感応度: target vol × "
                    "vol推定窓（日）</figcaption>"
                    + sensitivity_heatmap(sens, "vol_x_volwindow",
                                          "vol_windows", "vol window (days)")
                    + "</figure></div>")
        power = validation.get("statistical_power", {})
        val_html = f"""
<h2>Phase 3 検証ゲート（walk-forward 暦年独立窓）</h2>
{_table(wf_rows, ["窓", "PnL (USD)", "Sharpe", "MaxDD", ""])}
<p class="note">ゲート判定: 全窓プラス = <b>{gates.get('all_windows_positive')}</b> /
最大貢献窓({gates.get('best_window')})除外後 = <b>{gates.get('sum_ex_best', 0):+.2f} USD</b>
(プラス: {gates.get('positive_ex_best')})</p>
<h2>コストストレス（1x/3x/5x）</h2>
{_table(cs_rows, ["コスト", "年率", "Sharpe", "MaxDD", ""])}
<h2>パラメータ感応度</h2>
{heat}
<p class="note">統計的検出力: 取引数 {power.get('n_trades')} (最低目安
{power.get('min_trades')}) / Sharpe標準誤差 {power.get('sharpe_se', 0):.2f} /
t値 {power.get('sharpe_t', 0):.2f}</p>"""

    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CTA backtest report</title>
<style>
  body {{ background:{P['page']}; color:{P['ink']}; margin:0;
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ max-width: 1020px; margin: 0 auto; padding: 24px 20px 64px; }}
  h1 {{ font-size: 22px; }} h2 {{ font-size: 16px; margin-top: 36px;
       color:{P['ink']}; border-bottom: 1px solid {P['grid']};
       padding-bottom: 6px; }}
  .meta {{ color:{P['muted']}; font-size: 12px; }}
  figure {{ background:{P['surface']}; border:1px solid {P['grid']};
            border-radius:8px; padding:12px; margin:12px 0; overflow-x:auto; }}
  figcaption {{ color:{P['ink2']}; font-size:12px; margin-bottom:6px; }}
  .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .row figure {{ flex:1 1 420px; }}
  table {{ border-collapse: collapse; font-size: 12.5px; width:100%;
           background:{P['surface']}; font-variant-numeric: tabular-nums; }}
  th, td {{ border-bottom:1px solid {P['grid']}; padding:6px 10px;
            text-align:left; }}
  th {{ color:{P['ink2']}; font-weight:600; }}
  .note {{ color:{P['ink2']}; font-size:12.5px; }}
  svg {{ max-width:100%; height:auto; }}
</style></head><body><main>
<h1>分散CTAボット バックテストレポート</h1>
<p class="meta">生成 {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
 / commit {commit} / config {cfg.config_sha1} ({html.escape(cfg.config_path)})<br>
ユニバース: {html.escape(', '.join(s.split('/')[0] for s in cfg.symbols))} /
target vol {cfg.target_vol:.0%} / max gross {cfg.max_gross:g}x /
リバランス {cfg.rebalance_days}日 / 資本 ${cfg.init_capital_usd:.0f}</p>

<h2>サマリ</h2>
{_table(summary_rows, ["指標", "値"])}

<h2>エクイティカーブ / ドローダウン</h2>
<figure>{equity_chart(res)}</figure>

<h2>年次PnL / 資産別寄与</h2>
<div class="row">
<figure><figcaption>暦年別PnL（連続運用の内訳）</figcaption>{yearly_bar(yearly)}</figure>
<figure><figcaption>資産別PnL（コスト込み）</figcaption>{asset_bar(m)}</figure>
</div>
{_table(yearly_rows, ["年", "年率", "Sharpe", "MaxDD", "PnL (USD)", ""])}
{val_html}

<h2>取引ログサンプル（先頭15件）</h2>
<figure>{_table(fill_rows, ["時刻(UTC)", "銘柄", "数量", "signal価格",
                            "ref(次足始値)", "fill価格", "手数料", "slippage"])}
</figure>
<p class="note">fill価格 = 次足始値 ± slippage。signal価格（判定バー終値）との乖離は
全取引で記録され、ライブ移行後は実約定との乖離監視に同じ列を使う。</p>
</main></body></html>"""
    with open(path, "w") as f:
        f.write(doc)

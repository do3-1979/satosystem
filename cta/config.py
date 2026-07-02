"""設定読み込み。バックテストとライブは必ず同じConfigを共有する。"""
import configparser
import hashlib
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    db_path: str
    timeframe_min: int
    funding_pkl: str
    symbols: list
    horizons_days: list          # [(fast, slow), ...] 日数
    vol_window_days: int
    target_vol: float
    max_gross: float
    rebalance_days: int
    no_trade_band_pct: float
    dd_soft: float
    dd_hard: float
    fee_rate: float
    slip_rate: float
    min_notional_usd: float
    funding_default_annual: dict = field(default_factory=dict)  # symbol -> 年率
    init_capital_usd: float = 1000.0
    config_path: str = ""
    config_sha1: str = ""

    @property
    def bars_per_day(self):
        return 24 * 60 // self.timeframe_min

    @property
    def bars_per_year(self):
        return self.bars_per_day * 365


def load_config(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    with open(path) as f:
        raw = f.read()
    cp.read_string(raw)

    symbols = [s.strip() for s in cp.get("universe", "symbols").split(",") if s.strip()]
    horizons = []
    for pair in cp.get("strategy", "horizons_days").split(","):
        f_, s_ = pair.strip().split(":")
        horizons.append((int(f_), int(s_)))

    gold_annual = cp.getfloat("costs", "funding_default_annual_gold")
    crypto_annual = cp.getfloat("costs", "funding_default_annual_crypto")
    funding_default = {
        s: (gold_annual if s.startswith(("XAUT", "PAXG")) else crypto_annual)
        for s in symbols
    }

    base = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    funding_pkl = cp.get("data", "funding_pkl")
    if not os.path.isabs(funding_pkl):
        funding_pkl = os.path.join(base, funding_pkl)

    return Config(
        db_path=os.path.expanduser(cp.get("data", "db_path")),
        timeframe_min=cp.getint("data", "timeframe_min"),
        funding_pkl=funding_pkl,
        symbols=symbols,
        horizons_days=horizons,
        vol_window_days=cp.getint("strategy", "vol_window_days"),
        target_vol=cp.getfloat("strategy", "target_vol"),
        max_gross=cp.getfloat("strategy", "max_gross"),
        rebalance_days=cp.getint("strategy", "rebalance_days"),
        no_trade_band_pct=cp.getfloat("strategy", "no_trade_band_pct"),
        dd_soft=cp.getfloat("risk", "dd_soft"),
        dd_hard=cp.getfloat("risk", "dd_hard"),
        fee_rate=cp.getfloat("costs", "fee_rate"),
        slip_rate=cp.getfloat("costs", "slip_rate"),
        min_notional_usd=cp.getfloat("costs", "min_notional_usd"),
        funding_default_annual=funding_default,
        init_capital_usd=cp.getfloat("capital", "init_capital_usd"),
        config_path=os.path.abspath(path),
        config_sha1=hashlib.sha1(raw.encode()).hexdigest()[:12],
    )

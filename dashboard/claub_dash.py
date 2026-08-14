"""ClaubPulse Command — local dashboard for the ClaubPulse EA.

Reads YOUR MetaTrader 5 terminal read-only via the official MetaTrader5
Python package: account, per-strategy positions/deals (split by magic
number), and bar data for signal streaks. Serves:

  GET /            -> dashboard.html
  GET /api/state   -> state JSON

Configure via claub_config.json next to this file (see
claub_config.example.json). With "demo_mode": true — or when the
MetaTrader5 package / terminal is unavailable — the dashboard serves a
synthetic sample state so you can see the UI without any setup.

Run:  pythonw claub_dash.py   (http://127.0.0.1:8787)
Requires: Python 3.10+, `pip install MetaTrader5` (Windows only) for live use.
"""
from __future__ import annotations

import json
import math
import random

DEMO_SEED = 16
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "dashboard.html"
EQUITY_LOG = ROOT / "claub_equity.jsonl"

DEFAULT_CONFIG = {
    "demo_mode": True,
    "terminal_exe": "C:\\MT5\\terminal64.exe",
    "port": 8787,
    "poll_seconds": 30,
    "deals_since": "2026-01-01",
    "starting_equity": 25000.0,
    "strategies": [
        {"key": "zenith", "name": "Streak Pulse · S&P 500",
         "symbol": "#USSPX500", "tf_name": "H1", "magic": 79001,
         "buy_x": 4, "sell_x": 12, "pip_size": 1.0,
         "inputs": "percRisk 3.4 · SL 23000 / TP 35000 · trail 33000/7500"},
        {"key": "cable", "name": "Streak Pulse · GBPUSD",
         "symbol": "GBPUSD", "tf_name": "M5", "magic": 79002,
         "buy_x": 6, "sell_x": 6, "pip_size": 0.0001,
         "inputs": "0.05 lots · SL 320 / TP 390 · trail 230/190"},
    ],
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    f = ROOT / "claub_config.json"
    if f.exists():
        try:
            cfg.update(json.loads(f.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return cfg


CFG = load_config()
STRATS = CFG["strategies"]
DEALS_SINCE = datetime.fromisoformat(CFG["deals_since"])
START_EQ = float(CFG["starting_equity"])

state: dict = {"ok": False, "error": "starting up"}
_state_lock = threading.Lock()
_api_ready = False


def terminal_running() -> bool:
    """True if the configured terminal specifically is running (path match)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process terminal64 -ErrorAction SilentlyContinue).Path"],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000)
        return CFG["terminal_exe"].lower() in r.stdout.lower()
    except Exception:
        return False


def streaks(rates) -> tuple[int, int, list[int]]:
    """(bull, bear, last16 dirs) over completed bars; dojis skipped."""
    dirs = []
    for r in rates:
        o, c = r["open"], r["close"]
        dirs.append(1 if c > o else (-1 if c < o else 0))
    bull = bear = 0
    for d in reversed(dirs):
        if d == 0:
            continue
        if d == 1 and bear == 0:
            bull += 1
        elif d == -1 and bull == 0:
            bear += 1
        else:
            break
    return bull, bear, dirs[-16:]


def tf_const(name: str):
    return {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}[name]


def read_account() -> dict:
    global _api_ready
    out: dict = {"available": False}
    if mt5 is None:
        out["error"] = "MetaTrader5 package not installed"
        return out
    if not terminal_running():
        if _api_ready:
            mt5.shutdown()
            _api_ready = False
        out["error"] = "terminal not running"
        return out
    if not _api_ready:
        if not mt5.initialize(path=CFG["terminal_exe"], portable=True):
            out["error"] = f"initialize failed: {mt5.last_error()}"
            return out
        _api_ready = True
    ai = mt5.account_info()
    if ai is None:
        mt5.shutdown()
        _api_ready = False
        out["error"] = "account_info unavailable (IPC lost)"
        return out
    ti = mt5.terminal_info()
    all_pos = mt5.positions_get() or []
    all_deals = mt5.history_deals_get(
        DEALS_SINCE, datetime.now() + timedelta(days=1)) or []

    strat_out = []
    for s in STRATS:
        rates = mt5.copy_rates_from_pos(s["symbol"], tf_const(s["tf_name"]),
                                        1, 200)
        if rates is not None and len(rates):
            bull, bear, dirs = streaks(rates)
            price = float(rates[-1]["close"])
        else:
            bull = bear = 0
            dirs, price = [], None
        pos = [{
            "ticket": p.ticket, "side": "BUY" if p.type == 0 else "SELL",
            "volume": p.volume, "price_open": p.price_open,
            "price_current": p.price_current, "sl": p.sl, "tp": p.tp,
            "profit": round(p.profit + p.swap, 2), "time": p.time,
        } for p in all_pos if p.magic == s["magic"]]
        realized = 0.0
        n_deals = 0
        for d in all_deals:
            if d.magic != s["magic"] or d.type not in (0, 1):
                continue
            n_deals += 1
            if d.entry in (1, 3):
                realized += d.profit + d.swap + d.commission
        strat_out.append({
            **{k: s[k] for k in ("key", "name", "symbol", "tf_name",
                                 "magic", "buy_x", "sell_x", "inputs")},
            "bull": bull, "bear": bear, "dirs": dirs, "price": price,
            "to_buy": max(0, s["buy_x"] - bear),
            "to_sell": max(0, s["sell_x"] - bull),
            "positions": pos,
            "floating": round(sum(p["profit"] for p in pos), 2),
            "realized_total": round(realized, 2),
            "deal_count": n_deals,
        })

    trades = []
    by_pos: dict = {}
    for d in all_deals:
        if d.type in (0, 1):
            by_pos.setdefault(d.position_id, []).append(d)
    for pid, ds in by_pos.items():
        ins = [d for d in ds if d.entry == 0]
        outs = [d for d in ds if d.entry in (1, 3)]
        if not ins:
            continue
        i0 = ins[0]
        strat = next((s["key"] for s in STRATS if s["magic"] == i0.magic),
                     "other")
        t = {"strategy": strat, "symbol": i0.symbol,
             "side": "BUY" if i0.type == 0 else "SELL",
             "volume": i0.volume,
             "entry_time": i0.time, "entry_price": i0.price,
             "exit_time": None, "exit_price": None, "pnl": None,
             "reason": ""}
        if outs:
            o = outs[-1]
            c = (o.comment or "").lower()
            ps = next((s.get("pip_size", 1.0) for s in STRATS
                       if s["magic"] == i0.magic), 1.0)
            direction = 1 if i0.type == 0 else -1
            t.update({
                "exit_time": o.time, "exit_price": o.price,
                "pnl": round(sum(x.profit + x.swap + x.commission
                                 for x in ds), 2),
                "pips": round((o.price - i0.price) / ps * direction, 1),
                "reason": ("tp" if "tp" in c else
                           "sl" if "sl" in c else (c[:14] or "close")),
            })
        trades.append(t)
    trades.sort(key=lambda t: t["entry_time"])

    out.update(build_summary(ai.equity, ai.balance, round(ai.profit, 2),
                             bool(ti.trade_allowed) if ti else None,
                             strat_out, trades))
    out.update({"available": True, "login": ai.login, "server": ai.server,
                "currency": ai.currency})
    return out


def build_summary(equity, balance, floating, algo, strat_out, trades) -> dict:
    closed = [t for t in trades if t["exit_price"] is not None]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = -sum(t["pnl"] for t in losses)
    cur = best = 0
    for t in closed:
        cur = cur + 1 if t["pnl"] > 0 else 0
        best = max(best, cur)
    hist = load_equity()
    peak, mdd = float("-inf"), 0.0
    for p in hist:
        peak = max(peak, p["equity"])
        if peak > 0:
            mdd = min(mdd, (p["equity"] - peak) / peak * 100)
    pnl_total = round(equity - START_EQ, 2)
    stats = {
        "n_trades": len(closed), "wins": len(wins),
        "win_rate_pct": (round(100 * len(wins) / len(closed), 1)
                         if closed else 0),
        "profit_factor": (round(gross_w / gross_l, 2) if gross_l > 0
                          else ("∞" if gross_w > 0 else None)),
        "best": max((t["pnl"] for t in closed), default=0),
        "worst": min((t["pnl"] for t in closed), default=0),
        "avg_win": round(gross_w / len(wins), 2) if wins else 0,
        "avg_loss": round(-gross_l / len(losses), 2) if losses else 0,
        "max_drawdown_pct": round(mdd, 2),
        "total_return_pct": round(pnl_total / START_EQ * 100, 2),
        "starting_equity": START_EQ,
        "net_pips": round(sum(t.get("pips") or 0 for t in closed), 1),
        "floating_pct": round(floating / START_EQ * 100, 2),
    }
    for s in strat_out:
        s["pips_total"] = round(sum(t["pips"] for t in closed
                                    if t["strategy"] == s["key"]
                                    and t.get("pips") is not None), 1)
    weekly: dict = {}
    for t in closed:
        iso = datetime.utcfromtimestamp(t["exit_time"]).isocalendar()
        wk = f"{iso[0]}-W{iso[1]:02d}"
        weekly[wk] = round(weekly.get(wk, 0.0) + t["pnl"], 2)
    weekly_pnl = [{"week": k, "pnl": v} for k, v in sorted(weekly.items())]
    xp = 15 * len(closed) + 10 * len(wins)
    strat_keys = {t["strategy"] for t in closed}
    badge_defs = [
        ("First Trade", len(closed) >= 1),
        ("10 Trades", len(closed) >= 10),
        ("100 Trades", len(closed) >= 100),
        ("3 Win Streak", best >= 3),
        ("5 Win Streak", best >= 5),
        ("Profitable Run", pnl_total > 0 and len(closed) >= 5),
        ("Survived -10% DD", mdd <= -10 and pnl_total > 0),
        ("Profit Factor > 1.5", (gross_l > 0 and gross_w / gross_l > 1.5) or (gross_l == 0 and gross_w > 0)),
        ("Both Barrels", len(strat_keys & {s["key"] for s in STRATS}) >= 2),
    ]
    open_count = sum(len(s["positions"]) for s in strat_out)
    game = {
        "level": 1 + xp // 250, "xp": xp,
        "xp_into_level": xp % 250, "xp_needed": 250,
        "current_streak": cur, "best_streak": best,
        "badges": [{"name": n, "on": bool(v)} for n, v in badge_defs],
        "status": "IN_POSITION" if open_count else "HUNTING",
    }
    return {"balance": balance, "equity": equity, "floating": floating,
            "algo": algo, "strategies": strat_out, "trades": trades[-80:],
            "stats": stats, "game": game, "weekly_pnl": weekly_pnl}


def sample_state() -> dict:
    """Synthetic demo data so the dashboard renders with zero setup."""
    rng = random.Random(DEMO_SEED)
    now = int(time.time())
    eq, bal = START_EQ, START_EQ
    hist, trades = [], []
    for i in range(400):
        t = now - (400 - i) * 60
        if rng.random() < 0.04:
            # demo flavour: a solid-but-honest sample run — most trades win,
            # losses are real and visible, net drift is modestly positive
            pnl = round(rng.uniform(60, 240) if rng.random() < 0.68
                        else rng.uniform(-140, -45), 2)
            bal = round(bal + pnl, 2)
            trades.append({
                "strategy": rng.choice(["zenith", "cable"]),
                "symbol": rng.choice(["#USSPX500", "GBPUSD"]),
                "side": "BUY" if rng.random() < 0.8 else "SELL",
                "volume": 0.05, "entry_time": t - 3600,
                "entry_price": 7700 + rng.uniform(-40, 40),
                "exit_time": t, "exit_price": 7700 + rng.uniform(-40, 40),
                "pnl": pnl,
                "pips": round(abs(pnl) * rng.uniform(0.4, 1.2)
                              * (1 if pnl >= 0 else -1), 1),
                "reason": ("trail" if rng.random() < 0.4 else "tp") if pnl > 0 else "sl"})
        eq = round(bal + math.sin(i / 25) * 18 + rng.uniform(-6, 6), 2)
        hist.append({"t": t, "equity": eq, "balance": bal})
    strat_out = []
    for s in STRATS:
        dirs = [rng.choice([1, 1, -1, -1, 0]) for _ in range(16)]
        bull, bear, _ = streaks(
            [{"open": 0, "close": d} for d in dirs])
        strat_out.append({
            **{k: s[k] for k in ("key", "name", "symbol", "tf_name",
                                 "magic", "buy_x", "sell_x", "inputs")},
            "bull": bull, "bear": bear, "dirs": dirs,
            "price": 7731.05 if s["key"] == "zenith" else 1.35065,
            "to_buy": max(0, s["buy_x"] - bear),
            "to_sell": max(0, s["sell_x"] - bull),
            "positions": [], "floating": 0.0,
            "realized_total": round(sum(
                t["pnl"] for t in trades if t["strategy"] == s["key"]), 2),
            "deal_count": sum(
                2 for t in trades if t["strategy"] == s["key"]),
        })
    global _sample_hist
    _sample_hist = hist
    out = build_summary(eq, bal, 0.0, True, strat_out, trades)
    out.update({"available": True, "login": 12345678,
                "server": "Demo (synthetic sample data)", "currency": "USD"})
    return out


_sample_hist: list = []


def append_equity(acct: dict) -> None:
    try:
        with EQUITY_LOG.open("a", encoding="ascii") as f:
            f.write(json.dumps({"t": int(time.time()),
                                "equity": acct["equity"],
                                "balance": acct["balance"]}) + "\n")
    except OSError:
        pass


def load_equity(max_points: int = 5760) -> list[dict]:
    if not EQUITY_LOG.exists():
        return []
    try:
        lines = EQUITY_LOG.read_text(encoding="ascii").splitlines()
        if len(lines) > 25000:
            EQUITY_LOG.write_text("\n".join(lines[-12000:]) + "\n",
                                  encoding="ascii")
            lines = lines[-12000:]
    except OSError:
        return []
    out = []
    for ln in lines[-max_points:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def poll_loop() -> None:
    global state
    while True:
        snap: dict = {"updated": datetime.now(timezone.utc).isoformat(),
                      "ok": True}
        if CFG.get("demo_mode") or mt5 is None:
            snap["account"] = sample_state()
            snap["equity_hist"] = _sample_hist
        else:
            acct = read_account()
            if acct.get("available"):
                append_equity(acct)
            snap["account"] = acct
            snap["equity_hist"] = load_equity()
        with _state_lock:
            state = snap
        time.sleep(int(CFG["poll_seconds"]))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/state"):
            with _state_lock:
                body = json.dumps(state).encode()
            ctype = "application/json"
        else:
            body = HTML_PATH.read_bytes()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=poll_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", int(CFG["port"])),
                        Handler).serve_forever()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
김프 적립 신호 — 로컬 데스크톱 앱 (시세·계산 전용, 전송은 수동)
- API 키 불필요 (전부 공개 시세). 내 컴퓨터에서만 실행.
- 업비트/바이낸스 실시간 김프, 매수 신호, 이번 달 추천액, 경로 비교,
  그리고 '전송 체크리스트'(정확한 수량이 찍힌 수동 실행 안내)를 보여줌.
정보 제공용 · 투자자문 아님 · 프리미엄은 수분 단위로 변동.
"""
import json, os, ssl, threading, urllib.request, urllib.error
from datetime import datetime

# ---------------- 설정/파라미터 (웹앱과 동일) ----------------
ACC_ATH = 126296            # BTC ATH ($)
ACC_TOTAL = 100_000_000     # 총예산 1억
ACC_FLOOR_MONTHLY = 2_777_778  # 바닥선 월 적립 (5천만/18개월)

FEE_DEFAULT = {"upbitTrade": 0.0005, "binTrade": 0.001,
               "upbitBtcOut": 0.0009, "binBtcOut": 0.0002}
CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kimchi_config.json")

_ctx = ssl.create_default_context()
try:
    import certifi  # 있으면 사용
    _ctx.load_verify_locations(certifi.where())
except Exception:
    pass

def _load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            fee = {**FEE_DEFAULT, **d.get("fee", {})}
            return fee, bool(d.get("toWallet", False))
    except Exception:
        return dict(FEE_DEFAULT), False

def _save_cfg(fee, to_wallet):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump({"fee": fee, "toWallet": to_wallet}, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

# ---------------- 네트워크 ----------------
def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_upbit():
    arr = _get("https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-XRP,KRW-TRX")
    return {x["market"].replace("KRW-", ""): float(x["trade_price"]) for x in arr}

def fetch_global():
    # 바이낸스 우선, 실패 시 Bybit 폴백
    try:
        arr = _get('https://api.binance.com/api/v3/ticker/price'
                   '?symbols=%5B%22BTCUSDT%22%2C%22XRPUSDT%22%2C%22TRXUSDT%22%5D')
        o = {x["symbol"].replace("USDT", ""): float(x["price"]) for x in arr}
        if o.get("BTC", 0) > 0:
            return o
    except Exception:
        pass
    o = {}
    for c in ("BTC", "XRP", "TRX"):
        try:
            j = _get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={c}USDT")
            p = float(j["result"]["list"][0]["lastPrice"])
            if p > 0:
                o[c] = p
        except Exception:
            pass
    return o

def fetch_fx():
    # 두나무 → er-api.com 폴백
    try:
        j = _get("https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD")
        p = float((j[0] if isinstance(j, list) else j)["basePrice"])
        if p > 0:
            return p
    except Exception:
        pass
    try:
        j = _get("https://open.er-api.com/v6/latest/USD")
        p = float(j["rates"]["KRW"])
        if p > 0:
            return p
    except Exception:
        pass
    return None

# ---------------- 계산 (웹앱과 동일 로직) ----------------
def premium(up, bn, fx):
    if not (up and bn and fx):
        return None
    return (up / (bn * fx) - 1) * 100

def signal(P):
    if P is None:
        return ("—", "데이터 대기", 0.0, "gray")
    if P <= -2:
        return ("강한 역프", "적극 매수 · 스트레치 ×1.2", 1.2, "darkgreen")
    if P <= -0.5:
        return ("역프", "매수 우호 · 국내 직접매수", 1.0, "green")
    if P < 1.5:
        return ("중립", "바닥선(월 적립)만", 0.0, "#c79000")
    return ("김프", "국내 매수 자제 · 홀드 권고", 0.0, "#c0392b")

def stretch_for_drawdown(dd):
    if dd <= -70: return 6_500_000
    if dd <= -62: return 4_500_000
    if dd <= -55: return 2_500_000
    return 0

def recommend(btc_usd, P, spent):
    dd = (btc_usd - ACC_ATH) / ACC_ATH * 100
    label, action, w, color = signal(P)
    stretch = round(stretch_for_drawdown(dd) * w)
    remain = max(0, ACC_TOTAL - spent)
    reco = min(ACC_FLOOR_MONTHLY + stretch, remain)
    return {"dd": dd, "label": label, "action": action, "w": w, "color": color,
            "stretch": stretch, "floor": ACC_FLOOR_MONTHLY, "reco": reco, "remain": remain}

def route_compare(krw, up, bn, fx, bridge, to_wallet, fee):
    if not (krw > 0 and up and bn and fx):
        return None
    btc_a = krw * (1 - fee["upbitTrade"]) / up["BTC"]
    if to_wallet:
        btc_a -= fee["upbitBtcOut"]
    alt = krw * (1 - fee["upbitTrade"]) / up[bridge]
    usdt = alt * bn[bridge] * (1 - fee["binTrade"])
    btc_b = usdt / bn["BTC"] * (1 - fee["binTrade"])
    if to_wallet:
        btc_b -= fee["binBtcOut"]
    btc_a = max(0, btc_a); btc_b = max(0, btc_b)
    diff_pct = (btc_b / btc_a - 1) * 100 if btc_a > 0 else 0
    return {"bridge": bridge, "btcA": btc_a, "btcB": btc_b,
            "diff": btc_b - btc_a, "diffPct": diff_pct}

def best_bridge(up, bn, fx):
    cands = []
    for c in ("XRP", "TRX"):
        p = premium(up.get(c), bn.get(c), fx)
        if p is not None:
            cands.append((c, p))
    cands.sort(key=lambda x: x[1])  # 가장 할인(음수 큰) 먼저
    return cands[0][0] if cands else None

def won(n):
    return "₩{:,.0f}".format(n) if n is not None else "—"

# ---------------- 전송 체크리스트 (수동 실행 안내) ----------------
def transfer_steps(krw, up, bn, fx, use_bridge, bridge, to_wallet):
    """정확한 수량이 찍힌 수동 전송 단계 리스트 반환."""
    steps = []
    if not (krw > 0 and up and bn and fx):
        return ["시세 로딩 후 표시됩니다."]
    if not use_bridge:
        btc = krw / up["BTC"]
        steps.append(f"1. 업비트에서 {won(krw)}로 BTC 매수  (약 ₿{btc:.6f})")
        if to_wallet:
            steps.append("2. 업비트 → 개인지갑으로 BTC 출금  (※ 지갑주소 사전 등록 필요)")
    else:
        altqty = krw / up[bridge]
        usdt = altqty * bn[bridge]
        btc = usdt / bn["BTC"]
        steps.append(f"1. 업비트에서 {won(krw)}로 {bridge} 매수  (약 {altqty:,.2f} {bridge})")
        steps.append(f"2. {bridge}를 바이낸스 {bridge} 입금주소로 전송  (※ 네트워크 확인)")
        steps.append(f"3. 바이낸스에서 {bridge} → USDT 매도  (약 {usdt:,.2f} USDT)")
        steps.append(f"4. USDT로 BTC 매수  (약 ₿{btc:.6f})")
        if to_wallet:
            steps.append("5. 바이낸스 → 개인지갑으로 BTC 출금  (※ 지갑주소 사전 등록 필요)")
    steps.append("⚠️ 전송 중 가격 변동 리스크 있음 · 각 단계 수량은 시세 변동 시 달라짐")
    return steps

# ---------------- GUI ----------------
def run_gui():
    import tkinter as tk
    from tkinter import ttk

    fee, to_wallet = _load_cfg()
    state = {"up": {}, "bn": {}, "fx": None, "ts": 0, "loading": False}

    GREEN = "#217346"; BG = "#f3f3f3"
    root = tk.Tk()
    root.title("김프 적립 신호 — 로컬 (시세·계산 전용)")
    root.configure(bg=BG)
    root.geometry("640x760")

    # 상단 배지
    top = tk.Frame(root, bg=BG); top.pack(fill="x", padx=12, pady=(12, 4))
    badge = tk.Label(top, text="—", font=("Malgun Gothic", 30, "bold"),
                     fg="white", bg="gray", width=9)
    badge.pack(side="left", ipady=10)
    info = tk.Label(top, text="로딩중…", font=("Malgun Gothic", 10), bg=BG, justify="left")
    info.pack(side="left", padx=14)

    # 추천/경로
    reco_lbl = tk.Label(root, text="", font=("Malgun Gothic", 11, "bold"),
                        bg=BG, justify="left", anchor="w")
    reco_lbl.pack(fill="x", padx=12, pady=(4, 0))
    route_lbl = tk.Label(root, text="", font=("Malgun Gothic", 9), bg="white",
                         justify="left", anchor="w", relief="solid", bd=1, padx=8, pady=6)
    route_lbl.pack(fill="x", padx=12, pady=6)

    # 코인별 프리미엄 테이블
    tv = ttk.Treeview(root, columns=("up", "gl", "p"), show="headings", height=3)
    for c, t, w in (("up", "업비트(원)", 160), ("gl", "글로벌($)", 140), ("p", "프리미엄", 100)):
        tv.heading(c, text=t); tv.column(c, width=w, anchor="e")
    tv.pack(fill="x", padx=12)

    # 옵션 행 (개인지갑 출금)
    optf = tk.Frame(root, bg=BG); optf.pack(fill="x", padx=12, pady=(6, 0))
    wallet_var = tk.BooleanVar(value=to_wallet)
    def on_wallet():
        _save_cfg(fee, wallet_var.get()); render()
    tk.Checkbutton(optf, text="매수 후 개인지갑으로 출금 (경로 비교에 출금수수료 반영)",
                   variable=wallet_var, command=on_wallet, bg=BG,
                   font=("Malgun Gothic", 9)).pack(side="left")

    # 수수료 설정
    feef = tk.LabelFrame(root, text="⚙ 내 거래소 수수료 (경로 계산 반영)", bg=BG,
                         font=("Malgun Gothic", 9))
    feef.pack(fill="x", padx=12, pady=6)
    fee_vars = {}
    fields = [("upbitTrade", "업비트거래%", 100), ("binTrade", "바이낸스거래%", 100),
              ("upbitBtcOut", "업비트BTC출금", 10000), ("binBtcOut", "바이낸스BTC출금", 10000)]
    for i, (k, lab, mul) in enumerate(fields):
        tk.Label(feef, text=lab, bg=BG, font=("Malgun Gothic", 8)).grid(row=0, column=i*2, padx=(6, 2), pady=4)
        v = tk.StringVar(value=str(fee[k] * (100 if mul == 100 else 1)))
        fee_vars[k] = (v, mul)
        tk.Entry(feef, textvariable=v, width=8).grid(row=0, column=i*2+1, padx=(0, 6))
    def apply_fees():
        for k, (v, mul) in fee_vars.items():
            try:
                fee[k] = max(0.0, float(v.get()) / (100 if mul == 100 else 1))
            except ValueError:
                pass
        _save_cfg(fee, wallet_var.get()); render()
    tk.Button(feef, text="적용", command=apply_fees).grid(row=0, column=99, padx=6)

    # 전송 체크리스트
    chkf = tk.LabelFrame(root, text="📋 전송 체크리스트 (직접 실행 · 자동 아님)", bg=BG,
                         font=("Malgun Gothic", 9, "bold"))
    chkf.pack(fill="both", expand=True, padx=12, pady=6)
    chk_lbl = tk.Label(chkf, text="", font=("Malgun Gothic", 9.5), bg="white",
                       justify="left", anchor="nw")
    chk_lbl.pack(fill="both", expand=True, padx=6, pady=6)

    # 하단
    botf = tk.Frame(root, bg=BG); botf.pack(fill="x", padx=12, pady=(0, 10))
    stamp = tk.Label(botf, text="", font=("Malgun Gothic", 8), fg="#666", bg=BG)
    stamp.pack(side="left")
    tk.Button(botf, text="🔄 새로고침", command=lambda: refresh()).pack(side="right")
    disc = tk.Label(root, text="정보 제공용 · 투자자문 아님 · 프리미엄은 수분 단위로 변동 · API키 불필요(공개시세)",
                    font=("Malgun Gothic", 7.5), fg="#888", bg=BG)
    disc.pack(side="bottom", pady=(0, 6))

    def render():
        up, bn, fx = state["up"], state["bn"], state["fx"]
        if not up or "BTC" not in up:
            info.config(text="시세 로딩중…"); return
        P = premium(up["BTC"], bn.get("BTC"), fx)
        label, action, w, color = signal(P)
        badge.config(text=("—" if P is None else f"{P:+.2f}%"), bg=color)
        bnkrw = bn["BTC"] * fx if (bn.get("BTC") and fx) else None
        rec = recommend(bn.get("BTC", 0), P, 0)
        info.config(text=(f"{label}\n업비트 BTC: {won(up['BTC'])}\n"
                          f"바이낸스×환율: {won(bnkrw)}\n"
                          f"드로다운: {rec['dd']:.1f}%  (ATH ${ACC_ATH:,})"))
        btcqty = rec["reco"] / up["BTC"] if up["BTC"] else 0
        reco_lbl.config(text=(f"이번 달 추천: {won(rec['reco'])}  (≈ ₿{btcqty:.6f})   "
                              f"[바닥선 {won(rec['floor'])} + 스트레치 {won(rec['stretch'])}]  · {action}"))
        # 경로 비교
        bridge = best_bridge(up, bn, fx)
        amt = rec["reco"] or ACC_FLOOR_MONTHLY
        use_bridge = False
        if bridge:
            rc = route_compare(amt, up, bn, fx, bridge, wallet_var.get(), fee)
            if rc:
                if rc["diffPct"] > 0.3:
                    use_bridge = True
                    route_lbl.config(text=(
                        f"💡 {bridge} 다리 경로가 BTC 개수 더 많음  (기준 {won(amt)})\n"
                        f"   다리: ₿{rc['btcB']:.6f}  vs  직접: ₿{rc['btcA']:.6f}"
                        f"  → +₿{rc['diff']:.6f} (+{rc['diffPct']:.2f}%)"), fg="#0a7a3a")
                elif rc["diffPct"] < -0.05:
                    route_lbl.config(text=(
                        f"✅ 업비트 BTC 직접 매수가 유리  (기준 {won(amt)})\n"
                        f"   직접: ₿{rc['btcA']:.6f}  vs  {bridge} 다리: ₿{rc['btcB']:.6f}"
                        f"  ({rc['diffPct']:.2f}%)"), fg="#111")
                else:
                    route_lbl.config(text=(
                        f"⚖️ 거의 같음 (차이 {abs(rc['diffPct']):.2f}%) → 직접 매수가 단순·안전\n"
                        f"   전송 리스크 감안. 다리로 크게 벌려면 프리미엄 차 확대 또는 개인지갑 출금 시."),
                        fg="#111")
        # 코인 테이블
        tv.delete(*tv.get_children())
        for c in ("BTC", "XRP", "TRX"):
            p = premium(up.get(c), bn.get(c), fx)
            tv.insert("", "end", values=(
                won(up.get(c)), f"${bn.get(c, 0):,.4f}" if bn.get(c) else "—",
                "—" if p is None else f"{p:+.2f}%"))
        # 전송 체크리스트
        steps = transfer_steps(amt, up, bn, fx, use_bridge, bridge, wallet_var.get())
        chk_lbl.config(text="\n".join(steps))
        ts = datetime.fromtimestamp(state["ts"]).strftime("%H:%M:%S") if state["ts"] else "-"
        stale = not (up and bn.get("BTC") and fx)
        stamp.config(text=(f"⚠️ 지연 (마지막 {ts})" if stale else f"{ts} 갱신"),
                     fg=("#c0392b" if stale else "#666"))

    def refresh():
        if state["loading"]:
            return
        state["loading"] = True
        def work():
            up = bn = fx = None
            try: up = fetch_upbit()
            except Exception: pass
            try: bn = fetch_global()
            except Exception: pass
            try: fx = fetch_fx()
            except Exception: pass
            def done():
                # 세 값 다 있으면 갱신, 아니면 마지막값 유지
                if up and up.get("BTC") and bn and bn.get("BTC") and fx:
                    state.update(up=up, bn=bn, fx=fx, ts=datetime.now().timestamp())
                state["loading"] = False
                render()
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def tick():
        refresh(); root.after(40000, tick)  # 40초 자동
    tick()
    root.mainloop()

# ---------------- CLI 테스트 (--test) ----------------
def run_test():
    up = fetch_upbit(); bn = fetch_global(); fx = fetch_fx()
    P = premium(up["BTC"], bn["BTC"], fx)
    rec = recommend(bn["BTC"], P, 0)
    print("업비트BTC:", won(up["BTC"]), "| 바이낸스BTC: $%.0f" % bn["BTC"], "| 환율:", round(fx, 2))
    print("프리미엄: %+.2f%%" % P, "|", rec["label"], "| 드로다운: %.1f%%" % rec["dd"])
    print("이번달 추천:", won(rec["reco"]))
    for tw in (False, True):
        rc = route_compare(rec["reco"], up, bn, fx, best_bridge(up, bn, fx), tw, dict(FEE_DEFAULT))
        print(f"  경로({'개인지갑' if tw else '거래소'}): 직접 ₿{rc['btcA']:.6f} vs 다리 ₿{rc['btcB']:.6f} ({rc['diffPct']:+.2f}%)")
    print("체크리스트:")
    for s in transfer_steps(rec["reco"], up, bn, fx, True, best_bridge(up, bn, fx), False):
        print("  ", s)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        run_test()
    else:
        run_gui()

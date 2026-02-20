# === 複製這段程式碼到 Colab ===
import yfinance as yf
import pandas as pd
import numpy as np
import sys

# Force UTF-8 output for Windows console compatibility
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# === 這裡設定你想監控的股票與部位 ===
# 根據用戶提供的 V17.7 資料整理
CONFIG = {
    "RISK_FREE_RATE": 0.04,
    "BENCHMARK": "CSPX.L",  # 基準 (S&P 500 ETF)
    "PORTFOLIO": [
        {"ticker": "CNDX.L", "shares": 4, "cost": 1384.26, "type": "GROWTH"},
        {"ticker": "CSPX.L", "shares": 12, "cost": 695.64, "type": "CORE"},
        {"ticker": "VWRA.L", "shares": 57, "cost": 166.84, "type": "CORE"},
        {"ticker": "USSC.L", "shares": 0, "cost": 0, "type": "VALUE"},
        {"ticker": "SMH.L", "shares": 20, "cost": 59.35, "type": "TECH"},
        {"ticker": "SCHG", "shares": 61.13, "cost": 31.95, "type": "GROWTH"},
        {"ticker": "JEPQ.L", "shares": 80, "cost": 26.46, "type": "INCOME"},
        {"ticker": "FUSA.L", "shares": 0, "cost": 0, "type": "CORE"},
        {"ticker": "AIAI.L", "shares": 50, "cost": 28.67, "type": "TECH"},
        {"ticker": "RBOT.L", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "EQQU.L", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "NUCL.L", "shares": 30, "cost": 63.38, "type": "THEME"},
        {"ticker": "NATO.L", "shares": 100, "cost": 20.76, "type": "THEME"},
        {"ticker": "IUHC.L", "shares": 60, "cost": 12.47, "type": "SECTOR"},
        {"ticker": "IB01.L", "shares": 28, "cost": 119.67, "type": "CASH"},
        {"ticker": "VUAA.L", "shares": 0, "cost": 0, "type": "CORE"},
        {"ticker": "IUMO.L", "shares": 0, "cost": 0, "type": "CORE"},
        {"ticker": "DFNS.L", "shares": 0, "cost": 0, "type": "THEME"},
        {"ticker": "URNU.L", "shares": 35, "cost": 31.69, "type": "THEME"},
        {"ticker": "JEDI.L", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "VPN.L", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "GLDM", "shares": 0, "cost": 0, "type": "GOLD"},
        {"ticker": "VTI", "shares": 72.7, "cost": 297.90, "type": "CORE"}, # 合併 40@291.77 + 32.7@305.41
        {"ticker": "BND", "shares": 78.87, "cost": 65.31, "type": "BOND"}, # 合併 6@72.01 + 72.87@64.76
        {"ticker": "VXUS", "shares": 110.24, "cost": 73.58, "type": "CORE"}, # 合併 45@61.69 + 65.24@81.78
        {"ticker": "SOXX", "shares": 3.17, "cost": 284.39, "type": "TECH"},
        {"ticker": "2330.TW", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "0050.TW", "shares": 435, "cost": 71.85, "type": "CORE"},
        {"ticker": "006208.TW", "shares": 1963, "cost": 110.71, "type": "CORE"},
        {"ticker": "0052.TW", "shares": 5569, "cost": 17.12, "type": "TECH"},
        {"ticker": "00662.TW", "shares": 0, "cost": 0, "type": "TECH"},
        {"ticker": "00646.TW", "shares": 3000, "cost": 35.3, "type": "CORE"},
        {"ticker": "2347.TW", "shares": 1269, "cost": 64.7, "type": "STOCK"},
        {"ticker": "00985A.TW", "shares": 11500, "cost": 10.72, "type": "BOND"},
        {"ticker": "00988A.TW", "shares": 10000, "cost": 10, "type": "THEME"},
        {"ticker": "00965.TW", "shares": 0, "cost": 0, "type": "THEME"},
        {"ticker": "009805.TW", "shares": 13000, "cost": 12.91, "type": "THEME"},
        {"ticker": "009812.TW", "shares": 10000, "cost": 10.01, "type": "THEME"},
        {"ticker": "009813.TW", "shares": 10000, "cost": 10, "type": "THEME"},
    ]
}

def calculate_technical_indicators(item):
    ticker = item["ticker"]
    try:
        # 下載數據
        hist = yf.download(ticker, period="1y", interval="1d", progress=False)
        if hist.empty: return None
        
        df = hist['Close']
        if isinstance(df, pd.DataFrame): df = df.iloc[:, 0]

        # 1. 計算 RSI (14)
        delta = df.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        # 2. 計算 MA10
        ma10 = df.rolling(window=10).mean().iloc[-1]

        # 3. 計算 Alpha & Beta (與基準對比)
        bench = yf.download(CONFIG["BENCHMARK"], period="1y", progress=False)['Close']
        if isinstance(bench, pd.DataFrame): bench = bench.iloc[:, 0]
        
        returns = df.pct_change().dropna()
        bench_ret = bench.pct_change().dropna()
        aligned = pd.concat([returns, bench_ret], axis=1, join='inner').dropna()
        
        stock_ret = aligned.iloc[:, 0]
        market_ret = aligned.iloc[:, 1]
        
        if len(stock_ret) < 30: return None # 資料不足

        covariance = np.cov(stock_ret, market_ret)[0][1]
        beta = covariance / np.var(market_ret)
        
        stock_cagr = stock_ret.mean() * 252
        market_cagr = market_ret.mean() * 252
        alpha = stock_cagr - (CONFIG["RISK_FREE_RATE"] + beta * (market_cagr - CONFIG["RISK_FREE_RATE"]))

        current_price = df.iloc[-1]
        roi = ((current_price - item["cost"]) / item["cost"]) if item["cost"] > 0 else 0
        mv = current_price * item["shares"]

        return {
            "Ticker": ticker,
            "Price": current_price,
            "MA10": ma10,
            "RSI": current_rsi,
            "Alpha": alpha,
            "Beta": beta,
            "Shares": item["shares"],
            "Cost": item["cost"],
            "ROI": roi,
            "MV": mv
        }
    except Exception as e:
        return None

def get_signal_v17(stats):
    price = stats['Price']
    ma10 = stats['MA10']
    rsi = stats['RSI']
    alpha = stats['Alpha']
    ticker = stats['Ticker']
    
    # 特殊處理：現金/債券
    if any(x in ticker for x in ["IB01", "BND", "BIL"]):
        return "PARK_CASH", "🛡️ 防禦配置/利息收益 (DEFENSE_YIELD)"

    # 基本邏輯
    if rsi > 85:
        return "SELL", "� 技術指標極度過熱 (TECH_EXTREME)"
    if rsi > 70 and price > ma10 * 1.1:
        return "TRIM", "⚠️ 漲幅過快，建議減碼 (OVERVALUED)"
    
    if rsi < 45:
        return "BUY_TIER1", "✅ 定期定額/拉回分批 (DCA_ENTRY)"
    
    if price > ma10 and alpha > 0.05:
        return "HOLD_BULL", "🚀 多頭趨勢強勁 (TREND_STRONG)"
    
    if stats['Shares'] > 0:
        return "HOLD", "� 核心持有/中性續抱 (CORE_HOLD)"
        
    return "NEUTRAL", "⚪ 觀察中 (WATCHLIST)"

# === 主程式 ===
print(f"{'代號':<10} {'現價':<10} {'ROI%':<8} {'市值':<10} {'RSI':<6} {'MA10':<8} {'訊號 (V17.7)':<15} {'說明'}")
print("-" * 100)

total_mv = 0
total_cost = 0

for item in CONFIG["PORTFOLIO"]:
    stats = calculate_technical_indicators(item)
    if stats:
        action, reason = get_signal_v17(stats)
        
        # 視覺化
        roi_mark = "�" if stats['ROI'] > 0.1 else ("❄️" if stats['ROI'] < -0.05 else "  ")
        
        print(f"{stats['Ticker']:<10} {stats['Price']:<10.2f} {stats['ROI']*100:>6.1f}%{roi_mark} {stats['MV']:>10.0f} {stats['RSI']:>5.1f} {stats['MA10']:>8.2f} {action:<15} {reason}")
        
        if stats['Shares'] > 0:
            total_mv += stats['MV']
            total_cost += (stats['Cost'] * stats['Shares'])
    else:
        print(f"{item['ticker']:<10} 數據讀取失敗")

print("-" * 100)
if total_cost > 0:
    total_roi = (total_mv - total_cost) / total_cost
    print(f"帳戶總市值: {total_mv:,.2f} USD (預估)")
    print(f"帳戶總報酬: {total_roi*100:.2f}%")

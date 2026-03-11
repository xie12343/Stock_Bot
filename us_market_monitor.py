import os
import smtplib
import yfinance as yf
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 核心設定與警報閾值 (參考 NotebookLM V3.x 策略)
# ==========================================
STOCK_BOT_EMAIL = os.environ.get("STOCK_BOT_EMAIL")
STOCK_BOT_PWD = os.environ.get("STOCK_BOT_PWD")
GAS_URL = os.environ.get("GAS_URL")

# 設定「大跌」的觸發條件
# 參考 V3.1 終極版 95% VaR (風險價值) 約為 -2.1%
DROP_THRESHOLD_PCT = -0.021  
VIX_DANGER_LEVEL = 25.0      # VIX 恐慌指數大於 25 視為高風險

# ==========================================
# 2. 獲取美股即時數據
# ==========================================
def get_us_market_status():
    print("🔍 正在掃描美股即時報價與波動率 (Strategy: V3.x)...")
    try:
        # ^GSPC: 標普500, ^IXIC: 納斯達克, ^VIX: 恐慌指數
        tickers = yf.Tickers("^GSPC ^IXIC ^VIX")
        
        # 標普 500
        sp500_info = tickers.tickers["^GSPC"].fast_info
        sp500_price = sp500_info.last_price
        sp500_prev = sp500_info.previous_close
        sp500_change = (sp500_price - sp500_prev) / sp500_prev
        
        # 納斯達克
        ndx_info = tickers.tickers["^IXIC"].fast_info
        ndx_price = ndx_info.last_price
        ndx_prev = ndx_info.previous_close
        ndx_change = (ndx_price - ndx_prev) / ndx_prev
        
        # VIX
        vix_price = tickers.tickers["^VIX"].fast_info.last_price
        
        return {
            "SP500": {"price": sp500_price, "change": sp500_change},
            "NASDAQ": {"price": ndx_price, "change": ndx_change},
            "VIX": vix_price
        }
    except Exception as e:
        print(f"❌ 數據抓取失敗: {e}")
        return None

# ==========================================
# 3. 發送 Email 警報
# ==========================================
def send_email_alert(msg_content, is_critical=False):
    recipient = STOCK_BOT_EMAIL
    sender = STOCK_BOT_EMAIL
    password = STOCK_BOT_PWD
    
    if not password:
        print("❌ 錯誤：STOCK_BOT_PWD 未設定，無法發信。")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Portfolio Monitor <{sender}>"
        msg['To'] = recipient
        
        # 根據嚴重程度改變信件標題
        title_icon = "🚨 [緊急防護]" if is_critical else "⚠️ [市場警告]"
        msg['Subject'] = f"{title_icon} 美股波動警報 - 觸發 V3.1 安全閾值 ({datetime.now().strftime('%H:%M')})"
        
        msg.attach(MIMEText(msg_content, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("✅ 策略警報 Email 已成功發送！")
    except Exception as e:
        print(f"❌ 郵件發送失敗: {e}")

# ==========================================
# 4. 主邏輯：判斷是否觸發策略建議
# ==========================================
def run_monitor():
    market_data = get_us_market_status()
    if not market_data:
        return

    sp500_drop = market_data["SP500"]["change"]
    ndx_drop = market_data["NASDAQ"]["change"]
    vix = market_data["VIX"]
    
    # 判斷是否觸發警報 (跌破 V3.1 的 VaR 閾值 -2.1%)
    is_sp500_crash = sp500_drop <= DROP_THRESHOLD_PCT
    is_ndx_crash = ndx_drop <= DROP_THRESHOLD_PCT
    is_vix_high = vix >= VIX_DANGER_LEVEL
    
    print(f"📊 當前狀態: S&P500 {sp500_drop:.2%}, NASDAQ {ndx_drop:.2%}, VIX {vix:.2f}")

    if is_sp500_crash or is_ndx_crash or is_vix_high:
        # VIX >= 30 視為極度危險 (對應 V3.4 高波動環境)
        is_critical = (sp500_drop <= -0.03) or (vix >= 30) 
        
        report = (
            f"【2026 全球 ETF 投資系統 - 異常監控報告】\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"當前市場波動已觸發 V3.1 終極版之安全性閾值 (-2.1%)，\n"
            f"請評估您的資產配置平衡度：\n\n"
            f"📊 市場數據：\n"
            f"📉 S&P 500: {market_data['SP500']['price']:,.2f} ({sp500_drop:.2%})\n"
            f"📉 NASDAQ:  {market_data['NASDAQ']['price']:,.2f} ({ndx_drop:.2%})\n"
            f"🔥 VIX 指數: {vix:.2f} \n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 【策略建議一：5% 帶狀再平衡 (Rebalancing)】\n"
            f"根據筆記，若單一資產偏離目標比例超過 5%，應執行再平衡。\n"
            f"請檢查您是否需要從超漲資產 (如 V3.4 之 IUMO/SMH) 轉入防禦性資產 (如 V3.1 之 IUHC/IUFS)。\n\n"
            f"🎯 【策略建議二：避險保護 (Hedging)】\n"
            f"1. 商品建議：買進 (Buy) 次月合約 (04) Put。\n"
            f"2. 深度建議：視 VIX 水平調整，高 VIX 時可考慮 Zero-Cost Collar 降低避險成本。\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 備註：V3.5 全球版在此環境下通常具備最強抗壓性 (-19.8% MDD)，請檢查全球資產比例。\n"
            f"🔗 資產試算：{GAS_URL if GAS_URL else '未設定 GAS_URL'}"
        )
        send_email_alert(report, is_critical)
    else:
        print("✅ 目前市場波動位於 V3.1 安全防線內，無需發送報警。")

if __name__ == "__main__":
    run_monitor()
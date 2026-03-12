import os
import smtplib
import yfinance as yf
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 核心設定與警報閾值
# ==========================================
STOCK_BOT_EMAIL = os.environ.get("STOCK_BOT_EMAIL")
STOCK_BOT_PWD = os.environ.get("STOCK_BOT_PWD")

# 設定「大跌」的觸發條件 (可自行調整)
DROP_THRESHOLD_PCT = -0.015  # 指數下跌超過 1.5% 即觸發警報
VIX_DANGER_LEVEL = 25.0      # VIX 恐慌指數大於 25 視為高風險

# ==========================================
# 2. 獲取美股即時數據
# ==========================================
def get_us_market_status():
    print("🔍 正在掃描美股即時報價與波動率...")
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
        msg['From'] = f"Night Market Radar <{sender}>"
        msg['To'] = recipient
        
        # 根據嚴重程度改變信件標題
        title_icon = "🚨 [緊急防護]" if is_critical else "⚠️ [市場警告]"
        msg['Subject'] = f"{title_icon} 美股大跌警報 - 建議啟動 Put 避險 ({datetime.now().strftime('%H:%M')})"
        
        msg.attach(MIMEText(msg_content, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("✅ 避險警報 Email 已成功發送！")
    except Exception as e:
        print(f"❌ 郵件發送失敗: {e}")

# ==========================================
# 4. 主邏輯：判斷是否需要買 Put
# ==========================================
def run_monitor():
    market_data = get_us_market_status()
    if not market_data:
        return

    sp500_drop = market_data["SP500"]["change"]
    ndx_drop = market_data["NASDAQ"]["change"]
    vix = market_data["VIX"]
    
    # 判斷是否觸發警報 (任一指數跌破閾值，或 VIX 異常飆高)
    is_sp500_crash = sp500_drop <= DROP_THRESHOLD_PCT
    is_ndx_crash = ndx_drop <= DROP_THRESHOLD_PCT
    is_vix_high = vix >= VIX_DANGER_LEVEL
    
    print(f"📊 當前狀態: S&P500 {sp500_drop:.2%}, NASDAQ {ndx_drop:.2%}, VIX {vix:.2f}")

    if is_sp500_crash or is_ndx_crash or is_vix_high:
        is_critical = (sp500_drop <= -0.02) or (vix >= 30) # 跌超 2% 或 VIX 破 30 視為極度危險
        
        report = (
            f"【美股崩盤監控報告】\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"目前美股出現顯著下跌，台指夜盤可能已遭受波及，請立即評估是否啟動避險：\n\n"
            f"📉 S&P 500: {market_data['SP500']['price']:,.2f} ({sp500_drop:.2%})\n"
            f"📉 NASDAQ:  {market_data['NASDAQ']['price']:,.2f} ({ndx_drop:.2%})\n"
            f"🔥 VIX 指數: {vix:.2f} \n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 【系統行動建議：保護性賣權 (Buy Put)】\n"
            f"1. 請開啟富邦 APP，切換至「盤後 (夜盤)」行情。\n"
            f"2. 目標商品：建議尋找『次月合約 (04)』，履約價低於目前大盤約 300~500 點的 Put。\n"
            f"3. 操作方向：買進 (Buy)。\n"
            f"4. 資金控管：買方無保證金追繳風險，最大虧損為期初支付之權利金。\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 提醒：若打算今晚入睡前下單，建議使用『雲端條件單 (OCO)』設定停損與停利出局點。"
        )
        send_email_alert(report, is_critical)
    else:
        print("✅ 目前美股波動在安全範圍內，無需發送警報。")

if __name__ == "__main__":
    run_monitor()

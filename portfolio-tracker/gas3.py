import os
import requests
import json
from datetime import datetime
import smtplib
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 核心設定
# ==========================================
STOCK_BOT_EMAIL = os.environ.get("STOCK_BOT_EMAIL") or "xie12343@gmail.com"
STOCK_BOT_PWD = os.environ.get("STOCK_BOT_PWD") or "kasf euov ntjc fpiq" 
GAS_URL = os.environ.get("GAS_URL") or "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec"

USD_TWD_RATE = 32.5 
ALERT_THRESHOLD_USD = 1500000 

# ==========================================
# 2. 功能：抓取市場數據 (含 VIX)
# ==========================================
def get_market_intelligence():
    print("🔍 正在分析全球市場波動率與台股走勢...")
    try:
        # 抓取台股 (^TWII) 與 VIX 指數 (^VIX)
        tickers = yf.Tickers("^TWII ^VIX")
        
        # 台股 5 日趨勢
        twii_hist = tickers.tickers["^TWII"].history(period='5d')
        current_taiex = round(twii_hist['Close'].iloc[-1], 2)
        trend_5d = (current_taiex - twii_hist['Close'].iloc[0]) / twii_hist['Close'].iloc[0]
        
        # VIX 當前值
        vix_data = tickers.tickers["^VIX"].history(period='1d')
        current_vix = round(vix_data['Close'].iloc[-1], 2)
        
        return current_taiex, trend_5d, current_vix
    except Exception as e:
        print(f"❌ 數據抓取失敗: {e}")
        return None, None, None

# ==========================================
# 3. 功能：發送 Email 通知
# ==========================================
def send_email_alert(msg_content, strategy_name=""):
    recipient = "xie12343@gmail.com"
    sender = STOCK_BOT_EMAIL
    password = STOCK_BOT_PWD
    if not password: return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Portfolio Monitor <{sender}>"
        msg['To'] = recipient
        msg['Subject'] = f"🚨 {strategy_name} 防護警報 - {datetime.now().strftime('%Y-%m-%d')}"
        msg.attach(MIMEText(msg_content, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ 郵件失敗: {e}")
        return False

# ==========================================
# 4. 主流程
# ==========================================
def run_monitor():
    try:
        # 1. 資產檢查
        response = requests.get(GAS_URL, timeout=10)
        portfolio_raw = float(response.json().get('portfolio_value', 0))
        total_usd = portfolio_raw / USD_TWD_RATE if portfolio_raw > 10000000 else portfolio_raw
        
        # 2. 市場智能分析
        taiex, trend, vix = get_market_intelligence()
        
        if total_usd >= ALERT_THRESHOLD_USD and taiex:
            # --- 數據準備 ---
            p_put = int((taiex * 0.95) // 100 * 100)
            c_call = int((taiex * 1.05) // 100 * 100)
            col_p = int((taiex * 0.97) // 100 * 100)
            col_c = int((taiex * 1.03) // 100 * 100)
            hedge_qty = round((total_usd * USD_TWD_RATE) / (taiex * 200), 2)

            # --- VIX + 趨勢 綜合判斷邏輯 ---
            if vix > 30:
                best_strategy = "期貨空單對沖 (Short Hedge)"
                reason = f"VIX 指數極高 ({vix})，市場進入極度恐慌。期權保費過貴，建議直接用期貨鎖死風險。"
                rec_action = f"👉 賣出台指期空單 {hedge_qty} 口"
            elif vix > 22 or trend < -0.02:
                best_strategy = "保護性賣權 (Protective Put)"
                reason = f"市場波動加劇 (VIX: {vix}) 且趨勢向下。建議買入保險，防止資產崩跌。"
                rec_action = f"👉 買入 Put @{p_put}"
            elif trend > 0.02 and vix < 18:
                best_strategy = "覆蓋式買權 (Covered Call)"
                reason = "市場情緒穩定且溫和上漲。建議賣出價外 Call 賺取額外現金流。"
                rec_action = f"👉 賣出 Call @{c_call}"
            else:
                best_strategy = "零成本衣領策略 (Zero-Cost Collar)"
                reason = "市場處於中性震盪。建議使用零成本組合，鎖定上下 3% 區間。"
                rec_action = f"👉 賣出 Call @{col_c} + 買入 Put @{col_p}"

            # --- 郵件內容 ---
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            msg = (
                f"【資產防護決策報告】\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 資產總額：${total_usd:,.2f} USD\n"
                f"📊 市場狀態：\n"
                f"   - 台指點位：{taiex:,.2f} ({'↑' if trend>0 else '↓'} {trend:.2%})\n"
                f"   - VIX 恐懼指數：{vix} ({'偏高' if vix>20 else '穩定'})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 最佳對策：{best_strategy}\n"
                f"📝 判斷理由：{reason}\n"
                f"🚀 執行建議：{rec_action}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚖️ 其他參數參考：\n"
                f"   - 期貨對沖口數：{hedge_qty} 口\n"
                f"   - Collar 區間：{col_p} ~ {col_c}\n"
                f"   - 深度 Put 支撐：{p_put}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"請登入富邦 Neo SDK 執行操作。"
            )
            
            if send_email_alert(msg, strategy_name=best_strategy):
                print(f"✅ 決策郵件已發送。當前 VIX: {vix}")
        else:
            print(f"✅ 監控中... 資產 ${total_usd:,.0f} / VIX: {vix}")

    except Exception as e:
        print(f"❌ 執行異常: {e}")

if __name__ == "__main__":
    run_monitor()
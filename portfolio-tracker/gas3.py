import os
import requests
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 核心設定
# ==========================================
# 從環境變數讀取敏感資訊 (用於 GitHub Actions)
# 若本地執行且未設定環境變數，則使用預設值
STOCK_BOT_EMAIL = os.environ.get("STOCK_BOT_EMAIL", "xie12343@gmail.com")
STOCK_BOT_PWD = os.environ.get("STOCK_BOT_PWD", "") # 需提供 16 位 Gmail 應用程式密碼
GAS_URL = os.environ.get("GAS_URL", "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec")

USD_TWD_RATE = 32.5  # 基準匯率
ALERT_THRESHOLD_USD = 1500000 # 150萬美金觸發保護

# ==========================================
# 2. 功能：發送 Email 通知
# ==========================================
def send_email_alert(msg_content):
    recipient = "xie12343@gmail.com"
    sender = STOCK_BOT_EMAIL
    password = STOCK_BOT_PWD

    if not password:
        print("⚠️ 未設定 STOCK_BOT_PWD，跳過郵件寄送。")
        return False

    print(f"📧 正在寄送資產警報至: {recipient} ...")
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Portfolio Monitor <{sender}>"
        msg['To'] = recipient
        msg['Subject'] = f"🚨 資產防護警報 - {datetime.now().strftime('%Y-%m-%d')}"

        msg.attach(MIMEText(msg_content, 'plain'))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ 郵件寄送失敗: {e}")
        return False

# ==========================================
# 3. 主流程：同步資產並判定
# ==========================================
def run_monitor():
    print(f"📡 正在從 Google Sheet 抓取資產清單...")
    
    try:
        response = requests.get(GAS_URL, timeout=10)
        data = response.json()
        
        # 這裡假設你的 GAS 已經修正為回傳「加總後」的數字
        # 或是我們可以從你上傳的 CSV 邏輯來處理
        portfolio_raw = float(data.get('portfolio_value', 0))
        
        # 💡 自動匯率判定邏輯：
        # 根據你的 CSV，TWD 市值（如 006208）約 36萬，USD 市值（如 CSPX）約 1萬。
        # 如果總和超過 1000 萬，我們判定它是 TWD，自動轉 USD。
        if portfolio_raw > 10000000:
            total_usd = portfolio_raw / USD_TWD_RATE
            currency_tag = "TWD (已換算 USD)"
        else:
            total_usd = portfolio_raw
            currency_tag = "USD"

        print(f"💰 總資產計算結果: ${total_usd:,.2f} USD")

        # 判定是否觸發警報
        if total_usd >= ALERT_THRESHOLD_USD:
            # 建立訊息格式 (使用 Markdown 感的排版)
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            alert_msg = (
                f"\n🛡️ 【資產防護警報】\n"
                f"━━━━━━━━━━━━━━━\n"
                f"⏰ 時間：{now}\n"
                f"💵 總值：${total_usd:,.2f} USD\n"
                f"🏷️ 來源：{currency_tag}\n"
                f"📈 狀態：資產已達對沖閾值！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🎯 建議執行：Zero-Cost Collar\n"
                f"👉 賣出 Call @23600 (收權利金)\n"
                f"👉 買入 Put  @22800 (鎖定風險)\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💡 請登入富邦 Neo SDK 確認下單。"
            )
            
            if send_email_alert(alert_msg):
                print("✅ Email 警報已發送！")
        else:
            print(f"✅ 資產尚未達標 (${total_usd:,.0f} < {ALERT_THRESHOLD_USD:,.0f})，保持監控。")

    except Exception as e:
        print(f"❌ 監控執行失敗: {e}")

if __name__ == "__main__":
    run_monitor()

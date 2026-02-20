import os
import requests
import json
from datetime import datetime

# ==========================================
# 1. 核心設定
# ==========================================
# 從環境變數讀取敏感資訊 (用於 GitHub Actions)
# 若本地執行且未設定環境變數，則使用預設值
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "24f4aeddb3cd2f2b6531f3df858049b9") 
GAS_URL = os.environ.get("GAS_URL", "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec")

USD_TWD_RATE = 32.5  # 基準匯率
ALERT_THRESHOLD_USD = 1500000 # 150萬美金觸發保護
import socket

# 強制將 notify-api.line.me 解析為 IPv4 地址
def force_ipv4():
    old_getaddrinfo = socket.getaddrinfo
    def new_getaddrinfo(*args, **kwargs):
        res = old_getaddrinfo(*args, **kwargs)
        return [r for r in res if r[0] == socket.AF_INET]
    socket.getaddrinfo = new_getaddrinfo

force_ipv4()

# ==========================================
# 2. 功能：發送 Line 通知
# ==========================================
def send_line_alert(msg):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    payload = {"message": msg}
    try:
        # 增加 timeout 設定為 5 秒
        res = requests.post(url, headers=headers, data=payload, timeout=5)
        return res.status_code == 200
    except requests.exceptions.ConnectionError:
        print("❌ 網路連線錯誤，請檢查 DNS 或是否開啟了 VPN。")
        return False
    except Exception as e:
        print(f"Line 發送異常: {e}")
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
            
            if send_line_alert(alert_msg):
                print("✅ Line 警報已發送至手機！")
        else:
            print(f"✅ 資產尚未達標 (${total_usd:,.0f} < {ALERT_THRESHOLD_USD:,.0f})，保持監控。")

    except Exception as e:
        print(f"❌ 監控執行失敗: {e}")

if __name__ == "__main__":
    run_monitor()
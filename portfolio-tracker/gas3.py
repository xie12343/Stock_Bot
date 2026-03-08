import os
import requests
import json
import sys
from datetime import datetime
import smtplib
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 0. 輔助功能：載入本地 .env 檔案 (無需額外套件)
# ==========================================
def load_env(file_path=".env"):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
                    except ValueError:
                        continue

# 優先載入本地環境設定
load_env()

# 1. 核心設定 (支援 環境變數、.env 或 命令行參數)
# 參數範例: python gas3.py --gas_url YOUR_URL --mock
args = sys.argv[1:]
STOCK_BOT_EMAIL = os.environ.get("STOCK_BOT_EMAIL")
STOCK_BOT_PWD = os.environ.get("STOCK_BOT_PWD")
GAS_URL = os.environ.get("GAS_URL")

# 命令行參數覆蓋
if "--gas_url" in args:
    GAS_URL = args[args.index("--gas_url") + 1]

IS_MOCK = "--mock" in args

# --- 偵錯用：檢查變數是否存在 ---
if not GAS_URL and not IS_MOCK:
    print("❌ 錯誤：找不到 GAS_URL 環境變數，且未啟用 --mock 模式。")
    print("💡 提示：請在 .env 檔案中設定 GAS_URL，或使用命令: python gas3.py --mock")
else:
    if GAS_URL:
        print(f"✅ 已讀取 GAS_URL: {GAS_URL[:15]}...") # 只印出前 15 個字確保安全
    if IS_MOCK:
        print("🛠️ 啟用 MOCK 模式：將使用模擬測試數據。")

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
    recipient = STOCK_BOT_EMAIL
    sender = STOCK_BOT_EMAIL
    password = STOCK_BOT_PWD
    
    if not password:
        print("❌ 錯誤：STOCK_BOT_PWD 未設定")
        return False

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
        if IS_MOCK:
            print("📡 [MOCK] 正在使用模擬數據...")
            data = {
                "status": "success",
                "portfolio_value": 50000000, # 模擬台幣 5000 萬
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            if not GAS_URL:
                print("❌ 錯誤：GAS_URL 未設定，無法執行。")
                return

            print(f"📡 正在請求 GAS URL...")
            response = requests.get(GAS_URL, timeout=15)
            
            # 檢查 HTTP 狀態碼
            if response.status_code != 200:
                print(f"❌ API 請求失敗，狀態碼：{response.status_code}")
                return

            # 檢查是否抓到空的內容
            if not response.text.strip():
                print("❌ 錯誤：GAS 回傳內容為空，請檢查 GAS 程式碼是否已 return JSON 並重新部署為『新版本』")
                return

            # 嘗試解析 JSON
            try:
                data = response.json()
            except Exception:
                print(f"❌ 無à解析 JSON。收到的內容為: {response.text}")
                return

        # 1. 資產檢查
        portfolio_raw = float(data.get('portfolio_value', 0))
        total_usd = portfolio_raw / USD_TWD_RATE if portfolio_raw > 10000000 else portfolio_raw
        
        # 2. 市場智能分析
        taiex, trend, vix = get_market_intelligence()
        
        if total_usd >= ALERT_THRESHOLD_USD and taiex:
            # --- 數據準備與精算 ---
            portfolio_twd = total_usd * USD_TWD_RATE
            
            # 履約價計算 (取整數至百位)
            p_put = int((taiex * 0.95) // 100 * 100)      # 價外 5% Put (保險)
            col_p = int((taiex * 0.97) // 100 * 100)      # Collar 支撐 (價外 3%)
            col_c = int((taiex * 1.03) // 100 * 100)      # Collar 壓力 (價外 3%)
            
            # 口數計算 (精確計算名目本金對沖)
            # 選擇權與小台乘數為 50 元/點；大台為 200 元/點
            contract_value_50 = taiex * 50
            opt_qty = round(portfolio_twd / contract_value_50) # 選擇權與小台建議口數
            tx_qty = round(portfolio_twd / (taiex * 200), 1)   # 大台建議口數

            # --- VIX + 趨勢 綜合判斷邏輯 ---
            if vix > 30:
                market_view = "市場極度恐慌 (VIX 飆升)，選擇權保費極貴。"
                primary_rec = "方案 C (期貨對沖)"
            elif vix > 22 or trend < -0.02:
                market_view = "市場波動加劇且趨勢向下，下行風險高。"
                primary_rec = "方案 A (保護性賣權)"
            else:
                market_view = "市場處於中性震盪或緩跌。"
                primary_rec = "方案 B (衣領策略)"

            # --- 郵件內容構建 ---
            msg = (
                f"【資產防護決策報告】\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 資產總額：${total_usd:,.2f} USD (約 {portfolio_twd:,.0f} TWD)\n"
                f"📊 市場狀態：\n"
                f"   - 台指點位：{taiex:,.2f} ({'↑' if trend>0 else '↓'} {trend:.2%})\n"
                f"   - VIX 指數：{vix} ({market_view})\n"
                f"🎯 系統判定首選：{primary_rec}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"【執行方案評估與建議口數】\n\n"
                
                f"🔴 方案 A：保護性賣權 (Protective Put)\n"
                f"   - 操作：買入 {p_put} Put\n"
                f"   - 口數：{opt_qty} 口\n"
                f"   - 優點：最大虧損僅限於權利金，無保證金追繳風險；資產上漲獲利空間不受限。\n"
                f"   - 缺點：保費為沉沒成本，若指數未跌破 {p_put}，權利金將隨時間歸零 (Theta 耗損)。\n\n"

                f"🟡 方案 B：零成本衣領 (Zero-Cost Collar)\n"
                f"   - 操作：買入 {col_p} Put + 賣出 {col_c} Call\n"
                f"   - 口數：各 {opt_qty} 組\n"
                f"   - 優點：利用賣 Call 的收入補貼買 Put 的支出，達成接近「零成本」的防護。\n"
                f"   - 缺點：資產若大漲超過 {col_c}，超額利潤將被鎖死；賣 Call 需占用一定保證金。\n\n"

                f"🔵 方案 C：期貨完全對沖 (Short Hedge)\n"
                f"   - 操作：賣出 小台指 (MTX)\n"
                f"   - 口數：{opt_qty} 口 (或大台 {tx_qty} 口)\n"
                f"   - 優點：Delta 絕對值為 1，防護效果最直接，沒有時間價值流失的問題。\n"
                f"   - 缺點：若市場反轉向上，期貨空單將產生實質虧損，且需準備充足的維持保證金以防斷頭。\n\n"
                
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"請登入富邦 Neo SDK 或 e點通確認即時報價後執行。"
            )
            
            if STOCK_BOT_EMAIL and STOCK_BOT_PWD:
                if send_email_alert(msg, strategy_name=primary_rec):
                    print(f"✅ 決策郵件已發送。當前 VIX: {vix}，建議防護口數: {opt_qty}")
            else:
                print("⚠️ [跳過郵件] 由於未設定 STOCK_BOT_EMAIL 或 STOCK_BOT_PWD，郵件發送已跳過。")
                print("💬 建議決策內容：")
                print(msg)
                print(f"✅ 監控完成。當前 VIX: {vix}，建議防護口數: {opt_qty}")
        else:
            print(f"✅ 監控中... 資產 ${total_usd:,.0f} / VIX: {vix}")

    except Exception as e:
        print(f"❌ 執行異常: {e}")

if __name__ == "__main__":
    run_monitor()
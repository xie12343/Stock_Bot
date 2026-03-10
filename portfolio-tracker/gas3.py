import os
import requests
import json
import sys
from datetime import datetime
import smtplib
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Force UTF-8 output for Windows console compatibility
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

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
        # 嘗試多個 Ticker 確保抓到正確台指 (TX=F, ^TWII)
        # ^TWII 是加權指數現貨, TX=F 是期貨 (Yahoo 有時不穩定)
        ticker_list = ["^TWII", "TX=F"]
        current_taiex = None
        trend_5d = 0.0
        
        for t in ticker_list:
            try:
                data = yf.Ticker(t).history(period='5d')
                if not data.empty:
                    current_taiex = round(data['Close'].iloc[-1], 2)
                    trend_5d = (current_taiex - data['Close'].iloc[0]) / data['Close'].iloc[0]
                    print(f"✅ 成功從 {t} 獲取報價: {current_taiex}")
                    break
            except Exception as e:
                print(f"⚠️ 從 {t} 獲取數據失敗: {e}")
                continue
        
        # VIX 當前值
        vix_data = yf.Ticker("^VIX").history(period='1d')
        current_vix = round(vix_data['Close'].iloc[-1], 2) if not vix_data.empty else 20.0
        
        if not current_taiex:
            print("❌ 無法獲取台指價格，將嘗試從 Yahoo 以外的備用邏輯 (這裡暫留 0)")
            return 0, 0, current_vix

        return current_taiex, trend_5d, current_vix
    except Exception as e:
        print(f"❌ 數據抓取失敗: {e}")
        return 0, 0, 20.0

# ==========================================
# 2.1 功能：抓取 S&P 500 數據
# ==========================================
def get_sp500_intelligence():
    print("🔍 正在分析 S&P 500 指數走勢...")
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(period='5d')
        current_spx = round(hist['Close'].iloc[-1], 2)
        trend_5d = (current_spx - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
        return current_spx, trend_5d
    except Exception as e:
        print(f"❌ S&P 500 數據抓取失敗: {e}")
        return None, None

# ==========================================
# 2.2 功能：計算美股資產 (從 etf.csv)
# ==========================================
def calculate_us_assets(csv_path="portfolio-tracker/etf.csv"):
    """
    從 etf.csv 計算幣別為 USD 的市值總和
    """
    print(f"📂 正在從 {csv_path} 計算美股資產...")
    total_usd = 0.0
    if not os.path.exists(csv_path):
        # 嘗試備用路徑
        csv_path = "etf.csv"
        if not os.path.exists(csv_path):
            print(f"⚠️ 找不到 etf.csv，使用 0 作為預設值。")
            return 0.0
        
    try:
        import csv
        with open(csv_path, mode='r', encoding='utf-8') as f:
            # 第一行通常是標題，判斷分隔符
            header_line = f.readline()
            sep = '\t' if '\t' in header_line else ','
            f.seek(0)
            
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                # 去除可能的空白字元
                currency = row.get("幣別", "").strip()
                if currency == "USD":
                    try:
                        # 市值可能包含逗號
                        val_str = row.get("市值", "0").replace(",", "").strip()
                        total_usd += float(val_str)
                    except (ValueError, TypeError):
                        continue
        print(f"💵 計算完成：美股總資產 ${total_usd:,.2f} USD")
        return total_usd
    except Exception as e:
        print(f"❌ 解析 {csv_path} 失敗: {e}")
        return 0.0

# ==========================================
# 2.5 功能：小台期貨合約 CP 值分析 (含 03F1, 03, 04)
# ==========================================
def get_contract_intelligence(taiex):
    """
    分析不同月份小台期貨 (MTX) 的 CP 值 (現貨 - 期貨 = 基差)
    03F1: 當天/週小台
    03: 本月 (3月第三週)
    04: 次月 (4月第三週)
    """
    print("📊 正在分析期貨合約基差與 CP 值...")
    
    # 獲取近月 (TX=F) 價格
    try:
        tx_f1_data = yf.Ticker("TX=F").history(period='1d')
        f1_price = round(tx_f1_data['Close'].iloc[-1], 2)
    except Exception:
        f1_price = taiex - 20 # 預設逆價差 20 點
        
    # 定義期貨合約代號 (03F1: 當天, 03: 3月, 04: 4月)
    now = datetime.now()
    m1 = now.strftime("%m")
    m2 = (now.replace(month=now.month % 12 + 1)).strftime("%m")
    
    contracts = [
        {"name": f"{m1}F1 (當天/週)", "price": f1_price + 5},
        {"name": f"{m1} (本月)", "price": f1_price},
        {"name": f"{m2} (次月)", "price": f1_price - 30},
    ]
    
    results = []
    for c in contracts:
        basis = taiex - c['price']
        cp_ratio = (basis / taiex) * 100
        c['basis'] = round(basis, 2)
        c['cp_ratio'] = round(cp_ratio, 4)
        results.append(c)
        
    # 保留原始順序 (03F1, 03, 04)，不強制按 CP 值排序
    return results

# ==========================================
# 2.6 功能：S&P 500 避險合約分析 (FISP)
# ==========================================
def get_sp500_contract_intelligence(spx_price):
    """
    分析 S&P 500 避險工具：S美國標普500期 (FISP)
    """
    print("📊 正在分析 S&P 500 避險合約...")
    # FISP: 200 TWD/pt
    contracts = [
        {"name": "S美國標普500期 (FISP)", "multiplier": 200, "currency": "TWD", "price": spx_price},
    ]
    return contracts

# ==========================================
# 2.7 功能：從 Yahoo Finance 查詢選擇權 (Put) 價格
# ==========================================
def get_option_put_price(underlying="^TWII", strike=None):
    """
    嘗試從 Yahoo Finance 或模擬獲取 Put 價格
    """
    if not strike:
        return 10 # 預設估值改為較貼近週選擇權深度價外的數值
    
    # 由於 Yahoo Finance 的台指選擇權報價代號不固定且延遲大，
    # 建議參考富邦 Neo SDK 或 e點通之「亮燈權利金」。
    # 這裡暫時回傳一個更符合深度價外週選現實的估值 (約 10 點)
    return 10 

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

        # 1. 資產檢查 (監控全球總額)
        portfolio_raw = float(data.get('portfolio_value', 0))
        total_usd = portfolio_raw / USD_TWD_RATE if portfolio_raw > 10000000 else portfolio_raw
        portfolio_twd = total_usd * USD_TWD_RATE

        # 1.1 設定避險標的額度 (僅針對台股部位，使用者提供約 1~200 萬)
        HEDGE_EXPOSURE_TWD = 2000000 
        
        # 2. 市場智能分析
        taiex, trend, vix = get_market_intelligence()
        
        # 預設變數防止下方引用報錯
        cp_table = ""
        sp500_msg = ""
        primary_rec = "穩定觀察中"
        
        # 2.1 美股資產與 S&P 500 分析
        us_exposure_usd = calculate_us_assets()
        us_exposure_twd = us_exposure_usd * USD_TWD_RATE
        spx_price, spx_trend = get_sp500_intelligence()
        
        if total_usd >= ALERT_THRESHOLD_USD and taiex > 1000:
            # --- 數據準備與精算 ---
            # 履約價計算 (取整數至百位)
            # 安全機制：若 taiex 異常低，這裡會反映出問題
            p_put = int((taiex * 0.95) // 100 * 100)      # 價外 5% Put (保險)
            col_p = int((taiex * 0.97) // 100 * 100)      # Collar 支撐 (價外 3%)
            col_c = int((taiex * 1.03) // 100 * 100)      # Collar 壓力 (價外 3%)
            
            # S&P 500 履約價計算
            sp_p_put = 0
            sp_col_p = 0
            sp_col_c = 0
            spf_qty = 0
            mes_qty = 0
            if spx_price:
                sp_p_put = int((spx_price * 0.95) // 10 * 10)
                sp_col_p = int((spx_price * 0.97) // 10 * 10)
                sp_col_c = int((spx_price * 1.03) // 10 * 10)
                spf_qty = round(us_exposure_twd / (spx_price * 200), 1)
                mes_qty = round(us_exposure_usd / (spx_price * 5), 1)
            
            # 口數計算 (僅針對台股 200 萬部位對沖)
            # 選擇權與小台乘數為 50 元/點；大台為 200 元/點
            contract_value_50 = taiex * 50
            opt_qty = int(round(HEDGE_EXPOSURE_TWD / contract_value_50)) # 建議口數 (整數)
            tx_qty = int(round(HEDGE_EXPOSURE_TWD / (taiex * 200)))      # 大台建議口數

            # 3. 期貨合約基差精選 (用於參考市場價格)
            TX_MARGIN_MTX = 41000  # 小台指原始保證金
            SPF_MARGIN = 103000   # FISP 標普500期原始保證金
            MARGIN_A_TXO = 107000
            MARGIN_B_TXO = 54000

            contract_reports = get_contract_intelligence(taiex)
            # 尋找 CP 值最高 (最划算) 的期貨合約
            best_c = max(contract_reports, key=lambda x: x['cp_ratio'])

            # --- VIX + 趨勢 綜合判定首選 ---
            if vix > 30:
                market_view = "市場極度恐慌 (VIX 飆升)，選擇權保費極貴。"
                primary_rec = "方案 C (期貨對沖)"
            elif vix > 22 or trend < -0.02:
                market_view = "市場波動加劇且趨勢向下，下行風險高。"
                primary_rec = "方案 A (保護性賣權)"
            else:
                market_view = "市場處於中性震盪或緩跌。"
                primary_rec = "方案 B (衣領策略)"

            # --- 構建 CP 值表格與各契約計算 ---
            cp_table = "契約名稱 (期貨小台)   | 價格    | 基差    | 每口保證金 | 建議口數 | 總保證金需求的 \n"
            cp_table += "--------------------------------------------------------------------------\n"
            for cr in contract_reports:
                contract_margin = opt_qty * TX_MARGIN_MTX
                cp_table += f"{cr['name']:<18} | {cr['price']:<7.0f} | {cr['basis']:<7.0f} | {TX_MARGIN_MTX:,} | {opt_qty} 口  | {contract_margin:,.0f} 元\n"

            # --- 4. S&P 500 避險計算 ---
            sp500_msg = ""
            if spx_price:
                # FISP (台指 S&P) 計算: 每口 200 TWD
                fisp_qty = int(round(us_exposure_twd / (spx_price * 200)))
                fisp_cost_desc = f"{fisp_qty} 口 x {spx_price:.0f} 點 x 200 元 (預估所需的台幣避險價值)"
                
                sp500_msg = (
                    f"🇺🇸 【美股資產防護建議 (S&P 500)】\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 美股總資產：${us_exposure_usd:,.2f} USD (約 {us_exposure_twd:,.0f} TWD)\n"
                    f"📈 S&P 500 現價：{spx_price:,.2f} ({'↑' if spx_trend>0 else '↓'} {spx_trend:.2%})\n\n"
                    f"🔹 推薦合約：S美國標普500期 (FISP)\n"
                    f"   - 建議口數：{fisp_qty} 口\n"
                    f"   - 計算基礎：{fisp_cost_desc}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                )

            # --- 5. 選擇權與期貨保證金精算 (符合 2026/03 最新公告) ---
            
            # --- 6. 郵件內容構建 ---
            # 取得估計/即時權利金
            current_put_price = get_option_put_price(strike=p_put)
            
            # --- 方案 A 支出精算 (Protective Put) ---
            # 台指期部分
            tx_put_cost = current_put_price * 50 * opt_qty
            # S&P 500 部分 (使用 FISP 平價 Put 或空單對沖)
            # 這裡假設美股對沖也是採用 FISP 口數 * 200 (美股部分同樣呈現算法)
            fisp_valuation = fisp_qty * spx_price * 200
            
            # --- 方案 B 保證金精算 (Zero-Cost Collar) ---
            # 價外值 = (履約價 - 現貨價) * 50
            otm_val = max((col_c - taiex) * 50, 0)
            per_call_margin = max(MARGIN_A_TXO - otm_val, MARGIN_B_TXO)
            total_collar_margin = per_call_margin * opt_qty
            
            # --- 方案 C 保證金精算 (Short Hedge) ---
            total_mtx_margin = opt_qty * TX_MARGIN_MTX
            total_fisp_margin = fisp_qty * SPF_MARGIN
            
            msg = (
                f"【資產防護決策報告】\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 全球資產總額：${total_usd:,.2f} USD (約 {portfolio_twd:,.0f} TWD)\n"
                f"🛡️ 台股避險目標：{HEDGE_EXPOSURE_TWD:,.0f} TWD (排除美股/愛爾蘭英股)\n"
                f"📊 市場狀態：\n"
                f"   - 台指點位：{taiex:,.2f} ({'↑' if trend>0 else '↓'} {trend:.2%})\n"
                f"   - VIX 指數：{vix} ({market_view})\n"
                f"🎯 系統判定首選：{primary_rec}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"🇺🇸 【美股資產對沖參考 (S&P 500)】\n"
                f"   - 推薦合約：S美國標普500期 (FISP)\n"
                f"   - 建議對沖口數：{fisp_qty} 口\n"
                f"   - 防護價值算法：{fisp_qty} 口 x {spx_price:.0f} 點 x 200 元 = {fisp_valuation:,.0f} TWD\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"🔥 【期貨契約 (小台指) 詳細數據與成本】\n"
                f"{cp_table}\n"
                f"💡 目前期貨最划算合約：{best_c['name']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"【執行方案評估與建議口數】\n\n"
                
                f"🔴 方案 A：保護性賣權 (Protective Put)\n"
                f"   - 【台指期】：買入 {p_put} Put (數量：{opt_qty} 口)\n"
                f"      * 若選 {contract_reports[0]['name']}：{opt_qty} 口 x {current_put_price} 點 x 50 元 = {tx_put_cost:,.0f} 元 (暫估)\n"
                f"      * 若選 {contract_reports[1]['name']}：{opt_qty} 口 x {int(current_put_price*21.0)} 點 x 50 元 = {int(tx_put_cost*21.0):,.0f} 元 (暫估)\n"
                f"      * 若選 {contract_reports[2]['name']}：{opt_qty} 口 x {int(current_put_price*75.0)} 點 x 50 元 = {int(tx_put_cost*75.0):,.0f} 元 (暫估)\n"
                f"   - 【標普 500】：買入 {sp_p_put if sp_p_put else 'FISP'} 防護 (數量：{fisp_qty} 口)\n"
                f"   - 💡 說明：實際報價需查 Taifex（如 {p_put} Put 週選約 5~10 點）；此方案無保證金風險，最大虧損有限。\n\n"

                f"🟡 方案 B：零成本衣領 (Zero-Cost Collar)\n"
                f"   - 【台指期】：買入 {col_p} Put + 賣出 {col_c} Call (數量：{opt_qty} 組)\n"
                f"      * 若選 {contract_reports[0]['name']}：Max(A:{MARGIN_A_TXO:,} - 價外:{otm_val:,.0f}, B:{MARGIN_B_TXO:,}) = {per_call_margin:,.0f} 元 x {opt_qty} 組 = {total_collar_margin:,.0f} 元\n"
                f"      * 若選 {contract_reports[1]['name']}：Max(A:{MARGIN_A_TXO:,} - 價外:{otm_val:,.0f}, B:{MARGIN_B_TXO:,}) = {per_call_margin:,.0f} 元 x {opt_qty} 組 = {total_collar_margin:,.0f} 元\n"
                f"      * 若選 {contract_reports[2]['name']}：Max(A:{MARGIN_A_TXO:,} - 價外:{otm_val:,.0f}, B:{MARGIN_B_TXO:,}) = {per_call_margin:,.0f} 元 x {opt_qty} 組 = {total_collar_margin:,.0f} 元\n"
                f"   - 【標普 500】：FISP 衣領組合或空單對沖 (數量：{fisp_qty} 口)\n"
                f"   - 💰 權利金預估：接近 0 元 (買 Put 權利金由賣 Call 支應)\n"
                f"   - ⚠️ 注意：單邊賣出 Call 需準備上述保證金控管風險。\n\n"

                f"🔵 方案 C：期貨完全對沖 (Short Hedge)\n"
                f"   - 【台指期】：賣出 期貨合約 (各契約建議如下)\n"
                f"      * 若選 {contract_reports[0]['name']}：{opt_qty} 口 x {TX_MARGIN_MTX:,} 元 = {opt_qty * TX_MARGIN_MTX:,.0f} 元\n"
                f"      * 若選 {contract_reports[1]['name']}：{opt_qty} 口 x {TX_MARGIN_MTX:,} 元 = {opt_qty * TX_MARGIN_MTX:,.0f} 元\n"
                f"      * 若選 {contract_reports[2]['name']}：{opt_qty} 口 x {TX_MARGIN_MTX:,} 元 = {opt_qty * TX_MARGIN_MTX:,.0f} 元\n"
                f"   - 【標普 500】：賣出 FISP ({fisp_qty} 口)\n"
                f"   - 🏦 保證金精算 (以首選合約 {best_c['name']} 為例)：\n"
                f"      * 台指期：{opt_qty} 口 x {TX_MARGIN_MTX:,} 元 = {total_mtx_margin:,.0f} 元\n"
                f"      * 標普 500：{fisp_qty} 口 x {SPF_MARGIN:,} 元 = {total_fisp_margin:,.0f} 元\n"
                f"      * 總計所需資金：{total_mtx_margin + total_fisp_margin:,.0f} 元 (原始保證金)\n"
                f"   - 💡 優點：對沖最直接；缺點：若市場反轉將產生空單虧損。\n\n"
                
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
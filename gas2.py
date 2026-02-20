import pandas as pd
import numpy as np
import requests
import json
from fubon_neo.sdk import FubonSDK
from datetime import datetime

# ==========================================
# 1. 設定區 (請根據你的環境修改)
# ==========================================
GAS_URL = "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec"

TARGET_EXPIRY = "202603"  # 領口策略目標月份
UNDERLYING_PRICE = 23000  # 模擬台指期現價 (實務建議從 SDK 抓)

# 初始化 Fubon SDK (建議在外部完成登入)
sdk = FubonSDK()

# ==========================================
# 2. 功能模組：抓取 Google Sheet 總資產
# ==========================================
def get_portfolio_value_from_gas():
    print(f"📡 正在從 Google Sheet 同步資產數據...")
    try:
        response = requests.get(GAS_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                val = data.get('portfolio_value')
                # 這裡處理之前抓到文字的問題，確保轉為數字
                try:
                    return float(val)
                except:
                    print(f"⚠️ 抓取到的數值格式異常: {val}")
                    return None
    except Exception as e:
        print(f"❌ GAS 連線失敗: {e}")
    return None

# ==========================================
# 3. 功能模組：尋找零成本領口組合 (Collar)
# ==========================================
def find_zero_cost_collar(expiry):
    print(f"🔍 正在為 {expiry} 合約尋找零成本對沖組合...")
    
    # 取得合約清單 (處理 SDK 屬性遺失或需要登入的問題)
    try:
        contracts_res = sdk.futopt.get_contracts()
        df_all = pd.DataFrame(contracts_res.data)
    except Exception as e:
        print(f"⚠️ 無法取得即時合約 (SDK 限制或未登入)，使用模擬數據展示策略...")
        # 建立模擬合約數據
        strikes = range(20000, 26000, 200)
        mock_data = []
        for s in strikes:
            mock_data.append({'symbol': 'TXO', 'expiry_date': expiry, 'call_put': 'C', 'strike_price': s, 'code': f"TXO{s}C6"})
            mock_data.append({'symbol': 'TXO', 'expiry_date': expiry, 'call_put': 'P', 'strike_price': s, 'code': f"TXO{s}P6"})
        df_all = pd.DataFrame(mock_data)
    
    # 篩選 OTM 合約 (Call 選 > 現價, Put 選 < 現價)
    calls = df_all[(df_all['symbol'] == 'TXO') & (df_all['expiry_date'] == expiry) & 
                   (df_all['call_put'] == 'C') & (df_all['strike_price'] > UNDERLYING_PRICE)]
    
    puts = df_all[(df_all['symbol'] == 'TXO') & (df_all['expiry_date'] == expiry) & 
                  (df_all['call_put'] == 'P') & (df_all['strike_price'] < UNDERLYING_PRICE)]
    
    # 模擬抓取報價 (實際環境請更換為 sdk.marketdata.get_full_quotes)
    target_codes = list(calls['code'].head(5)) + list(puts['code'].tail(5))
    price_map = {code: np.random.randint(50, 150) for code in target_codes} 

    best_pair = None
    min_diff = float('inf')

    # 雙層迴圈尋找權利金最接近的組合 (收入 Call ≈ 支出 Put)
    for _, c_row in calls.head(5).iterrows():
        for _, p_row in puts.tail(5).iterrows():
            c_price = price_map.get(c_row['code'], 0)
            p_price = price_map.get(p_row['code'], 0)
            
            diff = abs(c_price - p_price)
            if diff < min_diff:
                min_diff = diff
                best_pair = {
                    'Call': {'code': c_row['code'], 'strike': c_row['strike_price'], 'price': c_price},
                    'Put': {'code': p_row['code'], 'strike': p_row['strike_price'], 'price': p_price},
                    'Net_Points': p_price - c_price
                }
    return best_pair

# ==========================================
# 4. 主流程整合
# ==========================================
def main():
    print("-" * 30)
    print(f"🚀 系統啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: 檢查雲端總資產
    sheet_value = get_portfolio_value_from_gas()
    if sheet_value:
        print(f"💰 目前雲端總資產：${sheet_value:,.2f} USD")
    else:
        print("❌ 無法取得有效的資產數據，請檢查 Google Sheet B1 儲存格內容。")

    # Step 2: 執行對沖策略分析
    collar = find_zero_cost_collar(TARGET_EXPIRY)
    
    if collar:
        print("\n🎯 [自動建議] 最佳零成本對沖組合：")
        print(f"  - 賣出 (Sell) Call: {collar['Call']['strike']} @ {collar['Call']['price']} 點")
        print(f"  - 買入 (Buy)  Put : {collar['Put']['strike']} @ {collar['Put']['price']} 點")
        
        net_cost_twd = collar['Net_Points'] * 50
        print(f"  - 預估淨成本: {net_cost_twd:,.0f} TWD (不含手續費)")
        
        # 這裡可以加入邏輯：如果資產 > 某個閾值，則執行下單
        if sheet_value and sheet_value > 1500000:
            print("\n🚨 警示：資產已達標，建議啟動保護策略！")
    
    print("-" * 30)

if __name__ == "__main__":
    main()
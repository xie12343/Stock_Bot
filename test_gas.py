import requests
import json

# 請將下方網址替換為你重新部署後取得的 /exec 網址
GAS_URL = "https://script.google.com/macros/s/AKfycbxLks0Ad8OidLHTfaRtztMCm9yH8_kQjNjIRYwD1XWwgjjnNq_kMKP0fWokErMhNZ0wqA/exec"

def fetch_portfolio_value():
    print(f"📡 正在嘗試連線至 Google Sheet...")
    try:
        # GAS 的 Web App 在請求時會發生重定向，requests 預設會處理 (allow_redirects=True)
        response = requests.get(GAS_URL, timeout=15)
        
        # 檢查伺服器回應狀態
        if response.status_code == 200:
            # 檢查內容是否為 JSON
            try:
                data = response.json()
                
                if data.get("status") == "success":
                    print(f"✅ 抓取成功！")
                    print(f"💰 目前總市值：{data.get('portfolio_value')}")
                    print(f"📅 更新時間：{data.get('last_update')}")
                    return data.get('portfolio_value')
                else:
                    print(f"❌ GAS 邏輯錯誤：{data.get('message')}")
            except json.JSONDecodeError:
                print("❌ 解析失敗：收到的內容不是 JSON 格式。")
                print("💡 這通常是因為網址權限未設為『所有人』，導致程式抓到登入頁面的 HTML。")
                print(f"原始回傳前 100 字：{response.text[:100]}")
        else:
            print(f"❌ 連線失敗，HTTP 狀態碼：{response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"🚀 網路連線發生異常：{e}")

if __name__ == "__main__":
    fetch_portfolio_value()

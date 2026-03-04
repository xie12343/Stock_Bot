import json
import pandas as pd
import numpy as np
from fubon_neo.sdk import FubonSDK, Order
from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

# ==========================================
# 1. 策略參數與配置
# ==========================================
# 追蹤標的清單 (台股部分)
TARGET_LIST = ["2330", "0050", "006208", "0052", "00662", "00646", "00985A"]

# 估值數據 (PEG) - 實務上建議透過 API 或資料庫每日更新
FUNDAMENTAL_DATA = {
    "2330": {"peg": 0.85},
    "0052": {"peg": 0.92}, # 已考慮 1 拆 7 後的成長性
    "0050": {"peg": 1.25},
    "00662": {"peg": 1.10},
}

class QuantTradingBot:
    def __init__(self, acc, pwd, pfx, pfx_pwd):
        import os
        if not os.path.exists(pfx):
            raise FileNotFoundError(f"憑證檔案不存在: {pfx}")
            
        self.sdk = FubonSDK()
        try:
            self.accounts = self.sdk.login(acc, pwd, pfx, pfx_pwd)
            if not self.accounts.is_success:
                 raise Exception(f"登入失敗: {self.accounts.message}")
            self.account = self.accounts.data[0]
            self.sdk.init_realtime()
            self.rest_stock = self.sdk.marketdata.rest_client.stock
            print(f"成功登入帳號: {self.account.account}")
        except Exception as e:
            print(f"SDK 登入過程中發生錯誤: {e}")
            raise

    def get_market_indicators(self, symbol):
        """
        獲取技術指標：MA60, MA200, RSI(14)
        """
        try:
            # 獲取歷史 K 線資料 (模擬獲取最近 250 日以計算年線)
            # 註：此處 timeframe 與 get_candles 用法需依 SDK 最新規範調整
            res = self.rest_stock.historical.candles(symbol=symbol, timeframe='D')
            df = pd.DataFrame(res['data'])
            df['close'] = df['close'].astype(float)
            
            # 計算指標
            ma60 = df['close'].rolling(window=60).mean().iloc[-1]
            ma200 = df['close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else 0
            
            # RSI(14)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            price = df['close'].iloc[-1]
            return price, ma60, ma200, rsi
        except Exception as e:
            print(f"標的 {symbol} 指標獲取失敗: {e}")
            return None

    def get_signal(self, symbol, price, ma60, ma200, rsi):
        """
        量化策略核心邏輯
        """
        peg = FUNDAMENTAL_DATA.get(symbol, {}).get("peg", 1.5) # 若無資料預設中性偏貴
        long_term_base = ma200 if ma200 > 0 else ma60
        bias = (price - long_term_base) / long_term_base
        is_cheap = (peg < 1.0)

        # 訊號判定
        if price < long_term_base and (rsi < 45 or is_cheap):
            return {"action": "BUY_STRONG", "strength": 1.5, "reason": "破年線且估值便宜/超跌"}
        
        if price > ma200 and price < ma60 and rsi < 55:
            return {"action": "BUY_DIP", "strength": 1.2, "reason": "多頭回測季線"}
            
        if bias > 0.20 or (rsi > 75 and peg > 1.5):
            return {"action": "PAUSE_BUY", "strength": 0.0, "reason": "乖離過大/市場過熱"}
            
        return {"action": "DCA_ONLY", "strength": 0.5, "reason": "趨勢穩定，維持定投"}

    def place_quant_order(self, symbol, signal_info):
        """
        根據訊號強度下單
        """
        if signal_info['strength'] <= 0:
            print(f"[{symbol}] 狀態: {signal_info['action']} ({signal_info['reason']}) -> 不執行買入")
            return

        # 基礎下單股數 (例如 100 股為一個 DCA 單位)
        # 若為 0052，因已 1 拆 7，建議將基礎股數乘以 7 以維持相同曝險
        base_unit = 100
        if symbol == "0052":
            base_unit = 700 
            
        target_qty = int(base_unit * signal_info['strength'])

        order = Order(
            buy_sell = BSAction.Buy,
            symbol = symbol,
            price = None,              # 市價/參考價
            quantity = target_qty,
            market_type = MarketType.Common,
            price_type = PriceType.Reference, # 使用參考價下單
            time_in_force = TimeInForce.ROD,
            order_type = OrderType.Stock
        )

        print(f"==> 執行下單: {symbol} | 動作: {signal_info['action']} | 股數: {target_qty} | 原因: {signal_info['reason']}")
        # 實際執行請取消下方註解
        # response = self.sdk.stock.place_order(self.account, order)
        # return response

# ==========================================
# 2. 自動執行流程
# ==========================================
if __name__ == "__main__":
    # 請填入您的富邦證券 API 資訊
    MY_ACC = "T121542706"
    MY_PWD = "Wc774474"
    MY_PFX = r"C:\CAFubon\T121542706\T121542706.pfx"
    MY_PFX_PWD = "Wc774474"

    bot = QuantTradingBot(MY_ACC, MY_PWD, MY_PFX, MY_PFX_PWD)

    for symbol in TARGET_LIST:
        market_data = bot.get_market_indicators(symbol)
        if market_data:
            price, ma60, ma200, rsi = market_data
            signal = bot.get_signal(symbol, price, ma60, ma200, rsi)
            bot.place_quant_order(symbol, signal)
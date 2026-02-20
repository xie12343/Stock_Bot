import pandas as pd
import numpy as np
from datetime import datetime
import webbrowser
import os
import yfinance as yf
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# 1. 擴展配置庫：包含映射 Ticker 用於技術分析 (作為技術參考基準)
# 1. 擴展配置庫：僅保留連結基金 (Feeder Funds) 的追蹤標的作為技術參考
# 主動型基金已移除 ETF 偽代號，避免誤導
TICKER_MAP = {
    "元大標普500": "00646.TW",
    "元大全球航太": "00965.TW",
    "元大台灣卓越50": "0050.TW",
    "00646": "00646.TW",
    "00965": "00965.TW",
    "0050": "0050.TW"
}

# 精準現價修正庫 (優先權最高)
# 若用戶回報價格不對，應在此處更新
FIX_CONFIG = {
    "摩根基金-JPM美國科技": {"price": 62.31, "sharpe": 2.10, "sortino": 2.85},
    "摩根基金-JPM美國企業成長": {"price": 50.22, "sharpe": 1.94, "sortino": 2.52},
    "統一全球新科技": {"price": 79.01, "sharpe": 1.55, "sortino": 1.98},
    "路博邁台灣5G": {"price": 60.27, "sharpe": 1.70, "sortino": 2.20},
    "統一奔騰": {"price": 464.39, "sharpe": 1.82, "sortino": 2.35},
    "安聯台灣智慧": {"price": 264.00, "sharpe": 1.95, "sortino": 2.68},
    "野村優質": {"price": 268.90, "sharpe": 1.80, "sortino": 2.20},
    "富邦台美雙星": {"price": 18.58, "sharpe": 1.20, "sortino": 1.50},
    "貝萊德世界科技": {"price": 111.83, "sharpe": 2.05, "sortino": 2.75},
    "富達全球科技": {"price": 65.75, "sharpe": 1.98, "sortino": 2.60},
    "富蘭克林坦伯頓科技": {"price": 58.84, "sharpe": 1.90, "sortino": 2.50},
    "統一台灣動力": {"price": 124.44, "sharpe": 1.75, "sortino": 2.30},
    "富邦新台商": {"price": 248.85, "sharpe": 1.65, "sortino": 2.10}
}

def get_technical_indicators(ticker_symbol):
    try:
        data = yf.download(ticker_symbol, period="14mo", interval="1d", progress=False)
        if data.empty: return None
        
        close = data['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        current_price = float(close.iloc[-1])
        ma60 = float(close.rolling(window=60).mean().iloc[-1])
        ma200 = float(close.rolling(window=200).mean().iloc[-1])
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float(100 - (100 / (1 + rs)).iloc[-1])
        
        return {"price": current_price, "ma60": ma60, "ma200": ma200, "rsi": rsi}
    except Exception: return None

def calculate_signal(price, ma60, ma200, rsi, peg=None):
    long_term_base = ma200 if ma200 > 0 else ma60
    if long_term_base == 0: return "DCA_ONLY", "✅ 維持長期定投", 0.5
    
    bias = (price - long_term_base) / long_term_base
    is_cheap = (peg is not None and peg < 1.0)
    
    if price < long_term_base and (rsi < 45 or is_cheap):
        return "BUY_STRONG", "🔴 跌破長期均線(便宜)", 1.5
    if price > ma200 and price < ma60 and rsi < 55:
        return "BUY_DIP", "🔵 多頭回測季線", 1.2
    if bias > 0.20 or (rsi > 75 and (peg if peg else 2.0) > 1.5):
        return "PAUSE_BUY", "⚠️ 乖離過大/過熱", 1.0
    return "DCA_ONLY", "✅ 維持長期定投", 0.5

def generate_html(df, output_name="基金_即時監控.html"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table_html = ""
    for _, row in df.iterrows():
        action = str(row.get('訊號', 'DCA_ONLY'))
        reason = str(row.get('說明', '-'))
        sig_class = action.lower()
        roi_str = str(row.get('報酬率', '0.00%'))
        roi_class = "positive" if "+" in roi_str else ("negative" if "-" in roi_str else "")
        f_type = str(row.get('類型', '主動基金'))
        
        # 處理技術指標顯示
        rsi_val = row.get('RSI', 0)
        rsi_display = f"{rsi_val:.1f}" if rsi_val > 0 else "-"
        
        table_html += f"""
        <tr class="sig-row-{sig_class}">
            <td><span class="ticker">{row['代號']}</span><br><small style="color:var(--dim)">{f_type}</small></td>
            <td class="price">${row['現價']:,.2f}</td>
            <td>{rsi_display}</td>
            <td><span class="roi {roi_class}">{roi_str}</span></td>
            <td><span class="signal-badge {sig_class}">{action}</span></td>
            <td class="reason">{reason}</td>
            <td class="time">{row.get('更新時間', '-')}</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>基金投資分析儀表板</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0b0f1a; --card: #161c2e; --accent: #60a5fa; --text: #f8fafc; --dim: #64748b;
                --strong-buy: #f87171; --dip-buy: #38bdf8; --pause: #fbbf24; --dca: #4ade80;
            }}
            body {{ background: var(--bg); color: var(--text); font-family: 'Inter', 'Noto Sans TC', sans-serif; margin: 0; padding: 40px; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: var(--card); border-radius: 20px; padding: 30px; border: 1px solid rgba(255,255,255,0.05); }}
            h1 {{ margin: 0; font-size: 26px; color: var(--accent); }}
            .meta {{ font-size: 13px; color: var(--dim); margin-top: 5px; margin-bottom: 25px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; padding: 12px; font-size: 13px; color: var(--dim); border-bottom: 1px solid rgba(255,255,255,0.1); }}
            td {{ padding: 16px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            .ticker {{ font-weight: 700; }}
            .price {{ font-family: 'Monaco', monospace; }}
            .roi.positive {{ color: #4ade80; }} .roi.negative {{ color: #f87171; }}
            .signal-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 800; text-transform: uppercase; }}
            .buy_strong {{ background: rgba(248,113,113,0.15); color: var(--strong-buy); border: 1px solid var(--strong-buy); }}
            .buy_dip {{ background: rgba(56,189,248,0.15); color: var(--dip-buy); border: 1px solid var(--dip-buy); }}
            .pause_buy {{ background: rgba(251,191,36,0.15); color: var(--pause); border: 1px solid var(--pause); }}
            .dca_only {{ background: rgba(74,222,128,0.15); color: var(--dca); border: 1px solid var(--dca); }}
            .reason {{ font-size: 14px; opacity: 0.9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>基金投資策略分析 (V3.0)</h1>
            <div class="meta">更新時間: {now_str} | 優先使用用戶提供之現價 | 修正 ROI 顯示</div>
            <table>
                <thead>
                    <tr><th>基金名稱/類型</th><th>目前現價</th><th>RSI (基準)</th><th>報酬率</th><th>操作訊號</th><th>分析說明</th><th>更新時間</th></tr>
                </thead>
                <tbody>{table_html}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
    with open(output_name, "w", encoding="utf-8") as f: f.write(html_content)
    return os.path.abspath(output_name)

def send_email(file_path, recipient):
    # 這裡可以從環境變數讀取，避免密碼外洩
    sender = os.environ.get("STOCK_BOT_EMAIL", "").strip()
    password = os.environ.get("STOCK_BOT_PWD", "").replace(" ", "").strip()
    
    if not sender or not password:
        status = f"EMAIL: {'已設定' if sender else '未設定'} / PWD: {'已設定' if password else '未設定'}"
        print(f"⚠️ {status}，缺少必要的環境變數，跳過郵件寄送。")
        return

    print(f"📧 嘗試登入發信帳號: {sender} ...")
    print(f"📧 正在寄送日報至: {recipient} ...")
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Stock Bot <{sender}>"
        msg['To'] = recipient
        msg['Subject'] = f"基金日報 - {datetime.now().strftime('%Y-%m-%d')}"

        # 讀取 HTML 作為內文
        with open(file_path, "r", encoding="utf-8") as f:
            html_body = f.read()
        
        msg.attach(MIMEText(html_body, 'html'))

        # 也可以添加附件
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {filename}")
            msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("✅ 郵件寄送成功！")
    except Exception as e:
        print(f"❌ 郵件寄送失敗: {e}")

def fix_fund_data(file_name):
    print("🚀 開始讀取基金資料並進行技術分析...")
    try: df = pd.read_csv(file_name, sep='\t', encoding='utf-8-sig')
    except: df = pd.read_csv(file_name, sep='\t', encoding='cp950')
    
    # 如果讀取後欄位不對（只有一欄），嘗試逗號分隔
    if len(df.columns) <= 1:
        try: df = pd.read_csv(file_name, encoding='utf-8-sig')
        except: df = pd.read_csv(file_name, encoding='cp950')

    # 初始化欄位
    float_cols = ['現價', '市值', '夏普值', '索提諾', 'RSI', 'MA60', 'MA200']
    for col in float_cols:
        if col not in df.columns: df[col] = 0.0
        df[col] = df[col].astype(float)

    cols_to_init = {'訊號': 'DCA_ONLY', '說明': '-', '更新時間': '', '報酬率': '0.00%', '類型': '主動型基金'}
    for col, val in cols_to_init.items():
        if col not in df.columns: df[col] = val
    df['更新時間'] = df['更新時間'].astype(str)

    for idx, row in df.iterrows():
        name = str(row['代號'])
        print(f"正在分析: {name}...")
        
        # 0. 判斷類型
        is_feeder = any(kw in name for kw in ["連結基金", "ETF"])
        df.at[idx, '類型'] = "連結基金/ETF" if is_feeder else "主動型基金"
        
        # 1. 優先匹配 FIX_CONFIG (精準現價)
        fixed_info = None
        for key, info in FIX_CONFIG.items():
            if key in name:
                fixed_info = info
                break
        
        # 2. 尋找技術指標代號 (Ticker Mapping) - 僅連結基金使用
        analysis_ticker = None
        if is_feeder:
            for key, ticker in TICKER_MAP.items():
                if key in name:
                    analysis_ticker = ticker
                    break
        
        tech = get_technical_indicators(analysis_ticker) if analysis_ticker else None
        
        # 3. 整合價格與指標
        # 優先權: FIX_CONFIG > Ticker Market Price > 0
        price = fixed_info['price'] if fixed_info else (tech['price'] if tech else 0.0)
        
        # 如果是主動基金且 CSV 中已有現價（非 0），且 FIX_CONFIG 沒提到，則保留原現價
        if not is_feeder and price == 0 and float(row.get('現價', 0)) > 0:
            price = float(row['現價'])
            
        df.at[idx, '現價'] = price
        
        if fixed_info:
            df.at[idx, '夏普值'] = fixed_info.get('sharpe', 0)
            df.at[idx, '索提諾'] = fixed_info.get('sortino', 0)

        if tech:
            df.at[idx, 'RSI'] = tech['rsi']
            df.at[idx, 'MA60'] = tech['ma60']
            df.at[idx, 'MA200'] = tech['ma200']
            sig, reason, _ = calculate_signal(price, tech['ma60'], tech['ma200'], tech['rsi'])
            df.at[idx, '訊號'] = sig
            df.at[idx, '說明'] = reason
        else:
            df.at[idx, '訊號'] = "DCA_ONLY"
            df.at[idx, '說明'] = "主動基金定期定額" if not is_feeder else "無參考基準數據"

        # 4. 計算市值與報酬率
        try:
            units = float(str(row['單位數']).replace(',', ''))
            cost = float(str(row['成本']).replace(',', ''))
            
            df.at[idx, '市值'] = round(price * units, 2)
            roi = (price - cost) / cost if cost != 0 else 0
            df.at[idx, '報酬率'] = f"{roi:+.2%}"
        except Exception: pass
        
        df.at[idx, '更新時間'] = datetime.now().strftime("%m/%d %H:%M")

    # 儲存與產生報告
    df.to_csv("基金_分析完成.csv", index=False, encoding='utf-8-sig')
    html_path = generate_html(df)
    print(f"\n✅ 分析完畢！ 🌐 HTML 報告已產生: {html_path}")
    
    # 自動寄送郵件
    send_email(html_path, "xie12343@gmail.com")
    
    # 僅在手動執行時開啟瀏覽器
    if "TERM_PROGRAM" in os.environ or "VSCODE_PID" in os.environ:
        webbrowser.open(f"file://{html_path}")

if __name__ == "__main__":
    fix_fund_data('基金.csv')
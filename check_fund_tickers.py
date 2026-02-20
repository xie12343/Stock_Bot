import yfinance as yf

# Potential fund tickers found in search
tickers = [
    "UNIONTECHNOL.TW", # 統一全球新科技 (UPAMC)
    "0P0000V0SF",       # 貝萊德世界科技 (BlackRock) 
    "0P00012JRK",       # 富達全球科技 (Fidelity)
    "0P0000F5H1",       # 安聯台灣智慧 (maybe?) - found in investing.com but let's check Yahoo
    "0P00006AKS",       # 野村優質 (maybe?) - found in investing.com
    "0P00000VPB"        # Another Fidelity variant
]

for t in tickers:
    print(f"Testing {t}...")
    try:
        data = yf.download(t, period="5d", progress=False)
        if not data.empty:
            print(f"  [OK] Last price: {data['Close'].iloc[-1]}")
        else:
            print(f"  [FAILED] Empty data")
    except Exception as e:
        print(f"  [ERROR] {e}")

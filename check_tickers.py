import yfinance as yf

tickers = [
    "UNIONTECHNOL.TW",
    "BWTIX",
    "FTKIX",
    "F000000K6A.HK",
    "F00000VPB5.HK",
    "F00000L7T9.HK",
    "F000000G0C.HK",
    "0050.TW",
    "00646.TW"
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

import yfinance as yf

print("\n=== Market Indices ===")
indices = {'^GSPC': 'S&P 500', '^DJI': 'Dow Jones', '^IXIC': 'NASDAQ', '^RUT': 'Russell 2000'}
for symbol, name in indices.items():
    try:
        t = yf.Ticker(symbol)
        price = t.info.get('regularMarketPrice', t.info.get('currentPrice', 'N/A'))
        print(f"{name}: {price:,.2f}" if isinstance(price, (int, float)) else f"{name}: {price}")
    except Exception as e:
        print(f"{name}: Error - {e}")

print("\n=== Tech Stocks ===")
tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
for symbol in tickers:
    try:
        t = yf.Ticker(symbol)
        price = t.info.get('currentPrice', t.info.get('regularMarketPrice', 'N/A'))
        print(f"{symbol}: ${price:,.2f}" if isinstance(price, (int, float)) else f"{symbol}: {price}")
    except Exception as e:
        print(f"{symbol}: Error - {e}")

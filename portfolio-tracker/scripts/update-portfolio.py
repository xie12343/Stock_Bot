#!/usr/bin/env python3
import re
import sys
import os
import yfinance as yf
from datetime import datetime

# Absolute path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_FILE = os.path.join(BASE_DIR, '../references/portfolio-holdings.md')
OUTPUT_FILE = os.path.join(BASE_DIR, '../portfolio-tracker.md')

def parse_holdings(filepath):
    """Parses the holdings markdown file for stocks and crypto."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into sections (rough parsing based on known headers)
    # Default to empty if headers not found
    stocks_section = ""
    crypto_section = ""
    
    if "## Stocks & ETFs" in content:
        parts = content.split("## Stocks & ETFs")
        if len(parts) > 1:
            # Take everything after Stocks header, stop at next header (Crypto)
            rest = parts[1]
            if "## Crypto" in rest:
                stocks_part, crypto_part = rest.split("## Crypto")
                stocks_section = stocks_part
                crypto_section = crypto_part
            else:
                stocks_section = rest

    # Regex to find Ticker: Shares
    # Matches: "TSLA: 30.18" or "DOGE: 27,088.22"
    # Handles optional 'shares' text and newlines
    pattern = r'([A-Z]+):\s*([\d,.]+)'
    
    stocks = {}
    for match in re.finditer(pattern, stocks_section):
        ticker = match.group(1).upper()
        shares = float(match.group(2).replace(',', ''))
        stocks[ticker] = shares
        
    cryptos = {}
    for match in re.finditer(pattern, crypto_section):
        ticker = match.group(1).upper()
        amount = float(match.group(2).replace(',', ''))
        # Ensure crypto tickers have -USD suffix for yfinance if not present
        if not ticker.endswith('-USD'):
            y_ticker = f"{ticker}-USD"
        else:
            y_ticker = ticker
        cryptos[y_ticker] = amount

    return stocks, cryptos

def fetch_data(tickers):
    """Fetches data for a list of tickers using yfinance."""
    if not tickers:
        return {}
    
    print(f"Fetching data for {len(tickers)} tickers...")
    # Using Ticker object for more reliable info or bulk download
    # Batch download is faster
    string_tickers = " ".join(tickers)
    data = yf.download(string_tickers, period="1d", group_by='ticker', threads=True)
    
    # Process data into a cleaner dictionary
    results = {}
    
    # yfinance structure varies if single vs multiple tickers
    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            # If only one ticker, data columns are direct
            # But yf.download(..., group_by='ticker') might still nest? 
            # Let's use Ticker object for safety on single, or handle the DataFrame carefully
            # Actually, let's use the Ticker approach for consistency if batch is tricky with 1 item
            t = yf.Ticker(ticker)
            hist = t.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                # Previous close is needed for change
                prev_close = t.info.get('previousClose', current_price) # Fallback
                change = current_price - prev_close
                pct_change = (change / prev_close) * 100
                
                results[ticker] = {
                    'price': current_price,
                    'change': change,
                    'pct_change': pct_change,
                    'name': t.info.get('shortName', ticker)
                }
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            
    else:
        # For multiple tickers
        for ticker in tickers:
            try:
                # Extract data for this ticker
                # columns are MultiIndex: (Ticker, PriceType)
                df = data[ticker]
                if not df.empty:
                    current_price = df['Close'].iloc[-1]
                    # We need previous close carefully. 
                    # If we only fetched 1d, we might not have prev close easily in history without 2d?
                    # yf.download often returns 'Adj Close', 'Close', 'Open', 'High', 'Low', 'Volume'
                    # We can estimate Change from Open or try to get prev close.
                    # Better approach for batch: use Tickers object to get info, but that's slow.
                    # Alternative: Open price as proxy for 'start of day'? 
                    # Or fetch 5d history to get yesterday's close.
                    
                    # Let's try fetching 5 days to be safe and getting the previous trading day close
                    pass
            except KeyError:
                print(f"No data for {ticker}")

    # REVISIT: Batch download 'price' access is simpler with .tickers access or just iterating?
    # Let's try a simpler approach: Tickers object for all
    
    final_results = {}
    chunks = [tickers[i:i + 10] for i in range(0, len(tickers), 10)]
    
    for chunk in chunks:
        joined_tickers = " ".join(chunk)
        # Using Tickers wrapper which spawns threads
        t_objs = yf.Tickers(joined_tickers)
        
        for ticker in chunk:
            try:
                info = t_objs.tickers[ticker].info
                # info dict usually has 'currentPrice', 'regularMarketPreviousClose'
                # fallback to 'regularMarketPrice'
                price = info.get('currentPrice') or info.get('regularMarketPrice')
                prev_close = info.get('regularMarketPreviousClose')
                
                if price and prev_close:
                    change = price - prev_close
                    pct_change = (change / prev_close) * 100
                    
                    final_results[ticker] = {
                        'price': price,
                        'change': change,
                        'pct_change': pct_change,
                        'name': info.get('shortName', ticker)
                    }
                else:
                    # Fallback if info is missing (common with some crypto or indices sometimes)
                    hist = t_objs.tickers[ticker].history(period="2d")
                    if len(hist) >= 1:
                        price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else price # Fallback
                        change = price - prev_close
                        pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        final_results[ticker] = {
                            'price': price,
                            'change': change,
                            'pct_change': pct_change,
                            'name': ticker
                        }
            except Exception as e:
                print(f"Failed to fetch info for {ticker}: {e}")
                
    return final_results

def generate_markdown(stocks, cryptos, data):
    """Generates the markdown content."""
    lines = []
    lines.append("# Portfolio Tracker")
    lines.append(f"**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    total_value = 0.0
    
    # --- Stocks Table ---
    lines.append("## Stocks & ETFs")
    lines.append("| Ticker | Shares | Price | Value | Change | % Change |")
    lines.append("|---|---|---|---|---|---|")
    
    stock_rows = []
    
    for ticker, shares in stocks.items():
        info = data.get(ticker)
        if info:
            price = info['price']
            value = price * shares
            change = info['change']
            pct = info['pct_change']
            
            # Formatting
            color = "🟢" if change >= 0 else "🔴"
            row = f"| **{ticker}** | {shares:.2f} | ${price:.2f} | **${value:,.2f}** | {color} {change:+.2f} | {color} {pct:+.2f}% |"
            stock_rows.append((value, row)) # Store value for sorting/totals
            total_value += value
        else:
            lines.append(f"| {ticker} | {shares} | ??? | ??? | - | - |")

    # Sort by value descending
    stock_rows.sort(key=lambda x: x[0], reverse=True)
    for _, row in stock_rows:
        lines.append(row)
        
    lines.append("")
    
    # --- Crypto Table ---
    lines.append("## Crypto")
    lines.append("| Ticker | Amount | Price | Value | Change | % Change |")
    lines.append("|---|---|---|---|---|---|")
    
    crypto_rows = []
    for ticker, amount in cryptos.items():
        info = data.get(ticker)
        if info:
            price = info['price']
            value = price * amount
            change = info['change']
            pct = info['pct_change']
             
            color = "🟢" if change >= 0 else "🔴"
            # Display name without -USD for cleanliness
            display_ticker = ticker.replace('-USD', '')
            row = f"| **{display_ticker}** | {amount:.4f} | ${price:,.2f} | **${value:,.2f}** | {color} {change:+.2f} | {color} {pct:+.2f}% |"
            crypto_rows.append((value, row))
            total_value += value
        else:
            lines.append(f"| {ticker} | {amount} | ??? | ??? | - | - |")
            
    # Sort crypto by value
    crypto_rows.sort(key=lambda x: x[0], reverse=True)
    for _, row in crypto_rows:
        lines.append(row)

    lines.append("")
    lines.append(f"## Total Portfolio Value: **${total_value:,.2f}**")
    lines.append("")
    
    # --- Analysis ---
    lines.append("## Analysis")
    
    # Winners & Losers
    all_performers = []
    for ticker in list(stocks.keys()) + list(cryptos.keys()):
        info = data.get(ticker)
        if info:
            all_performers.append((ticker.replace('-USD',''), info['pct_change']))
    
    all_performers.sort(key=lambda x: x[1], reverse=True)
    
    lines.append("### Top Winners")
    for t, p in all_performers[:3]:
        lines.append(f"- **{t}**: +{p:.2f}%")
        
    lines.append("")
    lines.append("### Top Losers")
    for t, p in all_performers[-3:]:
        lines.append(f"- **{t}**: {p:.2f}%")
        
    return "\n".join(lines)

def main():
    if not os.path.exists(HOLDINGS_FILE):
        print(f"Error: Holdings file not found at {HOLDINGS_FILE}")
        sys.exit(1)
        
    print("Parsing holdings...")
    stocks, cryptos = parse_holdings(HOLDINGS_FILE)
    print(f"Found {len(stocks)} stocks and {len(cryptos)} cryptos.")
    
    all_tickers = list(stocks.keys()) + list(cryptos.keys())
    
    print("Fetching market data...")
    market_data = fetch_data(all_tickers)
    
    print("Generating report...")
    markdown_content = generate_markdown(stocks, cryptos, market_data)
    
    print(f"Writing to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
        
    print("Done!")

if __name__ == "__main__":
    main()
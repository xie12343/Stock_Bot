import os
import sys
import json
import smtplib
import argparse
from datetime import datetime, timedelta
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
# 1. Configuration & Constants
# ==========================================
TARGET_ETFS = ["VOO", "QQQ", "SCHG", "SMH"]
DROP_THRESHOLD = -0.025  # -2.5% intraday or vs previous close
PROTECTIVE_STRIKE_OTM = 0.05  # Suggested strike is 5% OTM
EXPIRY_DAYS_MIN = 30
EXPIRY_DAYS_MAX = 90

# ==========================================
# 2. Helper Functions
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

def send_email_alert(msg_content, ticker):
    email = os.environ.get("STOCK_BOT_EMAIL")
    password = os.environ.get("STOCK_BOT_PWD")
    
    if not email or not password:
        print(f"⚠️  Skipping email for {ticker}: STOCK_BOT_EMAIL/PWD not set.")
        print("--- ALERT CONTENT ---")
        print(msg_content)
        print("----------------------")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Stock Bot <{email}>"
        msg['To'] = email
        msg['Subject'] = f"🚨 US Market Drop Alert: {ticker} Protective Put Signal"
        msg.attach(MIMEText(msg_content, 'plain'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Alert email sent for {ticker}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email for {ticker}: {e}")
        return False

# ==========================================
# 3. Core Logic
# ==========================================
def check_for_drops(ticker_symbol, mock=False):
    print(f"🔍 Analyzing {ticker_symbol}...")
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        if mock:
            # Simulate a 3% drop
            current_price = 100.0
            prev_close = 103.1
            drop_pct = (current_price - prev_close) / prev_close
        else:
            hist = ticker.history(period="2d")
            if len(hist) < 2:
                print(f"⚠️  Insufficient data for {ticker_symbol}")
                return
            
            prev_close = hist['Close'].iloc[-2]
            current_price = hist['Close'].iloc[-1]
            drop_pct = (current_price - prev_close) / prev_close

        print(f"   Current: ${current_price:.2f} | Prev Close: ${prev_close:.2f} | Change: {drop_pct:.2%}")

        if drop_pct <= DROP_THRESHOLD:
            print(f"🚨 BIG DROP DETECTED for {ticker_symbol}!")
            suggest_protective_put(ticker, current_price, drop_pct, mock)
        else:
            print(f"✅ {ticker_symbol} is stable.")

    except Exception as e:
        print(f"❌ Error checking {ticker_symbol}: {e}")

def suggest_protective_put(ticker, current_price, drop_pct, mock=False):
    ticker_symbol = ticker.ticker
    target_strike = current_price * (1 - PROTECTIVE_STRIKE_OTM)
    
    # Expiry selection
    suggested_expiry = "N/A"
    suggested_put = None
    
    try:
        if mock:
            suggested_expiry = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
            suggested_strike = round(target_strike, 0)
            put_price = 2.5
        else:
            expirations = ticker.options
            if not expirations:
                print(f"⚠️  No options available for {ticker_symbol}")
                return

            # Find an expiration between 30 and 90 days
            now = datetime.now()
            target_date_min = now + timedelta(days=EXPIRY_DAYS_MIN)
            target_date_max = now + timedelta(days=EXPIRY_DAYS_MAX)
            
            for expiry in expirations:
                expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
                if target_date_min <= expiry_dt <= target_date_max:
                    suggested_expiry = expiry
                    break
            
            if suggested_expiry == "N/A":
                suggested_expiry = expirations[0] # Fallback to first available

            # Get option chain
            chain = ticker.option_chain(suggested_expiry)
            puts = chain.puts
            
            # Find put closest to target strike (5% OTM)
            puts['diff'] = abs(puts['strike'] - target_strike)
            suggested_put = puts.sort_values('diff').iloc[0]
            suggested_strike = suggested_put['strike']
            put_price = suggested_put['lastPrice']

        report = (
            f"--- 2025 US ETF Protective Put Strategy ---\n\n"
            f"Asset: {ticker_symbol}\n"
            f"Condition: Market Drop detected ({drop_pct:.2%})\n"
            f"Current Price: ${current_price:.2f}\n\n"
            f"🎯 Recommended Hedge (Protective Put):\n"
            f"Expiration: {suggested_expiry}\n"
            f"Strike Price: ${suggested_strike:.2f} (approx. 5% OTM)\n"
            f"Estimated Cost: ${put_price:.2f} per share\n\n"
            f"Rationale: This put acts as insurance against further downside while maintaining your long position benefits if the market recovers.\n"
            f"Verification Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        send_email_alert(report, ticker_symbol)

    except Exception as e:
        print(f"❌ Error generating put suggestion for {ticker_symbol}: {e}")

# ==========================================
# 4. Main Entry
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="US ETF Protective Put Monitor")
    parser.add_argument("--mock", action="store_true", help="Run with mock data for testing")
    args = parser.parse_args()

    load_env()
    
    print(f"🚀 Starting Monitoring for {', '.join(TARGET_ETFS)}...")
    print(f"Threshold: {DROP_THRESHOLD:.1%}")
    print("-" * 40)

    for etf in TARGET_ETFS:
        check_for_drops(etf, mock=args.mock)
        print("-" * 40)

    print("🏁 Monitoring session complete.")

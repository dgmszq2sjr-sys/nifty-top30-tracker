from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

def get_nifty500_tickers():
    """Fetch all 500 tickers dynamically from the official NSE India CSV."""
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        df = pd.read_csv(url)
        return [f"{symbol}.NS" for symbol in df['Symbol'].tolist()]
    except Exception as e:
        print(f"Error fetching NIFTY 500 list: {e}")
        return []

# Universe set to NIFTY 500 tickers
NIFTY_UNIVERSE = get_nifty500_tickers()

def fetch_stock_data():
    if not NIFTY_UNIVERSE:
        return [], []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=45)

    # Fast multi-threaded batch download for all 500 tickers
    downloaded_data = yf.download(
        tickers=NIFTY_UNIVERSE,
        start=start_date,
        end=end_date,
        group_by='ticker',
        threads=True
    )

    data = []
    for ticker in NIFTY_UNIVERSE:
        try:
            if ticker in downloaded_data.columns.levels[0]:
                df_ticker = downloaded_data[ticker].dropna()
                hist = df_ticker['Close']
                if not hist.empty:
                    cmp = round(hist.iloc[-1], 2)
                    clean_symbol = ticker.replace('.NS', '')
                    
                    # Approximate market cap / price valuation
                    data.append({
                        'symbol': clean_symbol,
                        'name': clean_symbol,
                        'price': cmp,
                        'market_cap': cmp * 1_000_000,  # Proxy market cap calculation
                        'history': hist
                    })
        except Exception:
            continue

    if not data:
        return [], []

    df = pd.DataFrame(data)

    # Sort current Top 500 by Market Cap / Price
    df_sorted = df.sort_values(by='market_cap', ascending=False).reset_index(drop=True)
    current_top = df_sorted.head(500)
    current_symbols = set(current_top['symbol'])

    # Determine historical ranks from 35 days ago
    historical_caps = []
    for idx, row in df.iterrows():
        hist_series = row['history']
        if len(hist_series) > 0:
            past_price = hist_series.iloc[0]
            curr_price = row['price'] if row['price'] > 0 else hist_series.iloc[-1]
            past_cap = row['market_cap'] * (past_price / curr_price) if curr_price > 0 else 0
        else:
            past_cap = 0
        historical_caps.append(past_cap)

    df['past_market_cap'] = historical_caps
    past_top = df.sort_values(by='past_market_cap', ascending=False).head(500)
    past_symbols = set(past_top['symbol'])

    # Identify stocks that exited during the last 35 days
    exited_symbols = past_symbols - current_symbols
    exited_stocks = df[df['symbol'].isin(exited_symbols)].to_dict('records')

    # Remove non-serializable pandas Series before returning JSON-compatible dicts
    current_top_clean = current_top.drop(columns=['history']).to_dict('records')

    return current_top_clean, exited_stocks

@app.route('/')
def home():
    top_live, exited_stocks = fetch_stock_data()
    return render_template('index.html', top30=top_live, exited=exited_stocks)

if __name__ == '__main__':
    app.run(debug=True)
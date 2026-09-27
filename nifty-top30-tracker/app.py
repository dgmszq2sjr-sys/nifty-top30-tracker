from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

# Representative universe of top Nifty constituents
NIFTY_UNIVERSE = [
    "RELIANCE.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "SBIN.NS",
    "TCS.NS", "BAJFINANCE.NS", "LT.NS", "HINDUNILVR.NS", "SUNPHARMA.NS",
    "MARUTI.NS", "M&M.NS", "HCLTECH.NS", "AXISBANK.NS", "ITC.NS",
    "NTPC.NS", "ONGC.NS", "KOTAKBANK.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "ADANIPORTS.NS", "BEL.NS", "TECHM.NS", "WIPRO.NS", "TATAMOTORS.NS",
    "BAJAJ-AUTO.NS", "ASIANPAINT.NS", "TATASTEEL.NS", "POWERGRID.NS", "COALINDIA.NS",
    "NESTLEIND.NS", "GRASIM.NS", "JSWSTEEL.NS", "CIPLA.NS", "DRREDDY.NS"
]

def fetch_stock_data():
    data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=45) # Fetching extended window for 35 trading days

    for ticker in NIFTY_UNIVERSE:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        info = stock.info
        
        market_cap = info.get('marketCap', 0)
        cmp = info.get('currentPrice', 0)
        name = info.get('shortName', ticker.replace('.NS', ''))
        
        if not hist.empty and market_cap > 0:
            data.append({
                'symbol': ticker.replace('.NS', ''),
                'name': name,
                'price': cmp,
                'market_cap': market_cap,
                'history': hist['Close']
            })
            
    df = pd.DataFrame(data)
    
    # Sort current Top 30
    df_sorted = df.sort_values(by='market_cap', ascending=False).reset_index(drop=True)
    current_top30 = df_sorted.head(30)
    current_top30_symbols = set(current_top30['symbol'])
    
    # Determine historical top 30 from 35 days ago
    historical_caps = []
    for idx, row in df.iterrows():
        # Calculate approximate historical market cap from past price ratio
        hist_series = row['history']
        if len(hist_series) > 0:
            past_price = hist_series.iloc[0]
            curr_price = row['price'] if row['price'] > 0 else hist_series.iloc[-1]
            past_cap = row['market_cap'] * (past_price / curr_price) if curr_price > 0 else 0
        else:
            past_cap = 0
        historical_caps.append(past_cap)
        
    df['past_market_cap'] = historical_caps
    past_top30 = df.sort_values(by='past_market_cap', ascending=False).head(30)
    past_top30_symbols = set(past_top30['symbol'])
    
    # Identify stocks that exited the Top 30 during the last 35 days
    exited_symbols = past_top30_symbols - current_top30_symbols
    exited_stocks = df[df['symbol'].isin(exited_symbols)].to_dict('records')
    
    return current_top30.to_dict('records'), exited_stocks

@app.route('/')
def home():
    top30_live, exited_stocks = fetch_stock_data()
    return render_template('index.html', top30=top30_live, exited=exited_stocks)

if __name__ == '__main__':
    app.run(debug=True)
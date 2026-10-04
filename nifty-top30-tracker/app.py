import concurrent.futures
from datetime import datetime, timedelta
from flask import Flask, render_template
import pandas as pd
import requests
import yfinance as yf

app = Flask(__name__)


def get_nifty500_tickers():
  url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  try:
    response = requests.get(url, headers=headers, timeout=10)
    df = pd.read_csv(pd.io.common.BytesIO(response.content))
    return [f"{symbol}.NS" for symbol in df["Symbol"].tolist()]
  except Exception as e:
    print(f"Error fetching NIFTY 500 list: {e}")
    return []


NIFTY_UNIVERSE = get_nifty500_tickers()


def fetch_single_ticker(ticker, start_date, end_date):
  """Fetch price history for a single stock with safe error handling."""
  try:
    df = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=True,
    )
    if not df.empty and "Close" in df.columns:
      close_data = df["Close"]
      # Handle cases where yfinance returns a DataFrame vs Series
      if isinstance(close_data, pd.DataFrame):
        hist = close_data.iloc[:, 0].dropna()
      else:
        hist = close_data.dropna()

      if not hist.empty:
        cmp = round(float(hist.iloc[-1]), 2)
        clean_symbol = ticker.replace(".NS", "")
        return {
            "symbol": clean_symbol,
            "name": clean_symbol,
            "price": cmp,
            "market_cap": cmp * 1_000_000,
            "history": hist,
        }
  except Exception as e:
    print(f"Failed to fetch {ticker}: {e}")
  return None


def fetch_stock_data():
  if not NIFTY_UNIVERSE:
    return [], []

  end_date = datetime.now()
  start_date = end_date - timedelta(days=45)

  # Safe multi-threaded execution
  data = []
  with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(fetch_single_ticker, ticker, start_date, end_date)
        for ticker in NIFTY_UNIVERSE
    ]
    for future in concurrent.futures.as_completed(futures):
      res = future.result()
      if res:
        data.append(res)

  if not data:
    return [], []

  df = pd.DataFrame(data)
  df_sorted = df.sort_values(
      by="market_cap", ascending=False
  ).reset_index(drop=True)

  # Separate Top 500 records
  current_top = df_sorted.head(500)
  current_symbols = set(current_top["symbol"])

  # Calculate 35-day historical movement safely
  historical_caps = []
  for _, row in df.iterrows():
    hist_series = row["history"]
    if len(hist_series) > 0:
      past_price = float(hist_series.iloc[0])
      curr_price = (
          row["price"] if row["price"] > 0 else float(hist_series.iloc[-1])
      )
      past_cap = (
          row["market_cap"] * (past_price / curr_price) if curr_price > 0 else 0
      )
    else:
      past_cap = 0
    historical_caps.append(past_cap)

  df["past_market_cap"] = historical_caps
  past_top = df.sort_values(by="past_market_cap", ascending=False).head(500)
  past_symbols = set(past_top["symbol"])

  exited_symbols = past_symbols - current_symbols
  exited_stocks = df[df["symbol"].isin(exited_symbols)].to_dict("records")

  # Remove non-JSON serializable Pandas Series before passing to Flask Jinja template
  current_top_clean = current_top.drop(columns=["history"]).to_dict("records")

  for rank, item in enumerate(current_top_clean, start=1):
    item["rank"] = rank

  return current_top_clean, exited_stocks


@app.route("/")
def home():
  try:
    top_live, exited_stocks = fetch_stock_data()
    return render_template("index.html", top30=top_live, exited=exited_stocks)
  except Exception as e:
    print(f"Runtime execution error: {e}")
    # Return empty lists rather than letting Flask break with 500 Internal Server Error
    return render_template("index.html", top30=[], exited=[])


if __name__ == "__main__":
  app.run(debug=True)
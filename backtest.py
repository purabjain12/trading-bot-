import ccxt
import pandas as pd

print("🧪 Starting Backtest Engine...")

# --- CONFIGURATION ---
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1h'
SMA_SHORT = 20
SMA_LONG = 50
RSI_PERIOD = 14
VOLUME_PERIOD = 20
STOP_LOSS_PERCENT = 0.025
TAKE_PROFIT_PERCENT = 0.05
INITIAL_BALANCE = 10000  # Start with $10,000 fake USDT

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_backtest():
    # 1. Fetch Historical Data
    exchange = ccxt.binance()
    print(f"📥 Downloading historical data for {SYMBOL}...")
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=1000)
    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    
    # 2. Calculate Indicators
    df['sma_short'] = df['close'].rolling(window=SMA_SHORT).mean()
    df['sma_long'] = df['close'].rolling(window=SMA_LONG).mean()
    df['rsi'] = calculate_rsi(df, RSI_PERIOD)
    df['vol_avg'] = df['volume'].rolling(window=VOLUME_PERIOD).mean()
    
    # 3. Simulate Trading
    balance_usdt = INITIAL_BALANCE
    btc_held = 0
    entry_price = 0
    trades = []
    
    print(f"\n📊 Starting Balance: ${balance_usdt}")
    print("🔄 Running simulation...\n")
    
    # Start from row 100 to ensure indicators are calculated
    for i in range(100, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        # Check Exit (Stop Loss / Take Profit)
        if btc_held > 0:
            pnl_percent = (current_price - entry_price) / entry_price
            
            # Stop Loss
            if pnl_percent < -STOP_LOSS_PERCENT:
                balance_usdt += btc_held * current_price
                trades.append({'type': 'SELL (SL)', 'price': current_price, 'pnl': pnl_percent})
                btc_held = 0
                entry_price = 0
                continue
            
            # Take Profit
            if pnl_percent > TAKE_PROFIT_PERCENT:
                balance_usdt += btc_held * current_price
                trades.append({'type': 'SELL (TP)', 'price': current_price, 'pnl': pnl_percent})
                btc_held = 0
                entry_price = 0
                continue
        
        # Check Entry (Triple Confirmation)
        if btc_held == 0:
            score = 0
            if row['sma_short'] > row['sma_long']: 
                score += 1
            if row['rsi'] < 40: 
                score += 1
            if row['volume'] > row['vol_avg'] * 1.1: 
                score += 0.5
            
            if score >= 1.5:  # Signal Strength
                btc_to_buy = (balance_usdt * 0.5) / current_price
                if btc_to_buy > 0:
                    btc_held = btc_to_buy
                    balance_usdt -= (btc_to_buy * current_price)
                    entry_price = current_price
                    trades.append({'type': 'BUY', 'price': current_price})
    
    # 4. Finalize - Sell remaining BTC at last price
    if btc_held > 0:
        balance_usdt += btc_held * df.iloc[-1]['close']
    
    # 5. Report
    print("\n" + "="*50)
    print("📊 BACKTEST RESULTS")
    print("="*50)
    print(f"💰 Final Balance: ${balance_usdt:.2f}")
    profit = balance_usdt - INITIAL_BALANCE
    print(f"📈 Total Profit: ${profit:+.2f}")
    print(f"📈 Total Return: {((balance_usdt - INITIAL_BALANCE)/INITIAL_BALANCE)*100:+.2f}%")
    print(f"🔄 Total Trades: {len(trades)}")
    
    wins = [t for t in trades if t.get('pnl', 0) > 0]
    losses = [t for t in trades if t.get('pnl', 0) < 0]
    
    print(f"✅ Winning Trades: {len(wins)}")
    print(f"❌ Losing Trades: {len(losses)}")
    if len(trades) > 0:
        print(f"🎯 Win Rate: {(len(wins)/len(trades))*100:.1f}%")
    print("="*50)

if __name__ == "__main__":
    run_backtest()
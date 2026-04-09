import ccxt
import pandas as pd
import time
import os
from dotenv import load_dotenv
import requests

load_dotenv()
api_key = os.getenv('API_KEY')
secret_key = os.getenv('SECRET_KEY')

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret_key,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

def send_telegram_alert(message):
    """Send alert to your Telegram"""
    # ✅ FIXED: Token must be in quotes (it's a string)
    token = "8402393870:AAGBkci_o9sVTiCFmFYeOjMuLtEQ0g0hrbY"
    chat_id = "5949689771"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML"
        })
        print("📱 Telegram alert sent")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

print("🤖 Triple Confirmation Bot Started! Press Ctrl+C to stop.")

# Send startup alert
send_telegram_alert("🚀 <b>BOT STARTED</b>\n✅ Triple Confirmation Strategy Active\n🪙 Trading: BTC/USDT")

# --- STRATEGY CONFIG ---
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1h'
SMA_SHORT = 20
SMA_LONG = 50
RSI_PERIOD = 14
VOLUME_PERIOD = 20

# --- RISK MANAGEMENT ---
STOP_LOSS_PERCENT = 0.025
TAKE_PROFIT_PERCENT = 0.05
POSITION_SIZE_PERCENT = 0.3
MIN_SIGNAL_STRENGTH = 2

# --- STATE TRACKING ---
entry_price = None
entry_time = None
daily_pnl = 0
trades_today = 0

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_signals(df):
    current = df.iloc[-1]
    
    sma_short = df['close'].rolling(window=SMA_SHORT).mean().iloc[-1]
    sma_long = df['close'].rolling(window=SMA_LONG).mean().iloc[-1]
    rsi = calculate_rsi(df, RSI_PERIOD).iloc[-1]
    avg_volume = df['volume'].rolling(window=VOLUME_PERIOD).mean().iloc[-1]
    
    current_price = current['close']
    current_volume = current['volume']
    
    score = 0
    details = []
    
    if sma_short > sma_long:
        score += 1
        details.append("📈 Trend: BULLISH")
    elif sma_short < sma_long:
        score -= 1
        details.append("📉 Trend: BEARISH")
    else:
        details.append("➡️  Trend: NEUTRAL")
    
    if rsi < 40:  # ✅ Relaxed from 30 for more signals
        score += 1
        details.append("🟢 Momentum: OVERSOLD")
    elif rsi > 70:
        score -= 1
        details.append("🔴 Momentum: OVERBOUGHT")
    else:
        details.append(f"⚪ Momentum: NEUTRAL (RSI: {rsi:.1f})")
    
    if current_volume > avg_volume * 1.1:  # ✅ Relaxed from 1.2
        if score > 0:
            score += 0.5
            details.append("🔊 Volume: HIGH (Bullish)")
        elif score < 0:
            score -= 0.5
            details.append("🔊 Volume: HIGH (Bearish)")
        else:
            details.append("🔊 Volume: HIGH")
    else:
        details.append("🔇 Volume: LOW")
    
    return {
        'score': score,
        'details': details,
        'price': current_price,
        'rsi': rsi,
        'volume_ratio': current_volume / avg_volume
    }

def check_risk_exit(current_price, btc_balance):
    """Check stop loss and take profit"""
    global entry_price, daily_pnl
    
    if entry_price is None or btc_balance < 0.0001:
        return None, 0
    
    pnl_percent = (current_price - entry_price) / entry_price
    
    # ✅ STOP LOSS with Telegram alert
    if pnl_percent < -STOP_LOSS_PERCENT:
        print(f"🔴 STOP LOSS: -{abs(pnl_percent)*100:.2f}%")
        send_telegram_alert(
            f"🚨 <b>STOP LOSS TRIGGERED</b>\n"
            f"🔴 Price: ${current_price:.2f}\n"
            f"💸 Loss: {pnl_percent*100:.2f}%\n"
            f"🪙 Pair: {SYMBOL}"
        )
        return "SELL", pnl_percent
    
    # ✅ TAKE PROFIT with Telegram alert
    if pnl_percent > TAKE_PROFIT_PERCENT:
        print(f"🟢 TAKE PROFIT: +{pnl_percent*100:.2f}%")
        daily_pnl += (current_price - entry_price) * btc_balance
        entry_price = None
        send_telegram_alert(
            f"✅ <b>TAKE PROFIT HIT</b>\n"
            f"🟢 Price: ${current_price:.2f}\n"
            f"💰 Profit: {pnl_percent*100:.2f}%\n"
            f"🪙 Pair: {SYMBOL}"
        )
        return "SELL", pnl_percent
    
    return None, pnl_percent

while True:
    try:
        print(f"\n{'='*60}")
        print(f"🔄 Checking {SYMBOL} at {time.strftime('%H:%M:%S')}")
        
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        analysis = analyze_signals(df)
        
        print(f"💰 Price: ${analysis['price']:.2f}")
        print(f"📊 RSI: {analysis['rsi']:.1f} | Vol Ratio: {analysis['volume_ratio']:.2f}x")
        for detail in analysis['details']:
            print(f"   {detail}")
        print(f"🎯 Signal Strength: {analysis['score']:+.1f}/3.0")
        
        balance = exchange.fetch_balance()
        usdt_balance = balance['total']['USDT']
        btc_balance = balance['total']['BTC']
        
        # Check Risk Exit FIRST
        risk_exit, current_pnl = check_risk_exit(analysis['price'], btc_balance)
        if risk_exit == "SELL":
            print(f"✅ Executing RISK SELL: {btc_balance:.8f} BTC")
            order = exchange.create_market_sell_order(SYMBOL, btc_balance)
            trades_today += 1
            entry_price = None
            time.sleep(2)
            continue
        
        # Strategy Entry Logic
        signal_score = analysis['score']
        
        # BUY Signal
        if signal_score >= MIN_SIGNAL_STRENGTH and entry_price is None:
            print(f"✅ BUY SIGNAL CONFIRMED (Score: {signal_score:+.1f})")
            buy_amount = usdt_balance * POSITION_SIZE_PERCENT
            if buy_amount > 10:
                btc_to_buy = buy_amount / analysis['price']
                print(f"🛒 Buying {btc_to_buy:.8f} BTC (${buy_amount:.2f})")
                
                # ✅ Telegram Alert for BUY
                send_telegram_alert(
                    f"🛒 <b>BUY ORDER EXECUTED</b>\n"
                    f"💰 Price: ${analysis['price']:.2f}\n"
                    f"📊 RSI: {analysis['rsi']:.1f}\n"
                    f"🎯 Score: {signal_score:+.1f}\n"
                    f"💵 Amount: {btc_to_buy:.8f} BTC"
                )
                
                order = exchange.create_market_buy_order(SYMBOL, btc_to_buy)
                entry_price = analysis['price']
                entry_time = time.time()
                trades_today += 1
                print(f"🎯 Entry: ${entry_price:.2f}")
            else:
                print(f"⏸️  Insufficient USDT: ${usdt_balance:.2f}")
        
        # SELL Signal (Strategy-based)
        elif signal_score <= -MIN_SIGNAL_STRENGTH and entry_price is not None:
            print(f"✅ SELL SIGNAL CONFIRMED (Score: {signal_score:+.1f})")
            if btc_balance > 0.0001:
                print(f"💰 Selling {btc_balance:.8f} BTC")
                
                # ✅ Telegram Alert for SELL
                pnl = current_pnl * 100 if current_pnl else 0
                send_telegram_alert(
                    f"💰 <b>SELL ORDER EXECUTED</b>\n"
                    f"💵 Price: ${analysis['price']:.2f}\n"
                    f"📈 P&L: {pnl:+.2f}%"
                )
                
                order = exchange.create_market_sell_order(SYMBOL, btc_balance)
                entry_price = None
                print(f"🎯 Position closed")
        
        # Status Update
        if entry_price:
            current_pnl_pct = (analysis['price'] - entry_price) / entry_price * 100
            hold_time = (time.time() - entry_time) / 60
            print(f"📦 Open Position: ${entry_price:.2f} → ${analysis['price']:.2f} ({current_pnl_pct:+.2f}%) | Hold: {hold_time:.0f}min")
        
        print(f"📊 Daily: P&L ${daily_pnl:+.2f} | Trades: {trades_today}")
        
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
        send_telegram_alert("⏸️ <b>BOT STOPPED</b>\nUser manually stopped the bot.")
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        send_telegram_alert(f"❌ <b>BOT ERROR</b>\n{str(e)}")
        time.sleep(10)
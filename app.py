import json
import math
import os
import uuid
from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

POSITIONS_FILE = 'positions.json'


def load_positions():
    """Load positions from JSON file"""
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_positions(positions):
    """Save positions to JSON file"""
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f, indent=2)


def get_current_option_price(ticker, option_type, strike, expiration):
    """Get current market price of an option contract"""
    try:
        stock = yf.Ticker(ticker)
        opt = stock.option_chain(expiration)
        chain = opt.calls if option_type == 'call' else opt.puts
        contract = chain[chain['strike'] == float(strike)]
        if not contract.empty:
            return float(contract['lastPrice'].iloc[0])
        return None
    except Exception as e:
        print(f"Error fetching option price: {e}")
        return None


def calculate_position_pnl(position):
    """Calculate current price and unrealised P&L for a position.

    Returns (current_price, pnl) tuple; values are None when unavailable.
    """
    try:
        ticker = position['ticker']
        pos_type = position['type']
        quantity = float(position['quantity'])
        entry_price = float(position['entryPrice'])

        if pos_type == 'stock':
            analyzer = OptionsAnalyzer(ticker)
            current_price = analyzer.get_current_price()
            if current_price is None:
                return None, None
            pnl = (current_price - entry_price) * quantity
            return round(current_price, 2), round(pnl, 2)

        elif pos_type in ('call', 'put'):
            strike = position.get('strike')
            expiration = position.get('expiration')
            current_price = get_current_option_price(ticker, pos_type, strike, expiration)
            if current_price is None:
                return None, None
            pnl = (current_price - entry_price) * quantity * 100
            return round(current_price, 2), round(pnl, 2)

    except Exception as e:
        print(f"Error calculating P&L: {e}")

    return None, None

# ---------------------------------------------------------------------------
# System prompt for the AI multi-strategy options recommender
# ---------------------------------------------------------------------------
AI_SYSTEM_PROMPT = """You are a quantitative options strategy recommender.

Your job is to analyze the provided market inputs and produce:

1. A market regime summary (trend + volatility + conditions)
2. A separate trade recommendation for EACH strategy category listed below (or explicitly mark the strategy as "NO TRADE" with a reason)

You must NOT hallucinate data. Use only supplied inputs.

---

STRATEGY CATALOG (must output each section in this exact order):
1. Covered Call
2. Cash-Secured Put
3. Bull Put Credit Spread
4. Bear Call Credit Spread
5. Call Debit Spread
6. Put Debit Spread
7. Iron Condor
8. Calendar / Diagonal
9. Protective Put (Hedge)
10. Straddle / Strangle (only if risk_tolerance = high; otherwise NO TRADE)

For each bucket, output:
- Trade (legs, strikes, expiration)
- Pricing assumptions (mid prices from bid/ask)
- Max profit, max loss, break-even
- Probability of profit (approx via delta, or explain if not possible)
- Greeks exposure estimate (net delta/theta/vega directionally; numeric if possible)
- Capital required / buying power estimate
- Entry conditions
- Exit plan
- Risk summary
- Reject conditions (why it might be invalid)

If a strategy cannot be recommended under constraints, output:
  "status": "NO_TRADE"
  "reason": "..." (liquidity, bid-ask too wide, wrong regime, risk too high, etc.)

---

REQUIRED: MARKET REGIME + TREND DETECTION

You must compute and output a Market Snapshot with:
- Trend: bullish / bearish / sideways
  Use supplied trend if present, otherwise infer from ohlc_daily:
  * 20-day vs 50-day moving average (MA20, MA50)
  * slope of MA20 (rising/falling)
  * price vs MA50 (above/below)
- Volatility Regime: high / normal / low using IV percentile and/or VIX (if provided)
- Market Condition Label (one of):
  * "Bull + High IV"
  * "Bull + Low IV"
  * "Bear + High IV"
  * "Bear + Low IV"
  * "Sideways + High IV"
  * "Sideways + Low IV"
- Key levels (if inferable from data):
  * recent support/resistance from swing highs/lows (last ~20 bars)
- Action Bias: premium selling favored vs premium buying favored (based on IV percentile)

If the input data is insufficient to compute something, explicitly set it to null and explain why in "notes".

---

STRATEGY-SPECIFIC CONSTRUCTION RULES

General Liquidity Filters (apply to all legs):
Reject any leg if:
- oi < min_open_interest OR volume < min_volume
- bid/ask spread > max_bid_ask_spread_pct_of_mid

If any necessary leg fails filters, mark the strategy NO_TRADE.

DTE Selection:
- If target_return = income: choose expirations within preferred_dte_income
- If target_return = growth: choose expirations within preferred_dte_growth
- If target_return = hedge: hedge DTE can be longer (30-120), prefer liquid monthlies

Strike / Delta Preferences:
- Short options: delta in preferred_short_delta_range
- Long options: delta in preferred_long_delta_range
  If deltas are missing, approximate using moneyness + IV + time (state clearly as approximation).

Risk Controls:
Reject a strategy if:
- estimated max loss > capital * max_risk_per_trade_pct (unless explicitly "hedge" and user allows it)
- unlimited risk strategy is proposed when risk_tolerance != high

---

CALCULATIONS REQUIRED

You must compute (where applicable):
- mid = (bid + ask) / 2
- spread_width
- net_credit / net_debit
- max_profit
- max_loss
- break_even
- return_on_risk = max_profit / max_loss (credit spreads/condors)
- probability_of_profit_est:
  * For single short option: approx = 1 - |delta| (state approximation)
  * For spreads: approximate using short-leg delta (and note limitations)
- buying_power_estimate:
  * Covered call: 100 shares notional
  * CSP: strike*100 cash reserved
  * Credit spread: width*100 - credit*100
  * Debit spread: debit*100
  * Iron condor: max(widths)*100 - credit*100
  * Long options: premium*100

If you cannot compute a value due to missing inputs, set it to null and explain in "notes".

---

OUTPUT FORMAT (STRICT JSON)

You must output a single JSON object with:
- "market_snapshot"
- "recommendations" (array of 10 items, one per strategy bucket, in the exact order listed)
- "rankings" (optional): rank strategies that have "status": "TRADE" by a scoring model

Market snapshot schema:
{
  "trend": "bullish/bearish/sideways",
  "trend_evidence": {
    "ma20": null,
    "ma50": null,
    "ma20_slope": null,
    "price_vs_ma50": null
  },
  "volatility_regime": "high/normal/low",
  "iv_percentile": 72,
  "market_condition_label": "Bull + High IV",
  "support_levels": [],
  "resistance_levels": [],
  "action_bias": "premium_selling/premium_buying/mixed",
  "notes": ""
}

Recommendation item schema (for each strategy):
{
  "strategy_bucket": "Covered Call",
  "status": "TRADE/NO_TRADE",
  "rationale": "",
  "legs": [
    {"action":"SELL","type":"CALL","strike":900,"expiration":"2026-04-19","mid":12.55}
  ],
  "entry": {
    "conditions": "",
    "limit_price_logic": "use mid or better",
    "liquidity_checks_passed": true
  },
  "metrics": {
    "net_credit_debit": 0,
    "max_profit": 0,
    "max_loss": 0,
    "break_even": 0,
    "probability_of_profit_est": 0,
    "return_on_risk": null,
    "buying_power_estimate": 0
  },
  "greeks_profile": {
    "delta": null,
    "theta": null,
    "vega": null,
    "notes": "directional exposure summary if exact netting not possible"
  },
  "exit_plan": {
    "profit_take": "e.g., close at 50% of credit",
    "stop_loss": "e.g., close if loss reaches 2x credit",
    "time_stop": "e.g., close at 7 DTE",
    "adjustments": "roll, convert, hedge, etc."
  },
  "risk_summary": "",
  "reject_reasons": []
}

---

RANKING MODEL (OPTIONAL BUT PREFERRED)

If 2+ strategies produce valid trades, include "rankings" using a score:
- For income: weight theta, POP, liquidity, return on risk
- For growth: weight delta exposure, payoff asymmetry, cost
- For hedge: weight downside protection per $ spent

Return top 3 strategies with short justification.

---

BEHAVIOR RULES

- You are a risk manager first.
- Do not recommend trades that violate constraints.
- Do not output anything other than strict JSON.
- If inputs are incomplete, produce best-effort output with explicit nulls and notes.
- Avoid overly complex multi-leg structures beyond the catalog.
"""


# ---------------------------------------------------------------------------
# Black-Scholes Greeks (no scipy dependency)
# ---------------------------------------------------------------------------

# Default IV assumption when market data reports 0 or invalid values.
# 30 % is a conservative mid-range assumption for liquid large-cap options.
_DEFAULT_IV_FALLBACK = 0.30


def _norm_cdf(x):
    """Standard normal CDF using math.erf"""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x):
    """Standard normal PDF"""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_greeks(S, K, T, r, sigma, option_type='call'):
    """Return Black-Scholes Greeks for a European option.

    Returns a dict with delta, gamma, theta, vega; all None on invalid inputs.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {'delta': None, 'gamma': None, 'theta': None, 'vega': None}
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        n_d1 = _norm_pdf(d1)
        if option_type == 'call':
            delta = _norm_cdf(d1)
            theta = (
                -S * n_d1 * sigma / (2.0 * math.sqrt(T))
                - r * K * math.exp(-r * T) * _norm_cdf(d2)
            ) / 365.0
        else:
            delta = _norm_cdf(d1) - 1.0
            theta = (
                -S * n_d1 * sigma / (2.0 * math.sqrt(T))
                + r * K * math.exp(-r * T) * _norm_cdf(-d2)
            ) / 365.0
        gamma = n_d1 / (S * sigma * math.sqrt(T))
        vega = S * n_d1 * math.sqrt(T) / 100.0  # per 1 % IV move
        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta, 4),
            'vega': round(vega, 4),
        }
    except (ValueError, ZeroDivisionError):
        return {'delta': None, 'gamma': None, 'theta': None, 'vega': None}

class OptionsAnalyzer:
    """Class to analyze options data and calculate strategy payoffs"""
    
    def __init__(self, ticker):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)
        
    def get_current_price(self):
        """Get current stock price"""
        try:
            hist = self.stock.history(period="1d")
            if hist.empty:
                return None
            return hist['Close'].iloc[-1]
        except:
            return None
    
    def get_options_data(self):
        """Fetch options data for all available expiration dates"""
        try:
            expirations = self.stock.options
            if not expirations:
                return None, None
            
            current_price = self.get_current_price()
            if current_price is None:
                return None, None
            
            options_data = []
            
            # Get options for first 5 expiration dates
            for exp_date in expirations[:5]:
                opt = self.stock.option_chain(exp_date)
                
                # Process calls
                calls = opt.calls[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].copy()
                calls['type'] = 'call'
                calls['expiration'] = exp_date
                calls['daysToExpiry'] = (pd.to_datetime(exp_date) - pd.Timestamp.now()).days
                
                # Process puts
                puts = opt.puts[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].copy()
                puts['type'] = 'put'
                puts['expiration'] = exp_date
                puts['daysToExpiry'] = (pd.to_datetime(exp_date) - pd.Timestamp.now()).days
                
                # Filter strikes near current price (within 20%)
                lower_bound = current_price * 0.8
                upper_bound = current_price * 1.2
                
                calls = calls[(calls['strike'] >= lower_bound) & (calls['strike'] <= upper_bound)]
                puts = puts[(puts['strike'] >= lower_bound) & (puts['strike'] <= upper_bound)]
                
                options_data.append(pd.concat([calls, puts], ignore_index=True))
            
            if options_data:
                all_options = pd.concat(options_data, ignore_index=True)
                return all_options, current_price
            
            return None, None
        except Exception as e:
            print(f"Error fetching options data: {e}")
            return None, None
    
    def calculate_covered_call(self, current_price, strike, premium, shares=100):
        """Calculate covered call strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        # Own stock + Sell call
        payoffs = []
        for price in stock_prices:
            stock_pnl = (price - current_price) * shares
            call_pnl = premium * shares if price <= strike else (premium * shares - (price - strike) * shares)
            payoffs.append(stock_pnl + call_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_protective_put(self, current_price, strike, premium, shares=100):
        """Calculate protective put strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        # Own stock + Buy put
        payoffs = []
        for price in stock_prices:
            stock_pnl = (price - current_price) * shares
            put_pnl = -premium * shares if price >= strike else ((strike - price) * shares - premium * shares)
            payoffs.append(stock_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_long_straddle(self, current_price, strike, call_premium, put_premium, contracts=1):
        """Calculate long straddle strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        # Buy call + Buy put at same strike
        payoffs = []
        for price in stock_prices:
            call_pnl = -call_premium * 100 * contracts if price <= strike else ((price - strike) * 100 * contracts - call_premium * 100 * contracts)
            put_pnl = -put_premium * 100 * contracts if price >= strike else ((strike - price) * 100 * contracts - put_premium * 100 * contracts)
            payoffs.append(call_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_long_strangle(self, current_price, call_strike, put_strike, call_premium, put_premium, contracts=1):
        """Calculate long strangle strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        # Buy OTM call + Buy OTM put
        payoffs = []
        for price in stock_prices:
            call_pnl = -call_premium * 100 * contracts if price <= call_strike else ((price - call_strike) * 100 * contracts - call_premium * 100 * contracts)
            put_pnl = -put_premium * 100 * contracts if price >= put_strike else ((put_strike - price) * 100 * contracts - put_premium * 100 * contracts)
            payoffs.append(call_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_iron_condor(self, current_price, strikes, premiums, contracts=1):
        """Calculate iron condor strategy payoff"""
        # strikes: [put_buy, put_sell, call_sell, call_buy]
        # premiums: [put_buy, put_sell, call_sell, call_buy]
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        payoffs = []
        for price in stock_prices:
            # Buy put at lower strike
            put_buy_pnl = -premiums[0] * 100 * contracts if price >= strikes[0] else ((strikes[0] - price) * 100 * contracts - premiums[0] * 100 * contracts)
            
            # Sell put at higher strike
            put_sell_pnl = premiums[1] * 100 * contracts if price >= strikes[1] else (premiums[1] * 100 * contracts - (strikes[1] - price) * 100 * contracts)
            
            # Sell call at lower strike
            call_sell_pnl = premiums[2] * 100 * contracts if price <= strikes[2] else (premiums[2] * 100 * contracts - (price - strikes[2]) * 100 * contracts)
            
            # Buy call at higher strike
            call_buy_pnl = -premiums[3] * 100 * contracts if price <= strikes[3] else ((price - strikes[3]) * 100 * contracts - premiums[3] * 100 * contracts)
            
            payoffs.append(put_buy_pnl + put_sell_pnl + call_sell_pnl + call_buy_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def suggest_strategies(self, options_df, current_price):
        """Suggest reasonable options strategies based on available options"""
        strategies = []
        
        try:
            # Get ATM strike (at-the-money)
            atm_strike = options_df.iloc[(options_df['strike'] - current_price).abs().argsort()[:1]]['strike'].values[0]
            
            # Get nearest expiration
            nearest_exp = options_df['expiration'].min()
            nearest_options = options_df[options_df['expiration'] == nearest_exp]
            
            # 1. Covered Call - Sell OTM call
            otm_calls = nearest_options[(nearest_options['type'] == 'call') & 
                                        (nearest_options['strike'] > current_price)]
            if not otm_calls.empty:
                call = otm_calls.iloc[0]
                prices, payoffs = self.calculate_covered_call(current_price, call['strike'], call['lastPrice'])
                strategies.append({
                    'name': 'Covered Call',
                    'description': f"Own 100 shares + Sell 1 Call at ${call['strike']:.2f}",
                    'expiration': nearest_exp,
                    'strikes': [call['strike']],
                    'premium': call['lastPrice'],
                    'cost': current_price * 100 - call['lastPrice'] * 100,
                    'maxProfit': (call['strike'] - current_price) * 100 + call['lastPrice'] * 100,
                    'maxLoss': 'Unlimited (if stock drops)',
                    'prices': prices,
                    'payoffs': payoffs
                })
            
            # 2. Protective Put - Buy ITM/ATM put
            atm_puts = nearest_options[(nearest_options['type'] == 'put') & 
                                       (nearest_options['strike'] <= current_price)]
            if not atm_puts.empty:
                put = atm_puts.iloc[0]
                prices, payoffs = self.calculate_protective_put(current_price, put['strike'], put['lastPrice'])
                strategies.append({
                    'name': 'Protective Put',
                    'description': f"Own 100 shares + Buy 1 Put at ${put['strike']:.2f}",
                    'expiration': nearest_exp,
                    'strikes': [put['strike']],
                    'premium': put['lastPrice'],
                    'cost': current_price * 100 + put['lastPrice'] * 100,
                    'maxProfit': 'Unlimited (if stock rises)',
                    'maxLoss': (current_price - put['strike']) * 100 + put['lastPrice'] * 100,
                    'prices': prices,
                    'payoffs': payoffs
                })
            
            # 3. Long Straddle - Buy ATM call and put
            atm_calls = nearest_options[(nearest_options['type'] == 'call') & 
                                        (abs(nearest_options['strike'] - atm_strike) < 1)]
            atm_puts = nearest_options[(nearest_options['type'] == 'put') & 
                                       (abs(nearest_options['strike'] - atm_strike) < 1)]
            
            if not atm_calls.empty and not atm_puts.empty:
                call = atm_calls.iloc[0]
                put = atm_puts.iloc[0]
                prices, payoffs = self.calculate_long_straddle(current_price, atm_strike, 
                                                               call['lastPrice'], put['lastPrice'])
                strategies.append({
                    'name': 'Long Straddle',
                    'description': f"Buy 1 Call + Buy 1 Put at ${atm_strike:.2f}",
                    'expiration': nearest_exp,
                    'strikes': [atm_strike],
                    'premium': call['lastPrice'] + put['lastPrice'],
                    'cost': (call['lastPrice'] + put['lastPrice']) * 100,
                    'maxProfit': 'Unlimited',
                    'maxLoss': (call['lastPrice'] + put['lastPrice']) * 100,
                    'prices': prices,
                    'payoffs': payoffs
                })
            
            # 4. Long Strangle - Buy OTM call and put
            otm_calls = nearest_options[(nearest_options['type'] == 'call') & 
                                        (nearest_options['strike'] > current_price * 1.03)]
            otm_puts = nearest_options[(nearest_options['type'] == 'put') & 
                                       (nearest_options['strike'] < current_price * 0.97)]
            
            if not otm_calls.empty and not otm_puts.empty:
                call = otm_calls.iloc[0]
                put = otm_puts.iloc[0]
                prices, payoffs = self.calculate_long_strangle(current_price, call['strike'], 
                                                               put['strike'], call['lastPrice'], put['lastPrice'])
                strategies.append({
                    'name': 'Long Strangle',
                    'description': f"Buy 1 Call at ${call['strike']:.2f} + Buy 1 Put at ${put['strike']:.2f}",
                    'expiration': nearest_exp,
                    'strikes': [call['strike'], put['strike']],
                    'premium': call['lastPrice'] + put['lastPrice'],
                    'cost': (call['lastPrice'] + put['lastPrice']) * 100,
                    'maxProfit': 'Unlimited',
                    'maxLoss': (call['lastPrice'] + put['lastPrice']) * 100,
                    'prices': prices,
                    'payoffs': payoffs
                })
            
            # 5. Iron Condor - Sell OTM put spread + Sell OTM call spread
            otm_puts_sorted = nearest_options[(nearest_options['type'] == 'put') & 
                                               (nearest_options['strike'] < current_price)].sort_values('strike', ascending=False)
            otm_calls_sorted = nearest_options[(nearest_options['type'] == 'call') & 
                                                (nearest_options['strike'] > current_price)].sort_values('strike')
            
            if len(otm_puts_sorted) >= 2 and len(otm_calls_sorted) >= 2:
                put_sell = otm_puts_sorted.iloc[0]
                put_buy = otm_puts_sorted.iloc[1]
                call_sell = otm_calls_sorted.iloc[0]
                call_buy = otm_calls_sorted.iloc[1]
                
                strikes = [put_buy['strike'], put_sell['strike'], call_sell['strike'], call_buy['strike']]
                premiums = [put_buy['lastPrice'], put_sell['lastPrice'], call_sell['lastPrice'], call_buy['lastPrice']]
                
                prices, payoffs = self.calculate_iron_condor(current_price, strikes, premiums)
                
                net_premium = (put_sell['lastPrice'] - put_buy['lastPrice'] + 
                              call_sell['lastPrice'] - call_buy['lastPrice'])
                
                strategies.append({
                    'name': 'Iron Condor',
                    'description': f"Buy Put ${put_buy['strike']:.2f}, Sell Put ${put_sell['strike']:.2f}, Sell Call ${call_sell['strike']:.2f}, Buy Call ${call_buy['strike']:.2f}",
                    'expiration': nearest_exp,
                    'strikes': strikes,
                    'premium': net_premium,
                    'cost': 0,  # Net credit
                    'maxProfit': net_premium * 100,
                    'maxLoss': max(put_sell['strike'] - put_buy['strike'], 
                                   call_buy['strike'] - call_sell['strike']) * 100 - net_premium * 100,
                    'prices': prices,
                    'payoffs': payoffs
                })
        
        except Exception as e:
            print(f"Error suggesting strategies: {e}")
        
        return strategies

@app.route('/')
def index():
    """Render main dashboard page"""
    return render_template('index.html')

@app.route('/api/options/<ticker>')
def get_options(ticker):
    """API endpoint to fetch options data and strategies"""
    try:
        analyzer = OptionsAnalyzer(ticker.upper())
        
        # Get current price
        current_price = analyzer.get_current_price()
        if current_price is None:
            return jsonify({'error': 'Unable to fetch stock price. Please check ticker symbol.'}), 400
        
        # Get options data
        options_df, _ = analyzer.get_options_data()
        if options_df is None or options_df.empty:
            return jsonify({'error': 'No options data available for this ticker.'}), 400
        
        # Convert to records for JSON serialization
        options_list = options_df.to_dict('records')
        
        # Get strategy suggestions
        strategies = analyzer.suggest_strategies(options_df, current_price)
        
        return jsonify({
            'ticker': ticker.upper(),
            'currentPrice': round(current_price, 2),
            'options': options_list,
            'strategies': strategies
        })
    
    except Exception as e:
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500

@app.route('/api/market-data/<ticker>')
def get_market_data_for_ai(ticker):
    """Return a structured payload ready for the AI recommendation engine.

    Includes OHLC history, SPY trend, VIX, option chain with BS Greeks,
    and historical volatility.
    """
    try:
        ticker = ticker.upper()
        analyzer = OptionsAnalyzer(ticker)
        stock = analyzer.stock

        current_price = analyzer.get_current_price()
        if current_price is None:
            return jsonify({'error': 'Unable to fetch stock price'}), 400

        # OHLC (last 60 trading days)
        hist = stock.history(period='60d')
        ohlc_daily = [
            {
                'date': date.strftime('%Y-%m-%d'),
                'open': round(float(row['Open']), 2),
                'high': round(float(row['High']), 2),
                'low': round(float(row['Low']), 2),
                'close': round(float(row['Close']), 2),
                'volume': int(row['Volume']),
            }
            for date, row in hist.iterrows()
        ]

        # VIX level
        try:
            vix_hist = yf.Ticker('^VIX').history(period='1d')
            vix_level = round(float(vix_hist['Close'].iloc[-1]), 2) if not vix_hist.empty else None
        except Exception:
            vix_level = None

        # SPY trend (20-day vs 50-day MA)
        try:
            spy_hist = yf.Ticker('SPY').history(period='60d')
            if len(spy_hist) >= 20:
                spy_ma20 = float(spy_hist['Close'].tail(20).mean())
                spy_ma50 = float(spy_hist['Close'].tail(50).mean()) if len(spy_hist) >= 50 else spy_ma20
                spy_current = float(spy_hist['Close'].iloc[-1])
                if spy_current > spy_ma20 and spy_ma20 > spy_ma50:
                    spy_trend = 'up'
                elif spy_current < spy_ma20 and spy_ma20 < spy_ma50:
                    spy_trend = 'down'
                else:
                    spy_trend = 'sideways'
            else:
                spy_trend = 'sideways'
        except Exception:
            spy_trend = 'sideways'

        # 20-day historical volatility (annualised)
        hv = None
        if len(hist) >= 21:
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna().tail(20)
            hv = round(float(log_returns.std() * np.sqrt(252)), 4)

        # Option chain with BS Greeks (strikes within ±25 % of current price)
        risk_free_rate = 0.04
        expirations = stock.options
        if not expirations:
            return jsonify({'error': 'No options data available for this ticker'}), 400

        option_chain = []
        for exp_date in expirations[:4]:
            opt = stock.option_chain(exp_date)
            dte = (pd.to_datetime(exp_date) - pd.Timestamp.now()).days
            T = max(dte / 365.0, 0.001)

            for option_type, chain_df in [('call', opt.calls), ('put', opt.puts)]:
                for _, row in chain_df.iterrows():
                    if abs(row['strike'] - current_price) / current_price > 0.25:
                        continue
                    iv = float(row['impliedVolatility']) if float(row['impliedVolatility']) > 0 else _DEFAULT_IV_FALLBACK
                    greeks = bs_greeks(current_price, float(row['strike']), T, risk_free_rate, iv, option_type)
                    option_chain.append({
                        'expiration': exp_date,
                        'strike': float(row['strike']),
                        'type': option_type,
                        'bid': float(row['bid']),
                        'ask': float(row['ask']),
                        'delta': greeks['delta'],
                        'gamma': greeks['gamma'],
                        'theta': greeks['theta'],
                        'vega': greeks['vega'],
                        'oi': int(row['openInterest']) if pd.notna(row['openInterest']) else 0,
                        'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                        'iv': round(iv, 4),
                    })

        # Approximate IV percentile from ATM IV vs HV ratio
        iv_percentile = None
        atm_iv = next(
            (o['iv'] for o in option_chain
             if o['type'] == 'call' and abs(o['strike'] - current_price) / current_price < 0.02),
            None,
        )
        if atm_iv and hv:
            # Heuristic approximation: ratio of ATM IV to realised HV, capped at 100.
            # A true IV percentile requires a historical IV time-series; use this proxy
            # to give the AI a rough sense of relative richness/cheapness.
            iv_percentile = min(100, int(atm_iv / (hv + 1e-6) * 50))

        payload = {
            'ticker': ticker,
            'stock_price': round(current_price, 2),
            'ohlc_daily': ohlc_daily,
            'market_index_context': {
                'spy_trend': spy_trend,
                'vix_level': vix_level,
            },
            'implied_volatility_percentile': iv_percentile,
            'historical_volatility': hv,
            'risk_free_rate': risk_free_rate,
            'dividend_yield': 0.0,
            'option_chain': option_chain,
        }
        return jsonify(payload)

    except Exception as e:
        return jsonify({'error': f'Error fetching market data: {str(e)}'}), 500


@app.route('/api/recommend', methods=['POST'])
def get_ai_recommendations():
    """Call the OpenAI API with the multi-strategy system prompt and return JSON recommendations."""
    try:
        from openai import OpenAI  # lazy import; openai is optional

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'error': 'OpenAI API key not configured. '
                         'Set the OPENAI_API_KEY environment variable to enable AI recommendations.'
            }), 503

        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400

        for field in ('ticker', 'stock_price', 'option_chain'):
            if field not in payload:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': AI_SYSTEM_PROMPT},
                {'role': 'user', 'content': json.dumps(payload)},
            ],
            response_format={'type': 'json_object'},
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error getting AI recommendations: {str(e)}'}), 500



@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Return all tracked positions with current price and P&L"""
    positions = load_positions()
    result = []
    total_pnl = 0.0

    for pos in positions:
        current_price, pnl = calculate_position_pnl(pos)
        pos_with_pnl = dict(pos)
        pos_with_pnl['currentPrice'] = current_price
        pos_with_pnl['pnl'] = pnl
        if pnl is not None:
            total_pnl += pnl
        result.append(pos_with_pnl)

    return jsonify({'positions': result, 'totalPnl': round(total_pnl, 2)})


@app.route('/api/positions', methods=['POST'])
def add_position():
    """Add a new position to track"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    required_fields = ['ticker', 'type', 'quantity', 'entryPrice']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    pos_type = data['type']
    if pos_type not in ('stock', 'call', 'put'):
        return jsonify({'error': "type must be 'stock', 'call', or 'put'"}), 400

    if pos_type in ('call', 'put'):
        if 'strike' not in data or 'expiration' not in data:
            return jsonify({'error': 'Options positions require strike and expiration'}), 400

    try:
        quantity = float(data['quantity'])
        entry_price = float(data['entryPrice'])
        if quantity <= 0 or entry_price <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'quantity must be positive and entryPrice must be positive'}), 400

    position = {
        'id': str(uuid.uuid4()),
        'ticker': data['ticker'].upper().strip(),
        'type': pos_type,
        'quantity': quantity,
        'entryPrice': entry_price,
        'entryDate': datetime.now().strftime('%Y-%m-%d'),
    }

    if pos_type in ('call', 'put'):
        try:
            position['strike'] = float(data['strike'])
        except (ValueError, TypeError):
            return jsonify({'error': 'strike must be a number'}), 400
        try:
            expiration_date = datetime.strptime(data['expiration'], '%Y-%m-%d')
        except (ValueError, TypeError):
            return jsonify({'error': 'expiration must be in YYYY-MM-DD format'}), 400
        position['expiration'] = expiration_date.strftime('%Y-%m-%d')

    positions = load_positions()
    positions.append(position)
    save_positions(positions)

    return jsonify({'success': True, 'position': position}), 201


@app.route('/api/positions/<position_id>', methods=['DELETE'])
def delete_position(position_id):
    """Remove a position by id"""
    positions = load_positions()
    new_positions = [p for p in positions if p.get('id') != position_id]
    if len(new_positions) == len(positions):
        return jsonify({'error': 'Position not found'}), 404
    save_positions(new_positions)
    return jsonify({'success': True})


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)

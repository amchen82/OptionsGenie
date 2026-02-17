from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

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

if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)

"""
Demo version of OptionsGenie app with mock data for testing
Use this when Yahoo Finance API is not accessible
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

class MockOptionsAnalyzer:
    """Mock analyzer for demonstration purposes"""
    
    def __init__(self, ticker):
        self.ticker = ticker
        # Mock prices for common tickers
        self.mock_prices = {
            'AAPL': 150.0,
            'MSFT': 380.0,
            'TSLA': 200.0,
            'GOOGL': 140.0,
            'AMZN': 170.0,
            'META': 450.0,
            'NVDA': 700.0,
            'AMD': 150.0,
            'SPY': 500.0,
            'QQQ': 400.0,
        }
        
    def get_current_price(self):
        """Get mock stock price"""
        if self.ticker in self.mock_prices:
            return self.mock_prices[self.ticker]
        # Default price for unknown tickers
        return 100.0
    
    def get_options_data(self):
        """Generate mock options data"""
        current_price = self.get_current_price()
        
        # Create expiration dates
        today = datetime.now()
        expirations = [
            (today + timedelta(days=7)).strftime('%Y-%m-%d'),
            (today + timedelta(days=14)).strftime('%Y-%m-%d'),
            (today + timedelta(days=30)).strftime('%Y-%m-%d'),
            (today + timedelta(days=60)).strftime('%Y-%m-%d'),
            (today + timedelta(days=90)).strftime('%Y-%m-%d'),
        ]
        
        options_data = []
        
        for exp_date in expirations:
            days_to_expiry = (datetime.strptime(exp_date, '%Y-%m-%d') - today).days
            
            # Create strikes around current price
            strikes = np.arange(current_price * 0.85, current_price * 1.15, current_price * 0.025)
            
            for strike in strikes:
                # Calculate realistic premiums
                moneyness = abs(strike - current_price) / current_price
                time_factor = np.sqrt(days_to_expiry / 365.0)
                base_vol = 0.30
                
                # Call premiums
                if strike > current_price:  # OTM
                    call_premium = max(0.1, (strike - current_price) * 0.4 + base_vol * current_price * time_factor * 0.3)
                else:  # ITM
                    call_premium = (current_price - strike) + base_vol * current_price * time_factor * 0.4
                
                # Put premiums
                if strike < current_price:  # OTM
                    put_premium = max(0.1, (current_price - strike) * 0.4 + base_vol * current_price * time_factor * 0.3)
                else:  # ITM
                    put_premium = (strike - current_price) + base_vol * current_price * time_factor * 0.4
                
                # Add calls
                options_data.append({
                    'type': 'call',
                    'strike': strike,
                    'lastPrice': call_premium,
                    'bid': call_premium * 0.98,
                    'ask': call_premium * 1.02,
                    'volume': int(np.random.randint(10, 500)),
                    'openInterest': int(np.random.randint(100, 2000)),
                    'impliedVolatility': base_vol + np.random.uniform(-0.05, 0.05),
                    'expiration': exp_date,
                    'daysToExpiry': days_to_expiry
                })
                
                # Add puts
                options_data.append({
                    'type': 'put',
                    'strike': strike,
                    'lastPrice': put_premium,
                    'bid': put_premium * 0.98,
                    'ask': put_premium * 1.02,
                    'volume': int(np.random.randint(10, 500)),
                    'openInterest': int(np.random.randint(100, 2000)),
                    'impliedVolatility': base_vol + np.random.uniform(-0.05, 0.05),
                    'expiration': exp_date,
                    'daysToExpiry': days_to_expiry
                })
        
        return pd.DataFrame(options_data), current_price
    
    def calculate_covered_call(self, current_price, strike, premium, shares=100):
        """Calculate covered call strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        payoffs = []
        for price in stock_prices:
            stock_pnl = (price - current_price) * shares
            call_pnl = premium * shares if price <= strike else (premium * shares - (price - strike) * shares)
            payoffs.append(stock_pnl + call_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_protective_put(self, current_price, strike, premium, shares=100):
        """Calculate protective put strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        payoffs = []
        for price in stock_prices:
            stock_pnl = (price - current_price) * shares
            put_pnl = -premium * shares if price >= strike else ((strike - price) * shares - premium * shares)
            payoffs.append(stock_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_long_straddle(self, current_price, strike, call_premium, put_premium, contracts=1):
        """Calculate long straddle strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        payoffs = []
        for price in stock_prices:
            call_pnl = -call_premium * 100 * contracts if price <= strike else ((price - strike) * 100 * contracts - call_premium * 100 * contracts)
            put_pnl = -put_premium * 100 * contracts if price >= strike else ((strike - price) * 100 * contracts - put_premium * 100 * contracts)
            payoffs.append(call_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_long_strangle(self, current_price, call_strike, put_strike, call_premium, put_premium, contracts=1):
        """Calculate long strangle strategy payoff"""
        stock_prices = np.linspace(current_price * 0.7, current_price * 1.3, 50)
        
        payoffs = []
        for price in stock_prices:
            call_pnl = -call_premium * 100 * contracts if price <= call_strike else ((price - call_strike) * 100 * contracts - call_premium * 100 * contracts)
            put_pnl = -put_premium * 100 * contracts if price >= put_strike else ((put_strike - price) * 100 * contracts - put_premium * 100 * contracts)
            payoffs.append(call_pnl + put_pnl)
        
        return stock_prices.tolist(), payoffs
    
    def calculate_iron_condor(self, current_price, strikes, premiums, contracts=1):
        """Calculate iron condor strategy payoff"""
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
            # Get ATM strike
            atm_strike = options_df.iloc[(options_df['strike'] - current_price).abs().argsort()[:1]]['strike'].values[0]
            
            # Get nearest expiration
            nearest_exp = options_df['expiration'].min()
            nearest_options = options_df[options_df['expiration'] == nearest_exp]
            
            # 1. Covered Call
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
            
            # 2. Protective Put
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
            
            # 3. Long Straddle
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
            
            # 4. Long Strangle
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
            
            # 5. Iron Condor
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
                    'cost': 0,
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
        analyzer = MockOptionsAnalyzer(ticker.upper())
        
        # Get current price
        current_price = analyzer.get_current_price()
        
        # Get options data
        options_df, _ = analyzer.get_options_data()
        
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
    app.run(debug=False, host='0.0.0.0', port=5000)

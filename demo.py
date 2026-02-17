"""
Demo script to test OptionsGenie functionality with mock data
This demonstrates the dashboard works correctly when options data is available
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Mock options data for demonstration
def create_mock_options_data(ticker='AAPL', current_price=150.0):
    """Create realistic mock options data for testing"""
    
    print(f"\n{'='*60}")
    print(f"OptionsGenie Demo - Analyzing {ticker}")
    print(f"Current Stock Price: ${current_price:.2f}")
    print(f"{'='*60}\n")
    
    # Create expiration dates
    today = datetime.now()
    expirations = [
        (today + timedelta(days=7)).strftime('%Y-%m-%d'),
        (today + timedelta(days=14)).strftime('%Y-%m-%d'),
        (today + timedelta(days=30)).strftime('%Y-%m-%d'),
    ]
    
    options_data = []
    
    for exp_date in expirations:
        days_to_expiry = (datetime.strptime(exp_date, '%Y-%m-%d') - today).days
        
        # Create strikes around current price
        strikes = np.arange(current_price * 0.90, current_price * 1.10, 2.5)
        
        for strike in strikes:
            # Calculate realistic premiums based on moneyness and time
            moneyness = abs(strike - current_price) / current_price
            time_factor = np.sqrt(days_to_expiry / 365.0)
            base_vol = 0.30
            
            # Call premiums
            if strike > current_price:  # OTM
                call_premium = max(0.1, (strike - current_price) * 0.5 + base_vol * current_price * time_factor * 0.2)
            else:  # ITM
                call_premium = (current_price - strike) + base_vol * current_price * time_factor * 0.3
            
            # Put premiums
            if strike < current_price:  # OTM
                put_premium = max(0.1, (current_price - strike) * 0.5 + base_vol * current_price * time_factor * 0.2)
            else:  # ITM
                put_premium = (strike - current_price) + base_vol * current_price * time_factor * 0.3
            
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


def demonstrate_strategies(options_df, current_price):
    """Demonstrate strategy calculations"""
    
    print("AVAILABLE OPTIONS (Sample):")
    print("-" * 60)
    sample = options_df.head(10)[['type', 'strike', 'lastPrice', 'expiration', 'daysToExpiry']]
    print(sample.to_string(index=False))
    print(f"\n... and {len(options_df) - 10} more options\n")
    
    print("\nRECOMMENDED OPTIONS STRATEGIES:")
    print("=" * 60)
    
    # Get nearest expiration
    nearest_exp = options_df['expiration'].min()
    nearest_options = options_df[options_df['expiration'] == nearest_exp]
    
    # 1. Covered Call
    otm_calls = nearest_options[(nearest_options['type'] == 'call') & 
                                (nearest_options['strike'] > current_price)]
    if not otm_calls.empty:
        call = otm_calls.iloc[0]
        initial_cost = current_price * 100 - call['lastPrice'] * 100
        max_profit = (call['strike'] - current_price) * 100 + call['lastPrice'] * 100
        
        print("\n1. COVERED CALL")
        print(f"   Strategy: Own 100 shares + Sell 1 Call at ${call['strike']:.2f}")
        print(f"   Expiration: {nearest_exp} ({call['daysToExpiry']} days)")
        print(f"   Premium Received: ${call['lastPrice']:.2f} per share (${call['lastPrice']*100:.2f} total)")
        print(f"   Initial Cost: ${initial_cost:.2f}")
        print(f"   Max Profit: ${max_profit:.2f} (if stock >= ${call['strike']:.2f})")
        print(f"   Max Loss: Unlimited (if stock drops)")
        print(f"   Breakeven: ${current_price - call['lastPrice']:.2f}")
    
    # 2. Protective Put
    atm_puts = nearest_options[(nearest_options['type'] == 'put') & 
                               (nearest_options['strike'] <= current_price)]
    if not atm_puts.empty:
        put = atm_puts.iloc[0]
        initial_cost = current_price * 100 + put['lastPrice'] * 100
        max_loss = (current_price - put['strike']) * 100 + put['lastPrice'] * 100
        
        print("\n2. PROTECTIVE PUT")
        print(f"   Strategy: Own 100 shares + Buy 1 Put at ${put['strike']:.2f}")
        print(f"   Expiration: {nearest_exp} ({put['daysToExpiry']} days)")
        print(f"   Premium Paid: ${put['lastPrice']:.2f} per share (${put['lastPrice']*100:.2f} total)")
        print(f"   Initial Cost: ${initial_cost:.2f}")
        print(f"   Max Profit: Unlimited (if stock rises)")
        print(f"   Max Loss: ${max_loss:.2f} (protected below ${put['strike']:.2f})")
        print(f"   Breakeven: ${current_price + put['lastPrice']:.2f}")
    
    # 3. Long Straddle
    atm_strike = nearest_options.iloc[(nearest_options['strike'] - current_price).abs().argsort()[:1]]['strike'].values[0]
    atm_call = nearest_options[(nearest_options['type'] == 'call') & 
                               (abs(nearest_options['strike'] - atm_strike) < 1)]
    atm_put = nearest_options[(nearest_options['type'] == 'put') & 
                              (abs(nearest_options['strike'] - atm_strike) < 1)]
    
    if not atm_call.empty and not atm_put.empty:
        call = atm_call.iloc[0]
        put = atm_put.iloc[0]
        total_cost = (call['lastPrice'] + put['lastPrice']) * 100
        upper_breakeven = atm_strike + call['lastPrice'] + put['lastPrice']
        lower_breakeven = atm_strike - call['lastPrice'] - put['lastPrice']
        
        print("\n3. LONG STRADDLE")
        print(f"   Strategy: Buy 1 Call + Buy 1 Put at ${atm_strike:.2f}")
        print(f"   Expiration: {nearest_exp} ({call['daysToExpiry']} days)")
        print(f"   Premium Paid: ${call['lastPrice'] + put['lastPrice']:.2f} per share (${total_cost:.2f} total)")
        print(f"   Initial Cost: ${total_cost:.2f}")
        print(f"   Max Profit: Unlimited (needs large move)")
        print(f"   Max Loss: ${total_cost:.2f} (if stock stays at ${atm_strike:.2f})")
        print(f"   Breakeven: ${lower_breakeven:.2f} or ${upper_breakeven:.2f}")
    
    # 4. Long Strangle
    otm_calls = nearest_options[(nearest_options['type'] == 'call') & 
                                (nearest_options['strike'] > current_price * 1.03)]
    otm_puts = nearest_options[(nearest_options['type'] == 'put') & 
                               (nearest_options['strike'] < current_price * 0.97)]
    
    if not otm_calls.empty and not otm_puts.empty:
        call = otm_calls.iloc[0]
        put = otm_puts.iloc[0]
        total_cost = (call['lastPrice'] + put['lastPrice']) * 100
        upper_breakeven = call['strike'] + call['lastPrice'] + put['lastPrice']
        lower_breakeven = put['strike'] - call['lastPrice'] - put['lastPrice']
        
        print("\n4. LONG STRANGLE")
        print(f"   Strategy: Buy 1 Call at ${call['strike']:.2f} + Buy 1 Put at ${put['strike']:.2f}")
        print(f"   Expiration: {nearest_exp} ({call['daysToExpiry']} days)")
        print(f"   Premium Paid: ${call['lastPrice'] + put['lastPrice']:.2f} per share (${total_cost:.2f} total)")
        print(f"   Initial Cost: ${total_cost:.2f}")
        print(f"   Max Profit: Unlimited (needs large move)")
        print(f"   Max Loss: ${total_cost:.2f} (if stock between ${put['strike']:.2f} and ${call['strike']:.2f})")
        print(f"   Breakeven: ${lower_breakeven:.2f} or ${upper_breakeven:.2f}")
    
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
        
        net_credit = (put_sell['lastPrice'] - put_buy['lastPrice'] + 
                     call_sell['lastPrice'] - call_buy['lastPrice']) * 100
        max_loss = max(put_sell['strike'] - put_buy['strike'], 
                      call_buy['strike'] - call_sell['strike']) * 100 - net_credit
        
        print("\n5. IRON CONDOR")
        print(f"   Strategy: Buy Put ${put_buy['strike']:.2f}, Sell Put ${put_sell['strike']:.2f},")
        print(f"            Sell Call ${call_sell['strike']:.2f}, Buy Call ${call_buy['strike']:.2f}")
        print(f"   Expiration: {nearest_exp} ({put_sell['daysToExpiry']} days)")
        print(f"   Net Credit: ${net_credit:.2f}")
        print(f"   Initial Cost: $0 (net credit received)")
        print(f"   Max Profit: ${net_credit:.2f} (if stock between ${put_sell['strike']:.2f} and ${call_sell['strike']:.2f})")
        print(f"   Max Loss: ${max_loss:.2f}")
        print(f"   Profit Zone: ${put_sell['strike']:.2f} to ${call_sell['strike']:.2f}")
    
    print("\n" + "=" * 60)
    print("\nNOTE: These calculations assume holding until expiration.")
    print("Actual profits/losses will vary based on when you close positions.")
    print("\n")


if __name__ == '__main__':
    # Test with different tickers
    test_tickers = [
        ('AAPL', 150.0),
        ('MSFT', 380.0),
        ('TSLA', 200.0),
    ]
    
    for ticker, price in test_tickers:
        options_df, current_price = create_mock_options_data(ticker, price)
        demonstrate_strategies(options_df, current_price)
        print("\n" + "="*80 + "\n")

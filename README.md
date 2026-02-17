# OptionsGenie

An interactive options trading dashboard that analyzes stock options and displays various trading strategies with potential profit/loss calculations.

## Features

- **Stock Ticker Input**: Enter any stock ticker symbol to analyze
- **Real-Time Options Data**: Fetches current options prices from Yahoo Finance for different strike prices and expiration dates
- **Multiple Strategies**: Displays 5 popular options strategies:
  - **Covered Call**: Own stock + Sell call for income
  - **Protective Put**: Own stock + Buy put for downside protection
  - **Long Straddle**: Buy call + Buy put at same strike for volatility plays
  - **Long Strangle**: Buy OTM call + Buy OTM put for volatility plays
  - **Iron Condor**: Sell OTM put spread + Sell OTM call spread for premium collection
- **Visual Payoff Diagrams**: Interactive charts showing profit/loss at different stock prices
- **Options Chain Display**: Complete table of available options contracts with filtering
- **Strategy Details**: Shows max profit, max loss, initial cost, and expiration for each strategy

## Installation

1. Clone the repository:
```bash
git clone https://github.com/amchen82/OptionsGenie.git
cd OptionsGenie
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Dashboard Preview

![OptionsGenie Dashboard](https://github.com/user-attachments/assets/a076540e-edf1-42b3-b211-7d90b21cf653)
*Initial dashboard with ticker input*

![Options Analysis](https://github.com/user-attachments/assets/e66df242-ea58-48c2-946f-2a028ecd2e10)
*Complete analysis showing strategies and options data*

### Running the Application

1. Start the Flask web server:
```bash
python3 app.py
```

   **Note**: For testing purposes when Yahoo Finance API is not accessible (e.g., in restricted networks), use the demo version:
```bash
python3 app_demo.py
```
   The demo version uses mock data for common tickers (AAPL, MSFT, TSLA, etc.)

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Enter a stock ticker symbol (e.g., AAPL, MSFT, TSLA) and click "Analyze Options"

4. View the recommended strategies, payoff diagrams, and available options contracts

## Technical Details

### Backend
- **Flask**: Web framework for API and serving the dashboard
- **yfinance**: Fetches real-time stock and options data from Yahoo Finance
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical calculations for strategy payoffs

### Frontend
- **HTML/CSS/JavaScript**: Clean, responsive dashboard interface
- **Chart.js**: Interactive payoff diagrams showing profit/loss

### Strategy Calculations
Each strategy calculates profit/loss across a range of stock prices at expiration:
- Considers premium paid/received
- Accounts for option intrinsic value
- Shows breakeven points and maximum profit/loss scenarios

## How Options Strategies Work

1. **Covered Call**: Generate income by selling calls on stock you own. Profit is capped but you collect premium.

2. **Protective Put**: Protect against downside by buying puts. Acts as insurance for your stock position.

3. **Long Straddle**: Profit from large moves in either direction by buying both calls and puts at the same strike.

4. **Long Strangle**: Similar to straddle but cheaper - uses out-of-the-money options on both sides.

5. **Iron Condor**: Collect premium by selling options on both sides while limiting risk with further OTM options.

## Notes

- Options data requires internet access to Yahoo Finance APIs
- Strategies use reasonable strikes based on current stock price
- Calculations assume holding positions until expiration
- This tool is for educational purposes only - not financial advice

## Future Enhancements

- Add more strategies (bull call spread, bear put spread, butterfly, etc.)
- Historical volatility analysis
- Greeks calculation (delta, gamma, theta, vega)
- Portfolio tracking and multi-ticker analysis
- Real-time price updates
- Custom strategy builder 

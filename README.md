# OptionsGenie

An interactive options trading dashboard that analyzes stock options, displays various trading strategies with potential profit/loss calculations, and tracks your real-time portfolio P&L.

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
- **Portfolio Tracker**: Monitor real-time unrealized P&L for stocks and options positions, with day-over-day P&L history charting

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

   **For development with debug mode**:
```bash
FLASK_DEBUG=true python3 app.py
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

## Portfolio Position Tracker

Track your stocks and options positions with real-time unrealized P&L right from the dashboard.

### Accessing the Tracker

The **Portfolio Tracker** widget is always visible at the bottom of the main dashboard (`/`).  
For a dedicated full-featured view (grouped tables, P&L history chart) navigate to:

```
http://localhost:5000/positions
```

### Adding a Position

Fill in the form in the Portfolio Tracker section:

| Field | Description |
|-------|-------------|
| **Ticker** | Stock symbol (e.g. `AAPL`) |
| **Type** | `Stock`, `Call Option`, or `Put Option` |
| **Qty / Contracts** | Number of shares or option contracts |
| **Entry Price** | Your average cost per share or per contract (dollar value) |
| **Strike** *(options only)* | Option strike price |
| **Expiration** *(options only)* | Expiration date in `YYYY-MM-DD` format |

Click **Add** to save. Positions are stored in `positions.json` and survive server restarts.

### P&L Calculations

| Position Type | Formula |
|---------------|---------|
| Stock | `(current_price − entry_price) × quantity` |
| Call / Put | `(current_price − entry_price) × quantity × 100` |

Live prices are fetched from Yahoo Finance each time the positions list is loaded.

### REST API

The tracker is backed by three REST endpoints.

#### Retrieve all positions

```
GET /api/positions
```

**Response**

```json
{
  "positions": [
    {
      "id": "4ea493cb-...",
      "ticker": "AAPL",
      "type": "stock",
      "quantity": 10,
      "entryPrice": 150.0,
      "entryDate": "2026-03-01",
      "currentPrice": 175.0,
      "pnl": 250.0
    }
  ],
  "totalPnl": 250.0
}
```

#### Add a position

```
POST /api/positions
Content-Type: application/json
```

**Stock example**

```json
{
  "ticker": "AAPL",
  "type": "stock",
  "quantity": 10,
  "entryPrice": 150.0
}
```

**Call option example**

```json
{
  "ticker": "TSLA",
  "type": "call",
  "quantity": 2,
  "entryPrice": 5.0,
  "strike": 250.0,
  "expiration": "2027-01-16"
}
```

**Response (201 Created)**

```json
{
  "success": true,
  "position": {
    "id": "4ea493cb-...",
    "ticker": "TSLA",
    "type": "call",
    "quantity": 2,
    "entryPrice": 5.0,
    "strike": 250.0,
    "expiration": "2027-01-16",
    "entryDate": "2026-03-01"
  }
}
```

#### Remove a position

```
DELETE /api/positions/<id>
```

**Response (200 OK)**

```json
{ "success": true }
```

#### Retrieve P&L history

```
GET /api/positions/pnl-history
```

Returns daily total P&L snapshots (last 90 days) used to render the history chart on the `/positions` page.

**Response**

```json
{
  "history": [
    { "date": "2026-03-01", "totalPnl": 120.50 },
    { "date": "2026-03-02", "totalPnl": 250.00 }
  ]
}
```

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
- Real-time price updates via WebSocket
- Custom strategy builder

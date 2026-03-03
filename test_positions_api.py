"""Tests for the portfolio position tracking API endpoints.

Covers:
  GET  /api/positions
  POST /api/positions
  DELETE /api/positions/<id>
  GET  /api/positions/pnl-history
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import app as flask_app


class PositionsAPITestCase(unittest.TestCase):
    """Integration tests for the /api/positions endpoints."""

    def setUp(self):
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()

        # Redirect both data files to temporary files so tests are isolated
        self._tmp_dir = tempfile.mkdtemp()
        self._positions_file = os.path.join(self._tmp_dir, 'positions.json')
        self._pnl_file = os.path.join(self._tmp_dir, 'pnl_history.json')

        self._orig_positions_file = flask_app.POSITIONS_FILE
        self._orig_pnl_file = flask_app.PNL_HISTORY_FILE
        flask_app.POSITIONS_FILE = self._positions_file
        flask_app.PNL_HISTORY_FILE = self._pnl_file

    def tearDown(self):
        flask_app.POSITIONS_FILE = self._orig_positions_file
        flask_app.PNL_HISTORY_FILE = self._orig_pnl_file
        # Clean up temp files
        for f in (self._positions_file, self._pnl_file):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(self._tmp_dir)

    # ------------------------------------------------------------------
    # GET /api/positions
    # ------------------------------------------------------------------

    def test_get_positions_empty(self):
        """GET returns empty list and zero P&L when no positions stored."""
        resp = self.client.get('/api/positions')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('positions', data)
        self.assertIn('totalPnl', data)
        self.assertEqual(data['positions'], [])
        self.assertEqual(data['totalPnl'], 0.0)

    def test_get_positions_returns_stored_positions(self):
        """GET returns previously added positions."""
        # Add a stock position first
        self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'stock',
            'quantity': 10,
            'entryPrice': 150.0,
        })
        resp = self.client.get('/api/positions')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data['positions']), 1)
        self.assertEqual(data['positions'][0]['ticker'], 'AAPL')

    # ------------------------------------------------------------------
    # POST /api/positions – success cases
    # ------------------------------------------------------------------

    def test_post_stock_position(self):
        """POST with valid stock payload returns 201 and persists position."""
        payload = {
            'ticker': 'MSFT',
            'type': 'stock',
            'quantity': 5,
            'entryPrice': 300.0,
        }
        resp = self.client.post('/api/positions', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        pos = data['position']
        self.assertEqual(pos['ticker'], 'MSFT')
        self.assertEqual(pos['type'], 'stock')
        self.assertEqual(pos['quantity'], 5)
        self.assertEqual(pos['entryPrice'], 300.0)
        self.assertIn('id', pos)
        self.assertIn('entryDate', pos)

    def test_post_call_option_position(self):
        """POST with a call option payload returns 201."""
        payload = {
            'ticker': 'TSLA',
            'type': 'call',
            'quantity': 2,
            'entryPrice': 5.0,
            'strike': 250.0,
            'expiration': '2027-01-16',
        }
        resp = self.client.post('/api/positions', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        pos = data['position']
        self.assertEqual(pos['type'], 'call')
        self.assertEqual(pos['strike'], 250.0)
        self.assertEqual(pos['expiration'], '2027-01-16')

    def test_post_put_option_position(self):
        """POST with a put option payload returns 201."""
        payload = {
            'ticker': 'SPY',
            'type': 'put',
            'quantity': 1,
            'entryPrice': 3.5,
            'strike': 500.0,
            'expiration': '2027-03-21',
        }
        resp = self.client.post('/api/positions', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        pos = data['position']
        self.assertEqual(pos['type'], 'put')

    def test_ticker_uppercased(self):
        """POST normalises ticker to uppercase."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'aapl',
            'type': 'stock',
            'quantity': 1,
            'entryPrice': 100.0,
        })
        self.assertEqual(resp.status_code, 201)
        pos = resp.get_json()['position']
        self.assertEqual(pos['ticker'], 'AAPL')

    # ------------------------------------------------------------------
    # POST /api/positions – validation errors
    # ------------------------------------------------------------------

    def test_post_missing_required_field(self):
        """POST without 'ticker' returns 400."""
        resp = self.client.post('/api/positions', json={
            'type': 'stock',
            'quantity': 1,
            'entryPrice': 100.0,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    def test_post_invalid_type(self):
        """POST with unknown position type returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'invalid_type',
            'quantity': 1,
            'entryPrice': 100.0,
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_option_without_strike_returns_400(self):
        """POST a call option without strike returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'call',
            'quantity': 1,
            'entryPrice': 5.0,
            'expiration': '2027-01-16',
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_option_without_expiration_returns_400(self):
        """POST a put option without expiration returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'put',
            'quantity': 1,
            'entryPrice': 5.0,
            'strike': 200.0,
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_invalid_expiration_format_returns_400(self):
        """POST with non-ISO expiration date returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'call',
            'quantity': 1,
            'entryPrice': 5.0,
            'strike': 200.0,
            'expiration': '16/01/2027',  # wrong format
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_zero_quantity_returns_400(self):
        """POST with zero quantity returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'stock',
            'quantity': 0,
            'entryPrice': 100.0,
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_negative_entry_price_returns_400(self):
        """POST with negative entry price returns 400."""
        resp = self.client.post('/api/positions', json={
            'ticker': 'AAPL',
            'type': 'stock',
            'quantity': 1,
            'entryPrice': -50.0,
        })
        self.assertEqual(resp.status_code, 400)

    def test_post_empty_body_returns_400(self):
        """POST with no JSON body returns a client error (400 or 415)."""
        resp = self.client.post('/api/positions',
                                data='not json',
                                content_type='text/plain')
        self.assertIn(resp.status_code, (400, 415))

    # ------------------------------------------------------------------
    # DELETE /api/positions/<id>
    # ------------------------------------------------------------------

    def test_delete_existing_position(self):
        """DELETE removes the position and returns success."""
        add_resp = self.client.post('/api/positions', json={
            'ticker': 'NVDA',
            'type': 'stock',
            'quantity': 3,
            'entryPrice': 800.0,
        })
        position_id = add_resp.get_json()['position']['id']

        del_resp = self.client.delete(f'/api/positions/{position_id}')
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json()['success'])

        # Confirm it's gone
        get_resp = self.client.get('/api/positions')
        positions = get_resp.get_json()['positions']
        ids = [p['id'] for p in positions]
        self.assertNotIn(position_id, ids)

    def test_delete_nonexistent_position_returns_404(self):
        """DELETE with a non-existent ID returns 404."""
        resp = self.client.delete('/api/positions/does-not-exist')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('error', resp.get_json())

    # ------------------------------------------------------------------
    # P&L calculation logic
    # ------------------------------------------------------------------

    def test_stock_pnl_calculation(self):
        """Stock P&L = (current_price - entry_price) × quantity."""
        entry_price = 100.0
        current_price = 120.0
        quantity = 10

        # Directly test the helper function
        with patch('app.OptionsAnalyzer') as MockAnalyzer:
            mock_instance = MockAnalyzer.return_value
            mock_instance.get_current_price.return_value = current_price

            position = {
                'ticker': 'TEST',
                'type': 'stock',
                'quantity': quantity,
                'entryPrice': entry_price,
            }
            _, pnl = flask_app.calculate_position_pnl(position)

        expected = (current_price - entry_price) * quantity
        self.assertEqual(pnl, round(expected, 2))

    def test_option_pnl_calculation(self):
        """Option P&L = (current_price - entry_price) × quantity × 100."""
        entry_price = 3.0
        current_price = 5.0
        quantity = 2

        with patch('app.get_current_option_price', return_value=current_price):
            position = {
                'ticker': 'TEST',
                'type': 'call',
                'quantity': quantity,
                'entryPrice': entry_price,
                'strike': 200.0,
                'expiration': '2027-01-16',
            }
            _, pnl = flask_app.calculate_position_pnl(position)

        expected = (current_price - entry_price) * quantity * 100
        self.assertEqual(pnl, round(expected, 2))

    # ------------------------------------------------------------------
    # Data persistence
    # ------------------------------------------------------------------

    def test_persistence_across_requests(self):
        """Positions written by POST are returned by a later GET."""
        self.client.post('/api/positions', json={
            'ticker': 'META',
            'type': 'stock',
            'quantity': 7,
            'entryPrice': 500.0,
        })

        # Simulate a fresh GET (data should come from the JSON file)
        resp = self.client.get('/api/positions')
        tickers = [p['ticker'] for p in resp.get_json()['positions']]
        self.assertIn('META', tickers)

    # ------------------------------------------------------------------
    # GET /api/positions/pnl-history
    # ------------------------------------------------------------------

    def test_pnl_history_empty(self):
        """GET pnl-history returns empty list when no history exists."""
        resp = self.client.get('/api/positions/pnl-history')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('history', data)
        self.assertEqual(data['history'], [])

    def test_pnl_history_recorded_on_get_positions(self):
        """A call to GET /api/positions records a P&L snapshot for today."""
        self.client.get('/api/positions')
        resp = self.client.get('/api/positions/pnl-history')
        history = resp.get_json()['history']
        self.assertGreaterEqual(len(history), 1)
        self.assertIn('date', history[0])
        self.assertIn('totalPnl', history[0])


if __name__ == '__main__':
    unittest.main()

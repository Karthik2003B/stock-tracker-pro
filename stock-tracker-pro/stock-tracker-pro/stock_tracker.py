import yfinance as yf
import sqlite3
import smtplib
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import time
import threading
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import requests
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StockTracker:
    def __init__(self, db_name="stock_tracker.db"):
        self.db_name = db_name
        self.init_database()
        self.alerts = []
        self.tracking_active = False
        
    def init_database(self):
        """Initialize SQLite database for storing stock data and alerts"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Create stocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                change_percent REAL,
                volume INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                threshold REAL NOT NULL,
                email TEXT,
                telegram_chat_id TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create watchlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_to_watchlist(self, symbol: str):
        """Add a stock to the watchlist"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO watchlist (symbol) VALUES (?)", (symbol.upper(),))
            conn.commit()
            conn.close()
            logging.info(f"Added {symbol} to watchlist")
            return True
        except Exception as e:
            logging.error(f"Error adding {symbol} to watchlist: {e}")
            return False
    
    def remove_from_watchlist(self, symbol: str):
        """Remove a stock from the watchlist"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
            conn.commit()
            conn.close()
            logging.info(f"Removed {symbol} from watchlist")
            return True
        except Exception as e:
            logging.error(f"Error removing {symbol} from watchlist: {e}")
            return False
    
    def get_watchlist(self) -> List[str]:
        """Get all stocks in watchlist"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM watchlist ORDER BY added_at")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            return symbols
        except Exception as e:
            logging.error(f"Error fetching watchlist: {e}")
            return []
    
    def get_stock_data(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time stock data using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get current price and other metrics
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                # Fallback: get latest price from history
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                else:
                    return None
            
            previous_close = info.get('previousClose', current_price)
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close else 0
            
            return {
                'symbol': symbol.upper(),
                'price': round(current_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logging.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def store_stock_data(self, stock_data: Dict):
        """Store stock data in database"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stocks (symbol, price, change_percent, volume, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                stock_data['symbol'],
                stock_data['price'],
                stock_data['change_percent'],
                stock_data['volume'],
                stock_data['timestamp']
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error storing stock data: {e}")
    
    def create_alert(self, symbol: str, alert_type: str, threshold: float, 
                    email: Optional[str] = None, telegram_chat_id: Optional[str] = None):
        """Create a price alert"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (symbol, alert_type, threshold, email, telegram_chat_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol.upper(), alert_type, threshold, email, telegram_chat_id))
            conn.commit()
            conn.close()
            logging.info(f"Created {alert_type} alert for {symbol} at {threshold}")
            return True
        except Exception as e:
            logging.error(f"Error creating alert: {e}")
            return False
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE is_active = 1")
            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    'id': row[0],
                    'symbol': row[1],
                    'alert_type': row[2],
                    'threshold': row[3],
                    'email': row[4],
                    'telegram_chat_id': row[5],
                    'is_active': row[6],
                    'created_at': row[7]
                })
            conn.close()
            return alerts
        except Exception as e:
            logging.error(f"Error fetching alerts: {e}")
            return []
    
    def send_email_alert(self, email: str, subject: str, message: str, 
                        smtp_server="smtp.gmail.com", smtp_port=587, 
                        sender_email="", sender_password=""):
        """Send email alert"""
        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, email, text)
            server.quit()
            
            logging.info(f"Email alert sent to {email}")
            return True
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            return False
    
    def send_telegram_alert(self, chat_id: str, message: str, bot_token: str):
        """Send Telegram alert"""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                logging.info(f"Telegram alert sent to {chat_id}")
                return True
            else:
                logging.error(f"Telegram API error: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")
            return False
    
    def check_alerts(self, stock_data: Dict, email_config: Dict = None, telegram_config: Dict = None):
        """Check if any alerts should be triggered"""
        alerts = self.get_active_alerts()
        
        for alert in alerts:
            if alert['symbol'] != stock_data['symbol']:
                continue
            
            triggered = False
            current_price = stock_data['price']
            
            if alert['alert_type'] == 'above' and current_price >= alert['threshold']:
                triggered = True
            elif alert['alert_type'] == 'below' and current_price <= alert['threshold']:
                triggered = True
            elif alert['alert_type'] == 'change_above' and stock_data['change_percent'] >= alert['threshold']:
                triggered = True
            elif alert['alert_type'] == 'change_below' and stock_data['change_percent'] <= alert['threshold']:
                triggered = True
            
            if triggered:
                message = f"""
🚨 Stock Alert Triggered! 🚨

Symbol: {stock_data['symbol']}
Current Price: ${current_price}
Change: {stock_data['change']:+.2f} ({stock_data['change_percent']:+.2f}%)
Alert Type: {alert['alert_type']}
Threshold: {alert['threshold']}
Time: {stock_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
                """.strip()
                
                # Send email alert
                if alert['email'] and email_config:
                    self.send_email_alert(
                        alert['email'],
                        f"Stock Alert: {stock_data['symbol']}",
                        message,
                        **email_config
                    )
                
                # Send Telegram alert
                if alert['telegram_chat_id'] and telegram_config:
                    self.send_telegram_alert(
                        alert['telegram_chat_id'],
                        message,
                        telegram_config['bot_token']
                    )
                
                # Deactivate the alert to prevent spam
                self.deactivate_alert(alert['id'])
    
    def deactivate_alert(self, alert_id: int):
        """Deactivate an alert"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("UPDATE alerts SET is_active = 0 WHERE id = ?", (alert_id,))
            conn.commit()
            conn.close()
            logging.info(f"Deactivated alert {alert_id}")
        except Exception as e:
            logging.error(f"Error deactivating alert: {e}")
    
    def get_historical_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Get historical stock data from database"""
        try:
            conn = sqlite3.connect(self.db_name)
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = '''
                SELECT * FROM stocks 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp
            '''
            
            df = pd.read_sql_query(query, conn, params=(symbol.upper(), cutoff_date))
            conn.close()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            return df
        except Exception as e:
            logging.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()
    
    def create_price_chart(self, symbol: str, days: int = 30):
        """Create interactive price chart using Plotly"""
        df = self.get_historical_data(symbol, days)
        
        if df.empty:
            print(f"No historical data available for {symbol}")
            return None
        
        # Create candlestick-style chart (using line chart with price data)
        fig = make_subplots(
            rows=2, cols=1,
            row_width=[0.7, 0.3],
            vertical_spacing=0.1,
            subplot_titles=(f'{symbol} Stock Price', 'Volume')
        )
        
        # Price chart
        fig.add_trace(
            go.Scatter(
                x=df['timestamp'],
                y=df['price'],
                mode='lines+markers',
                name='Price',
                line=dict(color='blue', width=2),
                hovertemplate='<b>%{x}</b><br>Price: $%{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Volume chart
        fig.add_trace(
            go.Bar(
                x=df['timestamp'],
                y=df['volume'],
                name='Volume',
                marker_color='lightblue',
                hovertemplate='<b>%{x}</b><br>Volume: %{y:,}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f'{symbol} Stock Analysis - Last {days} Days',
            xaxis_title='Date',
            height=600,
            showlegend=True,
            template='plotly_white'
        )
        
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        
        return fig
    
    def create_portfolio_dashboard(self):
        """Create portfolio overview dashboard"""
        watchlist = self.get_watchlist()
        
        if not watchlist:
            print("No stocks in watchlist")
            return None
        
        portfolio_data = []
        for symbol in watchlist:
            stock_data = self.get_stock_data(symbol)
            if stock_data:
                portfolio_data.append(stock_data)
        
        if not portfolio_data:
            print("No current data available for watchlist stocks")
            return None
        
        df = pd.DataFrame(portfolio_data)
        
        # Create dashboard with multiple charts
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Current Prices', 'Percent Changes',
                'Market Cap Distribution', 'Volume Comparison'
            ),
            specs=[[{'type': 'bar'}, {'type': 'bar'}],
                   [{'type': 'pie'}, {'type': 'bar'}]]
        )
        
        # Current prices
        fig.add_trace(
            go.Bar(
                x=df['symbol'], y=df['price'],
                name='Current Price',
                marker_color='blue',
                hovertemplate='<b>%{x}</b><br>Price: $%{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Percent changes
        colors = ['green' if x >= 0 else 'red' for x in df['change_percent']]
        fig.add_trace(
            go.Bar(
                x=df['symbol'], y=df['change_percent'],
                name='Change %',
                marker_color=colors,
                hovertemplate='<b>%{x}</b><br>Change: %{y:.2f}%<extra></extra>'
            ),
            row=1, col=2
        )
        
        # Market cap pie chart (if available)
        market_cap_data = df[df['market_cap'].notna()]
        if not market_cap_data.empty:
            fig.add_trace(
                go.Pie(
                    labels=market_cap_data['symbol'],
                    values=market_cap_data['market_cap'],
                    name='Market Cap'
                ),
                row=2, col=1
            )
        
        # Volume comparison
        fig.add_trace(
            go.Bar(
                x=df['symbol'], y=df['volume'],
                name='Volume',
                marker_color='lightblue',
                hovertemplate='<b>%{x}</b><br>Volume: %{y:,}<extra></extra>'
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title='Portfolio Dashboard',
            height=800,
            showlegend=False,
            template='plotly_white'
        )
        
        return fig
    
    def start_tracking(self, interval_minutes: int = 5, email_config: Dict = None, telegram_config: Dict = None):
        """Start continuous stock tracking"""
        self.tracking_active = True
        
        def track():
            while self.tracking_active:
                watchlist = self.get_watchlist()
                
                for symbol in watchlist:
                    stock_data = self.get_stock_data(symbol)
                    if stock_data:
                        self.store_stock_data(stock_data)
                        self.check_alerts(stock_data, email_config, telegram_config)
                        print(f"{stock_data['symbol']}: ${stock_data['price']} ({stock_data['change_percent']:+.2f}%)")
                
                time.sleep(interval_minutes * 60)
        
        tracking_thread = threading.Thread(target=track, daemon=True)
        tracking_thread.start()
        logging.info(f"Started tracking {len(self.get_watchlist())} stocks every {interval_minutes} minutes")
    
    def stop_tracking(self):
        """Stop continuous tracking"""
        self.tracking_active = False
        logging.info("Stopped stock tracking")


# Example usage and demonstration
def main():
    """Demo of the stock tracker functionality"""
    tracker = StockTracker()
    
    # Add some stocks to watchlist
    stocks = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']
    print("Adding stocks to watchlist...")
    for stock in stocks:
        tracker.add_to_watchlist(stock)
    
    # Create some sample alerts
    print("\nCreating sample alerts...")
    tracker.create_alert('AAPL', 'above', 200.0, email='user@example.com')
    tracker.create_alert('TSLA', 'below', 180.0, telegram_chat_id='123456789')
    tracker.create_alert('NVDA', 'change_above', 5.0)  # 5% increase
    
    # Fetch and display current data
    print("\nFetching current stock data...")
    watchlist = tracker.get_watchlist()
    
    for symbol in watchlist:
        stock_data = tracker.get_stock_data(symbol)
        if stock_data:
            tracker.store_stock_data(stock_data)
            print(f"{symbol}: ${stock_data['price']} ({stock_data['change_percent']:+.2f}%)")
    
    # Create and show charts
    print("\nGenerating charts...")
    
    # Individual stock chart (if historical data exists)
    chart = tracker.create_price_chart('AAPL', days=7)
    if chart:
        chart.show()
    
    # Portfolio dashboard
    dashboard = tracker.create_portfolio_dashboard()
    if dashboard:
        dashboard.show()
    
    # Display active alerts
    alerts = tracker.get_active_alerts()
    print(f"\nActive alerts: {len(alerts)}")
    for alert in alerts:
        print(f"- {alert['symbol']}: {alert['alert_type']} {alert['threshold']}")
    
    # Example: Start tracking (uncomment to start continuous monitoring)
    # email_config = {
    #     'smtp_server': 'smtp.gmail.com',
    #     'smtp_port': 587,
    #     'sender_email': 'your-email@gmail.com',
    #     'sender_password': 'your-app-password'
    # }
    # 
    # telegram_config = {
    #     'bot_token': 'YOUR_TELEGRAM_BOT_TOKEN'
    # }
    # 
    # print("\nStarting continuous tracking...")
    # tracker.start_tracking(interval_minutes=1, email_config=email_config, telegram_config=telegram_config)
    
    print("\nDemo completed! Check the generated charts and database file.")


if __name__ == "__main__":
    main()

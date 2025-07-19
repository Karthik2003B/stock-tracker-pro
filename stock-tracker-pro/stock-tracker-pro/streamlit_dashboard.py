import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
from stock_tracker import StockTracker  # Import our main class
import json

# Configure Streamlit page
st.set_page_config(
    page_title="📈 Stock Tracker Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'tracker' not in st.session_state:
    st.session_state.tracker = StockTracker()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .positive { color: #00C851; }
    .negative { color: #ff4444; }
    .neutral { color: #666; }
    .big-font { font-size: 2rem !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("📈 Stock Tracker Pro")
    st.markdown("Real-time stock monitoring with alerts and portfolio analytics")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Auto-refresh settings
        st.subheader("Auto Refresh")
        auto_refresh = st.checkbox("Enable Auto Refresh", value=st.session_state.auto_refresh)
        if auto_refresh:
            refresh_interval = st.selectbox(
                "Refresh Interval (seconds)",
                [15, 30, 60, 300],
                index=1
            )
            st.session_state.refresh_interval = refresh_interval
        
        st.session_state.auto_refresh = auto_refresh
        
        # Manual refresh button
        if st.button("🔄 Refresh Now"):
            st.rerun()
        
        st.divider()
        
        # Notification settings
        st.subheader("📧 Notifications")
        with st.expander("Email Settings"):
            email_enabled = st.checkbox("Enable Email Alerts")
            if email_enabled:
                smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
                smtp_port = st.number_input("SMTP Port", value=587)
                sender_email = st.text_input("Sender Email")
                sender_password = st.text_input("App Password", type="password")
                
                if st.button("Test Email"):
                    if all([sender_email, sender_password]):
                        # Store email config in session state
                        st.session_state.email_config = {
                            'smtp_server': smtp_server,
                            'smtp_port': smtp_port,
                            'sender_email': sender_email,
                            'sender_password': sender_password
                        }
                        st.success("Email configuration saved!")
                    else:
                        st.error("Please fill in all email fields")
        
        with st.expander("Telegram Settings"):
            telegram_enabled = st.checkbox("Enable Telegram Alerts")
            if telegram_enabled:
                bot_token = st.text_input("Bot Token", type="password")
                if bot_token:
                    st.session_state.telegram_config = {'bot_token': bot_token}
                    st.success("Telegram configuration saved!")
    
    # Main content area
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠 Dashboard", 
        "📊 Watchlist", 
        "🚨 Alerts", 
        "📈 Charts", 
        "⚡ Live Tracking"
    ])
    
    with tab1:
        dashboard_tab()
    
    with tab2:
        watchlist_tab()
    
    with tab3:
        alerts_tab()
    
    with tab4:
        charts_tab()
    
    with tab5:
        live_tracking_tab()
    
    # Auto-refresh functionality
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

def dashboard_tab():
    st.header("Portfolio Overview")
    
    tracker = st.session_state.tracker
    watchlist = tracker.get_watchlist()
    
    if not watchlist:
        st.info("📝 Add some stocks to your watchlist to see the dashboard!")
        return
    
    # Fetch current data for all watchlist stocks
    portfolio_data = []
    for symbol in watchlist:
        with st.spinner(f"Fetching {symbol}..."):
            stock_data = tracker.get_stock_data(symbol)
            if stock_data:
                portfolio_data.append(stock_data)
    
    if not portfolio_data:
        st.error("Unable to fetch stock data. Please check your internet connection.")
        return
    
    df = pd.DataFrame(portfolio_data)
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_stocks = len(df)
        st.metric("Total Stocks", total_stocks)
    
    with col2:
        gainers = len(df[df['change_percent'] > 0])
        st.metric("Gainers", gainers, delta=f"{gainers/total_stocks:.1%}")
    
    with col3:
        avg_change = df['change_percent'].mean()
        st.metric(
            "Avg Change", 
            f"{avg_change:.2f}%",
            delta=f"{avg_change:.2f}%"
        )
    
    with col4:
        total_volume = df['volume'].sum()
        st.metric("Total Volume", f"{total_volume:,.0f}")
    
    st.divider()
    
    # Portfolio table
    st.subheader("Current Holdings")
    
    # Format the dataframe for display
    display_df = df.copy()
    display_df['Change'] = display_df['change'].apply(lambda x: f"${x:+.2f}")
    display_df['Change %'] = display_df['change_percent'].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"
    )
    display_df['Price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
    display_df['Volume'] = display_df['volume'].apply(lambda x: f"{x:,}" if pd.notna(x) else "N/A")
    
    # Create a styled table
    styled_df = display_df[['symbol', 'Price', 'Change', 'Change %', 'Volume']].style.applymap(
        lambda x: 'color: green' if '+' in str(x) else 'color: red' if '-' in str(x) else '',
        subset=['Change', 'Change %']
    )
    
    st.dataframe(styled_df, use_container_width=True)
    
    # Portfolio visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Price comparison chart
        fig_prices = px.bar(
            df, 
            x='symbol', 
            y='price',
            title='Current Prices',
            color='change_percent',
            color_continuous_scale='RdYlGn'
        )
        fig_prices.update_layout(height=400)
        st.plotly_chart(fig_prices, use_container_width=True)
    
    with col2:
        # Change percentage chart
        fig_changes = px.bar(
            df,
            x='symbol',
            y='change_percent',
            title='Daily Changes (%)',
            color='change_percent',
            color_continuous_scale='RdYlGn'
        )
        fig_changes.update_layout(height=400)
        st.plotly_chart(fig_changes, use_container_width=True)

def watchlist_tab():
    st.header("📊 Manage Watchlist")
    
    tracker = st.session_state.tracker
    
    # Add new stock
    col1, col2 = st.columns([3, 1])
    with col1:
        new_symbol = st.text_input(
            "Add Stock Symbol", 
            placeholder="e.g., AAPL, GOOGL, MSFT",
            help="Enter a valid stock ticker symbol"
        )
    with col2:
        if st.button("➕ Add Stock", type="primary"):
            if new_symbol:
                if tracker.add_to_watchlist(new_symbol.upper()):
                    st.success(f"Added {new_symbol.upper()} to watchlist!")
                    st.rerun()
                else:
                    st.error("Failed to add stock")
            else:
                st.error("Please enter a stock symbol")
    
    st.divider()
    
    # Current watchlist
    watchlist = tracker.get_watchlist()
    
    if watchlist:
        st.subheader("Current Watchlist")
        
        # Display watchlist with current prices
        for i, symbol in enumerate(watchlist):
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                
                stock_data = tracker.get_stock_data(symbol)
                
                with col1:
                    st.write(f"**{symbol}**")
                
                if stock_data:
                    with col2:
                        st.write(f"${stock_data['price']:.2f}")
                    
                    with col3:
                        change_color = "positive" if stock_data['change'] >= 0 else "negative"
                        st.markdown(
                            f"<span class='{change_color}'>{stock_data['change']:+.2f}</span>",
                            unsafe_allow_html=True
                        )
                    
                    with col4:
                        change_color = "positive" if stock_data['change_percent'] >= 0 else "negative"
                        st.markdown(
                            f"<span class='{change_color}'>{stock_data['change_percent']:+.2f}%</span>",
                            unsafe_allow_html=True
                        )
                else:
                    with col2:
                        st.write("Loading...")
                    with col3:
                        st.write("--")
                    with col4:
                        st.write("--")
                
                with col5:
                    if st.button("🗑️", key=f"remove_{symbol}", help=f"Remove {symbol}"):
                        if tracker.remove_from_watchlist(symbol):
                            st.success(f"Removed {symbol}")
                            st.rerun()
                
                if i < len(watchlist) - 1:
                    st.divider()
    else:
        st.info("Your watchlist is empty. Add some stocks to get started!")

def alerts_tab():
    st.header("🚨 Price Alerts")
    
    tracker = st.session_state.tracker
    watchlist = tracker.get_watchlist()
    
    if not watchlist:
        st.info("Add stocks to your watchlist first to create alerts.")
        return
    
    # Create new alert
    st.subheader("Create New Alert")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        alert_symbol = st.selectbox("Stock Symbol", watchlist)
    
    with col2:
        alert_type = st.selectbox(
            "Alert Type",
            ["above", "below", "change_above", "change_below"],
            format_func=lambda x: {
                "above": "Price Above",
                "below": "Price Below", 
                "change_above": "% Change Above",
                "change_below": "% Change Below"
            }[x]
        )
    
    with col3:
        threshold = st.number_input(
            "Threshold",
            min_value=0.0,
            step=0.01,
            help="Price threshold or percentage change"
        )
    
    with col4:
        st.write("")  # spacing
        st.write("")  # spacing
        
    # Contact method
    col1, col2 = st.columns(2)
    with col1:
        alert_email = st.text_input("Email (optional)", placeholder="your@email.com")
    with col2:
        telegram_chat = st.text_input("Telegram Chat ID (optional)", placeholder="123456789")
    
    if st.button("Create Alert", type="primary"):
        if threshold > 0:
            success = tracker.create_alert(
                alert_symbol, 
                alert_type, 
                threshold,
                alert_email if alert_email else None,
                telegram_chat if telegram_chat else None
            )
            if success:
                st.success("Alert created successfully!")
                st.rerun()
            else:
                st.error("Failed to create alert")
        else:
            st.error("Please enter a valid threshold")
    
    st.divider()
    
    # Display active alerts
    st.subheader("Active Alerts")
    alerts = tracker.get_active_alerts()
    
    if alerts:
        for alert in alerts:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                
                with col1:
                    st.write(f"**{alert['symbol']}**")
                
                with col2:
                    alert_type_display = {
                        "above": f"Price > ${alert['threshold']}",
                        "below": f"Price < ${alert['threshold']}",
                        "change_above": f"Change > {alert['threshold']}%",
                        "change_below": f"Change < {alert['threshold']}%"
                    }
                    st.write(alert_type_display[alert['alert_type']])
                
                with col3:
                    contacts = []
                    if alert['email']:
                        contacts.append("📧")
                    if alert['telegram_chat_id']:
                        contacts.append("📱")
                    st.write(" ".join(contacts) if contacts else "No contact")
                
                with col4:
                    st.write(alert['created_at'][:10])  # Show date only
                
                with col5:
                    if st.button("❌", key=f"deactivate_{alert['id']}", help="Deactivate alert"):
                        tracker.deactivate_alert(alert['id'])
                        st.success("Alert deactivated")
                        st.rerun()
                
                st.divider()
    else:
        st.info("No active alerts. Create some alerts to monitor your stocks!")

def charts_tab():
    st.header("📈 Stock Charts")
    
    tracker = st.session_state.tracker
    watchlist = tracker.get_watchlist()
    
    if not watchlist:
        st.info("Add stocks to your watchlist to view charts.")
        return
    
    # Chart controls
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_symbol = st.selectbox("Select Stock", watchlist)
    
    with col2:
        time_period = st.selectbox(
            "Time Period",
            [7, 30, 90, 180, 365],
            format_func=lambda x: f"{x} days"
        )
    
    if selected_symbol:
        # Get current stock data
        current_data = tracker.get_stock_data(selected_symbol)
        
        if current_data:
            # Display current metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Current Price", f"${current_data['price']:.2f}")
            
            with col2:
                st.metric(
                    "Change",
                    f"${current_data['change']:.2f}",
                    delta=f"{current_data['change_percent']:.2f}%"
                )
            
            with col3:
                if current_data.get('volume'):
                    st.metric("Volume", f"{current_data['volume']:,}")
            
            with col4:
                if current_data.get('market_cap'):
                    market_cap_b = current_data['market_cap'] / 1e9
                    st.metric("Market Cap", f"${market_cap_b:.1f}B")
            
            st.divider()
            
            # Historical chart
            chart = tracker.create_price_chart(selected_symbol, time_period)
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.info(f"No historical data available for {selected_symbol}. Start tracking to build history!")
                
                # Show real-time chart using yfinance data
                st.subheader("Real-time Data")
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(selected_symbol)
                    hist = ticker.history(period=f"{min(time_period, 365)}d")
                    
                    if not hist.empty:
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(
                            x=hist.index,
                            open=hist['Open'],
                            high=hist['High'],
                            low=hist['Low'],
                            close=hist['Close'],
                            name=selected_symbol
                        ))
                        
                        fig.update_layout(
                            title=f"{selected_symbol} Stock Price",
                            yaxis_title="Price ($)",
                            xaxis_title="Date",
                            height=500
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("Unable to fetch historical data")
                        
                except Exception as e:
                    st.error(f"Error fetching real-time data: {e}")
        else:
            st.error(f"Unable to fetch current data for {selected_symbol}")
    
    # Portfolio overview chart
    if len(watchlist) > 1:
        st.divider()
        st.subheader("Portfolio Overview")
        
        dashboard_chart = tracker.create_portfolio_dashboard()
        if dashboard_chart:
            st.plotly_chart(dashboard_chart, use_container_width=True)

def live_tracking_tab():
    st.header("⚡ Live Tracking")
    
    tracker = st.session_state.tracker
    watchlist = tracker.get_watchlist()
    
    if not watchlist:
        st.info("Add stocks to your watchlist to start live tracking.")
        return
    
    # Live tracking controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        tracking_interval = st.selectbox(
            "Update Interval",
            [1, 5, 15, 30, 60],
            format_func=lambda x: f"{x} minute{'s' if x > 1 else ''}",
            index=1
        )
    
    with col2:
        st.write("")  # spacing
        if st.button("🎯 Start Live Tracking", type="primary"):
            # Start tracking in background
            email_config = getattr(st.session_state, 'email_config', None)
            telegram_config = getattr(st.session_state, 'telegram_config', None)
            
            tracker.start_tracking(
                interval_minutes=tracking_interval,
                email_config=email_config,
                telegram_config=telegram_config
            )
            st.success("Live tracking started!")
    
    with col3:
        if st.button("⏹️ Stop Tracking"):
            tracker.stop_tracking()
            st.info("Live tracking stopped")
    
    st.divider()
    
    # Real-time display
    st.subheader("Real-time Prices")
    
    # Create a placeholder for live updates
    placeholder = st.empty()
    
    # Manual update for demonstration
    if st.button("🔄 Update Prices"):
        with placeholder.container():
            for symbol in watchlist:
                with st.spinner(f"Updating {symbol}..."):
                    stock_data = tracker.get_stock_data(symbol)
                    
                    if stock_data:
                        # Store the data
                        tracker.store_stock_data(stock_data)
                        
                        # Check for alerts
                        email_config = getattr(st.session_state, 'email_config', None)
                        telegram_config = getattr(st.session_state, 'telegram_config', None)
                        tracker.check_alerts(stock_data, email_config, telegram_config)
                        
                        # Display the data
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.write(f"**{symbol}**")
                        
                        with col2:
                            st.write(f"${stock_data['price']:.2f}")
                        
                        with col3:
                            change_color = "🟢" if stock_data['change'] >= 0 else "🔴"
                            st.write(f"{change_color} {stock_data['change']:+.2f}")
                        
                        with col4:
                            st.write(f"{stock_data['change_percent']:+.2f}%")
                        
                        st.divider()
    
    # Show recent activity
    st.subheader("Recent Activity")
    
    # Get recent stock data from database for all watchlist symbols
    recent_activity = []
    for symbol in watchlist[:5]:  # Limit to 5 for performance
        df = tracker.get_historical_data(symbol, days=1)
        if not df.empty:
            latest = df.iloc[-1]
            recent_activity.append({
                'Symbol': symbol,
                'Price': f"${latest['price']:.2f}",
                'Change %': f"{latest['change_percent']:+.2f}%",
                'Time': latest['timestamp'].strftime('%H:%M:%S')
            })
    
    if recent_activity:
        st.dataframe(pd.DataFrame(recent_activity), use_container_width=True)
    else:
        st.info("No recent activity. Start tracking to see live updates here!")

if __name__ == "__main__":
    main()

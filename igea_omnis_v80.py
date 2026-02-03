"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    IGEA OMNIS v8.0 - INSTITUTIONAL EDITION                                   ║
║                              Professional Market Intelligence & Portfolio Analytics                           ║
║                                        Bloomberg-Level Terminal                                               ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

Features:
- Advanced Technical Analysis (SMA, EMA, RSI, MACD, Bollinger, Stochastic, ATR, OBV)
- Custom Date Range Selection for all comparisons
- Multi-asset Screening with filters
- Personalized Watchlists
- Sector Heatmaps
- Performance Attribution
- Valuation Metrics (P/E, P/B, P/S, EV/EBITDA)
- Relative Strength Analysis
- Risk Decomposition
- Multi-panel Charts
- Economic Dashboard
- Central Bank Tracker
- And much more...
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta, date
from io import BytesIO
import json
import warnings
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings('ignore')

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logger = logging.getLogger("igea")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Optional imports
try:
    from fredapi import Fred
    FRED_OK = True
except ImportError:
    FRED_OK = False

try:
    from pytrends.request import TrendReq
    TRENDS_OK = True
except ImportError:
    TRENDS_OK = False

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="IGEA OMNIS v8.0 - Institutional",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# API KEYS
# =============================================================================
def load_api_keys():
    """Load API keys from Streamlit secrets or environment variables"""
    keys = {}
    
    # Try to load from Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and st.secrets:
            keys['fred'] = st.secrets.get('fred_api_key', st.secrets.get('FRED_API_KEY', ''))
            keys['finnhub'] = st.secrets.get('finnhub_api_key', st.secrets.get('FINNHUB_API_KEY', ''))
            keys['newsapi'] = st.secrets.get('newsapi_api_key', st.secrets.get('NEWSAPI_API_KEY', ''))
            logger.info("API keys loaded from Streamlit secrets")
            # Filter out empty keys
            keys = {k: v for k, v in keys.items() if v}
            if keys:
                return keys
    except Exception as e:
        logger.debug(f"Could not load from st.secrets: {e}")
    
    # Fallback to environment variables
    keys['fred'] = os.getenv('FRED_API_KEY', '')
    keys['finnhub'] = os.getenv('FINNHUB_API_KEY', '')
    keys['newsapi'] = os.getenv('NEWSAPI_API_KEY', '')
    
    # Filter out empty keys
    keys = {k: v for k, v in keys.items() if v}
    
    if keys:
        logger.info(f"API keys loaded from environment variables: {list(keys.keys())}")
    else:
        logger.warning("No API keys found in secrets or environment variables")
    
    return keys

API_KEYS = load_api_keys()

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
if 'comparison_assets' not in st.session_state:
    st.session_state.comparison_assets = ["SPY", "QQQ", "IWM"]
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {"AAPL": 0.2, "MSFT": 0.2, "GOOGL": 0.2, "AMZN": 0.2, "NVDA": 0.2}
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

# =============================================================================
# COMPREHENSIVE ASSETS DATABASE
# =============================================================================
INDICES = {
    # US Indices
    "S&P 500": {"ticker": "^GSPC", "flag": "🇺🇸", "region": "US", "description": "Large Cap US"},
    "NASDAQ 100": {"ticker": "^NDX", "flag": "🇺🇸", "region": "US", "description": "Tech-Heavy US"},
    "Dow Jones": {"ticker": "^DJI", "flag": "🇺🇸", "region": "US", "description": "Blue Chip US"},
    "Russell 2000": {"ticker": "^RUT", "flag": "🇺🇸", "region": "US", "description": "Small Cap US"},
    "S&P 400 MidCap": {"ticker": "^MID", "flag": "🇺🇸", "region": "US", "description": "Mid Cap US"},
    "VIX": {"ticker": "^VIX", "flag": "📊", "region": "US", "description": "Volatility Index"},
    # European Indices
    "FTSE 100": {"ticker": "^FTSE", "flag": "🇬🇧", "region": "Europe", "description": "UK Large Cap"},
    "DAX 40": {"ticker": "^GDAXI", "flag": "🇩🇪", "region": "Europe", "description": "German Blue Chip"},
    "CAC 40": {"ticker": "^FCHI", "flag": "🇫🇷", "region": "Europe", "description": "French Large Cap"},
    "Euro Stoxx 50": {"ticker": "^STOXX50E", "flag": "🇪🇺", "region": "Europe", "description": "Eurozone Blue Chip"},
    "IBEX 35": {"ticker": "^IBEX", "flag": "🇪🇸", "region": "Europe", "description": "Spanish Index"},
    "FTSE MIB": {"ticker": "FTSEMIB.MI", "flag": "🇮🇹", "region": "Europe", "description": "Italian Index"},
    "SMI": {"ticker": "^SSMI", "flag": "🇨🇭", "region": "Europe", "description": "Swiss Market Index"},
    "AEX": {"ticker": "^AEX", "flag": "🇳🇱", "region": "Europe", "description": "Dutch Index"},
    # Asian Indices
    "Nikkei 225": {"ticker": "^N225", "flag": "🇯🇵", "region": "Asia", "description": "Japanese Index"},
    "Hang Seng": {"ticker": "^HSI", "flag": "🇭🇰", "region": "Asia", "description": "Hong Kong Index"},
    "Shanghai Composite": {"ticker": "000001.SS", "flag": "🇨🇳", "region": "Asia", "description": "China A-Shares"},
    "KOSPI": {"ticker": "^KS11", "flag": "🇰🇷", "region": "Asia", "description": "Korean Index"},
    "ASX 200": {"ticker": "^AXJO", "flag": "🇦🇺", "region": "Asia", "description": "Australian Index"},
    "SENSEX": {"ticker": "^BSESN", "flag": "🇮🇳", "region": "Asia", "description": "Indian Index"},
    "Taiwan Weighted": {"ticker": "^TWII", "flag": "🇹🇼", "region": "Asia", "description": "Taiwan Index"},
}

FOREX = {
    # Major Pairs
    "EUR/USD": {"ticker": "EURUSD=X", "flag": "🇪🇺🇺🇸", "category": "Major", "pip": 0.0001},
    "GBP/USD": {"ticker": "GBPUSD=X", "flag": "🇬🇧🇺🇸", "category": "Major", "pip": 0.0001},
    "USD/JPY": {"ticker": "USDJPY=X", "flag": "🇺🇸🇯🇵", "category": "Major", "pip": 0.01},
    "USD/CHF": {"ticker": "USDCHF=X", "flag": "🇺🇸🇨🇭", "category": "Major", "pip": 0.0001},
    "AUD/USD": {"ticker": "AUDUSD=X", "flag": "🇦🇺🇺🇸", "category": "Major", "pip": 0.0001},
    "USD/CAD": {"ticker": "USDCAD=X", "flag": "🇺🇸🇨🇦", "category": "Major", "pip": 0.0001},
    "NZD/USD": {"ticker": "NZDUSD=X", "flag": "🇳🇿🇺🇸", "category": "Major", "pip": 0.0001},
    # Cross Pairs
    "EUR/GBP": {"ticker": "EURGBP=X", "flag": "🇪🇺🇬🇧", "category": "Cross", "pip": 0.0001},
    "EUR/JPY": {"ticker": "EURJPY=X", "flag": "🇪🇺🇯🇵", "category": "Cross", "pip": 0.01},
    "GBP/JPY": {"ticker": "GBPJPY=X", "flag": "🇬🇧🇯🇵", "category": "Cross", "pip": 0.01},
    "EUR/CHF": {"ticker": "EURCHF=X", "flag": "🇪🇺🇨🇭", "category": "Cross", "pip": 0.0001},
    "AUD/JPY": {"ticker": "AUDJPY=X", "flag": "🇦🇺🇯🇵", "category": "Cross", "pip": 0.01},
    "EUR/AUD": {"ticker": "EURAUD=X", "flag": "🇪🇺🇦🇺", "category": "Cross", "pip": 0.0001},
    "GBP/AUD": {"ticker": "GBPAUD=X", "flag": "🇬🇧🇦🇺", "category": "Cross", "pip": 0.0001},
    # Emerging Markets
    "USD/CNY": {"ticker": "USDCNY=X", "flag": "🇺🇸🇨🇳", "category": "EM", "pip": 0.0001},
    "USD/MXN": {"ticker": "USDMXN=X", "flag": "🇺🇸🇲🇽", "category": "EM", "pip": 0.0001},
    "USD/BRL": {"ticker": "USDBRL=X", "flag": "🇺🇸🇧🇷", "category": "EM", "pip": 0.0001},
    "USD/TRY": {"ticker": "USDTRY=X", "flag": "🇺🇸🇹🇷", "category": "EM", "pip": 0.0001},
    "USD/ZAR": {"ticker": "USDZAR=X", "flag": "🇺🇸🇿🇦", "category": "EM", "pip": 0.0001},
    "USD/INR": {"ticker": "USDINR=X", "flag": "🇺🇸🇮🇳", "category": "EM", "pip": 0.0001},
}

CRYPTO = {
    "Bitcoin": {"ticker": "BTC-USD", "symbol": "BTC", "category": "Layer 1"},
    "Ethereum": {"ticker": "ETH-USD", "symbol": "ETH", "category": "Layer 1"},
    "Solana": {"ticker": "SOL-USD", "symbol": "SOL", "category": "Layer 1"},
    "XRP": {"ticker": "XRP-USD", "symbol": "XRP", "category": "Payment"},
    "Cardano": {"ticker": "ADA-USD", "symbol": "ADA", "category": "Layer 1"},
    "Avalanche": {"ticker": "AVAX-USD", "symbol": "AVAX", "category": "Layer 1"},
    "Polkadot": {"ticker": "DOT-USD", "symbol": "DOT", "category": "Layer 0"},
    "Chainlink": {"ticker": "LINK-USD", "symbol": "LINK", "category": "Oracle"},
    "Polygon": {"ticker": "MATIC-USD", "symbol": "MATIC", "category": "Layer 2"},
    "Uniswap": {"ticker": "UNI-USD", "symbol": "UNI", "category": "DeFi"},
    "Litecoin": {"ticker": "LTC-USD", "symbol": "LTC", "category": "Payment"},
    "Bitcoin Cash": {"ticker": "BCH-USD", "symbol": "BCH", "category": "Payment"},
}

COMMODITIES = {
    # Precious Metals
    "Gold": {"ticker": "GC=F", "emoji": "🥇", "category": "Precious Metals", "unit": "$/oz"},
    "Silver": {"ticker": "SI=F", "emoji": "🥈", "category": "Precious Metals", "unit": "$/oz"},
    "Platinum": {"ticker": "PL=F", "emoji": "⬜", "category": "Precious Metals", "unit": "$/oz"},
    "Palladium": {"ticker": "PA=F", "emoji": "◻️", "category": "Precious Metals", "unit": "$/oz"},
    # Energy
    "Crude Oil WTI": {"ticker": "CL=F", "emoji": "🛢️", "category": "Energy", "unit": "$/bbl"},
    "Brent Crude": {"ticker": "BZ=F", "emoji": "🛢️", "category": "Energy", "unit": "$/bbl"},
    "Natural Gas": {"ticker": "NG=F", "emoji": "🔥", "category": "Energy", "unit": "$/MMBtu"},
    "Heating Oil": {"ticker": "HO=F", "emoji": "🛢️", "category": "Energy", "unit": "$/gal"},
    "Gasoline": {"ticker": "RB=F", "emoji": "⛽", "category": "Energy", "unit": "$/gal"},
    # Industrial Metals
    "Copper": {"ticker": "HG=F", "emoji": "🔶", "category": "Industrial Metals", "unit": "$/lb"},
    "Aluminum": {"ticker": "ALI=F", "emoji": "🔷", "category": "Industrial Metals", "unit": "$/lb"},
    # Agriculture
    "Wheat": {"ticker": "ZW=F", "emoji": "🌾", "category": "Agriculture", "unit": "¢/bu"},
    "Corn": {"ticker": "ZC=F", "emoji": "🌽", "category": "Agriculture", "unit": "¢/bu"},
    "Soybeans": {"ticker": "ZS=F", "emoji": "🫘", "category": "Agriculture", "unit": "¢/bu"},
    "Coffee": {"ticker": "KC=F", "emoji": "☕", "category": "Agriculture", "unit": "¢/lb"},
    "Sugar": {"ticker": "SB=F", "emoji": "🍬", "category": "Agriculture", "unit": "¢/lb"},
    "Cotton": {"ticker": "CT=F", "emoji": "🧵", "category": "Agriculture", "unit": "¢/lb"},
}

BONDS = {
    "US 1M T-Bill": {"ticker": "^IRX", "maturity": "1M", "duration": 0.08},
    "US 3M T-Bill": {"ticker": "^IRX", "maturity": "3M", "duration": 0.25},
    "US 2Y Treasury": {"ticker": "2YY=F", "maturity": "2Y", "duration": 1.9},
    "US 5Y Treasury": {"ticker": "^FVX", "maturity": "5Y", "duration": 4.5},
    "US 10Y Treasury": {"ticker": "^TNX", "maturity": "10Y", "duration": 8.5},
    "US 30Y Treasury": {"ticker": "^TYX", "maturity": "30Y", "duration": 18.0},
}

SECTORS = {
    "Technology": {"ticker": "XLK", "color": "#3b82f6", "benchmark": "NASDAQ 100"},
    "Healthcare": {"ticker": "XLV", "color": "#10b981", "benchmark": "S&P 500"},
    "Financials": {"ticker": "XLF", "color": "#f59e0b", "benchmark": "S&P 500"},
    "Energy": {"ticker": "XLE", "color": "#ef4444", "benchmark": "S&P 500"},
    "Consumer Discretionary": {"ticker": "XLY", "color": "#8b5cf6", "benchmark": "S&P 500"},
    "Consumer Staples": {"ticker": "XLP", "color": "#ec4899", "benchmark": "S&P 500"},
    "Industrials": {"ticker": "XLI", "color": "#14b8a6", "benchmark": "S&P 500"},
    "Materials": {"ticker": "XLB", "color": "#f97316", "benchmark": "S&P 500"},
    "Utilities": {"ticker": "XLU", "color": "#6366f1", "benchmark": "S&P 500"},
    "Real Estate": {"ticker": "XLRE", "color": "#84cc16", "benchmark": "S&P 500"},
    "Communication Services": {"ticker": "XLC", "color": "#0ea5e9", "benchmark": "S&P 500"},
}

TECH_STOCKS = {
    "NVIDIA": {"ticker": "NVDA", "sector": "Semiconductors", "market_cap": "Large"},
    "Apple": {"ticker": "AAPL", "sector": "Consumer Electronics", "market_cap": "Mega"},
    "Microsoft": {"ticker": "MSFT", "sector": "Software", "market_cap": "Mega"},
    "Alphabet": {"ticker": "GOOGL", "sector": "Internet", "market_cap": "Mega"},
    "Amazon": {"ticker": "AMZN", "sector": "E-commerce", "market_cap": "Mega"},
    "Meta": {"ticker": "META", "sector": "Social Media", "market_cap": "Mega"},
    "Tesla": {"ticker": "TSLA", "sector": "EV/Energy", "market_cap": "Large"},
    "AMD": {"ticker": "AMD", "sector": "Semiconductors", "market_cap": "Large"},
    "Broadcom": {"ticker": "AVGO", "sector": "Semiconductors", "market_cap": "Large"},
    "Netflix": {"ticker": "NFLX", "sector": "Streaming", "market_cap": "Large"},
    "Salesforce": {"ticker": "CRM", "sector": "Cloud", "market_cap": "Large"},
    "Adobe": {"ticker": "ADBE", "sector": "Software", "market_cap": "Large"},
    "Intel": {"ticker": "INTC", "sector": "Semiconductors", "market_cap": "Large"},
    "Cisco": {"ticker": "CSCO", "sector": "Networking", "market_cap": "Large"},
    "Oracle": {"ticker": "ORCL", "sector": "Enterprise Software", "market_cap": "Large"},
    "Qualcomm": {"ticker": "QCOM", "sector": "Semiconductors", "market_cap": "Large"},
    "Texas Instruments": {"ticker": "TXN", "sector": "Semiconductors", "market_cap": "Large"},
    "Micron": {"ticker": "MU", "sector": "Memory", "market_cap": "Large"},
    "Applied Materials": {"ticker": "AMAT", "sector": "Semiconductor Equipment", "market_cap": "Large"},
    "ServiceNow": {"ticker": "NOW", "sector": "Cloud", "market_cap": "Large"},
}

ETFS = {
    # US Equity
    "SPY": {"name": "SPDR S&P 500", "category": "US Large Cap", "expense": 0.09},
    "QQQ": {"name": "Invesco QQQ", "category": "US Tech", "expense": 0.20},
    "IWM": {"name": "iShares Russell 2000", "category": "US Small Cap", "expense": 0.19},
    "DIA": {"name": "SPDR Dow Jones", "category": "US Large Cap", "expense": 0.16},
    "VTI": {"name": "Vanguard Total Stock", "category": "US Total Market", "expense": 0.03},
    "VOO": {"name": "Vanguard S&P 500", "category": "US Large Cap", "expense": 0.03},
    # International
    "EFA": {"name": "iShares MSCI EAFE", "category": "Developed International", "expense": 0.32},
    "EEM": {"name": "iShares MSCI EM", "category": "Emerging Markets", "expense": 0.68},
    "VEA": {"name": "Vanguard FTSE Developed", "category": "Developed International", "expense": 0.05},
    "VWO": {"name": "Vanguard FTSE EM", "category": "Emerging Markets", "expense": 0.08},
    # Fixed Income
    "TLT": {"name": "iShares 20+ Year Treasury", "category": "Long-Term Bonds", "expense": 0.15},
    "IEF": {"name": "iShares 7-10 Year Treasury", "category": "Intermediate Bonds", "expense": 0.15},
    "SHY": {"name": "iShares 1-3 Year Treasury", "category": "Short-Term Bonds", "expense": 0.15},
    "LQD": {"name": "iShares Investment Grade", "category": "Corporate Bonds", "expense": 0.14},
    "HYG": {"name": "iShares High Yield", "category": "High Yield Bonds", "expense": 0.48},
    "BND": {"name": "Vanguard Total Bond", "category": "Total Bond Market", "expense": 0.03},
    # Commodities
    "GLD": {"name": "SPDR Gold", "category": "Gold", "expense": 0.40},
    "SLV": {"name": "iShares Silver", "category": "Silver", "expense": 0.50},
    "USO": {"name": "US Oil Fund", "category": "Oil", "expense": 0.83},
    # Sector
    "XLK": {"name": "Technology Select", "category": "Tech Sector", "expense": 0.10},
    "XLF": {"name": "Financial Select", "category": "Financial Sector", "expense": 0.10},
    "XLE": {"name": "Energy Select", "category": "Energy Sector", "expense": 0.10},
    "XLV": {"name": "Health Care Select", "category": "Healthcare Sector", "expense": 0.10},
}

# =============================================================================
# CSS - PROFESSIONAL WHITE THEME
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-primary: #f8fafc;
    --bg-secondary: #ffffff;
    --bg-tertiary: #f1f5f9;
    --border-light: #e2e8f0;
    --border-medium: #cbd5e1;
    --text-primary: #0f172a;
    --text-secondary: #334155;
    --text-tertiary: #64748b;
    --text-muted: #94a3b8;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-yellow: #f59e0b;
    --accent-purple: #8b5cf6;
    --accent-pink: #ec4899;
    --accent-cyan: #06b6d4;
    --accent-orange: #f97316;
}

* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.mono {
    font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
}

/* Main App */
.stApp {
    background: var(--bg-primary);
}

#MainMenu, footer, header {
    visibility: hidden;
}

/* Header */
.main-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #312e81 100%);
    padding: 1.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.15);
}

.main-header h1 {
    color: #ffffff;
    font-size: 1.75rem;
    font-weight: 800;
    margin: 0;
    text-align: center;
    letter-spacing: -0.02em;
}

.main-header .subtitle {
    color: rgba(255, 255, 255, 0.8);
    text-align: center;
    font-size: 0.875rem;
    font-weight: 400;
    margin-top: 0.25rem;
}

.main-header .timestamp {
    color: rgba(255, 255, 255, 0.6);
    text-align: center;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 0.75rem;
}

.regime-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.8rem;
    margin-top: 0.75rem;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
}

.regime-on { color: #4ade80; }
.regime-neutral { color: #facc15; }
.regime-off { color: #f87171; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-secondary);
    padding: 6px;
    border-radius: 12px;
    border: 1px solid var(--border-light);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    padding: 10px 16px;
    color: var(--text-tertiary);
    font-weight: 500;
    font-size: 0.85rem;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

/* Cards */
.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
}

.card:hover {
    border-color: var(--accent-blue);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.card-title {
    color: var(--text-primary);
    font-size: 0.9rem;
    font-weight: 600;
}

.card-label {
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.card-value {
    color: var(--text-primary);
    font-size: 1.5rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.card-value-sm {
    color: var(--text-primary);
    font-size: 1.1rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

.card-delta {
    font-size: 0.8rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.delta-up {
    background: rgba(16, 185, 129, 0.1);
    color: var(--accent-green);
}

.delta-down {
    background: rgba(239, 68, 68, 0.1);
    color: var(--accent-red);
}

/* Section Headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 1.5rem 0 0.5rem 0;
}

.section-title {
    color: var(--text-primary);
    font-size: 1.15rem;
    font-weight: 700;
}

.section-subtitle {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-bottom: 1rem;
}

/* Asset Row */
.asset-row {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    padding: 0.875rem 1rem;
    margin-bottom: 0.5rem;
    display: grid;
    grid-template-columns: 180px 1fr 120px;
    align-items: center;
    gap: 1rem;
    transition: all 0.2s ease;
}

.asset-row:hover {
    border-color: var(--accent-blue);
    transform: translateX(2px);
}

.asset-info {
    display: flex;
    flex-direction: column;
}

.asset-name {
    color: var(--text-primary);
    font-weight: 600;
    font-size: 0.9rem;
}

.asset-ticker {
    color: var(--text-muted);
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
}

.asset-price {
    text-align: right;
}

.price-value {
    color: var(--text-primary);
    font-size: 1rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

.price-change {
    font-size: 0.8rem;
    font-weight: 600;
}

.price-up { color: var(--accent-green); }
.price-down { color: var(--accent-red); }

/* Metric Grid */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem;
}

/* Table Styles */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.data-table th {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    font-weight: 600;
    text-align: left;
    padding: 0.75rem 1rem;
    border-bottom: 2px solid var(--border-light);
}

.data-table td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-light);
    color: var(--text-primary);
}

.data-table tr:hover {
    background: var(--bg-tertiary);
}

/* Polymarket Card */
.poly-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
}

.poly-card:hover {
    border-color: var(--accent-purple);
}

.poly-title {
    color: var(--text-primary);
    font-size: 0.9rem;
    font-weight: 500;
    line-height: 1.5;
    margin-bottom: 0.5rem;
}

.poly-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.poly-volume {
    color: var(--text-muted);
    font-size: 0.75rem;
}

.poly-volume span {
    color: var(--accent-purple);
    font-weight: 600;
}

/* News Card */
.news-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    transition: all 0.2s ease;
}

.news-card:hover {
    border-color: var(--accent-blue);
}

.news-title {
    color: var(--text-primary);
    font-size: 0.9rem;
    font-weight: 500;
    line-height: 1.5;
    margin-bottom: 0.5rem;
}

.news-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.news-source {
    color: var(--accent-blue);
    font-size: 0.75rem;
    font-weight: 600;
}

.news-time {
    color: var(--text-muted);
    font-size: 0.7rem;
}

/* Calendar Event */
.cal-event {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.cal-event-name {
    color: var(--text-primary);
    font-weight: 500;
}

.cal-event-date {
    color: var(--text-secondary);
    font-size: 0.85rem;
}

.cal-impact {
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
}

.impact-high {
    background: rgba(239, 68, 68, 0.1);
    color: var(--accent-red);
}

.impact-medium {
    background: rgba(245, 158, 11, 0.1);
    color: var(--accent-yellow);
}

.impact-low {
    background: rgba(16, 185, 129, 0.1);
    color: var(--accent-green);
}

/* Analysis Box */
.analysis-box {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}

.analysis-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 0.75rem;
}

.analysis-title {
    color: var(--text-primary);
    font-weight: 700;
    font-size: 1rem;
}

.analysis-badge {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 6px;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
}

.analysis-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--bg-tertiary);
}

.analysis-row:last-child {
    border-bottom: none;
}

.analysis-label {
    color: var(--text-tertiary);
    font-size: 0.85rem;
}

.analysis-value {
    color: var(--text-primary);
    font-weight: 600;
    font-size: 0.9rem;
    font-family: 'JetBrains Mono', monospace;
}

/* Heatmap Cell */
.heatmap-cell {
    padding: 0.5rem;
    text-align: center;
    font-weight: 600;
    font-size: 0.8rem;
    border-radius: 6px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
}

[data-testid="stSidebar"] .stMarkdown {
    color: var(--text-primary);
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

/* Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    background: var(--bg-secondary) !important;
    border-color: var(--border-light) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-secondary);
    border-radius: 8px;
}

/* Footer */
.app-footer {
    text-align: center;
    padding: 1.5rem;
    margin-top: 2rem;
    background: var(--bg-secondary);
    border-radius: 12px;
    border: 1px solid var(--border-light);
}

.app-footer .title {
    color: var(--accent-blue);
    font-weight: 700;
    font-size: 1rem;
}

.app-footer .sources {
    color: var(--text-tertiary);
    font-size: 0.8rem;
    margin-top: 0.25rem;
}

.app-footer .disclaimer {
    color: var(--text-muted);
    font-size: 0.7rem;
    margin-top: 0.5rem;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-tertiary);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: var(--border-medium);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* Watchlist Tag */
.watchlist-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: var(--bg-tertiary);
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 2px;
}

.watchlist-tag .remove {
    cursor: pointer;
    color: var(--text-muted);
}

.watchlist-tag .remove:hover {
    color: var(--accent-red);
}

/* Progress Bar */
.progress-bar {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}

/* Indicator Badge */
.indicator-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
}

.indicator-bullish {
    background: rgba(16, 185, 129, 0.1);
    color: var(--accent-green);
}

.indicator-bearish {
    background: rgba(239, 68, 68, 0.1);
    color: var(--accent-red);
}

.indicator-neutral {
    background: rgba(245, 158, 11, 0.1);
    color: var(--accent-yellow);
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HTTP RETRY HELPER
# =============================================================================
def http_get_with_retries(url, params=None, headers=None, retries=3, backoff=1, timeout=10):
    """
    HTTP GET with retries and exponential backoff
    
    Args:
        url: URL to fetch
        params: Query parameters
        headers: HTTP headers
        retries: Number of retry attempts
        backoff: Initial backoff time in seconds
        timeout: Request timeout in seconds
    
    Returns:
        Response object on success, None on failure
    """
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.ok:
                return response
            logger.warning(f"HTTP {response.status_code} for {url} (attempt {attempt + 1}/{retries})")
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {url} (attempt {attempt + 1}/{retries})")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1}/{retries})")
        
        if attempt < retries - 1:
            sleep_time = backoff * (2 ** attempt)
            logger.debug(f"Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    
    logger.error(f"Failed to fetch {url} after {retries} attempts")
    return None


# =============================================================================
# PARALLEL QUOTE FETCHING
# =============================================================================
def fetch_quotes_bulk(tickers, max_workers=8):
    """
    Fetch multiple quotes in parallel using ThreadPoolExecutor
    
    Args:
        tickers: List of ticker symbols
        max_workers: Maximum number of parallel workers
    
    Returns:
        Dictionary mapping ticker -> quote data
    """
    if not tickers:
        return {}
    
    results = {}
    
    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_ticker = {executor.submit(fetch_quote, ticker): ticker for ticker in tickers}
        
        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                quote = future.result()
                results[ticker] = quote
                logger.debug(f"Fetched quote for {ticker}")
            except Exception as e:
                logger.warning(f"Error fetching quote for {ticker}: {e}")
                results[ticker] = None
    
    return results


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================
@st.cache_data(ttl=60)
def fetch_quote(ticker):
    """Fetch current quote with extended data"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if hist.empty:
            logger.debug(f"No history data for {ticker}")
            return None
        
        info = {}
        try:
            info = stock.info
        except Exception as e:
            logger.debug(f"Could not fetch info for {ticker}: {e}")
        
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
        change = (current / prev - 1) * 100
        
        return {
            'price': current,
            'change': change,
            'open': hist['Open'].iloc[-1],
            'high': hist['High'].iloc[-1],
            'low': hist['Low'].iloc[-1],
            'volume': hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0,
            'prev_close': prev,
            'week_high': hist['High'].max(),
            'week_low': hist['Low'].min(),
            'history': hist,
            'info': info
        }
    except Exception as e:
        logger.warning(f"Error fetching quote for {ticker}: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_history(ticker, start_date=None, end_date=None, period="1y"):
    """Fetch historical data with custom date range"""
    try:
        stock = yf.Ticker(ticker)
        if start_date and end_date:
            hist = stock.history(start=start_date, end=end_date)
        else:
            hist = stock.history(period=period)
        return hist
    except Exception as e:
        logger.warning(f"Error fetching history for {ticker}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_multiple(tickers, start_date=None, end_date=None, period="1y"):
    """Fetch multiple tickers"""
    try:
        if start_date and end_date:
            data = yf.download(tickers, start=start_date, end=end_date, progress=False)
        else:
            data = yf.download(tickers, period=period, progress=False)
        
        if data.empty:
            logger.debug(f"No data returned for tickers: {tickers}")
            return pd.DataFrame()
        
        if isinstance(data.columns, pd.MultiIndex):
            prices = data['Close']
        else:
            if len(tickers) == 1:
                prices = data[['Close']].rename(columns={'Close': tickers[0]})
            else:
                prices = data['Close']
        
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(tickers[0] if isinstance(tickers, list) else tickers)
        
        return prices.ffill().dropna()
    except Exception as e:
        logger.warning(f"Error fetching multiple tickers {tickers}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_fred_series(series_id, months=60):
    """Fetch FRED economic data"""
    if not FRED_OK:
        logger.debug("FRED library not available")
        return None
    
    if 'fred' not in API_KEYS:
        logger.warning("FRED API key not configured")
        return None
    
    try:
        fred = Fred(api_key=API_KEYS['fred'])
        data = fred.get_series(series_id, observation_start=datetime.now() - timedelta(days=months * 31))
        return data.dropna()
    except Exception as e:
        logger.warning(f"Error fetching FRED series {series_id}: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_cpi_yoy():
    """Calculate CPI Year-over-Year"""
    data = fetch_fred_series("CPIAUCSL", 24)
    if data is not None and len(data) >= 13:
        return ((data.iloc[-1] - data.iloc[-13]) / data.iloc[-13]) * 100
    logger.debug("Insufficient CPI data for YoY calculation")
    return None


@st.cache_data(ttl=120)
def fetch_polymarket(limit=300):
    """Fetch Polymarket events"""
    response = http_get_with_retries(
        "https://gamma-api.polymarket.com/events",
        params={"limit": limit, "active": "true", "closed": "false"},
        retries=3,
        backoff=1,
        timeout=15
    )
    
    if response:
        try:
            return response.json()
        except Exception as e:
            logger.warning(f"Error parsing Polymarket response: {e}")
            return []
    
    logger.warning("Failed to fetch Polymarket events")
    return []


def search_polymarket(events, keywords, max_results=6):
    """Search and rank Polymarket events"""
    matches = []
    for event in events:
        title = event.get('title', '').lower()
        desc = event.get('description', '').lower()
        volume = float(event.get('volume', 0) or 0)
        
        if volume < 10000:
            continue
        
        score = sum(20 if kw.lower() in title else 8 if kw.lower() in desc else 0 for kw in keywords)
        score += min(volume / 100000, 15)
        
        if score > 0:
            matches.append({'event': event, 'score': score, 'volume': volume})
    
    return sorted(matches, key=lambda x: x['score'], reverse=True)[:max_results]


@st.cache_data(ttl=300)
def fetch_news(category="general"):
    """Fetch news from Finnhub"""
    if 'finnhub' not in API_KEYS:
        logger.warning("Finnhub API key not configured")
        return []
    
    response = http_get_with_retries(
        "https://finnhub.io/api/v1/news",
        params={"token": API_KEYS['finnhub'], "category": category},
        retries=3,
        backoff=1,
        timeout=10
    )
    
    if response:
        try:
            data = response.json()
            return data[:20] if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Error parsing Finnhub news response: {e}")
            return []
    
    logger.warning("Failed to fetch news from Finnhub")
    return []


@st.cache_data(ttl=600)
def fetch_google_trends(keywords):
    """Fetch Google Trends data"""
    if not TRENDS_OK:
        logger.debug("Google Trends library not available, using random data")
        dates = pd.date_range(end=datetime.now(), periods=90, freq='D')
        return pd.DataFrame({kw: np.random.randint(30, 100, 90) for kw in keywords}, index=dates)
    
    try:
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
        pytrends.build_payload(keywords, timeframe='today 3-m')
        data = pytrends.interest_over_time()
        if data.empty:
            raise ValueError("Empty data")
        if 'isPartial' in data.columns:
            data = data.drop(columns=['isPartial'])
        return data
    except Exception as e:
        logger.warning(f"Error fetching Google Trends for {keywords}: {e}")
        dates = pd.date_range(end=datetime.now(), periods=90, freq='D')
        return pd.DataFrame({kw: np.random.randint(30, 100, 90) for kw in keywords}, index=dates)


# =============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# =============================================================================
class TechnicalAnalysis:
    """Technical analysis indicators"""
    
    @staticmethod
    def sma(data, period):
        """Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data, period):
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data, period=14):
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data, fast=12, slow=26, signal=9):
        """MACD Indicator"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data, period=20, std_dev=2):
        """Bollinger Bands"""
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    @staticmethod
    def stochastic(high, low, close, k_period=14, d_period=3):
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        return k, d
    
    @staticmethod
    def atr(high, low, close, period=14):
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def obv(close, volume):
        """On-Balance Volume"""
        obv = [0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i-1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=close.index)
    
    @staticmethod
    def vwap(high, low, close, volume):
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return vwap
    
    @staticmethod
    def fibonacci_levels(high, low):
        """Fibonacci Retracement Levels"""
        diff = high - low
        levels = {
            '0.0%': high,
            '23.6%': high - 0.236 * diff,
            '38.2%': high - 0.382 * diff,
            '50.0%': high - 0.5 * diff,
            '61.8%': high - 0.618 * diff,
            '78.6%': high - 0.786 * diff,
            '100.0%': low
        }
        return levels
    
    @staticmethod
    def support_resistance(data, window=20):
        """Identify support and resistance levels"""
        highs = data['High'].rolling(window=window, center=True).max()
        lows = data['Low'].rolling(window=window, center=True).min()
        
        resistance_levels = data[data['High'] == highs]['High'].unique()[-5:]
        support_levels = data[data['Low'] == lows]['Low'].unique()[-5:]
        
        return list(support_levels), list(resistance_levels)


# =============================================================================
# QUANTITATIVE ANALYSIS ENGINE
# =============================================================================
class QuantEngine:
    """Quantitative analysis and portfolio management"""
    
    @staticmethod
    def returns(prices):
        """Calculate returns"""
        return prices.pct_change().dropna()
    
    @staticmethod
    def cumulative_returns(prices):
        """Calculate cumulative returns"""
        returns = prices.pct_change().fillna(0)
        return (1 + returns).cumprod() - 1
    
    @staticmethod
    def annualized_return(prices, periods_per_year=252):
        """Calculate annualized return"""
        total_return = prices.iloc[-1] / prices.iloc[0]
        years = len(prices) / periods_per_year
        return (total_return ** (1 / years) - 1) * 100 if years > 0 else 0
    
    @staticmethod
    def volatility(returns, periods_per_year=252):
        """Calculate annualized volatility"""
        return returns.std() * np.sqrt(periods_per_year) * 100
    
    @staticmethod
    def sharpe_ratio(returns, risk_free_rate=0.04, periods_per_year=252):
        """Calculate Sharpe ratio"""
        excess_returns = returns.mean() * periods_per_year - risk_free_rate
        volatility = returns.std() * np.sqrt(periods_per_year)
        return excess_returns / volatility if volatility > 0 else 0
    
    @staticmethod
    def sortino_ratio(returns, risk_free_rate=0.04, periods_per_year=252):
        """Calculate Sortino ratio"""
        excess_returns = returns.mean() * periods_per_year - risk_free_rate
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(periods_per_year)
        return excess_returns / downside_std if downside_std > 0 else 0
    
    @staticmethod
    def max_drawdown(prices):
        """Calculate maximum drawdown"""
        rolling_max = prices.expanding().max()
        drawdown = (prices - rolling_max) / rolling_max * 100
        return drawdown.min()
    
    @staticmethod
    def drawdown_series(prices):
        """Calculate drawdown series"""
        rolling_max = prices.expanding().max()
        return (prices - rolling_max) / rolling_max * 100
    
    @staticmethod
    def calmar_ratio(prices, periods_per_year=252):
        """Calculate Calmar ratio"""
        ann_return = QuantEngine.annualized_return(prices, periods_per_year)
        max_dd = abs(QuantEngine.max_drawdown(prices))
        return ann_return / max_dd if max_dd > 0 else 0
    
    @staticmethod
    def var(returns, confidence=0.95):
        """Calculate Value at Risk"""
        return -np.percentile(returns, (1 - confidence) * 100) * 100
    
    @staticmethod
    def cvar(returns, confidence=0.95):
        """Calculate Conditional Value at Risk (Expected Shortfall)"""
        var = np.percentile(returns, (1 - confidence) * 100)
        return -returns[returns <= var].mean() * 100
    
    @staticmethod
    def beta(asset_returns, market_returns):
        """Calculate beta"""
        covariance = np.cov(asset_returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        return covariance / market_variance if market_variance > 0 else 1
    
    @staticmethod
    def alpha(asset_returns, market_returns, risk_free_rate=0.04, periods_per_year=252):
        """Calculate Jensen's alpha"""
        beta = QuantEngine.beta(asset_returns, market_returns)
        asset_excess = asset_returns.mean() * periods_per_year - risk_free_rate
        market_excess = market_returns.mean() * periods_per_year - risk_free_rate
        return (asset_excess - beta * market_excess) * 100
    
    @staticmethod
    def information_ratio(asset_returns, benchmark_returns, periods_per_year=252):
        """Calculate Information Ratio"""
        active_returns = asset_returns - benchmark_returns
        tracking_error = active_returns.std() * np.sqrt(periods_per_year)
        return active_returns.mean() * periods_per_year / tracking_error if tracking_error > 0 else 0
    
    @staticmethod
    def tracking_error(asset_returns, benchmark_returns, periods_per_year=252):
        """Calculate Tracking Error"""
        active_returns = asset_returns - benchmark_returns
        return active_returns.std() * np.sqrt(periods_per_year) * 100
    
    @staticmethod
    def correlation_matrix(returns):
        """Calculate correlation matrix"""
        return returns.corr()
    
    @staticmethod
    def covariance_matrix(returns, periods_per_year=252):
        """Calculate annualized covariance matrix"""
        return returns.cov() * periods_per_year
    
    @staticmethod
    def portfolio_return(weights, returns):
        """Calculate portfolio return"""
        return np.sum(weights * returns.mean()) * 252
    
    @staticmethod
    def portfolio_volatility(weights, cov_matrix):
        """Calculate portfolio volatility"""
        return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252) * 100
    
    @staticmethod
    def backtest_portfolio(prices, weights, initial_capital=100000, rebalance_frequency='M'):
        """Backtest portfolio with periodic rebalancing"""
        tickers = [t for t in weights.keys() if t in prices.columns]
        if not tickers:
            return None
        
        prices = prices[tickers].copy()
        w = np.array([weights[t] for t in tickers])
        w = w / w.sum()
        
        returns = prices.pct_change().fillna(0)
        portfolio_values = [initial_capital]
        current_weights = w.copy()
        
        for i in range(1, len(returns)):
            daily_return = np.sum(current_weights * returns.iloc[i].values)
            portfolio_values.append(portfolio_values[-1] * (1 + daily_return))
            
            # Update weights based on returns
            current_weights = current_weights * (1 + returns.iloc[i].values)
            if current_weights.sum() > 0:
                current_weights = current_weights / current_weights.sum()
            
            # Rebalance check
            if rebalance_frequency == 'D':
                current_weights = w.copy()
            elif rebalance_frequency == 'W' and returns.index[i].weekday() == 0:
                current_weights = w.copy()
            elif rebalance_frequency == 'M' and returns.index[i].month != returns.index[i-1].month:
                current_weights = w.copy()
            elif rebalance_frequency == 'Q' and returns.index[i].quarter != returns.index[i-1].quarter:
                current_weights = w.copy()
            elif rebalance_frequency == 'Y' and returns.index[i].year != returns.index[i-1].year:
                current_weights = w.copy()
        
        return pd.Series(portfolio_values, index=returns.index)
    
    @staticmethod
    def full_metrics(prices, risk_free_rate=0.04):
        """Calculate comprehensive metrics"""
        if prices is None or len(prices) < 2:
            return None
        
        returns = prices.pct_change().dropna()
        
        total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
        years = len(prices) / 252
        cagr = ((prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1) * 100 if years > 0 else 0
        volatility = returns.std() * np.sqrt(252) * 100
        sharpe = QuantEngine.sharpe_ratio(returns, risk_free_rate)
        sortino = QuantEngine.sortino_ratio(returns, risk_free_rate)
        max_dd = QuantEngine.max_drawdown(prices)
        calmar = QuantEngine.calmar_ratio(prices)
        var_95 = QuantEngine.var(returns, 0.95)
        cvar_95 = QuantEngine.cvar(returns, 0.95)
        
        # Additional statistics
        skewness = returns.skew()
        kurtosis = returns.kurtosis()
        positive_days = (returns > 0).sum() / len(returns) * 100
        best_day = returns.max() * 100
        worst_day = returns.min() * 100
        
        return {
            'Total Return': total_return,
            'CAGR': cagr,
            'Volatility': volatility,
            'Sharpe': sharpe,
            'Sortino': sortino,
            'Max Drawdown': max_dd,
            'Calmar': calmar,
            'VaR 95%': var_95,
            'CVaR 95%': cvar_95,
            'Skewness': skewness,
            'Kurtosis': kurtosis,
            'Win Rate': positive_days,
            'Best Day': best_day,
            'Worst Day': worst_day,
            'Drawdown Series': QuantEngine.drawdown_series(prices)
        }


# =============================================================================
# MARKET REGIME DETECTION
# =============================================================================
@st.cache_data(ttl=120)
def detect_market_regime():
    """Detect current market regime with multiple signals"""
    signals = {}
    score = 0
    max_score = 6
    
    # Signal 1: SPY > SMA50 and SMA200
    try:
        # Fetch enough history for SMA200
        spy = yf.Ticker("SPY").history(period="1y")
        if not spy.empty and len(spy) >= 50:
            price = spy['Close'].iloc[-1]
            sma50 = spy['Close'].rolling(50).mean().iloc[-1]
            
            # Only calculate SMA200 if we have enough data
            if len(spy) >= 200:
                sma200 = spy['Close'].rolling(200).mean().iloc[-1]
                signals['spy_sma200'] = price > sma200
                signals['golden_cross'] = sma50 > sma200
                if signals.get('golden_cross'):
                    score += 1
            else:
                # Not enough data for SMA200
                signals['spy_sma200'] = None
                signals['golden_cross'] = None
                logger.debug(f"Insufficient data for SMA200 (only {len(spy)} days)")
            
            signals['spy_sma50'] = price > sma50
            if signals['spy_sma50']:
                score += 1
        else:
            logger.debug("Insufficient SPY data for regime detection")
    except Exception as e:
        logger.warning(f"Error in SPY regime signal: {e}")
    
    # Signal 2: VIX < 20
    try:
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty:
            signals['vix'] = vix['Close'].iloc[-1]
            if signals['vix'] < 20:
                score += 1
    except Exception as e:
        logger.debug(f"Error in VIX regime signal: {e}")
    
    # Signal 3: DXY trend
    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="1mo")
        if not dxy.empty and len(dxy) > 1:
            signals['dxy_down'] = dxy['Close'].iloc[-1] < dxy['Close'].iloc[0]
            if signals['dxy_down']:
                score += 1
    except Exception as e:
        logger.debug(f"Error in DXY regime signal: {e}")
    
    # Signal 4: Yield Curve
    if FRED_OK and 'fred' in API_KEYS:
        try:
            fred = Fred(api_key=API_KEYS['fred'])
            spread = fred.get_series('T10Y2Y', observation_start=datetime.now() - timedelta(days=30))
            if len(spread) > 0:
                signals['yield_spread'] = spread.iloc[-1]
                if spread.iloc[-1] > 0:
                    score += 1
        except Exception as e:
            logger.debug(f"Error in yield curve regime signal: {e}")
    
    # Signal 5: High Yield Spread
    try:
        hyg = yf.Ticker("HYG").history(period="1mo")
        lqd = yf.Ticker("LQD").history(period="1mo")
        if not hyg.empty and not lqd.empty:
            spread_change = (hyg['Close'].iloc[-1] / hyg['Close'].iloc[0]) - (lqd['Close'].iloc[-1] / lqd['Close'].iloc[0])
            signals['credit_spread'] = spread_change > 0
            if signals['credit_spread']:
                score += 1
    except Exception as e:
        logger.debug(f"Error in credit spread regime signal: {e}")
    
    signals['score'] = score
    signals['max_score'] = max_score
    
    if score >= 4:
        return "Risk On", "🟢", "regime-on", signals
    elif score <= 2:
        return "Risk Off", "🔴", "regime-off", signals
    else:
        return "Neutral", "🟡", "regime-neutral", signals


# =============================================================================
# CHARTING FUNCTIONS
# =============================================================================
def create_sparkline(data, height=50, color=None):
    """Create a mini sparkline chart"""
    if data is None or len(data) < 2:
        return None
    
    is_positive = data.iloc[-1] >= data.iloc[0]
    line_color = color or ("#10b981" if is_positive else "#ef4444")
    fill_color = "rgba(16,185,129,0.1)" if is_positive else "rgba(239,68,68,0.1)"
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data.index,
        y=data.values,
        mode='lines',
        line=dict(color=line_color, width=2),
        fill='tozeroy',
        fillcolor=fill_color,
        hovertemplate='%{y:.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        hovermode='x unified'
    )
    
    return fig


def create_line_chart(data, title="", height=400, show_legend=True):
    """Create a professional line chart"""
    fig = go.Figure()
    
    colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
    
    if isinstance(data, pd.DataFrame):
        for i, col in enumerate(data.columns):
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data[col],
                mode='lines',
                name=str(col),
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>'
            ))
    else:
        is_positive = data.iloc[-1] >= data.iloc[0]
        color = "#10b981" if is_positive else "#ef4444"
        fill_color = "rgba(16,185,129,0.1)" if is_positive else "rgba(239,68,68,0.1)"
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data.values,
            mode='lines',
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=fill_color,
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#0f172a', family='Inter')) if title else None,
        height=height,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family='Inter', color='#64748b'),
        xaxis=dict(
            showgrid=True,
            gridcolor='#f1f5f9',
            tickformat='%b %d, %Y',
            linecolor='#e2e8f0'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f1f5f9',
            linecolor='#e2e8f0'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ) if show_legend else dict(visible=False),
        hovermode='x unified'
    )
    
    return fig


def create_candlestick_chart(data, title="", height=500, show_volume=True, indicators=None):
    """Create a professional candlestick chart with indicators"""
    if data.empty:
        return None
    
    # Create subplots
    row_heights = [0.6, 0.2, 0.2] if show_volume else [0.7, 0.3]
    rows = 3 if show_volume else 2
    
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=row_heights
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='Price',
        increasing_line_color='#10b981',
        decreasing_line_color='#ef4444',
        increasing_fillcolor='#10b981',
        decreasing_fillcolor='#ef4444'
    ), row=1, col=1)
    
    # Add indicators
    if indicators:
        if 'SMA20' in indicators:
            sma20 = TechnicalAnalysis.sma(data['Close'], 20)
            fig.add_trace(go.Scatter(x=data.index, y=sma20, name='SMA 20', line=dict(color='#3b82f6', width=1.5)), row=1, col=1)
        
        if 'SMA50' in indicators:
            sma50 = TechnicalAnalysis.sma(data['Close'], 50)
            fig.add_trace(go.Scatter(x=data.index, y=sma50, name='SMA 50', line=dict(color='#f59e0b', width=1.5)), row=1, col=1)
        
        if 'EMA20' in indicators:
            ema20 = TechnicalAnalysis.ema(data['Close'], 20)
            fig.add_trace(go.Scatter(x=data.index, y=ema20, name='EMA 20', line=dict(color='#8b5cf6', width=1.5)), row=1, col=1)
        
        if 'BB' in indicators:
            upper, mid, lower = TechnicalAnalysis.bollinger_bands(data['Close'])
            fig.add_trace(go.Scatter(x=data.index, y=upper, name='BB Upper', line=dict(color='#94a3b8', width=1, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=lower, name='BB Lower', line=dict(color='#94a3b8', width=1, dash='dash'), fill='tonexty', fillcolor='rgba(148, 163, 184, 0.1)'), row=1, col=1)
    
    # Volume
    if show_volume and 'Volume' in data.columns:
        colors = ['#10b981' if data['Close'].iloc[i] >= data['Open'].iloc[i] else '#ef4444' for i in range(len(data))]
        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], name='Volume', marker_color=colors, opacity=0.7), row=2, col=1)
    
    # RSI
    if indicators and 'RSI' in indicators:
        rsi = TechnicalAnalysis.rsi(data['Close'])
        rsi_row = 3 if show_volume else 2
        fig.add_trace(go.Scatter(x=data.index, y=rsi, name='RSI', line=dict(color='#8b5cf6', width=1.5)), row=rsi_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=rsi_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#10b981", line_width=1, row=rsi_row, col=1)
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#0f172a', family='Inter')) if title else None,
        height=height,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family='Inter', color='#64748b'),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
        hovermode='x unified'
    )
    
    # Update axes
    for i in range(1, rows + 1):
        fig.update_xaxes(showgrid=True, gridcolor='#f1f5f9', linecolor='#e2e8f0', row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor='#f1f5f9', linecolor='#e2e8f0', row=i, col=1)
    
    return fig


def create_heatmap(data, title="", height=400):
    """Create a correlation heatmap"""
    fig = go.Figure(data=go.Heatmap(
        z=data.values,
        x=data.columns,
        y=data.index,
        colorscale='RdBu_r',
        zmid=0,
        text=np.round(data.values, 2),
        texttemplate='%{text}',
        textfont=dict(size=10, color='#0f172a'),
        hovertemplate='%{x} vs %{y}: %{z:.3f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#0f172a', family='Inter')) if title else None,
        height=height,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family='Inter', color='#64748b')
    )
    
    return fig


def create_sector_heatmap(sectors_data, title="Sector Performance"):
    """Create a sector performance heatmap"""
    fig = go.Figure()
    
    # Sort by performance
    sorted_sectors = sorted(sectors_data.items(), key=lambda x: x[1], reverse=True)
    
    names = [s[0] for s in sorted_sectors]
    values = [s[1] for s in sorted_sectors]
    colors = ['#10b981' if v >= 0 else '#ef4444' for v in values]
    
    fig.add_trace(go.Bar(
        x=values,
        y=names,
        orientation='h',
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in values],
        textposition='outside',
        hovertemplate='%{y}: %{x:.2f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#0f172a', family='Inter')),
        height=max(300, len(names) * 35),
        margin=dict(l=10, r=80, t=50, b=10),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family='Inter', color='#64748b'),
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=True, zerolinecolor='#e2e8f0'),
        yaxis=dict(showgrid=False)
    )
    
    return fig


def create_drawdown_chart(drawdown_series, title="Drawdown", height=250):
    """Create a drawdown chart"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=drawdown_series.index,
        y=drawdown_series.values,
        mode='lines',
        line=dict(color='#ef4444', width=2),
        fill='tozeroy',
        fillcolor='rgba(239, 68, 68, 0.1)',
        hovertemplate='%{y:.2f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#0f172a', family='Inter')) if title else None,
        height=height,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family='Inter', color='#64748b'),
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9'),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', title='Drawdown (%)')
    )
    
    return fig


# =============================================================================
# UI COMPONENT FUNCTIONS
# =============================================================================
def show_metric_card(label, value, delta=None, prefix="", suffix=""):
    """Display a metric card"""
    delta_html = ""
    if delta is not None:
        delta_class = "delta-up" if delta >= 0 else "delta-down"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f'<span class="card-delta {delta_class}">{arrow} {abs(delta):.2f}%</span>'
    
    st.markdown(f"""
    <div class="card">
        <div class="card-label">{label}</div>
        <div class="card-value">{prefix}{value}{suffix}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def show_asset_row(name, ticker, icon="📈", show_chart=True, prefetched_quote=None):
    """Display an asset row with sparkline
    
    Args:
        name: Display name for the asset
        ticker: Ticker symbol
        icon: Display icon
        show_chart: Whether to show sparkline chart
        prefetched_quote: Optional pre-fetched quote data to avoid redundant API calls
    """
    quote = prefetched_quote if prefetched_quote is not None else fetch_quote(ticker)
    
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.markdown(f"**{icon} {name}**")
        st.caption(f"`{ticker}`")
    
    with col2:
        if show_chart and quote and quote.get('history') is not None and len(quote['history']) > 1:
            fig = create_sparkline(quote['history']['Close'], height=45)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"spark_{ticker}_{name}_{hash(name)}")
    
    with col3:
        if quote:
            price = quote.get('price')
            change = quote.get('change')
            
            if price is not None and change is not None:
                # Format price
                if price > 10000:
                    price_str = f"{price:,.0f}"
                elif price > 100:
                    price_str = f"{price:,.2f}"
                elif price > 1:
                    price_str = f"{price:.4f}"
                else:
                    price_str = f"{price:.6f}"
                
                color = "#10b981" if change >= 0 else "#ef4444"
                arrow = "▲" if change >= 0 else "▼"
                
                st.markdown(f"""
                <div style="text-align: right;">
                    <div class="price-value">{price_str}</div>
                    <div class="price-change" style="color: {color};">{arrow} {abs(change):.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align: right; color: #94a3b8;'>N/A</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align: right; color: #94a3b8;'>N/A</div>", unsafe_allow_html=True)


def show_polymarket_card(event, volume):
    """Display a Polymarket event card"""
    title = event.get('title', 'Unknown')[:100]
    slug = event.get('slug', '')
    
    st.markdown(f"""
    <div class="poly-card">
        <div class="poly-title">{title}</div>
        <div class="poly-meta">
            <span class="poly-volume">Volume: <span>${volume/1e6:.2f}M</span></span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if slug:
        st.markdown(f"[View on Polymarket →](https://polymarket.com/event/{slug})")


def show_news_card(article):
    """Display a news card"""
    title = article.get('headline', article.get('title', 'No title'))[:120]
    source = article.get('source', 'Unknown')
    url = article.get('url', '')
    timestamp = article.get('datetime', '')
    
    time_str = ""
    if timestamp:
        try:
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%H:%M")
        except:
            pass
    
    st.markdown(f"""
    <div class="news-card">
        <div class="news-title">{title}</div>
        <div class="news-meta">
            <span class="news-source">{source}</span>
            <span class="news-time">{time_str}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if url:
        st.markdown(f"[Read more →]({url})")


def show_analysis_box(title, metrics, badge=None):
    """Display an analysis box with metrics"""
    badge_html = f'<span class="analysis-badge">{badge}</span>' if badge else ''
    
    rows_html = ""
    for label, value in metrics.items():
        if isinstance(value, float):
            if abs(value) > 100:
                value_str = f"{value:,.0f}"
            else:
                value_str = f"{value:.2f}"
        else:
            value_str = str(value)
        
        # Color coding for certain metrics
        color = ""
        if 'Return' in label or 'CAGR' in label:
            color = "color: #10b981;" if float(str(value).replace('%', '').replace(',', '')) >= 0 else "color: #ef4444;"
        elif 'Drawdown' in label:
            color = "color: #ef4444;"
        
        rows_html += f'''
        <div class="analysis-row">
            <span class="analysis-label">{label}</span>
            <span class="analysis-value" style="{color}">{value_str}</span>
        </div>
        '''
    
    st.markdown(f"""
    <div class="analysis-box">
        <div class="analysis-header">
            <span class="analysis-title">{title}</span>
            {badge_html}
        </div>
        {rows_html}
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# TAB IMPLEMENTATIONS
# =============================================================================
def tab_dashboard():
    """Main Dashboard Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📊 Market Overview</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Real-time market snapshot and key indicators</div>", unsafe_allow_html=True)
    
    # Quick stats row - use bulk fetching for better performance
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    # Fetch all quotes in parallel
    quick_stats_tickers = ["SPY", "QQQ", "^VIX", "DX-Y.NYB", "GC=F", "BTC-USD"]
    quotes = fetch_quotes_bulk(quick_stats_tickers, max_workers=6)
    
    spy = quotes.get("SPY")
    with col1:
        if spy:
            show_metric_card("S&P 500", f"{spy['price']:,.2f}", spy['change'], "$")
        else:
            show_metric_card("S&P 500", "N/A")
    
    qqq = quotes.get("QQQ")
    with col2:
        if qqq:
            show_metric_card("NASDAQ", f"{qqq['price']:,.2f}", qqq['change'], "$")
        else:
            show_metric_card("NASDAQ", "N/A")
    
    vix = quotes.get("^VIX")
    with col3:
        if vix:
            show_metric_card("VIX", f"{vix['price']:.2f}", vix['change'])
        else:
            show_metric_card("VIX", "N/A")
    
    dxy = quotes.get("DX-Y.NYB")
    with col4:
        if dxy:
            show_metric_card("DXY", f"{dxy['price']:.2f}", dxy['change'])
        else:
            show_metric_card("DXY", "N/A")
    
    gold = quotes.get("GC=F")
    with col5:
        if gold:
            show_metric_card("Gold", f"{gold['price']:,.0f}", gold['change'], "$")
        else:
            show_metric_card("Gold", "N/A")
    
    btc = quotes.get("BTC-USD")
    with col6:
        if btc:
            show_metric_card("Bitcoin", f"{btc['price']:,.0f}", btc['change'], "$")
        else:
            show_metric_card("Bitcoin", "N/A")
    
    st.markdown("---")
    
    # Two columns layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 📈 S&P 500 Chart")
        
        # Date range selector
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            start_date = st.date_input("Start", value=date.today() - timedelta(days=365), key="dash_start")
        with c2:
            end_date = st.date_input("End", value=date.today(), key="dash_end")
        with c3:
            indicators = st.multiselect("Indicators", ["SMA20", "SMA50", "EMA20", "BB", "RSI"], default=["SMA20", "SMA50"], key="dash_ind")
        
        spy_data = fetch_history("SPY", start_date=start_date, end_date=end_date)
        if not spy_data.empty:
            fig = create_candlestick_chart(spy_data, title="S&P 500 ETF (SPY)", indicators=indicators)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="dash_spy_chart")
    
    with col2:
        st.markdown("#### 🏭 Sector Performance")
        
        # Bulk fetch sector quotes
        sector_tickers = [info['ticker'] for info in SECTORS.values()]
        sector_quotes = fetch_quotes_bulk(sector_tickers, max_workers=8)
        
        sector_perf = {}
        for name, info in SECTORS.items():
            q = sector_quotes.get(info['ticker'])
            if q:
                sector_perf[name] = q['change']
        
        if sector_perf:
            fig = create_sector_heatmap(sector_perf)
            st.plotly_chart(fig, use_container_width=True, key="sector_heatmap")
    
    st.markdown("---")
    
    # Bottom section
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 📰 Top News")
        news = fetch_news()
        for article in news[:5]:
            show_news_card(article)
    
    with col2:
        st.markdown("#### 🎰 Prediction Markets")
        events = fetch_polymarket(300)
        markets = search_polymarket(events, ['market', 'stock', 'fed', 'economy', 'recession'], max_results=5)
        for m in markets:
            show_polymarket_card(m['event'], m['volume'])
    
    with col3:
        st.markdown("#### 📅 Economic Calendar")
        calendar_events = [
            ("FOMC Meeting", "Jan 28-29, 2025", "HIGH"),
            ("CPI Release", "Feb 12, 2025", "HIGH"),
            ("NFP Report", "Feb 7, 2025", "HIGH"),
            ("GDP Q4 (2nd)", "Feb 27, 2025", "MEDIUM"),
            ("PCE Inflation", "Feb 28, 2025", "HIGH"),
            ("ISM Manufacturing", "Feb 3, 2025", "MEDIUM"),
        ]
        
        for event, date_str, impact in calendar_events:
            impact_class = f"impact-{impact.lower()}"
            st.markdown(f"""
            <div class="cal-event">
                <div>
                    <span class="cal-event-name">{event}</span><br>
                    <span class="cal-event-date">{date_str}</span>
                </div>
                <span class="cal-impact {impact_class}">{impact}</span>
            </div>
            """, unsafe_allow_html=True)


def tab_monetary():
    """Monetary Policy Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>🏛️ Monetary Policy</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Central bank rates, policy outlook, and predictions</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Central Bank Rates")
        
        cols = st.columns(4)
        
        fed = fetch_fred_series("FEDFUNDS", 3)
        with cols[0]:
            if fed is not None and len(fed) > 0:
                show_metric_card("🇺🇸 Fed Funds", f"{fed.iloc[-1]:.2f}", suffix="%")
            else:
                show_metric_card("🇺🇸 Fed Funds", "N/A")
        
        with cols[1]:
            show_metric_card("🇪🇺 ECB Rate", "2.65", suffix="%")
        
        with cols[2]:
            show_metric_card("🇬🇧 BoE Rate", "4.50", suffix="%")
        
        with cols[3]:
            show_metric_card("🇯🇵 BoJ Rate", "0.50", suffix="%")
        
        st.markdown("---")
        
        st.markdown("#### Fed Funds Rate History")
        fed_hist = fetch_fred_series("FEDFUNDS", 120)
        if fed_hist is not None:
            fig = create_line_chart(fed_hist, title="Federal Funds Rate (%)", height=300)
            st.plotly_chart(fig, use_container_width=True, key="fed_hist")
        
        st.markdown("---")
        
        st.markdown("#### Economic Calendar")
        calendar_events = [
            ("FOMC Meeting", "Jan 28-29, 2025", "HIGH"),
            ("FOMC Minutes", "Feb 19, 2025", "MEDIUM"),
            ("CPI Release", "Feb 12, 2025", "HIGH"),
            ("PPI Release", "Feb 13, 2025", "MEDIUM"),
            ("NFP Report", "Feb 7, 2025", "HIGH"),
            ("Jobless Claims", "Weekly", "MEDIUM"),
            ("PCE Inflation", "Feb 28, 2025", "HIGH"),
            ("GDP Q4 (2nd Est)", "Feb 27, 2025", "MEDIUM"),
        ]
        
        for event, date_str, impact in calendar_events:
            impact_class = f"impact-{impact.lower()}"
            st.markdown(f"""
            <div class="cal-event">
                <div>
                    <span class="cal-event-name">{event}</span><br>
                    <span class="cal-event-date">{date_str}</span>
                </div>
                <span class="cal-impact {impact_class}">{impact}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### Fed Predictions")
        events = fetch_polymarket(300)
        markets = search_polymarket(events, ['fed', 'fomc', 'rate', 'powell', 'interest', 'cut', 'hike'], max_results=8)
        for m in markets:
            show_polymarket_card(m['event'], m['volume'])


def tab_macro():
    """Macro Economics Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📊 Macro Indicators</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Real-time economic data from FRED</div>", unsafe_allow_html=True)
    
    # Key metrics
    cols = st.columns(5)
    
    cpi = fetch_cpi_yoy()
    with cols[0]:
        show_metric_card("CPI (YoY)", f"{cpi:.2f}" if cpi else "N/A", suffix="%")
    
    unemp = fetch_fred_series("UNRATE", 3)
    with cols[1]:
        if unemp is not None and len(unemp) > 0:
            show_metric_card("Unemployment", f"{unemp.iloc[-1]:.1f}", suffix="%")
        else:
            show_metric_card("Unemployment", "N/A")
    
    spread = fetch_fred_series("T10Y2Y", 3)
    with cols[2]:
        if spread is not None and len(spread) > 0:
            show_metric_card("10Y-2Y Spread", f"{spread.iloc[-1]:.2f}", suffix="%")
        else:
            show_metric_card("10Y-2Y Spread", "N/A")
    
    gdp = fetch_fred_series("GDPC1", 12)
    with cols[3]:
        if gdp is not None and len(gdp) >= 2:
            gdp_growth = ((gdp.iloc[-1] / gdp.iloc[-2]) - 1) * 100 * 4
            show_metric_card("GDP Growth (Ann)", f"{gdp_growth:.1f}", suffix="%")
        else:
            show_metric_card("GDP Growth", "N/A")
    
    pce = fetch_fred_series("PCEPI", 24)
    with cols[4]:
        if pce is not None and len(pce) >= 13:
            pce_yoy = ((pce.iloc[-1] - pce.iloc[-13]) / pce.iloc[-13]) * 100
            show_metric_card("PCE (YoY)", f"{pce_yoy:.2f}", suffix="%")
        else:
            show_metric_card("PCE (YoY)", "N/A")
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### CPI Trend (YoY %)")
        cpi_data = fetch_fred_series("CPIAUCSL", 120)
        if cpi_data is not None and len(cpi_data) > 12:
            cpi_yoy = cpi_data.pct_change(12) * 100
            fig = create_line_chart(cpi_yoy.dropna(), height=300)
            st.plotly_chart(fig, use_container_width=True, key="cpi_chart")
    
    with col2:
        st.markdown("#### Yield Curve Spread (10Y-2Y)")
        spread_data = fetch_fred_series("T10Y2Y", 120)
        if spread_data is not None:
            fig = create_line_chart(spread_data, height=300)
            # Add zero line
            fig.add_hline(y=0, line_dash="dash", line_color="#ef4444", line_width=1)
            st.plotly_chart(fig, use_container_width=True, key="spread_chart")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Unemployment Rate")
        unemp_data = fetch_fred_series("UNRATE", 120)
        if unemp_data is not None:
            fig = create_line_chart(unemp_data, height=300)
            st.plotly_chart(fig, use_container_width=True, key="unemp_chart")
    
    with col2:
        st.markdown("#### Real GDP Growth (QoQ Ann.)")
        gdp_data = fetch_fred_series("A191RL1Q225SBEA", 60)
        if gdp_data is not None:
            fig = create_line_chart(gdp_data, height=300)
            fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8", line_width=1)
            st.plotly_chart(fig, use_container_width=True, key="gdp_chart")


def tab_bonds():
    """Bonds Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📊 Bonds & Fixed Income</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Treasury yields and yield curve analysis</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    # Bulk fetch all bond quotes
    bond_tickers = [info['ticker'] for info in BONDS.values()]
    bond_quotes = fetch_quotes_bulk(bond_tickers, max_workers=6)
    
    with col1:
        st.markdown("#### US Treasury Yields")
        for name, info in BONDS.items():
            show_asset_row(name, info['ticker'], "🇺🇸", 
                          prefetched_quote=bond_quotes.get(info['ticker']))
    
    with col2:
        st.markdown("#### Yield Curve")
        
        maturities = ['3M', '2Y', '5Y', '10Y', '30Y']
        yields_data = []
        
        for info in BONDS.values():
            q = bond_quotes.get(info['ticker'])
            yields_data.append(q['price'] if q else None)
        
        if all(y is not None for y in yields_data):
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=maturities,
                y=yields_data,
                mode='lines+markers',
                line=dict(color='#3b82f6', width=3),
                marker=dict(size=12),
                hovertemplate='%{x}: %{y:.2f}%<extra></extra>'
            ))
            
            fig.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor='#ffffff',
                paper_bgcolor='#ffffff',
                xaxis=dict(title="Maturity", showgrid=True, gridcolor='#f1f5f9'),
                yaxis=dict(title="Yield (%)", showgrid=True, gridcolor='#f1f5f9')
            )
            
            st.plotly_chart(fig, use_container_width=True, key="yield_curve")
            
            # Yield curve status
            if yields_data[3] - yields_data[0] < 0:
                st.error("⚠️ **Yield Curve INVERTED** - Historically a recession indicator")
            else:
                st.success("✅ **Yield Curve Normal**")
        
        st.markdown("---")
        st.markdown("#### Spread Analysis")
        
        spread_10y2y = yields_data[3] - yields_data[1] if yields_data[3] and yields_data[1] else None
        spread_10y3m = yields_data[3] - yields_data[0] if yields_data[3] and yields_data[0] else None
        
        if spread_10y2y:
            st.metric("10Y - 2Y Spread", f"{spread_10y2y:.2f}%", 
                     delta="Normal" if spread_10y2y > 0 else "Inverted")
        if spread_10y3m:
            st.metric("10Y - 3M Spread", f"{spread_10y3m:.2f}%",
                     delta="Normal" if spread_10y3m > 0 else "Inverted")


def tab_forex():
    """Forex Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>💱 Forex / Currencies</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Major, cross, and emerging market currency pairs</div>", unsafe_allow_html=True)
    
    # Category filter
    category = st.radio("Category", ["All", "Major", "Cross", "Emerging Markets"], horizontal=True, key="fx_cat")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        for pair_name, info in FOREX.items():
            if category == "All" or info['category'] == category or (category == "Emerging Markets" and info['category'] == "EM"):
                show_asset_row(pair_name, info['ticker'], info['flag'])
    
    with col2:
        st.markdown("#### Currency Chart")
        
        pair = st.selectbox("Select Pair", list(FOREX.keys()), key="fx_pair")
        
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Start", value=date.today() - timedelta(days=180), key="fx_start")
        with c2:
            end = st.date_input("End", value=date.today(), key="fx_end")
        
        ticker = FOREX[pair]['ticker']
        hist = fetch_history(ticker, start_date=start, end_date=end)
        
        if not hist.empty:
            fig = create_line_chart(hist['Close'], title=pair, height=350)
            st.plotly_chart(fig, use_container_width=True, key="fx_chart")
            
            # Stats
            returns = hist['Close'].pct_change().dropna()
            vol = returns.std() * np.sqrt(252) * 100
            
            st.markdown("#### Statistics")
            st.markdown(f"""
            - **Current**: {hist['Close'].iloc[-1]:.4f}
            - **High**: {hist['High'].max():.4f}
            - **Low**: {hist['Low'].min():.4f}
            - **Volatility (Ann.)**: {vol:.2f}%
            """)


def tab_crypto():
    """Crypto Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>🪙 Cryptocurrency</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Digital asset prices and analysis</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    # Bulk fetch all crypto quotes
    crypto_tickers = [info['ticker'] for info in CRYPTO.values()]
    crypto_quotes = fetch_quotes_bulk(crypto_tickers, max_workers=8)
    
    with col1:
        st.markdown("#### Major Cryptocurrencies")
        for name, info in CRYPTO.items():
            show_asset_row(name, info['ticker'], info['symbol'], 
                          prefetched_quote=crypto_quotes.get(info['ticker']))
        
        st.markdown("---")
        st.markdown("#### Bitcoin Chart")
        
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            start = st.date_input("Start", value=date.today() - timedelta(days=365), key="btc_start")
        with c2:
            end = st.date_input("End", value=date.today(), key="btc_end")
        with c3:
            indicators = st.multiselect("Indicators", ["SMA20", "SMA50", "BB", "RSI"], default=["SMA50"], key="btc_ind")
        
        btc_data = fetch_history("BTC-USD", start_date=start, end_date=end)
        if not btc_data.empty:
            fig = create_candlestick_chart(btc_data, title="Bitcoin (BTC-USD)", indicators=indicators)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="btc_chart")
    
    with col2:
        st.markdown("#### Crypto Markets")
        events = fetch_polymarket(300)
        markets = search_polymarket(events, ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana'], max_results=6)
        for m in markets:
            show_polymarket_card(m['event'], m['volume'])
        
        st.markdown("---")
        st.markdown("#### Market Stats")
        
        btc = crypto_quotes.get("BTC-USD")
        eth = crypto_quotes.get("ETH-USD")
        
        if btc and eth:
            eth_btc = eth['price'] / btc['price']
            st.metric("ETH/BTC Ratio", f"{eth_btc:.4f}")
            
            # BTC Dominance estimate
            total_crypto_mc = btc['price'] * 21000000 + eth['price'] * 120000000
            btc_dom = (btc['price'] * 21000000) / total_crypto_mc * 100
            st.metric("Est. BTC Dominance", f"{btc_dom:.1f}%")


def tab_tech():
    """Tech Stocks Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>💻 Technology</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Tech sector stocks and analysis</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    
    # Bulk fetch tech stocks
    tech_stocks_list = list(TECH_STOCKS.items())[:12]
    tech_tickers = [info['ticker'] for name, info in tech_stocks_list]
    tech_quotes = fetch_quotes_bulk(tech_tickers, max_workers=8)
    
    with col1:
        st.markdown("#### Tech Stocks")
        for name, info in tech_stocks_list:
            show_asset_row(name, info['ticker'], "💻", 
                          prefetched_quote=tech_quotes.get(info['ticker']))
    
    with col2:
        st.markdown("#### Stock Analysis")
        
        stock = st.selectbox("Select Stock", list(TECH_STOCKS.keys()), key="tech_stock")
        
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            start = st.date_input("Start", value=date.today() - timedelta(days=365), key="tech_start")
        with c2:
            end = st.date_input("End", value=date.today(), key="tech_end")
        with c3:
            indicators = st.multiselect("Indicators", ["SMA20", "SMA50", "EMA20", "BB", "RSI"], default=["SMA20", "SMA50", "RSI"], key="tech_ind")
        
        ticker = TECH_STOCKS[stock]['ticker']
        data = fetch_history(ticker, start_date=start, end_date=end)
        
        if not data.empty:
            fig = create_candlestick_chart(data, title=f"{stock} ({ticker})", indicators=indicators, height=500)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="tech_chart")
            
            # Metrics
            metrics = QuantEngine.full_metrics(data['Close'])
            if metrics:
                st.markdown("#### Performance Metrics")
                cols = st.columns(4)
                with cols[0]:
                    show_metric_card("Total Return", f"{metrics['Total Return']:.2f}", suffix="%")
                with cols[1]:
                    show_metric_card("Volatility", f"{metrics['Volatility']:.2f}", suffix="%")
                with cols[2]:
                    show_metric_card("Sharpe", f"{metrics['Sharpe']:.2f}")
                with cols[3]:
                    show_metric_card("Max Drawdown", f"{metrics['Max Drawdown']:.2f}", suffix="%")


def tab_markets():
    """Global Markets Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📈 Global Markets</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>World indices and commodities</div>", unsafe_allow_html=True)
    
    region = st.radio("Region", ["All", "US", "Europe", "Asia"], horizontal=True, key="mkt_region")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Global Indices")
        
        # Collect tickers to fetch based on region filter
        indices_to_show = [(name, info) for name, info in INDICES.items() 
                          if region == "All" or info['region'] == region]
        indices_tickers = [info['ticker'] for name, info in indices_to_show]
        
        # Bulk fetch quotes for indices
        indices_quotes = fetch_quotes_bulk(indices_tickers, max_workers=8)
        
        # Display with pre-fetched quotes
        for name, info in indices_to_show:
            show_asset_row(name, info['ticker'], info['flag'], 
                          prefetched_quote=indices_quotes.get(info['ticker']))
        
        st.markdown("---")
        st.markdown("#### Commodities")
        
        comm_cat = st.radio("Category", ["All", "Precious Metals", "Energy", "Agriculture"], horizontal=True, key="comm_cat")
        
        # Collect commodity tickers based on category filter
        commodities_to_show = [(name, info) for name, info in COMMODITIES.items() 
                               if comm_cat == "All" or info['category'] == comm_cat]
        commodities_tickers = [info['ticker'] for name, info in commodities_to_show]
        
        # Bulk fetch quotes for commodities
        commodities_quotes = fetch_quotes_bulk(commodities_tickers, max_workers=8)
        
        # Display with pre-fetched quotes
        for name, info in commodities_to_show:
            show_asset_row(name, info['ticker'], info['emoji'], 
                          prefetched_quote=commodities_quotes.get(info['ticker']))
    
    with col2:
        st.markdown("#### Smart Money Ratios")
        
        # Fetch all ratio tickers in parallel
        ratio_tickers = ["XLY", "XLP", "SPY", "TLT", "HG=F", "GC=F"]
        ratio_quotes = fetch_quotes_bulk(ratio_tickers, max_workers=6)
        
        # XLY/XLP Ratio
        st.markdown("**Consumer Disc./Staples (Risk Appetite)**")
        xly = ratio_quotes.get("XLY")
        xlp = ratio_quotes.get("XLP")
        if xly and xlp:
            ratio = xly['price'] / xlp['price']
            spread = xly['change'] - xlp['change']
            show_metric_card("XLY/XLP", f"{ratio:.3f}", spread)
            
            if spread > 2:
                st.success("📈 **Risk-On** - Discretionary outperforming")
            elif spread < -2:
                st.warning("📉 **Risk-Off** - Staples outperforming")
            else:
                st.info("➡️ **Neutral**")
        
        st.markdown("---")
        
        # SPY/TLT Ratio
        st.markdown("**Stocks/Bonds Ratio**")
        spy = ratio_quotes.get("SPY")
        tlt = ratio_quotes.get("TLT")
        if spy and tlt:
            ratio = spy['price'] / tlt['price']
            spread = spy['change'] - tlt['change']
            show_metric_card("SPY/TLT", f"{ratio:.3f}", spread)
            
            if spread > 3:
                st.success("📈 **Stocks Leading**")
            elif spread < -3:
                st.warning("📉 **Flight to Safety**")
            else:
                st.info("➡️ **Balanced**")
        
        st.markdown("---")
        
        # Copper/Gold Ratio
        st.markdown("**Copper/Gold (Economic Growth)**")
        copper = ratio_quotes.get("HG=F")
        gold = ratio_quotes.get("GC=F")
        if copper and gold:
            ratio = copper['price'] / gold['price'] * 1000
            show_metric_card("Cu/Au Ratio", f"{ratio:.2f}")


def tab_compare():
    """Comparison & Analysis Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>🔍 Compare & Analyze</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Custom asset comparison with detailed analytics</div>", unsafe_allow_html=True)
    
    # Inputs
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        tickers_input = st.text_input(
            "Assets (comma-separated)",
            value=", ".join(st.session_state.comparison_assets),
            key="compare_tickers"
        )
    
    with col2:
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=365), key="compare_start")
    
    with col3:
        end_date = st.date_input("End Date", value=date.today(), key="compare_end")
    
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    
    if not tickers:
        st.info("Enter at least one ticker to analyze")
        return
    
    st.session_state.comparison_assets = tickers
    
    # Fetch data
    prices = fetch_multiple(tickers, start_date=start_date, end_date=end_date)
    
    if prices.empty:
        st.error("Could not fetch data for the specified tickers and date range")
        return
    
    st.markdown("---")
    
    # Performance Chart
    st.markdown("#### 📈 Normalized Performance (Base 100)")
    normalized = (prices / prices.iloc[0]) * 100
    fig = create_line_chart(normalized, height=400)
    st.plotly_chart(fig, use_container_width=True, key="perf_chart")
    
    st.markdown("---")
    
    # Detailed Analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Performance Metrics")
        
        returns = prices.pct_change().dropna()
        
        for ticker in tickers:
            if ticker in prices.columns:
                metrics = QuantEngine.full_metrics(prices[ticker])
                if metrics:
                    show_analysis_box(
                        ticker,
                        {
                            'Price': f"${prices[ticker].iloc[-1]:,.2f}",
                            'Total Return': f"{metrics['Total Return']:.2f}%",
                            'CAGR': f"{metrics['CAGR']:.2f}%",
                            'Volatility': f"{metrics['Volatility']:.2f}%",
                            'Sharpe Ratio': f"{metrics['Sharpe']:.2f}",
                            'Sortino Ratio': f"{metrics['Sortino']:.2f}",
                            'Max Drawdown': f"{metrics['Max Drawdown']:.2f}%",
                            'VaR 95%': f"{metrics['VaR 95%']:.2f}%",
                            'Win Rate': f"{metrics['Win Rate']:.1f}%",
                            'Best Day': f"{metrics['Best Day']:.2f}%",
                            'Worst Day': f"{metrics['Worst Day']:.2f}%"
                        }
                    )
    
    with col2:
        st.markdown("#### 🔗 Correlation Matrix")
        if len(tickers) > 1:
            corr = returns.corr()
            fig = create_heatmap(corr, height=350)
            st.plotly_chart(fig, use_container_width=True, key="corr_chart")
        
        st.markdown("---")
        
        st.markdown("#### 📉 Drawdown Analysis")
        for ticker in tickers[:3]:  # Limit to 3 for readability
            if ticker in prices.columns:
                dd = QuantEngine.drawdown_series(prices[ticker])
                fig = create_drawdown_chart(dd, title=f"{ticker} Drawdown", height=150)
                st.plotly_chart(fig, use_container_width=True, key=f"dd_{ticker}")


def tab_portfolio():
    """Portfolio Lab Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>🧪 Portfolio Lab</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Backtest and analyze portfolio strategies</div>", unsafe_allow_html=True)
    
    # Portfolio inputs
    col1, col2 = st.columns([2, 1])
    
    with col1:
        tickers_input = st.text_input("Portfolio Assets", value="AAPL, MSFT, GOOGL, AMZN, NVDA", key="port_tickers")
    
    with col2:
        weights_input = st.text_input("Weights", value="0.2, 0.2, 0.2, 0.2, 0.2", key="port_weights")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        benchmark = st.text_input("Benchmark", value="SPY", key="port_bench")
    
    with col2:
        start_date = st.date_input("Start", value=date.today() - timedelta(days=365*2), key="port_start")
    
    with col3:
        end_date = st.date_input("End", value=date.today(), key="port_end")
    
    with col4:
        risk_free = st.number_input("Risk-Free %", value=4.0, step=0.1, key="port_rf") / 100
    
    with col5:
        rebalance = st.selectbox("Rebalance", ["Monthly", "Quarterly", "Yearly", "Never"], key="port_rebal")
    
    rebal_map = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y", "Never": "N"}
    
    if st.button("🚀 Run Backtest", type="primary", key="port_run"):
        tickers = [t.strip().upper() for t in tickers_input.split(",")]
        
        try:
            weights = [float(w.strip()) for w in weights_input.split(",")]
        except:
            weights = [1/len(tickers)] * len(tickers)
        
        if len(weights) != len(tickers):
            weights = [1/len(tickers)] * len(tickers)
        
        # Normalize weights
        weights = [w / sum(weights) for w in weights]
        weights_dict = {t: w for t, w in zip(tickers, weights)}
        
        with st.spinner("Running backtest..."):
            all_tickers = tickers + [benchmark.upper()]
            prices = fetch_multiple(all_tickers, start_date=start_date, end_date=end_date)
            
            if prices.empty:
                st.error("Could not fetch data")
                return
            
            # Backtest
            portfolio = QuantEngine.backtest_portfolio(
                prices, weights_dict, 
                initial_capital=100000, 
                rebalance_frequency=rebal_map[rebalance]
            )
            
            if portfolio is None:
                st.error("Backtest failed")
                return
            
            # Benchmark
            bench_ticker = benchmark.upper()
            if bench_ticker in prices.columns:
                bench_values = (prices[bench_ticker] / prices[bench_ticker].iloc[0]) * 100000
            else:
                bench_values = portfolio
            
            # Metrics
            port_metrics = QuantEngine.full_metrics(portfolio, risk_free)
            bench_metrics = QuantEngine.full_metrics(bench_values, risk_free)
        
        st.markdown("---")
        
        # Results
        st.markdown("#### 📊 Performance Comparison")
        
        cols = st.columns(6)
        metrics_display = [
            ("CAGR", "CAGR", "%"),
            ("Volatility", "Volatility", "%"),
            ("Sharpe", "Sharpe", ""),
            ("Sortino", "Sortino", ""),
            ("Max DD", "Max Drawdown", "%"),
            ("Calmar", "Calmar", "")
        ]
        
        for i, (label, key, suffix) in enumerate(metrics_display):
            with cols[i]:
                port_val = port_metrics[key]
                bench_val = bench_metrics[key]
                diff = port_val - bench_val
                
                st.markdown(f"""
                <div class="card">
                    <div class="card-label">{label}</div>
                    <div class="card-value-sm">{port_val:.2f}{suffix}</div>
                    <div style="font-size: 0.7rem; color: #94a3b8;">Bench: {bench_val:.2f}{suffix}</div>
                    <div class="card-delta {'delta-up' if diff >= 0 else 'delta-down'}">{'▲' if diff >= 0 else '▼'} {abs(diff):.2f}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📈 Portfolio vs Benchmark")
            port_norm = (portfolio / portfolio.iloc[0]) * 100
            bench_norm = (bench_values / bench_values.iloc[0]) * 100
            combined = pd.DataFrame({'Portfolio': port_norm, benchmark.upper(): bench_norm})
            fig = create_line_chart(combined, height=350)
            st.plotly_chart(fig, use_container_width=True, key="wealth_chart")
        
        with col2:
            st.markdown("#### 📉 Drawdown")
            fig = create_drawdown_chart(port_metrics['Drawdown Series'], height=350)
            st.plotly_chart(fig, use_container_width=True, key="dd_chart")
        
        # Additional stats
        st.markdown("---")
        st.markdown("#### 📋 Detailed Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            show_analysis_box(
                "Portfolio",
                {
                    'Final Value': f"${portfolio.iloc[-1]:,.0f}",
                    'Total Return': f"{port_metrics['Total Return']:.2f}%",
                    'CAGR': f"{port_metrics['CAGR']:.2f}%",
                    'Volatility': f"{port_metrics['Volatility']:.2f}%",
                    'Sharpe Ratio': f"{port_metrics['Sharpe']:.2f}",
                    'Sortino Ratio': f"{port_metrics['Sortino']:.2f}",
                    'Max Drawdown': f"{port_metrics['Max Drawdown']:.2f}%",
                    'Calmar Ratio': f"{port_metrics['Calmar']:.2f}",
                    'VaR 95%': f"{port_metrics['VaR 95%']:.2f}%",
                    'CVaR 95%': f"{port_metrics['CVaR 95%']:.2f}%",
                    'Win Rate': f"{port_metrics['Win Rate']:.1f}%",
                    'Skewness': f"{port_metrics['Skewness']:.2f}",
                    'Kurtosis': f"{port_metrics['Kurtosis']:.2f}"
                },
                badge=f"{rebalance} Rebalancing"
            )
        
        with col2:
            show_analysis_box(
                f"Benchmark ({benchmark.upper()})",
                {
                    'Final Value': f"${bench_values.iloc[-1]:,.0f}",
                    'Total Return': f"{bench_metrics['Total Return']:.2f}%",
                    'CAGR': f"{bench_metrics['CAGR']:.2f}%",
                    'Volatility': f"{bench_metrics['Volatility']:.2f}%",
                    'Sharpe Ratio': f"{bench_metrics['Sharpe']:.2f}",
                    'Sortino Ratio': f"{bench_metrics['Sortino']:.2f}",
                    'Max Drawdown': f"{bench_metrics['Max Drawdown']:.2f}%",
                    'Calmar Ratio': f"{bench_metrics['Calmar']:.2f}",
                    'VaR 95%': f"{bench_metrics['VaR 95%']:.2f}%",
                    'CVaR 95%': f"{bench_metrics['CVaR 95%']:.2f}%",
                    'Win Rate': f"{bench_metrics['Win Rate']:.1f}%",
                    'Skewness': f"{bench_metrics['Skewness']:.2f}",
                    'Kurtosis': f"{bench_metrics['Kurtosis']:.2f}"
                },
                badge="Buy & Hold"
            )


def tab_watchlist():
    """Watchlist Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>👁️ Watchlist</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Track your favorite assets</div>", unsafe_allow_html=True)
    
    # Add ticker
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("Add Ticker", key="add_ticker", placeholder="Enter ticker symbol...")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Add", key="add_btn"):
            if new_ticker and new_ticker.upper() not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_ticker.upper())
                st.rerun()
    
    # Display watchlist
    st.markdown("---")
    
    if st.session_state.watchlist:
        # Watchlist tags
        tags_html = ""
        for ticker in st.session_state.watchlist:
            tags_html += f'<span class="watchlist-tag">{ticker} <span class="remove" onclick="this.parentElement.remove()">×</span></span>'
        
        st.markdown(f"**Current Watchlist:** {tags_html}", unsafe_allow_html=True)
        
        # Remove ticker
        remove_ticker = st.selectbox("Remove Ticker", [""] + st.session_state.watchlist, key="remove_select")
        if remove_ticker and st.button("🗑️ Remove", key="remove_btn"):
            st.session_state.watchlist.remove(remove_ticker)
            st.rerun()
        
        st.markdown("---")
        
        # Bulk fetch all watchlist quotes for better performance
        watchlist_quotes = fetch_quotes_bulk(st.session_state.watchlist, max_workers=8)
        
        # Display assets with pre-fetched quotes
        for ticker in st.session_state.watchlist:
            show_asset_row(ticker, ticker, "⭐", 
                          prefetched_quote=watchlist_quotes.get(ticker))
        
        # Performance comparison
        st.markdown("---")
        st.markdown("#### 📈 Watchlist Performance")
        
        period = st.selectbox("Period", ["1W", "1M", "3M", "6M", "1Y"], index=2, key="watch_period")
        period_map = {"1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
        
        prices = fetch_multiple(st.session_state.watchlist, period=period_map[period])
        if not prices.empty:
            normalized = (prices / prices.iloc[0]) * 100
            fig = create_line_chart(normalized, height=400)
            st.plotly_chart(fig, use_container_width=True, key="watch_chart")
    else:
        st.info("Your watchlist is empty. Add some tickers above!")


def tab_news():
    """News Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📰 News & Events</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Latest financial news and market events</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Latest Headlines")
        news = fetch_news()
        if news:
            for article in news[:15]:
                show_news_card(article)
        else:
            st.warning("Unable to fetch news")
    
    with col2:
        st.markdown("#### Google Trends")
        keywords = ["Inflation", "Recession", "Fed", "Stocks", "Bitcoin"]
        trends = fetch_google_trends(keywords)
        
        for kw in keywords:
            if kw in trends.columns:
                current = trends[kw].iloc[-1]
                st.markdown(f"**{kw}** — Interest: {current}/100")
                fig = create_sparkline(trends[kw], height=50)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key=f"trend_{kw}")
        
        st.markdown("---")
        
        st.markdown("#### Quick Links")
        st.markdown("""
        **📰 News**
        - [Bloomberg](https://bloomberg.com)
        - [CNBC](https://cnbc.com)
        - [Reuters](https://reuters.com)
        - [WSJ](https://wsj.com)
        - [FT](https://ft.com)
        
        **🏛️ Central Banks**
        - [Federal Reserve](https://federalreserve.gov)
        - [ECB](https://ecb.europa.eu)
        - [Bank of England](https://bankofengland.co.uk)
        
        **📊 Data**
        - [FRED](https://fred.stlouisfed.org)
        - [TradingView](https://tradingview.com)
        - [Yahoo Finance](https://finance.yahoo.com)
        """)


def tab_geopolitics():
    """Geopolitics Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>🌍 Geopolitics</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Global events and prediction markets</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Geopolitical Markets")
        events = fetch_polymarket(300)
        markets = search_polymarket(events, ['war', 'ukraine', 'russia', 'china', 'taiwan', 'trump', 'election', 'tariff', 'sanctions'], max_results=10)
        for m in markets:
            show_polymarket_card(m['event'], m['volume'])
    
    with col2:
        st.markdown("#### Trend Analysis")
        keywords = ["War", "Sanctions", "Trade War", "Elections"]
        trends = fetch_google_trends(keywords)
        
        for kw in keywords:
            if kw in trends.columns:
                current = trends[kw].iloc[-1]
                prev = trends[kw].iloc[-8] if len(trends[kw]) > 8 else trends[kw].iloc[0]
                change = current - prev
                
                st.markdown(f"**{kw}** — Interest: {current}/100")
                fig = create_sparkline(trends[kw], height=60)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key=f"geo_trend_{kw}")


def tab_reports():
    """Reports Tab"""
    st.markdown("<div class='section-header'><span class='section-title'>📥 Reports & Export</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-subtitle'>Generate and download market reports</div>", unsafe_allow_html=True)
    
    st.markdown("#### Select Assets for Report")
    
    all_tickers = []
    
    with st.expander("🌍 Indices", expanded=True):
        cols = st.columns(4)
        for i, (name, info) in enumerate(list(INDICES.items())[:12]):
            with cols[i % 4]:
                if st.checkbox(name, key=f"rep_{info['ticker']}"):
                    all_tickers.append(info['ticker'])
    
    with st.expander("🪙 Crypto"):
        cols = st.columns(4)
        for i, (name, info) in enumerate(CRYPTO.items()):
            with cols[i % 4]:
                if st.checkbox(name, key=f"rep_{info['ticker']}"):
                    all_tickers.append(info['ticker'])
    
    with st.expander("💻 Tech Stocks"):
        cols = st.columns(4)
        for i, (name, info) in enumerate(list(TECH_STOCKS.items())[:12]):
            with cols[i % 4]:
                if st.checkbox(name, key=f"rep_{info['ticker']}"):
                    all_tickers.append(info['ticker'])
    
    with st.expander("📦 ETFs"):
        cols = st.columns(4)
        for i, (ticker, info) in enumerate(list(ETFS.items())[:12]):
            with cols[i % 4]:
                if st.checkbox(f"{ticker} - {info['name']}", key=f"rep_{ticker}"):
                    all_tickers.append(ticker)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.date_input("Start Date", value=date.today() - timedelta(days=365), key="rep_start")
    with col2:
        end = st.date_input("End Date", value=date.today(), key="rep_end")
    with col3:
        format_type = st.selectbox("Format", ["Excel", "CSV"], key="rep_format")
    
    if all_tickers and st.button("📥 Generate Report", type="primary", key="rep_generate"):
        with st.spinner("Generating report..."):
            prices = fetch_multiple(all_tickers, start_date=start, end_date=end)
            
            if not prices.empty:
                returns = prices.pct_change().dropna()
                corr = returns.corr()
                
                # Calculate metrics for each asset
                metrics_data = []
                for ticker in all_tickers:
                    if ticker in prices.columns:
                        m = QuantEngine.full_metrics(prices[ticker])
                        if m:
                            metrics_data.append({
                                'Ticker': ticker,
                                'Total Return (%)': m['Total Return'],
                                'CAGR (%)': m['CAGR'],
                                'Volatility (%)': m['Volatility'],
                                'Sharpe': m['Sharpe'],
                                'Max Drawdown (%)': m['Max Drawdown']
                            })
                
                metrics_df = pd.DataFrame(metrics_data)
                
                if format_type == "Excel":
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        prices.to_excel(writer, sheet_name='Prices')
                        returns.to_excel(writer, sheet_name='Returns')
                        corr.to_excel(writer, sheet_name='Correlation')
                        metrics_df.to_excel(writer, sheet_name='Metrics', index=False)
                    output.seek(0)
                    
                    st.download_button(
                        "📥 Download Excel Report",
                        data=output,
                        file_name=f"IGEA_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.download_button(
                        "📥 Download CSV (Prices)",
                        data=prices.to_csv(),
                        file_name=f"IGEA_Prices_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.error("Could not fetch data for the selected assets")


# =============================================================================
# SIDEBAR
# =============================================================================
def render_sidebar():
    """Render the sidebar"""
    with st.sidebar:
        st.markdown("### 🏛️ IGEA OMNIS")
        st.caption("v8.0 Institutional Edition")
        
        st.markdown("---")
        
        # Market Regime
        regime_name, regime_emoji, regime_class, signals = detect_market_regime()
        st.markdown("#### Market Regime")
        st.markdown(f"""
        <div class="regime-badge {regime_class}">
            {regime_emoji} {regime_name} ({signals['score']}/{signals['max_score']})
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Signals
        st.markdown("#### Signals")
        if signals.get('spy_sma50') is not None:
            st.markdown(f"{'✅' if signals['spy_sma50'] else '❌'} SPY > SMA50")
        if signals.get('golden_cross') is not None:
            st.markdown(f"{'✅' if signals['golden_cross'] else '❌'} Golden Cross")
        if signals.get('vix') is not None:
            vix_ok = signals['vix'] < 20
            st.markdown(f"{'✅' if vix_ok else '❌'} VIX < 20 ({signals['vix']:.1f})")
        if signals.get('dxy_down') is not None:
            st.markdown(f"{'✅' if signals['dxy_down'] else '❌'} DXY Down")
        if signals.get('yield_spread') is not None:
            spread_ok = signals['yield_spread'] > 0
            st.markdown(f"{'✅' if spread_ok else '❌'} Yield Curve")
        if signals.get('credit_spread') is not None:
            st.markdown(f"{'✅' if signals['credit_spread'] else '❌'} Credit Spread")
        
        st.markdown("---")
        
        # Quick Stats
        st.markdown("#### Quick Stats")
        
        # Fetch sidebar stats in parallel
        sidebar_tickers = ["SPY", "^VIX"]
        sidebar_quotes = fetch_quotes_bulk(sidebar_tickers, max_workers=2)
        
        spy = sidebar_quotes.get("SPY")
        if spy:
            color = "#10b981" if spy['change'] >= 0 else "#ef4444"
            arrow = "▲" if spy['change'] >= 0 else "▼"
            st.markdown(f"**S&P 500**: ${spy['price']:,.2f} <span style='color:{color}'>{arrow}{abs(spy['change']):.2f}%</span>", unsafe_allow_html=True)
        
        vix_q = sidebar_quotes.get("^VIX")
        if vix_q:
            color = "#10b981" if vix_q['price'] < 20 else "#f59e0b" if vix_q['price'] < 30 else "#ef4444"
            st.markdown(f"**VIX**: <span style='color:{color}'>{vix_q['price']:.2f}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Data Sources
        st.markdown("#### Data Sources")
        st.caption("✅ Yahoo Finance")
        st.caption(f"{'✅' if FRED_OK else '⚠️'} FRED")
        st.caption(f"{'✅' if TRENDS_OK else '⚠️'} Google Trends")
        st.caption("✅ Polymarket")
        st.caption("✅ Finnhub")
        
        st.markdown("---")
        
        # Refresh
        if st.button("🔄 Refresh Data", key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()
        
        st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")


# =============================================================================
# MAIN APPLICATION
# =============================================================================
def main():
    """Main application"""
    render_sidebar()
    
    # Header
    regime_name, regime_emoji, regime_class, _ = detect_market_regime()
    current_datetime = datetime.now().strftime("%A, %B %d, %Y — %H:%M:%S")
    
    st.markdown(f"""
    <div class="main-header">
        <h1>🏛️ IGEA OMNIS v8.0</h1>
        <div class="subtitle">Institutional Market Intelligence & Portfolio Analytics</div>
        <div class="timestamp">{current_datetime}</div>
        <div style="text-align: center;">
            <span class="regime-badge {regime_class}">{regime_emoji} {regime_name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation Tabs
    tabs = st.tabs([
        "📊 Dashboard",
        "🏛️ Monetary",
        "📊 Macro",
        "📊 Bonds",
        "💱 Forex",
        "💻 Tech",
        "🪙 Crypto",
        "📈 Markets",
        "🌍 Geopolitics",
        "🔍 Compare",
        "🧪 Portfolio",
        "👁️ Watchlist",
        "📰 News",
        "📥 Reports"
    ])
    
    with tabs[0]:
        tab_dashboard()
    with tabs[1]:
        tab_monetary()
    with tabs[2]:
        tab_macro()
    with tabs[3]:
        tab_bonds()
    with tabs[4]:
        tab_forex()
    with tabs[5]:
        tab_tech()
    with tabs[6]:
        tab_crypto()
    with tabs[7]:
        tab_markets()
    with tabs[8]:
        tab_geopolitics()
    with tabs[9]:
        tab_compare()
    with tabs[10]:
        tab_portfolio()
    with tabs[11]:
        tab_watchlist()
    with tabs[12]:
        tab_news()
    with tabs[13]:
        tab_reports()
    
    # Footer
    st.markdown("""
    <div class="app-footer">
        <div class="title">IGEA OMNIS v8.0 — Institutional Edition</div>
        <div class="sources">Yahoo Finance • FRED • Polymarket • Google Trends • Finnhub</div>
        <div class="disclaimer">⚠️ For informational purposes only • Not financial advice</div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

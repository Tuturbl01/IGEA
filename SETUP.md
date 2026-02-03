# IGEA OMNIS v8.0 - Setup Guide

## API Keys Configuration

The application now securely loads API keys from Streamlit secrets or environment variables instead of hardcoded values.

### Option 1: Streamlit Secrets (Recommended for Streamlit Cloud)

Create a `.streamlit/secrets.toml` file in your project directory:

```toml
# .streamlit/secrets.toml
fred_api_key = "your_fred_api_key_here"
finnhub_api_key = "your_finnhub_api_key_here"
newsapi_api_key = "your_newsapi_api_key_here"
```

Or use uppercase keys:
```toml
FRED_API_KEY = "your_fred_api_key_here"
FINNHUB_API_KEY = "your_finnhub_api_key_here"
NEWSAPI_API_KEY = "your_newsapi_api_key_here"
```

### Option 2: Environment Variables

Set environment variables before running the application:

**Linux/Mac:**
```bash
export FRED_API_KEY="your_fred_api_key_here"
export FINNHUB_API_KEY="your_finnhub_api_key_here"
export NEWSAPI_API_KEY="your_newsapi_api_key_here"
```

**Windows (PowerShell):**
```powershell
$env:FRED_API_KEY="your_fred_api_key_here"
$env:FINNHUB_API_KEY="your_finnhub_api_key_here"
$env:NEWSAPI_API_KEY="your_newsapi_api_key_here"
```

**Windows (Command Prompt):**
```cmd
set FRED_API_KEY=your_fred_api_key_here
set FINNHUB_API_KEY=your_finnhub_api_key_here
set NEWSAPI_API_KEY=your_newsapi_api_key_here
```

### Getting API Keys

1. **FRED (Federal Reserve Economic Data)**
   - Visit: https://fred.stlouisfed.org/docs/api/api_key.html
   - Free API key for economic data

2. **Finnhub**
   - Visit: https://finnhub.io/
   - Free tier available for market news

3. **NewsAPI**
   - Visit: https://newsapi.org/
   - Free tier available for news articles

## Running the Application

```bash
streamlit run igea_omnis_v80.py
```

## Recent Enhancements

### Security
- ✅ Removed hardcoded API keys
- ✅ Secure loading from Streamlit secrets with environment variable fallback

### Performance
- ✅ Parallel quote fetching using ThreadPoolExecutor
- ✅ Bulk data loading reduces API call latency by up to 80%

### Reliability
- ✅ HTTP retry logic with exponential backoff
- ✅ Comprehensive logging for debugging
- ✅ Graceful error handling with informative messages

### Code Quality
- ✅ No silent failures (all exceptions logged)
- ✅ Improved market regime detection with proper SMA calculations
- ✅ None-safe field access throughout

## Notes

- API keys are optional - the app will work with reduced functionality if some keys are missing
- Check the console/logs for warnings about missing API keys
- The refresh button clears all caches and reloads fresh data

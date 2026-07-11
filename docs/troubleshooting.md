# Troubleshooting Guide

This comprehensive guide covers common issues, solutions, and frequently asked questions for the Trading System.

## System Status

**Production-Ready Trading System** with comprehensive data integration and robust testing infrastructure.

## Frequently Asked Questions

### Installation Issues

**Q: What are the system requirements?**
A: The system requires:
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Windows 10+ (for local deployment)

**Q: How do I install the system?**
A: Follow these steps:
1. Clone the repository: `git clone https://github.com/nishantnayar/trading-system.git`
2. Create conda environment: `conda create -n trading-system python=3.11`
3. Install dependencies: `pip install -r requirements.txt`
4. Set up databases: `python scripts/setup_databases.py`
5. Configure environment: Copy `deployment/env.example` to `.env`

**Q: What if I get import errors?**
A: Ensure you're in the project root directory and have activated your conda environment. Check that all dependencies are installed with `pip list`.

### Configuration Problems

**Q: How do I configure the database?**
A: Edit your `.env` file with the correct database credentials:
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
TRADING_DB_NAME=trading_system
PREFECT_DB_NAME=prefect
```

**Q: How do I get Alpaca API keys?**
A: 
1. Sign up at [Alpaca Markets](https://alpaca.markets/)
2. Go to your dashboard
3. Generate API keys
4. Add them to your `.env` file:
```env
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

### Runtime Errors

**Q: The system won't start, what should I check?**
A: Check these in order:
1. Database connectivity: `python scripts/test_database_connections.py`
2. Environment variables: `cat .env`
3. **Database logs** (primary): Query `logging.system_logs` table in PostgreSQL
4. **File logs** (fallback): `tail -f logs/errors.log` (only if database fails)
4. Port availability: Ensure ports 8001, 8501, 4200, 5432, 6379 are free

**Q: How do I check if all services are running?**
A: Use the health check script:
```bash
python scripts/run_tests.py check
```

**Q: How do I access the Streamlit UI?**
A: The Streamlit UI is available at `http://localhost:8501`. If it's not running, start it with:
```bash
python streamlit_ui/run_streamlit.py
# Or
streamlit run streamlit_ui/streamlit_app.py
```

**Q: How do I set up AI features (stock screener with natural language)?**
A: 
1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Install a model: `ollama pull phi3`
3. Test connection: `python scripts/test_ollama.py`
4. Natural language queries will work in the Stock Screener page

**Q: Do I need Ollama for the stock screener?**
A: No, Ollama is optional. You can use traditional filters without it. Natural language queries require Ollama.

## Common Issues

### Prefect Workflow Issues

**Error**: `Prefect server not accessible` or `Connection refused`

**Solutions**:
1. **Check Prefect Server Status**:
   ```bash
   # Check if Prefect server is running
   curl http://localhost:4200/api/health
   
   # If not running, start it
   prefect server start
   ```

2. **Verify Database Connection**:
   ```bash
   # Check Prefect database connection
   prefect config get PREFECT_API_DATABASE_CONNECTION_URL
   
   # Test connection
   psql -h localhost -U postgres -d prefect -c "SELECT 1;"
   ```

3. **Check Worker Status**:
   ```bash
   # List workers
   prefect worker ls
   
   # Start worker if needed
   prefect worker start --pool default-agent-pool
   ```

**Error**: `Flow deployment failed` or `Deployment not found`

**Solutions**:
1. **Verify Flow Code**:
   ```bash
   # Check flow syntax
   python -m py_compile src/shared/prefect/flows/data_ingestion/yahoo_flows.py
   ```

2. **Redeploy Flows**:
   ```bash
   # Redeploy all flows
   python src/shared/prefect/flows/data_ingestion/yahoo_flows.py
   ```

3. **Check Deployment Status**:
   ```bash
   # List deployments
   prefect deployment ls
   
   # Inspect specific deployment
   prefect deployment inspect "Daily Market Data Update/Daily Market Data Update"
   ```

**Error**: `duplicate key value violates unique constraint "unique_symbol_timestamp"` when loading Yahoo adjusted data

**Cause**: The `market_data` table still has the old unique constraint on `(symbol, timestamp)` only, so adjusted and unadjusted rows conflict.

**Solution**: Run the migration to switch to `(symbol, timestamp, data_source)` and allow `yahoo_adjusted`:
```bash
psql -h <host> -U <user> -d <database> -f scripts/20_market_data_allow_yahoo_adjusted.sql
```
See [Data Sources: Yahoo](data-ingestion/data-sources-yahoo.md) and `scripts/20_market_data_allow_yahoo_adjusted.sql`.

**Error**: `Flow run failed` or `Task execution error`

**Solutions**:
1. **Check Flow Run Logs**:
   ```bash
   # List recent flow runs
   prefect flow-run ls --limit 10
   
   # View logs for specific run
   prefect flow-run logs <flow-run-id>
   ```

2. **Check Database Logs**:
   ```sql
   -- Query system logs for errors
   SELECT * FROM logging.system_logs 
   WHERE level = 'ERROR' 
   ORDER BY timestamp DESC 
   LIMIT 20;
   ```

3. **Verify Data Availability**:
   ```bash
   # Check if required data exists
   python -c "from src.shared.database.connection import get_db; db = next(get_db()); print(db.execute('SELECT COUNT(*) FROM market_data').scalar())"
   ```

### Data Ingestion Issues

**Error**: `Yahoo Finance API rate limit exceeded` or `429 Too Many Requests`

**Solutions**:
1. **Add Rate Limiting**:
   ```python
   import time
   time.sleep(1)  # Wait 1 second between requests
   ```

2. **Use Batch Processing**:
   ```python
   # Process symbols in smaller batches
   batch_size = 10
   for i in range(0, len(symbols), batch_size):
       batch = symbols[i:i+batch_size]
       process_batch(batch)
       time.sleep(5)  # Wait between batches
   ```

3. **Check Load Runs Table**:
   ```sql
   -- Verify what data has been loaded
   SELECT symbol, MAX(date) as last_load_date 
   FROM data_ingestion.load_runs 
   GROUP BY symbol 
   ORDER BY last_load_date DESC;
   ```

**Error**: `Symbol not found` or `Invalid symbol`

**Solutions**:
1. **Verify Symbol in Database**:
   ```sql
   -- Check if symbol exists
   SELECT * FROM data_ingestion.symbols WHERE symbol = 'AAPL';
   ```

2. **Check Symbol Status**:
   ```sql
   -- Check for delisted symbols
   SELECT * FROM data_ingestion.symbols WHERE status = 'delisted';
   ```

3. **Update Symbol List**:
   ```bash
   # Reload symbols from company info
   python scripts/load_yahoo_data.py --data-type company_info --symbols AAPL,GOOGL
   ```

**Error**: `Data quality validation failed`

**Solutions**:
1. **Check Data Completeness**:
   ```sql
   -- Find missing data
   SELECT symbol, COUNT(*) as missing_count
   FROM market_data
   WHERE close IS NULL OR volume IS NULL
   GROUP BY symbol;
   ```

2. **Validate Price Ranges**:
   ```sql
   -- Find invalid price data
   SELECT * FROM market_data
   WHERE high < low OR open <= 0 OR close <= 0;
   ```

3. **Check for Duplicates**:
   ```sql
   -- Find duplicate entries
   SELECT symbol, timestamp, COUNT(*) 
   FROM market_data 
   GROUP BY symbol, timestamp 
   HAVING COUNT(*) > 1;
   ```

### Technical Indicators Issues

**Error**: `Insufficient data for indicator calculation`

**Solutions**:
1. **Check Historical Data Availability**:
   ```sql
   -- Verify sufficient historical data
   SELECT symbol, COUNT(*) as data_points, 
          MIN(timestamp) as earliest, MAX(timestamp) as latest
   FROM market_data
   WHERE symbol = 'AAPL'
   GROUP BY symbol;
   ```

2. **Calculate Required Lookback Period**:
   ```python
   # SMA_200 requires 200 days of data
   # RSI_14 requires 14+ days
   # Ensure you have enough historical data
   ```

3. **Backfill Missing Data**:
   ```bash
   # Load historical data
   python scripts/load_historical_data.py --symbols AAPL --start-date 2023-01-01
   ```

**Error**: `Indicator calculation timeout` or `Slow performance`

**Solutions**:
1. **Use Database-Backed Indicators**:
   ```sql
   -- Query pre-calculated indicators
   SELECT * FROM analytics.technical_indicators_latest
   WHERE symbol = 'AAPL';
   ```

2. **Optimize Calculation**:
   ```python
   # Use vectorized operations
   import pandas as pd
   df['sma_20'] = df['close'].rolling(window=20).mean()
   ```

3. **Batch Processing**:
   ```python
   # Process multiple symbols in batches
   for symbol_batch in chunks(symbols, 10):
       calculate_indicators_batch(symbol_batch)
   ```

### Streamlit UI Issues

**Error**: `ModuleNotFoundError: No module named 'streamlit'`

**Solution**: Install Streamlit and dependencies:
```bash
pip install streamlit plotly
```

**Error**: `Port 8501 is already in use`

**Solution**: Either stop the existing Streamlit process or use a different port:
```bash
# Kill existing process
pkill -f streamlit

# Or use different port
streamlit run streamlit_ui/streamlit_app.py --server.port 8502
```

**Error**: `Session state not persisting across pages`

**Solution**: Ensure session state is properly initialized in the main app:
```python
# In streamlit_app.py
def initialize_session_state():
    if 'selected_symbol' not in st.session_state:
        st.session_state.selected_symbol = 'AAPL'
```

**Error**: `Charts not displaying properly`

**Solutions**:
1. **Check Plotly Installation**:
   ```bash
   pip install plotly
   pip install --upgrade plotly
   ```

2. **Verify Data Format**:
   ```python
   # Ensure data has required columns
   required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
   assert all(col in df.columns for col in required_cols)
   ```

3. **Check Browser Console**:
   - Open browser developer tools (F12)
   - Check Console tab for JavaScript errors
   - Verify Plotly.js is loaded

4. **Clear Browser Cache**:
   ```bash
   # Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
   ```

**Error**: `API request failed` or `Connection timeout`

**Solutions**:
1. **Check FastAPI Server**:
   ```bash
   # Verify server is running
   curl http://localhost:8001/health
   
   # Check server logs
   tail -f logs/errors.log
   ```

2. **Verify API Endpoint**:
   ```bash
   # Test endpoint directly
   curl http://localhost:8001/api/market-data/stats
   ```

3. **Check CORS Settings**:
   ```python
   # In FastAPI app, ensure CORS is configured
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(CORSMiddleware, allow_origins=["*"])
   ```

**Error**: `Session state reset` or `Data lost on page refresh`

**Solutions**:
1. **Persist Critical Data**:
   ```python
   # Use st.session_state for temporary data
   # Use database for persistent data
   if 'portfolio_data' not in st.session_state:
       st.session_state.portfolio_data = load_from_database()
   ```

2. **Save User Preferences**:
   ```python
   # Store preferences in database or file
   save_user_preferences(st.session_state.user_preferences)
   ```

**Error**: `LLM service not available` or `Ollama connection failed`

**Solutions**:
1. **Verify Ollama is installed and running**:
   ```bash
   # Check if Ollama is running
   ollama list
   
   # If not running, start it
   # Windows: Usually runs as a service
   # Linux/macOS: Check service status
   ```

2. **Install a model**:
   ```bash
   # Install recommended model
   ollama pull phi3
   ```

3. **Test connection**:
   ```bash
   python scripts/test_ollama.py
   ```

4. **Check environment variables**:
   ```bash
   # Verify OLLAMA_BASE_URL in .env (default: http://localhost:11434)
   ```

5. **Natural language queries won't work without Ollama**:
   - Use traditional filters instead
   - Or install and configure Ollama for AI features

### Database Connection Issues

**Error**: `Database connection error: connection to server at "localhost" (::1), port 5432 failed`

**Solutions**:
1. **Check PostgreSQL Status**:
   ```bash
   # Windows
   net start postgresql-x64-15
   
   # Linux/macOS
   sudo systemctl start postgresql
   sudo service postgresql start
   ```

2. **Verify Database Exists**:
   ```bash
   python scripts/test_database_connections.py
   ```

3. **Check Environment Variables**:
   ```bash
   # Verify .env file exists and has correct values
   cat .env
   ```

**Error**: `FATAL: database "trading_system" does not exist`

**Solution**: Run the database setup script:
```bash
python scripts/setup_databases.py
```

### API Errors

**Error**: `ModuleNotFoundError: No module named 'src'`

**Solution**: Ensure you're running from the project root directory:
```bash
cd /path/to/trading-system
python scripts/test_database_connections.py
```

**Error**: `pytest.mark.unit is not a registered marker`

**Solution**: Ensure `pytest.ini` exists with markers defined:
```ini
[tool:pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    database: Database tests
    slow: Slow tests
```

### Strategy Engine Issues

**Error**: `Strategy not found` or `Strategy execution failed`

**Solutions**:
1. **Verify Strategy Configuration**:
   ```bash
   # Check strategy configuration file
   cat config/strategies.yaml
   
   # Validate YAML syntax
   python -c "import yaml; yaml.safe_load(open('config/strategies.yaml'))"
   ```

2. **Check Strategy Status**:
   ```python
   # Query strategy status from database
   SELECT * FROM strategy_engine.strategies WHERE name = 'momentum_strategy';
   ```

3. **Test Strategy Logic**:
   ```python
   # Run strategy in test mode
   from src.services.strategy_engine.backtest import BacktestEngine
   engine = BacktestEngine()
   results = engine.run_backtest(
       strategy="momentum_strategy",
       symbols=["AAPL"],
       start_date="2024-01-01",
       end_date="2024-12-31",
       test_mode=True
   )
   ```

**Error**: `Backtest failed` or `Insufficient data for backtest`

**Solutions**:
1. **Check Historical Data Availability**:
   ```sql
   -- Verify sufficient data for backtest period
   SELECT symbol, COUNT(*) as data_points,
          MIN(timestamp) as earliest, MAX(timestamp) as latest
   FROM data_ingestion.market_data
   WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL')
     AND timestamp >= '2024-01-01'
     AND timestamp <= '2024-12-31'
   GROUP BY symbol;
   ```

2. **Validate Backtest Parameters**:
   ```python
   # Ensure start_date < end_date
   # Ensure sufficient initial capital
   # Check commission and slippage settings
   ```

3. **Review Backtest Logs**:
   ```python
   # Check backtest execution logs
   SELECT * FROM strategy_engine.backtest_runs
   WHERE strategy_id = 'momentum_strategy'
   ORDER BY created_at DESC
   LIMIT 10;
   ```

**Error**: `Signal generation timeout` or `Slow signal calculation`

**Solutions**:
1. **Optimize Indicator Calculations**:
   ```python
   # Use pre-calculated indicators from database
   SELECT * FROM analytics.technical_indicators_latest
   WHERE symbol = 'AAPL';
   ```

2. **Reduce Symbol Universe**:
   ```python
   # Process fewer symbols at once
   # Use batch processing for large universes
   ```

3. **Cache Indicator Results**:
   ```python
   # Cache frequently accessed indicators
   from functools import lru_cache
   
   @lru_cache(maxsize=1000)
   def get_indicator(symbol: str, indicator: str):
       # Cache indicator calculations
       pass
   ```

### Risk Management Issues

**Error**: `Risk limit exceeded` or `Trade rejected by risk management`

**Solutions**:
1. **Check Current Exposure**:
   ```sql
   -- Calculate current portfolio exposure
   SELECT 
       SUM(market_value) / (SELECT portfolio_value FROM account) as total_exposure,
       symbol,
       market_value
   FROM positions
   GROUP BY symbol, market_value;
   ```

2. **Review Risk Limits**:
   ```yaml
   # Check risk limits in config/strategies.yaml
   risk_limits:
     max_drawdown: 0.05
     max_daily_loss: 0.02
     max_positions: 10
     max_sector_exposure: 0.3
   ```

3. **Adjust Position Size**:
   ```python
   # Reduce position size if limits are too restrictive
   # Or adjust risk limits if appropriate
   ```

**Error**: `Circuit breaker triggered` or `Trading stopped`

**Solutions**:
1. **Check Circuit Breaker Status**:
   ```python
   # Query circuit breaker status
   SELECT * FROM risk_management.circuit_breakers
   WHERE triggered = true;
   ```

2. **Review Trigger Conditions**:
   ```sql
   -- Check current drawdown
   SELECT current_drawdown, max_drawdown_limit
   FROM risk_management.portfolio_metrics
   ORDER BY timestamp DESC
   LIMIT 1;
   
   -- Check daily loss
   SELECT daily_pnl, max_daily_loss_limit
   FROM risk_management.daily_metrics
   WHERE date = CURRENT_DATE;
   ```

3. **Reset Circuit Breaker** (if appropriate):
   ```python
   # Only reset if conditions have improved
   # Review why circuit breaker triggered first
   # Adjust risk limits if needed
   ```

**Error**: `Position sizing calculation failed`

**Solutions**:
1. **Verify Portfolio Value**:
   ```python
   # Check current portfolio value
   account = get_account()
   portfolio_value = float(account['portfolio_value'])
   ```

2. **Check Position Sizing Method**:
   ```python
   # Verify method is valid
   valid_methods = ['fixed_fractional', 'volatility', 'kelly', 'risk_parity']
   assert method in valid_methods
   ```

3. **Validate Parameters**:
   ```python
   # Ensure base_size, max_size, min_size are valid
   assert 0 < base_size <= 1
   assert 0 < max_size <= 1
   assert min_size < base_size
   ```

### Configuration Validation

**Error**: `Invalid configuration` or `Configuration file not found`

**Solutions**:
1. **Validate YAML Syntax**:
   ```bash
   # Check YAML syntax
   python -c "import yaml; yaml.safe_load(open('config/strategies.yaml'))"
   ```

2. **Verify Required Fields**:
   ```python
   # Validate configuration structure
   required_fields = ['name', 'enabled', 'parameters', 'risk_limits']
   for strategy in config['strategies']:
       assert all(field in strategy for field in required_fields)
   ```

3. **Check Environment Variables**:
   ```bash
   # Verify all required env vars are set
   python scripts/validate_config.py
   ```

**Error**: `API key invalid` or `Authentication failed`

**Solutions**:
1. **Verify API Keys**:
   ```bash
   # Check .env file
   cat .env | grep API_KEY
   
   # Test API connection
   python scripts/test_alpaca_connection.py
   ```

2. **Check API Key Permissions**:
   ```python
   # Verify API key has required permissions
   # Paper trading keys should work for paper trading
   # Live trading keys required for live trading
   ```

3. **Regenerate API Keys** (if needed):
   ```bash
   # Generate new keys from Alpaca dashboard
   # Update .env file with new keys
   # Restart services
   ```

### Performance Problems

**Issue**: Slow database queries

**Solutions**:
1. **Check Database Indexes**:
   ```sql
   -- List indexes on market_data table
   SELECT indexname, indexdef 
   FROM pg_indexes 
   WHERE tablename = 'market_data';
   
   -- Create missing indexes if needed
   CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp 
   ON market_data(symbol, timestamp DESC);
   ```

2. **Monitor Query Performance**:
   ```sql
   -- Enable query logging
   SET log_min_duration_statement = 1000;  -- Log queries > 1 second
   
   -- Check slow queries
   SELECT query, mean_exec_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_exec_time DESC 
   LIMIT 10;
   ```

3. **Optimize Connection Pool**:
   ```python
   # Adjust pool size in database.py
   pool_size=10,
   max_overflow=20,
   pool_recycle=3600
   ```

4. **Use Query Optimization**:
   ```sql
   -- Use EXPLAIN ANALYZE to optimize queries
   EXPLAIN ANALYZE 
   SELECT * FROM market_data 
   WHERE symbol = 'AAPL' 
   AND timestamp > NOW() - INTERVAL '30 days';
   ```

**Issue**: High memory usage

**Solutions**:
1. **Check Memory Usage**:
   ```python
   import psutil
   process = psutil.Process()
   print(f"Memory usage: {process.memory_info().rss / 1024 / 1024} MB")
   ```

2. **Monitor Service Resources**:
   ```bash
   # Check system resources
   top
   # Or
   htop
   ```

3. **Optimize Data Processing**:
   ```python
   # Use chunking for large datasets
   chunk_size = 1000
   for chunk in pd.read_sql(query, conn, chunksize=chunk_size):
       process_chunk(chunk)
   ```

4. **Implement Data Archiving**:
   ```sql
   -- Archive old data
   CREATE TABLE market_data_archive AS 
   SELECT * FROM market_data 
   WHERE timestamp < NOW() - INTERVAL '1 year';
   
   DELETE FROM market_data 
   WHERE timestamp < NOW() - INTERVAL '1 year';
   ```

**Issue**: Slow API responses

**Solutions**:
1. **Enable Caching**:
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   def get_market_data(symbol: str):
       # Cache frequently accessed data
       pass
   ```

2. **Use Async Endpoints**:
   ```python
   @router.get("/api/data/{symbol}")
   async def get_data(symbol: str):
       # Use async for I/O operations
       return await fetch_data_async(symbol)
   ```

3. **Optimize Database Queries**:
   ```python
   # Use select_related for joins
   # Use only() to limit fields
   # Add pagination for large result sets
   ```

## Database Issues

### Connection Problems

**Error**: `psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed`

**Troubleshooting Steps**:
1. Verify PostgreSQL is running
2. Check port 5432 is not blocked
3. Verify user credentials
4. Check firewall settings

### Schema Issues

**Error**: `Schema 'data_ingestion' for service 'data_ingestion' not found`

**Solution**: Run the database setup script:
```bash
python scripts/setup_databases.py
```

### Data Issues

**Error**: `Data validation failed`

**Solutions**:
1. Check data format and types
2. Verify required fields are present
3. Review data validation rules
4. Check for data corruption

## CI/CD Issues

### Workflow Failures

**Error**: `This request has been automatically failed because it uses a deprecated version of actions/upload-artifact: v3`

**Solution**: Update to latest action versions:
```yaml
# ❌ Old (deprecated)
- uses: actions/upload-artifact@v3

# ✅ New (current)
- uses: actions/upload-artifact@v5
```

**Error**: `Permission denied (publickey)`

**Solutions**:
1. Check repository permissions
2. Verify workflow permissions
3. Use built-in GITHUB_TOKEN
4. Check GitHub Pages source setting

### Build Failures

**Error**: `No coverage data found`

**Solution**: Ensure coverage is generated:
```bash
# Run tests with coverage
python scripts/run_tests.py all

# Check if coverage.xml exists
ls -la coverage.xml
```

**Error**: `Black formatting check failed`

**Solution**: Format code with Black:
```bash
black .
```

## Performance Issues

### Slow Startup

**Causes**:
- Database connection delays
- Large dependency loading
- Resource constraints

**Solutions**:
1. Check database connectivity
2. Monitor system resources
3. Review startup logs
4. Optimize imports

### Memory Issues

**Causes**:
- Memory leaks
- Large data processing
- Inefficient data structures

**Solutions**:
1. Monitor memory usage
2. Review data processing logic
3. Implement data streaming
4. Use memory profiling tools

### Database Performance

**Causes**:
- Missing indexes
- Inefficient queries
- Connection pool issues

**Solutions**:
1. Add database indexes
2. Optimize queries
3. Tune connection pool
4. Monitor query performance

## Getting Help

### Self-Help Resources

1. **Check Logs**: Review service logs for error details
2. **Run Diagnostics**: Use built-in diagnostic scripts
3. **Review Documentation**: Check relevant documentation sections
4. **Search Issues**: Look for similar issues in GitHub issues

### Diagnostic Commands

```bash
# Check system health
python scripts/run_tests.py check

# Test database connections
python scripts/test_database_connections.py

# Run full test suite
python scripts/run_tests.py all

# Check code quality
black --check .
isort --check-only .
flake8 .
mypy src/
```

### Support Channels

1. **GitHub Issues**: Create an issue for bugs or feature requests
2. **Discussions**: Use GitHub Discussions for questions
3. **Documentation**: Check the comprehensive documentation
4. **Email**: Contact nishant.nayar@hotmail.com for urgent issues

### Reporting Issues

When reporting issues, please include:
1. **Error Message**: Complete error message and stack trace
2. **Steps to Reproduce**: Detailed steps to reproduce the issue
3. **Environment**: Python version, OS, database version
4. **Logs**: Relevant log files and output
5. **Configuration**: Your `.env` file (remove sensitive data)

### Emergency Procedures

**System Down**:
1. Check service status
2. Review error logs
3. Restart services in order
4. Verify database connectivity

**Data Issues**:
1. Check database integrity
2. Review recent changes
3. Restore from backup if needed: `pg_restore -h localhost -U postgres -d trading_system --clean --if-exists backups/trading_backup_YYYYMMDD.dump` (see [Prefect Architecture](development/architecture-prefect.md#prefect-backup-and-recovery))
4. Contact support immediately

---

**Remember**: Always test changes in a development environment before applying to production!

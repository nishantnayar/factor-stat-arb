---
title: "Getting Started"
description: "Complete setup and configuration guide for the Trading System"
last_updated: "2026-04-03"
version: "1.0.0"
status: "✅ Complete"
author: "Trading System Team"
---

# Getting Started

This comprehensive guide will help you install, configure, and run the Trading System for the first time.

## Installation Flow

```mermaid
graph LR
    A[Clone<br/>Repository] --> B[Create<br/>Environment]
    B --> C[Install<br/>Dependencies]
    C --> D[Configure<br/>.env File]
    D --> E[Setup<br/>Databases]
    E --> F[Start<br/>Services]
    F --> G[Access<br/>Dashboard]
    
    style A fill:#e1f5ff
    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#fff4e1
    style E fill:#e8f5e9
    style F fill:#e8f5e9
    style G fill:#f3e5f5
```

## Prerequisites

### System Requirements

- **Operating System**: Windows 10+ (recommended for local deployment)
- **Python**: 3.11+ (required)
- **Database**: PostgreSQL 15+ (required)
- **Cache**: Redis 7+ (optional but recommended)
- **Memory**: 8GB+ RAM (recommended)
- **Storage**: 10GB+ free space

### Required Software

1. **Python 3.11+**
   - Download from [python.org](https://www.python.org/downloads/)
   - Or use Anaconda: [anaconda.com](https://www.anaconda.com/download)

2. **PostgreSQL 15+**
   - Download from [postgresql.org](https://www.postgresql.org/download/)
   - Or use package manager:
     ```bash
     # Windows (Chocolatey)
     choco install postgresql
     
     # macOS (Homebrew)
     brew install postgresql
     
     # Ubuntu/Debian
     sudo apt-get install postgresql postgresql-contrib
     ```

3. **Redis 7+** (Optional)
   - Download from [redis.io](https://redis.io/download)
   - Or use package manager:
     ```bash
     # Windows (Chocolatey)
     choco install redis
     
     # macOS (Homebrew)
     brew install redis
     
     # Ubuntu/Debian
     sudo apt-get install redis-server
     ```

4. **Ollama** (Optional, for AI-powered stock screener)
   - Download from [ollama.ai](https://ollama.ai)
   - Install a model after installation:
     ```bash
     ollama pull phi3
     ```

## Installation

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/nishantnayar/trading-system.git
cd trading-system
```

### Step 2: Create Python Environment

**Using Anaconda (Recommended)**:
```bash
# Create conda environment
conda create -n trading-system python=3.11
conda activate trading-system
```

**Using venv**:
```bash
# Create virtual environment
python -m venv trading-system-env

# Activate environment
# Windows
trading-system-env\Scripts\activate
# macOS/Linux
source trading-system-env/bin/activate
```

### Step 3: Install Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Install test dependencies (optional)
pip install -r requirements-test.txt
```

### Step 4: Verify Installation

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Verify core dependencies
python -c "import sqlalchemy, redis, fastapi; print('Core dependencies installed successfully')"
```

## Configuration

### Step 1: Environment Configuration

1. **Copy the environment template**:
   ```bash
   cp deployment/env.example .env
   ```

2. **Edit the `.env` file** with your settings:
   ```env
   # Database Configuration - Trading System
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password_here
   TRADING_DB_NAME=trading_system
   
   # Database Configuration - Prefect
   PREFECT_DB_NAME=prefect
   PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://postgres:password@localhost:5432/prefect
   
   # Redis Configuration
   REDIS_URL=redis://localhost:6379/0
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   
   # Alpaca API Configuration
   ALPACA_API_KEY=your_api_key_here
   ALPACA_SECRET_KEY=your_secret_key_here
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   
   # Ollama Configuration (Optional, for AI features)
   OLLAMA_BASE_URL=http://localhost:11434
   
   # Application Configuration
   APP_NAME=Trading System
   APP_VERSION=1.0.0
   DEBUG=false
   LOG_LEVEL=INFO
   ```

### Step 2: Database Setup

1. **Start PostgreSQL**:
   ```bash
   # Windows
   net start postgresql-x64-15
   
   # Linux/macOS
   sudo systemctl start postgresql
   # or
   sudo service postgresql start
   ```

2. **Run database setup script**:
   ```bash
   python scripts/setup_databases.py
   ```

   This script will:
   - Create the `trading_system` database
   - Create the `prefect` database
   - Create service-specific schemas
   - Configure Prefect database connection

### Step 3: Verify Database Setup

```bash
# Test database connections
python scripts/test_database_connections.py
```

Expected output:
```
Database Connection Verification
==================================================
Quick verification of database connections and basic functionality.
For comprehensive testing, use: python scripts/run_tests.py unit
==================================================

--- Trading Database ---
trading_system database connection successful

--- Prefect Database ---
Prefect database connection successful

--- Service Schemas ---
Schema 'data_ingestion' for service 'data_ingestion' is accessible
Schema 'strategy_engine' for service 'strategy_engine' is accessible
Schema 'execution' for service 'execution' is accessible
Schema 'risk_management' for service 'risk_management' is accessible
Schema 'analytics' for service 'analytics' is accessible
Schema 'notification' for service 'notification' is accessible
Schema 'logging' for service 'logging' is accessible
Schema 'shared' for service 'shared' is accessible

--- Connection Pools ---
Trading database pool: size=10, checked_out=0
Prefect database pool: size=10, checked_out=0

Verification Results: 4/4 checks passed
SUCCESS: All database connections verified!
Database is ready for use.
```

### Step 4: Alpaca API Setup (Optional)

1. **Sign up for Alpaca**:
   - Go to [Alpaca Markets](https://alpaca.markets/)
   - Create an account
   - Verify your identity

2. **Generate API Keys**:
   - Go to your dashboard
   - Navigate to API Keys section
   - Generate new API keys
   - Copy the API key and secret key

3. **Update `.env` file**:
   ```env
   ALPACA_API_KEY=your_actual_api_key
   ALPACA_SECRET_KEY=your_actual_secret_key
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ```

### Step 5: Ollama Setup (Optional, for AI Features)

1. **Install Ollama**:
   - Download from [ollama.ai](https://ollama.ai)
   - Install and start the service

2. **Install a Model**:
   ```bash
   # Recommended model for stock screener
   ollama pull phi3
   ```

3. **Test Connection**:
   ```bash
   python scripts/test_ollama.py
   ```

4. **Update `.env` file** (if using custom URL):
   ```env
   OLLAMA_BASE_URL=http://localhost:11434
   ```

## First Run

### Step 1: Start Redis (Optional)

```bash
# Start Redis server
redis-server

# Or start as service
# Windows
net start redis
# Linux/macOS
sudo systemctl start redis
```

### Step 2: Start Ollama (Optional, for AI Features)

```bash
# Start Ollama service
# Windows: Usually starts automatically after installation
# Linux/macOS: Usually runs as a service

# Verify it's running
ollama list
```

### Step 3: Start Prefect Server (Optional)

```bash
# Start Prefect server
prefect server start
```

The Prefect UI will be available at `http://localhost:4200`.

### Step 4: Run the Application

```bash
# Start the trading system API
python main.py
```

Or start individual components:

```bash
# Start web server
python -m src.web.main

# Start specific services
python -m src.services.data_ingestion.main
python -m src.services.strategy_engine.main
python -m src.services.execution.main
```

### Step 5: Access the Streamlit UI

1. **Open your browser** and go to `http://localhost:8501`
2. **Check the Streamlit interface** for system status
3. **Verify the application** is running correctly
4. **Test AI Features** (if Ollama is installed):
   - Navigate to the Stock Screener page
   - Try a natural language query like "Find tech stocks with RSI below 30"

## Verification

### Step 1: Run Tests

```bash
# Run quick verification
python scripts/test_database_connections.py

# Run unit tests
python scripts/run_tests.py unit

# Run all tests
python scripts/run_tests.py all
```

### Step 2: Check Application Health

```bash
# Check if the application is running
curl http://localhost:8001/health

# Or open in browser
# http://localhost:8501 for Streamlit UI
# http://localhost:8001/docs for API documentation
```

### Step 3: Verify Database

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d trading_system

# Check schemas
\dn

# Check tables
\dt

# Exit
\q
```

### Step 4: Check Logs

The system uses **database-first logging** with file fallback. Logs are primarily stored in PostgreSQL for queryable analysis.

**Query logs from database:**
```sql
-- Connect to PostgreSQL
psql -h localhost -U postgres -d trading_system

-- View recent system logs
SELECT timestamp, service, level, message 
FROM logging.system_logs 
ORDER BY timestamp DESC 
LIMIT 50;

-- View errors
SELECT timestamp, service, level, message 
FROM logging.system_logs 
WHERE level IN ('ERROR', 'CRITICAL')
ORDER BY timestamp DESC;

-- View performance logs
SELECT service, operation, execution_time_ms, timestamp
FROM logging.performance_logs
ORDER BY timestamp DESC
LIMIT 20;
```

**View file logs (fallback only):**
```bash
# View error logs (only written if database fails)
tail -f logs/errors.log

# Note: Most logs are in the database, not files
# Files are only used as a fallback mechanism
```

For more information, see the [Logging Architecture](development/logging.md) documentation.

## Next Steps

### 1. Explore the System

- **Streamlit UI**: Navigate through the multipage interface at `http://localhost:8501`
- **API Documentation**: Visit `http://localhost:8001/docs`
- **Market Data**: Explore interactive charts and analytics with Plotly
- **AI Stock Screener**: Try natural language queries in the Screener page (requires Ollama)

### 2. Configure Trading

- **Set up strategies**: Configure your trading strategies
- **Risk management**: Set appropriate risk limits
- **Paper trading**: Start with paper trading to test strategies

### 3. Development

- **Read documentation**: Check the comprehensive documentation
- **Run tests**: Ensure all tests pass
- **Code quality**: Use the built-in code quality tools

#### Code Quality Tools

The project uses automated code quality tools:

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Check linting with Flake8
flake8 .

# Type checking with mypy
mypy src/
```

**Configuration:**
- `.isort.cfg` - isort configuration (Black-compatible)
- `pytest.ini` - pytest and linting configuration
- All tools are pre-configured to work together

### 4. Production Deployment

- **Security**: Review security settings
- **Monitoring**: Set up monitoring and alerting
- **Backup**: Implement backup strategies

## Troubleshooting

If you encounter issues during setup:

1. **Check the logs**: Review error messages in log files
2. **Verify prerequisites**: Ensure all required software is installed
3. **Check configuration**: Verify your `.env` file settings
4. **Run diagnostics**: Use the built-in diagnostic scripts
5. **Review documentation**: Check the troubleshooting guide

For detailed troubleshooting information, see [Troubleshooting Guide](troubleshooting.md).

## Support

- **Documentation**: [Complete Documentation](https://nishantnayar.github.io/trading-system)
- **GitHub Issues**: [Report Issues](https://github.com/nishantnayar/trading-system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nishantnayar/trading-system/discussions)
- **Email**: nishant.nayar@hotmail.com

---

**Congratulations!** You've successfully set up the Trading System. You're now ready to start developing and trading!

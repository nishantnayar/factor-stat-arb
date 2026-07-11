# Prefect Deployment Configuration

> **📋 Implementation Status**: 🚧 In Progress  
> **Prefect Version**: 3.4.14

This document covers Prefect configuration including YAML files, environment variables, settings classes, and work pool configuration.

## Prefect Configuration (`prefect.yaml`)

### Sample: `deployment/prefect/prefect.yaml`

```yaml
# Prefect 3.4.14 Configuration
name: trading-system-prefect

prefect:
  version: 3.4.14
  
  # Work Pools Configuration
  work_pools:
    - name: data-ingestion-pool
      type: process
      base_job_template:
        job_configuration:
          command: >
            python -m prefect.engine
          env:
            PREFECT_API_URL: "${PREFECT_API_URL}"
            POSTGRES_HOST: "${POSTGRES_HOST}"
            POSTGRES_PORT: "${POSTGRES_PORT}"
            POSTGRES_USER: "${POSTGRES_USER}"
            POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
            TRADING_DB_NAME: "${TRADING_DB_NAME}"
          
    - name: analytics-pool
      type: process
      base_job_template:
        job_configuration:
          command: >
            python -m prefect.engine
          env:
            PREFECT_API_URL: "${PREFECT_API_URL}"
            # ... other env vars

  # Deployments
  deployments:
    - name: polygon-daily-ingestion
      flow_name: polygon-daily-ingestion
      entrypoint: src/shared/prefect/flows/data_ingestion/polygon_flows.py:polygon_daily_ingestion
      work_pool_name: data-ingestion-pool
      schedule:
        cron: "0 20 * * 1-5"  # 8 PM CT weekdays
        timezone: "America/Chicago"
      parameters:
        days_back: 1
        incremental: true
      tags:
        - data-ingestion
        - polygon
        - scheduled
      
    - name: Daily Market Data Update
      flow_name: Daily Market Data Update
      entrypoint: src/shared/prefect/flows/data_ingestion/yahoo_flows.py:yahoo_market_data_flow
      work_pool_name: data-ingestion-pool
      schedule:
        cron: "15 22 * * 1-5"  # 22:15 UTC Mon-Fri (after US market close)
        timezone: "UTC"
      parameters:
        days_back: 7
        interval: "1h"
      tags:
        - data-ingestion
        - yahoo
        - market-data
        - scheduled
      
    - name: Weekly Company Information Update
      flow_name: Weekly Company Information Update
      entrypoint: src/shared/prefect/flows/data_ingestion/yahoo_flows.py:yahoo_company_info_flow
      work_pool_name: data-ingestion-pool
      schedule:
        cron: "0 23 * * 5"  # 23:00 UTC Friday (after US close + daily Yahoo jobs)
        timezone: "UTC"
      tags:
        - data-ingestion
        - yahoo
        - company-info
        - scheduled
      
    - name: Weekly Key Statistics Update
      flow_name: Weekly Key Statistics Update
      entrypoint: src/shared/prefect/flows/data_ingestion/yahoo_flows.py:yahoo_key_statistics_flow
      work_pool_name: data-ingestion-pool
      schedule:
        cron: "0 2 * * 6"  # 02:00 UTC Saturday - example only; repo does not deploy standalone key stats
        timezone: "UTC"
      tags:
        - data-ingestion
        - yahoo
        - key-statistics
        - scheduled
      
    - name: Weekly Company Data Update
      flow_name: Weekly Company Data Update
      entrypoint: src/shared/prefect/flows/data_ingestion/yahoo_flows.py:yahoo_company_info_then_key_statistics_flow
      work_pool_name: data-ingestion-pool
      schedule:
        cron: "30 1 * * 6"  # 01:30 UTC Saturday (Fri evening US; staggered from company-info)
        timezone: "UTC"
      tags:
        - data-ingestion
        - yahoo
        - company-info
        - key-statistics
        - scheduled
      
    - name: indicators-daily-calculation
      flow_name: indicators-daily-calculation
      entrypoint: src/shared/prefect/flows/analytics/indicator_flows.py:calculate_daily_indicators
      work_pool_name: analytics-pool
      schedule:
        cron: "0 21 * * 1-5"  # 9 PM CT weekdays (after data ingestion)
        timezone: "America/Chicago"
      parameters:
        days_back: 1
      tags:
        - analytics
        - indicators
        - scheduled
```

## Work Pool Configuration (Phase 7 - Optional)

**Note:** YAML configs are optional. Can use Python `serve()` API instead. Create these only if using YAML-based deployments.

### Sample YAML: `deployment/prefect/work-pools/data-ingestion-pool.yaml`

```yaml
name: data-ingestion-pool
type: process
description: Work pool for data ingestion flows (Polygon, Yahoo)

base_job_template:
  job_configuration:
    command: >
      python -m prefect.engine
    env:
      # Prefect
      PREFECT_API_URL: "http://localhost:4200/api"
      
      # Database
      POSTGRES_HOST: "${POSTGRES_HOST}"
      POSTGRES_PORT: "${POSTGRES_PORT}"
      POSTGRES_USER: "${POSTGRES_USER}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
      TRADING_DB_NAME: "${TRADING_DB_NAME}"
      
      # API Keys (from environment)
      POLYGON_API_KEY: "${POLYGON_API_KEY}"
      
    # Resource limits
    cpu: 2
    memory: "4Gi"
    
  variables:
    batch_size:
      type: int
      default: 100
    requests_per_minute:
      type: int
      default: 2
```

## Configuration Changes Required

### Environment Variables (`deployment/env.example`)

Add these new sections to `deployment/env.example`:

```bash
# ============================================
# Prefect 3.4.14 Configuration
# ============================================

# Prefect Server Configuration
PREFECT_API_URL=http://localhost:4200/api
PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://postgres:password@localhost:5432/prefect
PREFECT_LOGGING_LEVEL=INFO
PREFECT_LOGGING_TO_API_ENABLED=true
PREFECT_SERVER_API_HOST=0.0.0.0
PREFECT_UI_URL=http://localhost:4200

# Prefect Work Pool Names
PREFECT_WORK_POOL_DATA_INGESTION=data-ingestion-pool
PREFECT_WORK_POOL_ANALYTICS=analytics-pool
PREFECT_WORK_POOL_MAINTENANCE=maintenance-pool

# Prefect Flow Configuration
PREFECT_FLOW_RETRY_ATTEMPTS=3
PREFECT_FLOW_RETRY_DELAY_SECONDS=60
PREFECT_FLOW_TIMEOUT_SECONDS=3600

# Prefect Database Name
PREFECT_DB_NAME=prefect
```

### Settings Class (`src/config/settings.py`)

Add these fields to the `Settings` class:

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # ============================================
    # Prefect Configuration
    # ============================================
    
    # Prefect Server Configuration
    prefect_api_url: str = Field(
        default="http://localhost:4200/api",
        alias="PREFECT_API_URL"
    )
    
    prefect_db_connection_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/prefect",
        alias="PREFECT_API_DATABASE_CONNECTION_URL"
    )
    
    prefect_logging_level: str = Field(
        default="INFO",
        alias="PREFECT_LOGGING_LEVEL"
    )
    
    prefect_logging_to_api_enabled: bool = Field(
        default=True,
        alias="PREFECT_LOGGING_TO_API_ENABLED"
    )
    
    prefect_server_api_host: str = Field(
        default="0.0.0.0",
        alias="PREFECT_SERVER_API_HOST"
    )
    
    prefect_ui_url: str = Field(
        default="http://localhost:4200",
        alias="PREFECT_UI_URL"
    )
    
    # Prefect Work Pool Names
    prefect_work_pool_data_ingestion: str = Field(
        default="data-ingestion-pool",
        alias="PREFECT_WORK_POOL_DATA_INGESTION"
    )
    
    prefect_work_pool_analytics: str = Field(
        default="analytics-pool",
        alias="PREFECT_WORK_POOL_ANALYTICS"
    )
    
    prefect_work_pool_maintenance: str = Field(
        default="maintenance-pool",
        alias="PREFECT_WORK_POOL_MAINTENANCE"
    )
    
    # Prefect Flow Defaults
    prefect_flow_retry_attempts: int = Field(
        default=3,
        alias="PREFECT_FLOW_RETRY_ATTEMPTS"
    )
    
    prefect_flow_retry_delay_seconds: int = Field(
        default=60,
        alias="PREFECT_FLOW_RETRY_DELAY_SECONDS"
    )
    
    prefect_flow_timeout_seconds: int = Field(
        default=3600,
        alias="PREFECT_FLOW_TIMEOUT_SECONDS"
    )
```

### Database Configuration (`src/config/database.py`)

✅ **No changes needed** - The database configuration already supports Prefect:
- `prefect_db_name` field exists
- `prefect_db_url` property exists
- Support for `database="prefect"` in `get_engine()`

### Configuration Summary

**Files to Modify:**
- `deployment/env.example` - Add 11 new environment variables
- `src/config/settings.py` - Add 11 new Prefect configuration fields

**Files to Create:**
- `src/shared/prefect/config.py` - Prefect configuration module (see [Code Patterns](prefect-deployment-code-patterns.md))

**Configuration Notes:**
- Database connection URL must use `postgresql+asyncpg://` format (Prefect 3.x requires asyncpg)
- API URL must include `/api` suffix: `http://localhost:4200/api`
- All new fields have defaults for backward compatibility

## Related Documentation

- [Prefect Deployment](prefect-deployment.md) — Overview and index
- [Operations](prefect-deployment-operations.md) — Runbook, monitoring, troubleshooting
- [Code Patterns](prefect-deployment-code-patterns.md) — Task/flow patterns, deployment definitions
- [Advanced Topics](prefect-deployment-advanced.md) — Design decisions

---

**Last Updated**: 4/3/2026  
**Status**: 🚧 In Progress


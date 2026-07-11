---
title: "Database Architecture"
description: "Database architecture overview and index to database documentation"
last_updated: "2026-04-03"
version: "1.0.0"
status: "✅ Complete"
author: "Trading System Team"
---

# Database Architecture

## Overview

This document provides an index to the database architecture documentation. For detailed information on specific aspects, please refer to the dedicated documents below:

## Database Sub-documents

- [**Database Overview**](database-overview.md): High-level architecture, distribution strategy, setup options, and implementation approach.
- [**Database Schema**](database-schema.md): Comprehensive schema definitions for all database tables, including constraints, indexes, and relationships.
- [**Database Optimization**](database-optimization.md): Performance tuning, indexing strategies, partitioning, ORM patterns, monitoring, and maintenance.

---

**Note**: This document serves as an index to the modular database documentation.

## Database Architecture Diagram

```mermaid
graph TB
    subgraph "PostgreSQL Instance"
        TradingDB[(trading_system<br/>Database)]
        PrefectDB[(prefect<br/>Database)]
    end
    
    subgraph "Trading System Schemas"
        DataIngestion[data_ingestion<br/>Schema]
        Strategy[strategy_engine<br/>Schema]
        Execution[execution<br/>Schema]
        Risk[risk_management<br/>Schema]
        Analytics[analytics<br/>Schema]
        Logging[logging<br/>Schema]
    end
    
    subgraph "Prefect Schema"
        PrefectSchema[public<br/>Schema]
    end
    
    TradingDB --> DataIngestion
    TradingDB --> Strategy
    TradingDB --> Execution
    TradingDB --> Risk
    TradingDB --> Analytics
    TradingDB --> Logging
    
    PrefectDB --> PrefectSchema
    
    style TradingDB fill:#00A86B
    style PrefectDB fill:#009688
    style DataIngestion fill:#e8f5e9
    style Analytics fill:#e8f5e9
    style Logging fill:#e8f5e9
```


# Data Sources Implementation Plan

> **📋 Implementation Status**: 🚧 In Progress  
> **Focus**: Yahoo Finance Integration

This document outlines the implementation plan for Yahoo Finance integration and future enhancements to the multi-source data architecture.

---

## Implementation Plan

### Phase 1: Database Setup ✅ COMPLETED

- [x] Add `data_source` column to `market_data` table
- [x] Update unique constraint to `(symbol, timestamp, data_source)`
- [x] Allow `yahoo_adjusted` in `valid_data_source` CHECK (migration `scripts/20_market_data_allow_yahoo_adjusted.sql`)
- [x] Update Python models and loaders (client/loader support `auto_adjust`; dual series)
- [x] Update tests

### Phase 2: Yahoo Client & Models

**Files to Create:**
1. `src/services/yahoo/__init__.py`
2. `src/services/yahoo/client.py` (~300 lines)
3. `src/services/yahoo/exceptions.py` (~50 lines)
4. `src/services/yahoo/models.py` (~200 lines)

**Key Classes:**
- `YahooClient`: API wrapper using `yfinance`
- Exception classes: `YahooAPIError`, `YahooDataError`, etc.
- Pydantic models for all data types

**Estimated Effort:** 4-6 hours

### Phase 3: Database Schema

**Files to Create:**
1. `scripts/08_create_yahoo_tables.sql` (~150 lines)
2. `scripts/08_rollback_yahoo_tables.sql` (~50 lines)
3. `src/shared/database/models/company_info.py`
4. `src/shared/database/models/fundamentals.py`
5. `src/shared/database/models/corporate_actions.py`

**Tables:**
- `company_info`
- `key_statistics`
- `dividends`
- `stock_splits`
- `financial_statements`

**Estimated Effort:** 3-4 hours

### Phase 4: Yahoo Loader

**Files to Create:**
1. `src/services/yahoo/loader.py` (~500 lines)

**Key Methods:**
- `load_market_data()`: OHLCV data
- `load_company_info()`: Company profile
- `load_key_statistics()`: Financial metrics
- `load_financials()`: Financial statements
- `load_dividends()`: Dividend history (with date range support)
- `load_splits()`: Stock split history (with date range support)
- `load_analyst_recommendations()`: Analyst recommendation counts over time
- `load_esg_scores()`: ESG (Environmental, Social, Governance) scores
- `load_all_data()`: Comprehensive load
- `load_all_symbols_data()`: Batch processing

**Estimated Effort:** 6-8 hours

### Phase 5: CLI Script

**Files to Create:**
1. `scripts/load_yahoo_data.py` (~400 lines)

**Features:**
- Single symbol or all symbols
- Select data types to load
- Date range specification
- Progress tracking
- Error handling and logging

**Estimated Effort:** 2-3 hours

### Phase 6: Testing

**Files to Create:**
1. `tests/unit/test_yahoo_client.py` (~300 lines)
2. `tests/unit/test_yahoo_loader.py` (~400 lines)
3. `tests/integration/test_yahoo_integration.py` (~200 lines)

**Test Coverage:**
- Client methods (mocked API calls)
- Loader methods (database integration)
- Error handling
- Data validation
- Edge cases

**Estimated Effort:** 4-5 hours

### Phase 7: Documentation

**Files to Update:**
1. Data sources documentation (already done!)
2. `docs/api/data-ingestion.md`
3. `README.md`
4. Add usage examples

**Estimated Effort:** 1-2 hours

### Total Estimated Effort

**25-35 hours** (~1 week of focused development)

---

## Next Steps

1. ✅ Review this documentation
2. ⏳ Run Phase 1 migration (add `data_source` column)
3. ⏳ Implement Phase 2 (Yahoo Client)
4. ⏳ Implement Phase 3 (Database Schema)
5. ⏳ Implement Phase 4 (Yahoo Loader)
6. ⏳ Implement Phase 5 (CLI Script)
7. ⏳ Implement Phase 6 (Testing)
8. ⏳ Update remaining documentation

---

## Questions & Considerations

**Questions to Address:**
1. Should we implement automatic source fallback?
2. Do we need real-time reconciliation between sources?
3. Should fundamentals be loaded on a schedule or on-demand?
4. Do we want to track data quality metrics over time?
5. Should we implement a "preferred source" configuration per symbol?

**Technical Decisions:**
1. Use `yfinance` library (most popular, well-maintained)
2. Store financial statements as JSONB (flexible schema)
3. Separate loader classes (better separation of concerns)
4. UTC timezone for all timestamps (consistency)
5. Batch processing for multiple symbols (efficiency)

---

## Related Documentation

- [Data Sources Overview](data-sources-overview.md): Multi-source architecture overview
- [Yahoo Finance Integration](data-sources-yahoo.md): Comprehensive Yahoo Finance integration guide
- [Data Source Comparison](data-sources-comparison.md): Feature comparison and best practices

---

**Last Updated**: 4/3/2026  
**Status**: 🚧 In Progress (Phase 1 complete; Yahoo dual series and migration 20 in place)


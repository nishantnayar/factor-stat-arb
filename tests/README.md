# Tests

## Critical: Use a Separate Test Database

**Never run pytest against your main development or production database.**

Some fixtures (e.g. `setup_test_tables`) **drop tables** including `data_ingestion.market_data` during teardown. Running pytest with `TRADING_DB_NAME=trading_system` (or your main DB) has in the past caused **catastrophic data loss**.

### Safeguards in place

1. **Table drops only when**:
   - The database name ends with `_test` (e.g. `trading_system_test`), and
   - `data_ingestion.market_data` has no more than 1000 rows (configurable in `conftest.py`: `MAX_MARKET_DATA_ROWS_BEFORE_REFUSE_DROP`).

2. **Startup warning**: If `TRADING_DB_NAME` is `trading_system`, a critical warning is printed to stderr when pytest loads.

3. **Production-like DB names** (e.g. `trading_system`) never have their tables dropped; the teardown is skipped and a warning is emitted.

### How to run tests safely

1. **Create a dedicated test database** (one-time):
   ```sql
   CREATE DATABASE trading_system_test;
   ```

2. **Run pytest with the test database**:
   ```bash
   TRADING_DB_NAME=trading_system_test pytest tests/
   ```
   Or set in a `.env.test` and load it:
   ```bash
   export TRADING_DB_NAME=trading_system_test
   pytest tests/
   ```

3. **CI**: Ensure your CI environment sets `TRADING_DB_NAME=trading_system_test` (or similar) so tests never touch the main DB.

### If you see "Skipping DROP" or "REFUSING to DROP"

- **Skipping DROP**: You are connected to a DB that is not considered a test DB (e.g. `trading_system`). Tables were not dropped. Use `trading_system_test` for pytest.
- **REFUSING to DROP**: The table `data_ingestion.market_data` has more than 1000 rows. The fixture will not drop it to avoid data loss. Use a test database that does not contain large production-like data.

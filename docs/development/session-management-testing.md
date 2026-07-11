# Session Management Testing Checklist

## What We've Built

### ✅ Core Infrastructure
- **`src/shared/database/base.py`** - Session management with transactions
- **`src/shared/database/mixins.py`** - Reusable model components
- **`src/shared/database/__init__.py`** - Module exports
- **`tests/unit/test_database_base.py`** - Unit tests (mock-based)
- **`examples/database_usage.py`** - Usage examples
- **`scripts/test_session_management.py`** - Integration tests (real DB)

### ✅ Features Implemented
- ✔️ Transaction context manager (`db_transaction`)
- ✔️ Read-only session context manager (`db_readonly_session`)
- ✔️ Manual session management (`get_session`)
- ✔️ Comprehensive error handling (4 error types)
- ✔️ Automatic logging
- ✔️ Connection pooling integration
- ✔️ 10 reusable mixins

## Testing Status

### ✅ Unit Tests (No Database Required)
All unit tests passing:
```bash
pytest tests/unit/test_database_base.py
```

- ✔️ Transaction commit
- ✔️ IntegrityError handling
- ✔️ OperationalError handling
- ✔️ DataError handling
- ✔️ ProgrammingError handling
- ✔️ General exception handling
- ✔️ Read-only session
- ✔️ Manual session creation

### 🔄 Integration Tests (Requires Database)

**Prerequisites:**
1. PostgreSQL running on localhost:5432
2. `.env` file with correct database password
3. Databases created (trading_system, Prefect)
4. Schemas created (data_ingestion, etc.)

**To run:**
```bash
python scripts/test_session_management.py
```

**Tests included:**
1. Database connection
2. Schema access
3. Create test table
4. Transaction insert
5. Read-only query
6. Model serialization
7. Transaction update
8. Transaction rollback
9. Duplicate constraint handling
10. Complex query

## Setup Required

### 1. Update `.env` File

Edit the `.env` file in the project root with your PostgreSQL password:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_ACTUAL_PASSWORD_HERE  # ← Change this!
TRADING_DB_NAME=trading_system
PREFECT_DB_NAME=Prefect
```

### 2. Ensure Database Setup is Complete

Run the database setup if you haven't already:

```bash
# Option 1: SQL Scripts
psql -U postgres -h localhost -p 5432 -f scripts/01_create_databases.sql
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/02_create_core_tables.sql
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/03_create_indexes.sql

# Option 2: Python Script
python scripts/setup_databases.py
```

### 3. Install Required Dependencies

```bash
pip install loguru sqlalchemy psycopg2 python-dotenv
```

## Running the Tests

### Run Unit Tests (Always Works)
```bash
pytest tests/unit/test_database_base.py -v
```

### Run Integration Tests (Requires DB Setup)
```bash
python scripts/test_session_management.py
```

### Run Example Scripts
```bash
python examples/database_usage.py
```

## Expected Output (Integration Tests)

When properly configured, you should see:

```
============================================================
SESSION MANAGEMENT INTEGRATION TESTS
============================================================

============================================================
TEST 1: Database Connection
============================================================
[PASS] Database connection successful

============================================================
TEST 2: Schema Access
============================================================
[PASS] Schema 'data_ingestion' is accessible

... (10 tests total)

============================================================
TEST SUMMARY
============================================================
Total Tests: 10
[PASS] Passed: 10
[FAIL] Failed: 0
Success Rate: 100.0%
============================================================

[SUCCESS] All tests passed! Session management is working correctly.
```

## Troubleshooting

### Issue: "password authentication failed"
**Solution:** Update the `POSTGRES_PASSWORD` in your `.env` file

### Issue: "database does not exist"
**Solution:** Run the database setup scripts:
```bash
psql -U postgres -h localhost -p 5432 -f scripts/01_create_databases.sql
```

### Issue: "schema not found"
**Solution:** Run the schema creation script:
```bash
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/02_create_core_tables.sql
```

### Issue: ModuleNotFoundError
**Solution:** Install missing dependencies:
```bash
pip install loguru sqlalchemy psycopg2 python-dotenv
```

## Next Steps

Once integration tests pass:

1. ✅ Session management is fully working
2. ✅ Ready to create SQLAlchemy models
3. ✅ Ready to implement service repositories
4. ✅ Ready to build APIs

## Contact

If you encounter issues, check:
- PostgreSQL service is running
- `.env` file has correct credentials
- Databases and schemas are created
- All dependencies are installed


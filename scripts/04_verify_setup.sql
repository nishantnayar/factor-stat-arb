-- Database Setup Verification Script
-- Run this script to verify that all databases, schemas, and tables were created successfully

-- Check if databases exist
SELECT 
    datname as database_name,
    pg_get_userbyid(datdba) as owner,
    encoding,
    datcollate as collation
FROM pg_database 
WHERE datname IN ('trading_system', 'Prefect')
ORDER BY datname;

-- Connect to trading_system database
\c trading_system;

-- Check if all schemas exist
SELECT 
    schema_name,
    schema_owner
FROM information_schema.schemata 
WHERE schema_name IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
) 
ORDER BY schema_name;

-- Check tables in each schema
SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)
ORDER BY table_schema, table_name;

-- Check indexes
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)
ORDER BY schemaname, tablename, indexname;

-- Check custom types
SELECT 
    typname as type_name,
    typtype as type_type,
    typcategory as category
FROM pg_type 
WHERE typname IN ('order_side', 'order_type', 'order_status', 'time_in_force', 'trade_type')
ORDER BY typname;

-- Check constraints
SELECT 
    tc.table_schema,
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc 
    ON tc.constraint_name = cc.constraint_name
WHERE tc.table_schema IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)
ORDER BY tc.table_schema, tc.table_name, tc.constraint_name;

-- Check foreign key relationships
SELECT 
    tc.table_schema,
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema IN (
        'data_ingestion', 'strategy_engine', 'execution', 
        'risk_management', 'analytics', 'notification', 
        'logging', 'shared'
    )
ORDER BY tc.table_schema, tc.table_name, tc.constraint_name;

-- Summary counts
SELECT 
    'Databases' as object_type,
    COUNT(*) as count
FROM pg_database 
WHERE datname IN ('trading_system', 'Prefect')

UNION ALL

SELECT 
    'Schemas' as object_type,
    COUNT(*) as count
FROM information_schema.schemata 
WHERE schema_name IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)

UNION ALL

SELECT 
    'Tables' as object_type,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_schema IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)

UNION ALL

SELECT 
    'Indexes' as object_type,
    COUNT(*) as count
FROM pg_indexes 
WHERE schemaname IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
)

UNION ALL

SELECT 
    'Custom Types' as object_type,
    COUNT(*) as count
FROM pg_type 
WHERE typname IN ('order_side', 'order_type', 'order_status', 'time_in_force', 'trade_type')

UNION ALL

SELECT 
    'Constraints' as object_type,
    COUNT(*) as count
FROM information_schema.table_constraints 
WHERE table_schema IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
);

-- Test basic functionality
SELECT 'Database setup verification completed successfully!' as status;

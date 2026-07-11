# Prefect Deployment Advanced Topics

> **📋 Implementation Status**: 🚧 In Progress  
> **Prefect Version**: 3.4.14

This document covers design decisions for Prefect deployment. For runbook, migration, and best practices, see [Operations](prefect-deployment-operations.md). For the `days_back` parameter, see [Operations — Understanding days_back](prefect-deployment-operations.md#understanding-days_back).

## Key Design Decisions

### Why `serve()` API?

Prefect 3.x introduces the `serve()` API, which is simpler than the older deployment-building approach. Flows are deployed by calling `.serve()` on the flow object.

**Benefits:**

- Simpler API than previous deployment builders
- Python-based configuration (easier to version control)
- Dynamic deployment logic
- Better integration with code

### Why Separate Work Pools?

- **Resource isolation**: Different pools can have different resource limits
- **Parallelism control**: Limit concurrent executions per pool
- **Environment separation**: Different pools can use different environments

**Example:**

- `data-ingestion-pool`: Data ingestion (Polygon, Yahoo)
- `analytics-pool`: Analytics (indicator calculations)
- `maintenance-pool`: Maintenance (cleanup, archiving)

### Why YAML + Python?

- **YAML**: Static configuration (work pools, schedules)
- **Python**: Dynamic deployment logic and code reuse

**Best practice:** Use YAML for initial setup; use Python `serve()` API for deployments (more flexible).

### Task Granularity

**Coarse-grained** (one task per symbol):

- Example: `load_polygon_symbol_data_task(symbol)` processes entire symbol
- Better for parallelization; less granular observability

**Fine-grained** (fetch / validate / store separate):

- Example: `fetch_data_task()`, `validate_data_task()`, `store_data_task()`
- Better for observability; more overhead, less parallelization

**Recommendation:** Start coarse-grained; refine as needed.

## Related Documentation

- [Prefect Deployment](prefect-deployment.md) — Overview and index
- [Operations](prefect-deployment-operations.md) — Runbook, days_back, migration, best practices
- [Configuration](prefect-deployment-configuration.md) — YAML, env, settings
- [Code Patterns](prefect-deployment-code-patterns.md) — Task/flow patterns, deployment definitions

---

**Last Updated**: 4/3/2026  
**Status**: 🚧 In Progress


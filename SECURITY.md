# Security Policy

## Scope

Factor Stat Arb is a **paper-trading, educational** project. It targets Alpaca's paper
endpoint (`PAPER_TRADING=true`) and never places real orders. It handles API keys and a
database password, so basic secret hygiene still applies.

## Secrets and configuration

- **Never commit secrets.** `.env` is gitignored; keep all keys and passwords there. Use
  `.env.example` (placeholders only) as the template.
- **Use a separate Alpaca paper key** from any other project's, so paper P&L stays
  attributable to this repo.
- **Rotate keys** if they are ever exposed (pasted into a chat/log, shared, committed).
  Alpaca paper keys can be regenerated from the Alpaca dashboard.
- The Prefect database URL is derived from `POSTGRES_PASSWORD` - do not hardcode the
  password in a second place.
- On a shared machine, restrict `.env` permissions (`icacls` on Windows, `chmod 600` on
  Linux/Mac).

## Databases

- The application DB (`factor_stat_arb`) and Prefect DB (`factor_stat_arb_prefect`) are
  separate from any `trading_system` databases - do not point this repo at those.
- Do not run tests against a database whose name does not end in `_test`.

## Reporting a vulnerability

This is a personal project without a formal disclosure process. If you find a security
issue, please open a private report by emailing the maintainer (see the GitHub profile
for [nishantnayar](https://github.com/nishantnayar)) rather than filing a public issue.

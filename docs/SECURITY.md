# Security Guide

> **Last Updated**: 4/3/2026  
> **Status**: Security Best Practices

This guide covers security best practices, API key management, and security considerations for the Trading System.

## Overview

Security is paramount in trading systems, especially when handling API keys, financial data, and system access. This guide provides comprehensive security practices for protecting your trading system.

## API Key Management

### Environment Variables

**Never commit API keys to version control.** Always use environment variables stored in `.env` files that are excluded from Git.

#### Best Practices

1. **Use `.env` Files**:
   ```bash
   # Add to .gitignore
   .env
   .env.local
   .env.*.local
   ```

2. **Template Files**:
   - Keep `deployment/env.example` as a template
   - Never include actual keys in example files
   - Use placeholder values

3. **Environment Variable Security**:
   ```bash
   # Good: Use strong, unique keys
   ALPACA_API_KEY=your_api_key_here
   ALPACA_SECRET_KEY=your_secret_key_here
   
   # Set proper file permissions (Linux/Mac)
   chmod 600 .env
   ```

### API Key Rotation

- **Regular Rotation**: Rotate API keys periodically (every 90 days recommended)
- **Immediate Revocation**: Revoke keys immediately if compromised
- **Separate Keys**: Use different keys for development, staging, and production
- **Paper Trading First**: Always use paper trading API keys for testing

### Alpaca API Keys

1. **Account Security**:
   - Enable two-factor authentication (2FA) on your Alpaca account
   - Use paper trading keys for development
   - Limit API key permissions when possible

2. **Key Storage**:
   ```bash
   # Store in .env file (not in code)
   ALPACA_API_KEY=PKxxxxxxxxxxxxx
   ALpACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxx
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ```

3. **Key Validation**:
   - Never share API keys in logs or error messages
   - Mask keys in debug output
   - Validate keys before use

### Polygon.io API Keys

1. **Key Management**:
   ```bash
   POLYGON_API_KEY=your_polygon_key
   ```

2. **Rate Limiting**:
   - Respect rate limits to avoid key revocation
   - Monitor API usage
   - Implement backoff strategies

## Database Security

### Connection Security

1. **Strong Passwords**:
   - Use complex passwords for PostgreSQL users
   - Change default passwords immediately
   - Use password managers

2. **Connection Strings**:
   ```bash
   # Use environment variables, never hardcode
   POSTGRES_URL=postgresql://user:password@localhost:5432/trading_system
   ```

3. **SSL/TLS**:
   - Enable SSL for production databases
   - Use connection pooling securely
   - Restrict database access by IP when possible

### Database Access Control

1. **User Permissions**:
   - Use least-privilege principle
   - Create separate users for different services
   - Revoke unnecessary permissions

2. **Schema Isolation**:
   - Use schema-based isolation (already implemented)
   - Limit cross-schema access
   - Use row-level security (RLS) when appropriate

## Application Security

### Code Security

1. **Dependencies**:
   - Regularly update dependencies
   - Check for known vulnerabilities: `pip audit`
   - Use pinned versions in `requirements.txt`

2. **Input Validation**:
   - Validate all user inputs
   - Use Pydantic models for data validation
   - Sanitize inputs before database queries

3. **SQL Injection Prevention**:
   - Always use parameterized queries (SQLAlchemy ORM does this)
   - Never concatenate user input into SQL queries
   - Use ORM methods instead of raw SQL when possible

### Authentication & Authorization

1. **API Authentication** (Future):
   - Implement API key authentication for production
   - Use JWT tokens for user sessions
   - Implement rate limiting

2. **Streamlit Security**:
   - Run Streamlit on localhost for development
   - Use authentication for production deployments
   - Enable HTTPS for production

### Secrets Management

1. **Configuration Files**:
   - Never commit secrets to Git
   - Use environment variables
   - Consider using secrets management services for production

2. **Logging**:
   - Never log API keys or secrets
   - Sanitize sensitive data in logs
   - Use log levels appropriately

## Network Security

### Local Deployment

1. **Firewall**:
   - Restrict database ports (5432) to localhost
   - Use Redis authentication
   - Limit service exposure

2. **Port Security**:
   - Run services on localhost when possible
   - Use reverse proxy for production
   - Enable HTTPS for external access

### API Security

1. **HTTPS**:
   - Always use HTTPS for production
   - Validate SSL certificates
   - Use strong ciphers

2. **CORS**:
   - Configure CORS properly for FastAPI
   - Restrict allowed origins
   - Use appropriate headers

## Data Security

### Data Encryption

1. **At Rest**:
   - Enable PostgreSQL encryption at rest
   - Encrypt backups
   - Secure file storage

2. **In Transit**:
   - Use HTTPS/TLS for all connections
   - Use encrypted database connections
   - Secure WebSocket connections

### Data Privacy

1. **Personal Information**:
   - Minimize data collection
   - Follow GDPR/privacy regulations
   - Secure user data

2. **Trading Data**:
   - Protect trading strategies
   - Secure historical data
   - Control data access

## Best Practices Summary

### Do's ✅

- ✅ Store all secrets in environment variables
- ✅ Use `.env` files excluded from Git
- ✅ Rotate API keys regularly
- ✅ Use paper trading keys for development
- ✅ Enable 2FA on all accounts
- ✅ Keep dependencies updated
- ✅ Use strong passwords
- ✅ Validate all inputs
- ✅ Log errors, not secrets
- ✅ Use HTTPS for production

### Don'ts ❌

- ❌ Never commit API keys to Git
- ❌ Don't hardcode secrets in code
- ❌ Don't share API keys
- ❌ Don't log sensitive information
- ❌ Don't use production keys for development
- ❌ Don't disable security features
- ❌ Don't ignore security warnings
- ❌ Don't use default passwords
- ❌ Don't expose services unnecessarily
- ❌ Don't skip input validation

## Incident Response

### If API Keys Are Compromised

1. **Immediate Actions**:
   - Revoke compromised keys immediately
   - Generate new keys
   - Review recent API activity
   - Check for unauthorized trades

2. **Prevention**:
   - Review access logs
   - Update security practices
   - Notify affected services

### Security Monitoring

1. **Log Monitoring**:
   - Monitor for authentication failures
   - Watch for unusual API activity
   - Check database access logs

2. **Alerts**:
   - Set up alerts for failed logins
   - Monitor API rate limit violations
   - Track unusual trading activity

## Additional Resources

- [Alpaca Security Best Practices](https://alpaca.markets/docs/api-documentation/how-to/authentication/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

**Important**: Security is an ongoing process. Regularly review and update your security practices. When in doubt, err on the side of caution.


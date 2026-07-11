# CI/CD Pipeline Documentation

## Overview

The Trading System uses a comprehensive CI/CD pipeline built on GitHub Actions to ensure code quality, security, and reliable deployments. The pipeline is designed to support both development and production workflows.

## Pipeline Architecture

### **Workflow Structure**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Code Push     │───▶│   CI Pipeline   │───▶│   CD Pipeline   │
│   PR/Main       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │ Security Scans  │
                       │ Documentation   │
                       └─────────────────┘
```

## Workflows

### 1. **Continuous Integration (`ci.yml`)**

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

**Jobs:**

#### **Code Quality Checks**
- **Black**: Code formatting validation
- **isort**: Import sorting validation
- **Flake8**: Linting and style checks
- **mypy**: Type checking
- **bandit**: Security vulnerability scanning
- **safety**: Dependency vulnerability scanning

#### **Database Tests**
- **PostgreSQL 15**: Test database setup
- **Connection Tests**: Database connectivity verification
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing

#### **Full Test Suite**
- **Comprehensive Testing**: All test categories
- **Coverage Reporting**: Code coverage analysis
- **Parallel Execution**: Optimized test performance

#### **Documentation Build**
- **MkDocs**: Documentation generation
- **Link Validation**: Broken link detection
- **Artifact Upload**: Documentation artifacts

### 2. **Continuous Deployment (`cd.yml`)**

**Triggers:**
- Push to `main` branch (staging)
- Manual workflow dispatch (staging/production)

**Environments:**

#### **Staging Deployment**
- **Automatic**: On push to `main`
- **Smoke Tests**: Basic functionality verification
- **Environment**: Staging infrastructure

#### **Production Deployment**
- **Manual**: Requires explicit approval
- **Prerequisites**: Staging deployment success
- **Environment**: Production infrastructure

#### **Database Migration**
- **Manual**: Separate workflow for database changes
- **Verification**: Migration validation
- **Rollback**: Automatic rollback on failure

### 3. **Security Scanning (`security.yml`)**

**Triggers:**
- Weekly schedule (Monday 2 AM)
- Push to `main` branch
- Pull requests to `main`

**Scans:**

#### **Dependency Security**
- **Safety**: Python package vulnerabilities
- **pip-audit**: Additional dependency scanning
- **Reports**: JSON format for analysis

#### **Code Security**
- **Bandit**: Python security linter
- **Semgrep**: Advanced code analysis
- **Reports**: Detailed security findings

#### **Filesystem Security**
- **Trivy**: Filesystem vulnerability scanning
- **SARIF**: GitHub Security tab integration
- **Multi-format**: JSON and SARIF reports

#### **Secret Scanning**
- **TruffleHog**: Secret detection
- **Full History**: Complete repository scan
- **Verified Only**: High-confidence findings

### 4. **Documentation (`docs.yml`)**

**Triggers:**
- Push to `main` or `develop`
- Pull requests to `main`

**Features:**

#### **Documentation Build**
- **MkDocs**: Static site generation
- **Material Theme**: Modern documentation UI
- **GitHub Pages**: Automatic deployment

#### **Documentation Linting**
- **Link Validation**: Broken link detection
- **Structure Check**: Documentation organization

#### **Documentation Testing**
- **Code Examples**: Syntax validation
- **Python Compilation**: Code block testing
- **Integration**: Documentation accuracy

## Environment Configuration

### **Required Secrets**

```yaml
# GitHub Secrets
GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # Automatic
DATABASE_URL: ${{ secrets.DATABASE_URL }}  # Production database
REDIS_URL: ${{ secrets.REDIS_URL }}        # Production Redis
ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
```

### **Environment Variables**

```yaml
# Test Environment
POSTGRES_HOST: localhost
POSTGRES_PORT: 5432
POSTGRES_USER: postgres
POSTGRES_PASSWORD: postgres
TRADING_DB_NAME: trading_system_test
PREFECT_DB_NAME: Prefect
REDIS_HOST: localhost
REDIS_PORT: 6379
```

## Quality Gates

### **Code Quality Requirements**

1. **Formatting**: All code must pass Black formatting
2. **Imports**: All imports must be sorted with isort
3. **Linting**: No Flake8 errors allowed
4. **Types**: mypy type checking must pass
5. **Security**: No high-severity security issues

### **Test Requirements**

1. **Unit Tests**: 100% pass rate required
2. **Integration Tests**: All database tests must pass
3. **Coverage**: Minimum 80% code coverage
4. **Performance**: Tests must complete within time limits

### **Documentation Requirements**

1. **Build**: Documentation must build successfully
2. **Links**: No broken internal links
3. **Examples**: All code examples must be valid
4. **Structure**: Proper documentation organization

## Deployment Strategy

### **Staging Deployment**

```yaml
# Automatic on main branch push
staging:
  trigger: push to main
  environment: staging
  tests: smoke tests
  approval: automatic
```

### **Production Deployment**

```yaml
# Manual with approval
production:
  trigger: workflow_dispatch
  environment: production
  prerequisites: staging success
  approval: manual
  tests: full production tests
```

### **Database Migrations**

```yaml
# Separate workflow for safety
migration:
  trigger: workflow_dispatch
  environment: production
  approval: manual
  rollback: automatic on failure
```

## Monitoring and Notifications

### **Success Notifications**

- **Slack**: Team notifications
- **Email**: Stakeholder updates
- **GitHub**: Status checks and comments

### **Failure Notifications**

- **Immediate**: Critical failures
- **Escalation**: Production issues
- **Rollback**: Automatic on deployment failure

### **Metrics Tracking**

- **Build Time**: Pipeline performance
- **Test Coverage**: Quality metrics
- **Deployment Frequency**: Release velocity
- **Failure Rate**: Reliability metrics

## Best Practices

### **Development Workflow**

1. **Feature Branches**: Create from `develop`
2. **Pull Requests**: Required for all changes
3. **Code Review**: At least one approval required
4. **Testing**: All tests must pass before merge

### **Release Process**

1. **Version Bumping**: Semantic versioning
2. **Changelog**: Update release notes
3. **Tagging**: Git tags for releases
4. **Documentation**: Update docs with changes

### **Security Practices**

1. **Dependency Updates**: Regular security updates
2. **Secret Management**: Use GitHub Secrets
3. **Access Control**: Principle of least privilege
4. **Audit Logs**: Track all changes

## Troubleshooting

### **Common Issues**

#### **Build Failures**
```bash
# Check logs
gh run list
gh run view <run-id>

# Local testing
python scripts/run_tests.py all
```

#### **Database Issues**
```bash
# Test database connection
python scripts/test_database_connections.py

# Check database status
python scripts/setup_databases.py
```

#### **Documentation Issues**
```bash
# Build locally
mkdocs build

# Check links
mkdocs build --strict
```

### **Debug Commands**

```bash
# Run specific test category
python scripts/run_tests.py unit
python scripts/run_tests.py integration
python scripts/run_tests.py database

# Check code quality
black --check .
isort --check-only .
flake8 .
mypy src/
bandit -r src/
safety check
```

## GitHub Pages Setup

### **Prerequisites**

1. **Repository Access**: You must have admin/write access to the repository
2. **GitHub Pages Enabled**: Pages must be enabled in repository settings
3. **Correct Permissions**: Workflow must have proper permissions

### **Step-by-Step Setup**

#### **1. Enable GitHub Pages**

1. Go to your repository on GitHub
2. Click **Settings** tab
3. Scroll down to **Pages** section (left sidebar)
4. Under **Source**, select **GitHub Actions**
5. Click **Save**

#### **2. Configure Repository Permissions**

1. In repository **Settings**
2. Go to **Actions** → **General**
3. Scroll to **Workflow permissions**
4. Select **Read and write permissions**
5. Check **Allow GitHub Actions to create and approve pull requests**
6. Click **Save**

#### **3. Verify Workflow Configuration**

The workflow should have these permissions:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

#### **4. Deploy Documentation**

1. Push changes to `main` branch
2. Go to **Actions** tab
3. Find the **Documentation** workflow
4. Click on the latest run
5. Monitor the deployment progress

### **Troubleshooting GitHub Pages**

#### **Error: Permission Denied**

**Error**: `Permission to nishantnayar/Trading-System.git denied to github-actions[bot]`

**Solutions**:

1. **Check Repository Permissions**:
   - Go to Settings → Actions → General
   - Ensure "Read and write permissions" is selected
   - Save changes

2. **Verify Workflow Permissions**:
   ```yaml
   permissions:
     contents: read
     pages: write
     id-token: write
   ```

3. **Check GitHub Pages Source**:
   - Go to Settings → Pages
   - Ensure source is set to "GitHub Actions"

#### **Error: 403 Forbidden**

**Error**: `The requested URL returned error: 403`

**Solutions**:

1. **Regenerate Token** (if using personal access token):
   - Go to Settings → Developer settings → Personal access tokens
   - Generate new token with `repo` and `workflow` permissions
   - Update repository secrets

2. **Use Built-in GITHUB_TOKEN** (recommended):
   - Remove custom token from workflow
   - Use `${{ secrets.GITHUB_TOKEN }}` (automatic)

#### **Error: Pages Not Found**

**Error**: 404 when accessing GitHub Pages URL

**Solutions**:

1. **Check Deployment Status**:
   - Go to Actions tab
   - Look for "Deploy to GitHub Pages" job
   - Ensure it completed successfully

2. **Verify Pages Settings**:
   - Go to Settings → Pages
   - Check if Pages is enabled
   - Verify source is "GitHub Actions"

3. **Check Custom Domain** (if used):
   - Ensure CNAME file is correct
   - Verify DNS settings

## Future Enhancements

### **Phase 2: Advanced Testing**
- **Load Testing**: Performance under load
- **Stress Testing**: System limits
- **Chaos Engineering**: Failure testing
- **Contract Testing**: API contracts

### **Phase 3: Advanced Deployment**
- **Blue-Green Deployment**: Zero-downtime deployments
- **Canary Releases**: Gradual rollouts
- **Feature Flags**: Toggle functionality
- **A/B Testing**: Experimentation

### **Phase 4: Monitoring Integration**
- **APM**: Application performance monitoring
- **Logging**: Centralized log management
- **Metrics**: Business and technical metrics
- **Alerting**: Proactive issue detection

### **Phase 5: Compliance**
- **Audit Trails**: Complete change tracking
- **Compliance Reports**: Regulatory requirements
- **Data Governance**: Data lifecycle management
- **Security Standards**: Industry compliance

---

## Quick Reference

### **Local Development**
```bash
# Run all tests
python scripts/run_tests.py all

# Run specific tests
python scripts/run_tests.py unit
python scripts/run_tests.py integration

# Check code quality
black .
isort .
flake8 .
mypy src/
```

### **CI/CD Commands**
```bash
# Trigger deployment
gh workflow run cd.yml -f environment=staging

# Check workflow status
gh run list
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

### **Emergency Procedures**
```bash
# Rollback deployment
gh workflow run rollback.yml

# Skip CI (emergency only)
git commit -m "Emergency fix [skip ci]"
```

---

**This CI/CD pipeline ensures reliable, secure, and high-quality deployments for the Trading System while maintaining development velocity and operational excellence.**

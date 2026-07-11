# Contributing to Trading System

Thank you for your interest in contributing to the Trading System! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Follow the project's coding standards
- Test your changes thoroughly
- Document your contributions

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Git
- Basic understanding of algorithmic trading concepts

### Development Setup

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/your-username/trading-system.git
   cd trading-system
   ```

2. **Set Up Development Environment**
   ```bash
   # Create conda environment
   conda create -n trading-system-dev python=3.11
   conda activate trading-system-dev
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-test.txt
   
   # Install pre-commit hooks
   pre-commit install
   ```

3. **Configure Environment**
   ```bash
   # Copy example environment file
   cp deployment/env.example .env
   # Edit .env with your configuration
   ```

4. **Set Up Databases**
   ```bash
   # Initialize databases
   python scripts/setup_databases.py
   ```

5. **Run Tests**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test suite
   pytest tests/unit/
   pytest tests/integration/
   ```

## Development Workflow

### Branch Naming

Use descriptive branch names:
- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions

### Commit Messages

Follow conventional commit format:
```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(api): add order placement endpoint
fix(database): resolve connection pool issue
docs(readme): update installation instructions
```

### Pull Request Process

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation

3. **Run Quality Checks**
   ```bash
   # Format code
   black .
   isort .
   
   # Lint code
   flake8 .
   
   # Type check
   mypy src/
   
   # Run tests
   pytest
   ```

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat(scope): your feature description"
   ```

5. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   # Create PR on GitHub
   ```

6. **PR Requirements**
   - ✅ All tests pass
   - ✅ Code follows style guidelines
   - ✅ Documentation updated
   - ✅ No merge conflicts
   - ✅ Descriptive PR description

## Coding Standards

### Python Style Guide

- Follow PEP 8
- Use Black for formatting (88 character line length)
- Use isort for import sorting
- Type hints required for all functions
- Docstrings for all public functions/classes

### Code Quality Tools

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type checking
mypy src/

# Run tests with coverage
pytest --cov=src --cov-report=html
```

### Type Hints

Always use type hints:
```python
from typing import List, Dict, Optional

def process_data(
    symbols: List[str],
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> Dict[str, pd.DataFrame]:
    """Process market data for given symbols."""
    pass
```

### Docstrings

Use Google-style docstrings:
```python
def calculate_returns(
    prices: pd.Series,
    method: str = "simple"
) -> pd.Series:
    """Calculate returns from price series.
    
    Args:
        prices: Series of prices
        method: Return calculation method ('simple' or 'log')
    
    Returns:
        Series of returns
    
    Raises:
        ValueError: If method is not 'simple' or 'log'
    """
    pass
```

## Testing Guidelines

### Test Structure

- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Use pytest fixtures for common setup
- Mock external dependencies (APIs, databases)

### Writing Tests

```python
import pytest
from src.services.data_ingestion import DataLoader

def test_load_market_data_success():
    """Test successful market data loading."""
    loader = DataLoader()
    result = loader.load_data("AAPL", "2024-01-01", "2024-01-31")
    assert result is not None
    assert len(result) > 0

def test_load_market_data_invalid_symbol():
    """Test handling of invalid symbol."""
    loader = DataLoader()
    with pytest.raises(ValueError):
        loader.load_data("INVALID", "2024-01-01", "2024-01-31")
```

### Test Coverage

- Aim for >80% code coverage
- Test edge cases and error conditions
- Test both success and failure paths

## Documentation Standards

### Code Documentation

- Document all public APIs
- Include examples in docstrings
- Explain complex algorithms
- Document assumptions and limitations

### Documentation Updates

When adding features:
- Update relevant documentation files
- Add examples if applicable
- Update API reference if needed
- Update CHANGELOG.md

## Areas for Contribution

### High Priority

- ✅ **Strategy Engine**: Core strategy framework implementation
- ✅ **Risk Management**: Risk calculation and monitoring
- ✅ **Backtesting**: Historical strategy testing framework
- ✅ **Performance Optimization**: Query optimization, caching improvements

### Medium Priority

- 📊 **Additional Data Sources**: Integration with new data providers
- 📈 **Advanced Analytics**: Additional technical indicators
- 🔔 **Notifications**: Email/SMS alert system
- 📱 **Mobile Support**: Responsive UI improvements

### Documentation

- 📝 **Tutorials**: Step-by-step guides for common tasks
- 📚 **API Examples**: More code examples
- 🎨 **Architecture Diagrams**: Visual system documentation
- 🐛 **Troubleshooting**: Additional troubleshooting guides

## Reporting Issues

### Bug Reports

Include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Error messages and stack traces
- Relevant log files

### Feature Requests

Include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation (if applicable)
- Examples of similar features (if any)

## Code Review Process

1. **Automated Checks**: CI/CD runs tests and quality checks
2. **Review**: Maintainers review code for:
   - Correctness
   - Code quality
   - Test coverage
   - Documentation
3. **Feedback**: Address review comments
4. **Approval**: Once approved, changes are merged

## Questions?

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and discussions
- **Email**: nishant.nayar@hotmail.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to the Trading System! 🚀


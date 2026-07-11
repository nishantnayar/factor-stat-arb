# Trading System Timezone Architecture

> **Status**: ✅ Fully Documented (v1.0.0)

## Timezone Strategy

### Overview
The trading system handles three primary timezones to ensure accurate data processing, trading operations, and user experience:

- **UTC**: Universal storage and vendor data (database storage)
- **EST/EDT**: Trading operations (market timezone)
- **CST/CDT**: User interface (your local timezone)

### Core Principles

1. **Storage**: All timestamps stored in UTC in database
2. **Processing**: Internal operations use UTC
3. **Display**: Convert to user's timezone (Central) for UI
4. **Trading**: Convert to market timezone (Eastern) for trading operations
5. **Vendor Data**: Handle incoming UTC data from external sources

### Timezone Configuration

#### Environment Variables
```env
# Timezone Configuration
DEFAULT_TIMEZONE=UTC
USER_TIMEZONE=America/Chicago
TRADING_TIMEZONE=America/New_York
VENDOR_TIMEZONE=UTC
```

#### Timezone Constants
```python
# src/shared/utils/timezone.py
from zoneinfo import ZoneInfo

# Timezone definitions
UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")

# Timezone aliases for clarity
USER_TIMEZONE = CENTRAL
TRADING_TIMEZONE = EASTERN
STORAGE_TIMEZONE = UTC
```

### Reusable Utility Functions

#### 1. Timezone Configuration
```python
def get_central_timezone() -> ZoneInfo:
    """Get Central timezone (user's local timezone)"""
    return ZoneInfo("America/Chicago")

def get_eastern_timezone() -> ZoneInfo:
    """Get Eastern timezone (trading timezone)"""
    return ZoneInfo("America/New_York")

def get_utc_timezone() -> ZoneInfo:
    """Get UTC timezone (storage timezone)"""
    return ZoneInfo("UTC")

# Current time in different timezones
def now_utc() -> datetime:
    """Get current time in UTC"""
    return datetime.now(UTC)

def now_central() -> datetime:
    """Get current time in Central timezone"""
    return datetime.now(CENTRAL)

def now_eastern() -> datetime:
    """Get current time in Eastern timezone"""
    return datetime.now(EASTERN)
```

#### 2. Conversion Functions
```python
def to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert datetime to UTC"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(UTC)

def to_central(dt: datetime) -> datetime:
    """Convert datetime to Central timezone"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CENTRAL)

def to_eastern(dt: datetime) -> datetime:
    """Convert datetime to Eastern timezone"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(EASTERN)

def convert_timezone(dt: datetime, from_tz: ZoneInfo, to_tz: ZoneInfo) -> datetime:
    """Convert datetime between timezones"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=from_tz)
    return dt.astimezone(to_tz)

# Smart conversion (detects source timezone)
def smart_convert_to_utc(dt: datetime) -> datetime:
    """Smart conversion to UTC, handling naive datetimes"""
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def smart_convert_to_central(dt: datetime) -> datetime:
    """Smart conversion to Central timezone"""
    utc_dt = smart_convert_to_utc(dt)
    return utc_dt.astimezone(CENTRAL)

def smart_convert_to_eastern(dt: datetime) -> datetime:
    """Smart conversion to Eastern timezone"""
    utc_dt = smart_convert_to_utc(dt)
    return utc_dt.astimezone(EASTERN)
```

#### 3. Trading-Specific Utilities
```python
def is_market_hours(dt: datetime) -> bool:
    """Check if datetime is during market hours (9:30 AM - 4:00 PM EST)"""
    eastern_dt = to_eastern(dt)
    market_open = eastern_dt.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = eastern_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # Check if it's a weekday
    if eastern_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    return market_open <= eastern_dt <= market_close

def get_next_market_open(dt: datetime) -> datetime:
    """Get next market open time in UTC"""
    eastern_dt = to_eastern(dt)
    next_open = eastern_dt.replace(hour=9, minute=30, second=0, microsecond=0)
    
    # If it's past today's market open, get tomorrow's
    if eastern_dt.time() > next_open.time():
        next_open += timedelta(days=1)
    
    # Skip weekends
    while next_open.weekday() >= 5:
        next_open += timedelta(days=1)
    
    return to_utc(next_open, EASTERN)

def get_last_market_close(dt: datetime) -> datetime:
    """Get last market close time in UTC"""
    eastern_dt = to_eastern(dt)
    last_close = eastern_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # If it's before today's market close, get yesterday's
    if eastern_dt.time() < last_close.time():
        last_close -= timedelta(days=1)
    
    # Skip weekends
    while last_close.weekday() >= 5:
        last_close -= timedelta(days=1)
    
    return to_utc(last_close, EASTERN)

def get_trading_day(dt: datetime) -> date:
    """Get trading day for a given datetime"""
    eastern_dt = to_eastern(dt)
    
    # If before market open, use previous trading day
    if eastern_dt.time() < time(9, 30):
        eastern_dt -= timedelta(days=1)
    
    # Skip weekends
    while eastern_dt.weekday() >= 5:
        eastern_dt -= timedelta(days=1)
    
    return eastern_dt.date()

# Timezone-aware business logic
def get_trading_timestamp(dt: datetime) -> datetime:
    """Convert to EST for trading operations"""
    return to_eastern(dt)

def get_display_timestamp(dt: datetime) -> datetime:
    """Convert to Central for UI display"""
    return to_central(dt)
```

#### 4. Data Processing Utilities
```python
def normalize_vendor_timestamp(dt: datetime, vendor_tz: str = "UTC") -> datetime:
    """Normalize vendor timestamp to UTC"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    
    if dt.tzinfo is None:
        # Assume vendor timezone
        vendor_zone = ZoneInfo(vendor_tz)
        dt = dt.replace(tzinfo=vendor_zone)
    
    return dt.astimezone(UTC)

def process_market_data_timestamps(data: List[Dict]) -> List[Dict]:
    """Process market data timestamps to UTC"""
    processed_data = []
    for record in data:
        if 'timestamp' in record:
            record['timestamp'] = normalize_vendor_timestamp(record['timestamp'])
        processed_data.append(record)
    return processed_data

# Database operations
def ensure_utc_timestamp(dt: datetime) -> datetime:
    """Ensure timestamp is in UTC for database storage"""
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def format_for_database(dt: datetime) -> datetime:
    """Format timestamp for database storage (UTC)"""
    return ensure_utc_timestamp(dt)
```

#### 5. Logging and Display
```python
def log_with_timezone(message: str, level: str, tz: ZoneInfo = None):
    """Log message with timezone context"""
    if tz is None:
        tz = CENTRAL  # Default to user timezone
    
    timestamp = datetime.now(tz)
    formatted_message = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}"
    
    # Use appropriate log level
    if level.upper() == "ERROR":
        logger.error(formatted_message)
    elif level.upper() == "WARNING":
        logger.warning(formatted_message)
    elif level.upper() == "INFO":
        logger.info(formatted_message)
    else:
        logger.debug(formatted_message)

def format_timestamp_for_logging(dt: datetime) -> str:
    """Format timestamp for logging with timezone info"""
    central_dt = to_central(dt)
    return central_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

# UI formatting
def format_for_display(dt: datetime, format_str: str = None) -> str:
    """Format timestamp for UI display"""
    if format_str is None:
        format_str = '%Y-%m-%d %H:%M:%S %Z'
    
    central_dt = to_central(dt)
    return central_dt.strftime(format_str)

def format_trading_time(dt: datetime) -> str:
    """Format timestamp for trading context (Eastern)"""
    eastern_dt = to_eastern(dt)
    return eastern_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
```

#### 6. Validation and Error Handling
```python
class TimezoneError(Exception):
    """Custom exception for timezone-related errors"""
    pass

def validate_timezone_aware(dt: datetime) -> bool:
    """Validate that datetime is timezone-aware"""
    return dt.tzinfo is not None

def ensure_timezone_aware(dt: datetime, default_tz: ZoneInfo = None) -> datetime:
    """Ensure datetime is timezone-aware"""
    if dt.tzinfo is None:
        if default_tz is None:
            default_tz = UTC
        return dt.replace(tzinfo=default_tz)
    return dt

def handle_timezone_conversion_error(dt: datetime, target_tz: ZoneInfo) -> datetime:
    """Handle timezone conversion errors gracefully"""
    try:
        return dt.astimezone(target_tz)
    except Exception as e:
        logger.error(f"Timezone conversion error: {e}")
        # Fallback to UTC
        return ensure_timezone_aware(dt, UTC).astimezone(target_tz)
```

### Database Integration

#### Updated Database Mixins
```python
# src/shared/database/mixins.py
from src.shared.utils.timezone import ensure_utc_timestamp

class TimestampMixin:
    """Adds timezone-aware created_at timestamp to models"""
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when record was created (UTC)",
    )
    
    def set_created_at(self, dt: datetime = None):
        """Set created_at timestamp in UTC"""
        if dt is None:
            dt = datetime.now()
        self.created_at = ensure_utc_timestamp(dt)

class UpdateTimestampMixin(TimestampMixin):
    """Adds timezone-aware created_at and updated_at timestamps to models"""
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when record was last updated (UTC)",
    )
    
    def set_updated_at(self, dt: datetime = None):
        """Set updated_at timestamp in UTC"""
        if dt is None:
            dt = datetime.now()
        self.updated_at = ensure_utc_timestamp(dt)
```

### API Response Formatting

#### Timezone-Aware API Responses
```python
# src/web/api/timezone_helpers.py
from src.shared.utils.timezone import to_central, format_for_display

def format_api_timestamp(dt: datetime) -> str:
    """Format timestamp for API responses (Central timezone)"""
    return format_for_display(dt)

def format_trading_timestamp(dt: datetime) -> str:
    """Format timestamp for trading context (Eastern timezone)"""
    return format_trading_time(dt)

# Pydantic model with timezone conversion
class TimestampResponse(BaseModel):
    timestamp: str
    timezone: str = "America/Chicago"  # Central timezone
    
    @classmethod
    def from_datetime(cls, dt: datetime):
        return cls(
            timestamp=format_for_display(dt),
            timezone="America/Chicago"
        )
```

### Usage Examples

#### Data Ingestion (Vendor sends UTC)
```python
# Vendor data comes in UTC
vendor_data = {"timestamp": "2024-01-15T14:30:00Z"}
utc_time = normalize_vendor_timestamp(parse_iso(vendor_data["timestamp"]))

# Store in database (already UTC)
db_record = {"timestamp": utc_time}
```

#### Trading Operations (Convert to EST)
```python
# Convert to Eastern for trading
trading_time = get_trading_timestamp(utc_time)

# Check if market is open
if is_market_hours(trading_time):
    # Execute trade
    execute_trade(symbol, quantity, price, trading_time)
```

#### UI Display (Convert to Central)
```python
# Convert to Central for display
display_time = get_display_timestamp(utc_time)

# Format for UI
formatted_time = format_for_display(display_time)
```

#### Logging (With timezone context)
```python
# Log with timezone context
log_with_timezone(f"Trade executed at {trading_time}", "INFO")

# Format timestamp for logging
log_timestamp = format_timestamp_for_logging(utc_time)
```

### Benefits

1. **Consistency**: All timestamps handled uniformly across the system
2. **Clarity**: Explicit timezone conversions with clear function names
3. **Maintainability**: Centralized timezone logic in utility functions
4. **Reliability**: Robust error handling for timezone conversion issues
5. **Performance**: Optimized conversion functions with minimal overhead
6. **Testability**: Isolated, testable utility functions
7. **User Experience**: Timestamps displayed in user's local timezone
8. **Trading Accuracy**: Trading operations use correct market timezone

### Testing Strategy

#### Timezone Test Cases
```python
# tests/unit/test_timezone.py
def test_timezone_conversions():
    """Test timezone conversion functions"""
    utc_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
    
    # Test conversion to Central
    central_time = to_central(utc_time)
    assert central_time.hour == 8  # 14:30 UTC = 08:30 CST
    
    # Test conversion to Eastern
    eastern_time = to_eastern(utc_time)
    assert eastern_time.hour == 9  # 14:30 UTC = 09:30 EST

def test_market_hours():
    """Test market hours detection"""
    # Market open time (9:30 AM EST)
    market_open = datetime(2024, 1, 15, 9, 30, 0, tzinfo=EASTERN)
    assert is_market_hours(market_open)
    
    # Market close time (4:00 PM EST)
    market_close = datetime(2024, 1, 15, 16, 0, 0, tzinfo=EASTERN)
    assert is_market_hours(market_close)
    
    # After hours
    after_hours = datetime(2024, 1, 15, 18, 0, 0, tzinfo=EASTERN)
    assert not is_market_hours(after_hours)

def test_vendor_data_normalization():
    """Test vendor data timestamp normalization"""
    # UTC timestamp from vendor
    vendor_timestamp = "2024-01-15T14:30:00Z"
    normalized = normalize_vendor_timestamp(vendor_timestamp)
    
    assert normalized.tzinfo == UTC
    assert normalized.hour == 14
    assert normalized.minute == 30
```

This comprehensive timezone strategy ensures that your trading system handles timezones correctly across all components while maintaining data integrity and providing a consistent user experience.

---

**See Also**:
- [Architecture Overview](architecture-overview.md) - System overview
- [Database Architecture](architecture-database.md) - Timezone-aware database design
- [Services Architecture](architecture-services.md) - Service timezone handling

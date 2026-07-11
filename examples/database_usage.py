"""
Database Usage Examples
Demonstrates how to use the database base functionality
"""

from datetime import datetime, timezone
from decimal import Decimal

from src.shared.database.base import (
    db_readonly_session,
    db_transaction,
    execute_in_transaction,
    execute_readonly,
)


def example_create_order():
    """Example: Create a trading order"""
    print("=== Creating Order Example ===")

    # Simulate order data
    order_data = {
        "order_id": "ORD-12345",
        "account_id": "ACC-001",
        "symbol": "AAPL",
        "quantity": 100,
        "price": Decimal("150.00"),
        "side": "buy",
        "status": "pending",
    }

    def create_order_in_db(session, order_data):
        """Function to create order in database"""
        # This would use actual Order model when implemented
        print(f"Creating order: {order_data['order_id']}")
        print(f"Symbol: {order_data['symbol']}")
        print(f"Quantity: {order_data['quantity']}")
        print(f"Price: ${order_data['price']}")
        return order_data["order_id"]

    # Execute in transaction
    order_id = execute_in_transaction(create_order_in_db, order_data)
    print(f"Order created with ID: {order_id}")
    print()


def example_query_market_data():
    """Example: Query market data"""
    print("=== Querying Market Data Example ===")

    def get_market_data(session, symbol, days=7):
        """Function to get market data from database"""
        # This would use actual MarketData model when implemented
        print(f"Querying market data for {symbol} (last {days} days)")

        # Simulate query results
        mock_data = [
            {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "close": Decimal("150.25"),
            },
            {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "close": Decimal("149.80"),
            },
            {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "close": Decimal("151.10"),
            },
        ]

        print(f"Found {len(mock_data)} records")
        for record in mock_data:
            print(f"  {record['timestamp']}: ${record['close']}")

        return mock_data

    # Execute read-only query
    data = execute_readonly(get_market_data, "AAPL", 7)
    print(f"Retrieved {len(data)} market data records")
    print()


def example_complex_transaction():
    """Example: Complex transaction with multiple operations"""
    print("=== Complex Transaction Example ===")

    def execute_trade_transaction(session, order_id, execution_price):
        """Complex transaction: update order, create trade, update position"""
        print(f"Executing trade for order {order_id} at ${execution_price}")

        # Step 1: Update order status
        print("1. Updating order status to 'filled'")

        # Step 2: Create trade record
        trade_id = f"TRD-{order_id.split('-')[1]}"
        print(f"2. Creating trade record: {trade_id}")

        # Step 3: Update position
        print("3. Updating position")

        # Step 4: Log the transaction
        print("4. Logging transaction")

        return trade_id

    # Execute complex transaction
    trade_id = execute_in_transaction(
        execute_trade_transaction, "ORD-12345", Decimal("150.25")
    )
    print(f"Trade executed with ID: {trade_id}")
    print()


def example_analytics_query():
    """Example: Analytics query with aggregation"""
    print("=== Analytics Query Example ===")

    def get_portfolio_summary(session, account_id):
        """Get portfolio summary with aggregations"""
        print(f"Generating portfolio summary for account {account_id}")

        # Simulate aggregated data
        summary = [
            {
                "symbol": "AAPL",
                "quantity": 100,
                "avg_price": Decimal("150.00"),
                "current_value": Decimal("15025.00"),
            },
            {
                "symbol": "GOOGL",
                "quantity": 50,
                "avg_price": Decimal("2800.00"),
                "current_value": Decimal("140000.00"),
            },
            {
                "symbol": "MSFT",
                "quantity": 75,
                "avg_price": Decimal("300.00"),
                "current_value": Decimal("22500.00"),
            },
        ]

        total_value = sum(record["current_value"] for record in summary)
        print(f"Portfolio Summary:")
        for record in summary:
            print(
                f"  {record['symbol']}: {record['quantity']} shares @ ${record['avg_price']} = ${record['current_value']}"
            )
        print(f"  Total Portfolio Value: ${total_value}")

        return summary

    # Execute analytics query
    summary = execute_readonly(get_portfolio_summary, "ACC-001")
    print(f"Portfolio analysis completed for {len(summary)} positions")
    print()


def example_error_handling():
    """Example: Error handling in transactions"""
    print("=== Error Handling Example ===")

    def risky_operation(session, should_fail=True):
        """Operation that might fail"""
        print("Performing risky operation...")

        if should_fail:
            print("Simulating database error...")
            raise ValueError("Simulated database constraint violation")

        print("Operation completed successfully")
        return "Success"

    # Test successful operation
    print("Testing successful operation:")
    try:
        result = execute_in_transaction(risky_operation, should_fail=False)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print()

    # Test failed operation
    print("Testing failed operation:")
    try:
        result = execute_in_transaction(risky_operation, should_fail=True)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error caught: {e}")
        print("Transaction was automatically rolled back")

    print()


if __name__ == "__main__":
    print("Database Usage Examples")
    print("=" * 50)
    print()

    # Run examples
    example_create_order()
    example_query_market_data()
    example_complex_transaction()
    example_analytics_query()
    example_error_handling()

    print("All examples completed!")
    print()
    print("Note: These examples use mock data.")
    print("In production, you would use actual SQLAlchemy models.")
    print("The session management and error handling work the same way.")

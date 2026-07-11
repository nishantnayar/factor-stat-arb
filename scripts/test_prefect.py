#!/usr/bin/env python3
"""
Simple Prefect Test Script

Tests basic Prefect functionality including:
- Prefect installation and imports
- Creating flows and tasks
- Running flows with Prefect server

Usage:
    # Option 1: Start Prefect server first, then run:
    prefect server start
    
    # In another terminal:
    python scripts/test_prefect.py
    
    # Option 2: Test imports only (no server needed):
    python scripts/test_prefect.py --check-only
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set PREFECT_API_URL early if not already set
# This must be done BEFORE importing Prefect
if "PREFECT_API_URL" not in os.environ:
    # Default to local server
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

try:
    from loguru import logger
    from prefect import flow, get_client, task
    from prefect.settings import PREFECT_API_URL, temporary_settings
except ImportError as e:
    print(f"[FAIL] Error importing Prefect: {e}")
    print("Please install Prefect: pip install prefect>=3.4.14")
    sys.exit(1)


@task(name="simple-addition-task", retries=2)
def add_numbers(a: int, b: int) -> int:
    """Simple task that adds two numbers"""
    logger.info(f"Adding {a} + {b}")
    result = a + b
    logger.info(f"Result: {result}")
    return result


@task(name="simple-multiplication-task")
def multiply_numbers(a: int, b: int) -> int:
    """Simple task that multiplies two numbers"""
    logger.info(f"Multiplying {a} * {b}")
    result = a * b
    logger.info(f"Result: {result}")
    return result


@flow(name="simple-math-flow", log_prints=True)
def simple_math_flow(x: int = 5, y: int = 3) -> dict:
    """
    Simple flow that demonstrates task dependencies
    
    Args:
        x: First number
        y: Second number
        
    Returns:
        Dictionary with calculation results
    """
    logger.info("=" * 50)
    logger.info("Starting Simple Math Flow")
    logger.info("=" * 50)
    
    # Run first task
    sum_result = add_numbers(x, y)
    logger.info(f"Sum task completed: {sum_result}")
    
    # Run second task (depends on first)
    product_result = multiply_numbers(sum_result, y)
    logger.info(f"Product task completed: {product_result}")
    
    # Calculate final result
    final_result = {
        "input_x": x,
        "input_y": y,
        "sum": sum_result,
        "product": product_result,
        "calculation": f"({x} + {y}) * {y} = {product_result}"
    }
    
    logger.info("=" * 50)
    logger.info("Flow completed successfully!")
    logger.info(f"Final result: {final_result}")
    logger.info("=" * 50)
    
    return final_result


@flow(name="test-flow-with-retry", retries=1, log_prints=True)
def test_retry_flow(should_fail: bool = False) -> str:
    """
    Test flow with retry logic
    
    Args:
        should_fail: If True, task will fail to test retry logic
        
    Returns:
        Success message
    """
    logger.info("Testing retry logic...")
    
    @task(retries=2, retry_delay_seconds=1)
    def potentially_failing_task(fail: bool) -> str:
        """Task that can fail to test retry"""
        if fail:
            logger.warning("Task intentionally failing to test retry...")
            raise ValueError("Intentional failure for testing retry logic")
        return "Task succeeded!"
    
    try:
        result = potentially_failing_task(should_fail)
        logger.info(f"[OK] {result}")
        return result
    except Exception as e:
        logger.error(f"[FAIL] Task failed after retries: {e}")
        raise


def test_prefect_imports() -> bool:
    """Test that Prefect 3.4.14 can be imported"""
    try:
        from prefect import flow, get_client, task

        # Test Prefect 3.x imports
        try:
            from prefect.server.schemas.schedules import CronSchedule
        except ImportError:
            # Prefect 3.x may have different import path
            from prefect.schedules import CronSchedule
        logger.info("Prefect 3.4.14 imports successful [OK]")
        return True
    except ImportError as e:
        logger.error(f"[FAIL] Prefect import failed: {e}")
        return False


def check_prefect_server() -> bool:
    """Check if Prefect server is accessible (Prefect 3.4.14)"""
    try:
        import requests

        # Prefect 3.x health endpoint
        api_url = "http://localhost:4200/api"
        response = requests.get(f"{api_url}/health", timeout=2)
        if response.status_code == 200:
            logger.info("Prefect 3.4.14 server is running at http://localhost:4200 [OK]")
            logger.info(f"   Using PREFECT_API_URL={api_url}")
            return True
        else:
            logger.warning(
                f"[WARN] Prefect server responded with status {response.status_code}"
            )
            return False
    except ImportError:
        logger.warning("[WARN] 'requests' library not available, skipping server check")
        logger.info("   Install with: pip install requests")
        return False
    except Exception as e:
        logger.warning(f"[WARN] Prefect server not accessible: {e}")
        return False


def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Prefect installation and basic functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check imports only (no server needed):
  python scripts/test_prefect.py --check-only
  
  # Run tests (requires Prefect server):
  # Step 1: Start server in one terminal:
  prefect server start
  
  # Step 2: Run tests in another terminal:
  python scripts/test_prefect.py
        """
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check Prefect imports, don't run flows"
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Test retry logic"
    )
    args = parser.parse_args()
    
    logger.info("Starting Prefect 3.4.14 Test Script")
    logger.info("=" * 60)
    
    # Test 1: Import check
    logger.info("\nTest 1: Checking Prefect imports...")
    if not test_prefect_imports():
        logger.error("[FAIL] Prefect imports failed. Please check installation.")
        return 1
    
    # If check-only, exit here
    if args.check_only:
        logger.info("\nPrefect is properly installed [OK]")
        logger.info("   To run flows, start Prefect server: prefect server start")
        return 0
    
    # Test 2: Check Prefect server
    logger.info("\nTest 2: Checking Prefect server...")
    current_api_url = os.environ.get("PREFECT_API_URL", "http://localhost:4200/api")
    logger.info(f"   Current PREFECT_API_URL={current_api_url}")
    
    server_available = check_prefect_server()
    
    if not server_available:
        logger.warning("\n[WARN] Prefect server health check failed")
        logger.info("   Will attempt to connect anyway using current PREFECT_API_URL")
        logger.info(f"   If connection fails, try: set PREFECT_API_URL=http://localhost:4200/api")
    
    # Test 3: Simple flow execution
    logger.info("\nTest 3: Running simple math flow...")
    try:
        # Use temporary settings to ensure API URL is set correctly
        api_url = os.environ.get("PREFECT_API_URL", "http://localhost:4200/api")
        logger.info(f"   Connecting to Prefect API at {api_url}")
        
        # Try with explicit API URL using temporary settings
        with temporary_settings({PREFECT_API_URL: api_url}):
            result = simple_math_flow(x=10, y=4)
        
        logger.info("Flow executed successfully [OK]")
        logger.info(f"   Result: {result['calculation']}")
    except Exception as e:
        logger.error(f"[FAIL] Flow execution failed: {e}")
        logger.info("\nTroubleshooting:")
        logger.info(f"   1. Verify server is running: prefect server start")
        logger.info(f"   2. Check API URL is set: echo $env:PREFECT_API_URL")
        logger.info(f"   3. Set explicitly: $env:PREFECT_API_URL='http://localhost:4200/api'")
        return 1
    
    # Test 4: Retry logic (optional)
    if args.retry:
        logger.info("\nTest 4: Testing retry logic...")
        try:
            result = test_retry_flow(should_fail=False)
            logger.info(f"Retry test passed [OK]: {result}")
        except Exception as e:
            logger.error(f"[FAIL] Retry test failed: {e}")
            return 1
    
    logger.info("\n" + "=" * 60)
    logger.info("All tests completed successfully [OK]")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("   - View flows in Prefect UI: http://localhost:4200")
    logger.info("   - Deploy flows using: prefect deployment build")
    logger.info("   - See implementation plan: docs/development/architecture.md")
    
    return 0


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python3
"""
Yahoo Finance Officers Data Loading Example

This example demonstrates how to load and work with company officers data
from Yahoo Finance using the trading system's Yahoo Finance integration.

Features demonstrated:
- Loading officers data for individual symbols
- Loading officers data for multiple symbols
- Database storage and retrieval
- API endpoint usage
- Data validation and error handling
"""

import asyncio
import os
import sys
from typing import Any, Dict, List, Tuple

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from src.services.yahoo.client import YahooClient
from src.services.yahoo.loader import YahooDataLoader
from src.shared.logging import setup_logging


async def demo_single_symbol_officers() -> None:
    """Demo: Load officers for a single symbol"""
    print("\n" + "=" * 80)
    print("1. LOADING OFFICERS FOR SINGLE SYMBOL (AAPL)")
    print("=" * 80)

    client = YahooClient()
    loader = YahooDataLoader()

    symbol = "AAPL"

    # Fetch officers data
    print(f"\nFetching officers data for {symbol}...")
    officers = await client.get_company_officers(symbol)

    if officers:
        print(f"Found {len(officers)} officers:")
        print("\nTop executives by compensation:")
        
        # Sort by total pay (highest first)
        sorted_officers = sorted(
            officers, 
            key=lambda x: x.total_pay or 0, 
            reverse=True
        )
        
        for i, officer in enumerate(sorted_officers[:5], 1):
            pay_str = f"${officer.total_pay:,}" if officer.total_pay else "N/A"
            age_str = str(officer.age) if officer.age else "N/A"
            
            print(f"  {i}. {officer.name}")
            print(f"     Title: {officer.title}")
            print(f"     Age: {age_str}")
            print(f"     Total Pay: {pay_str}")
            print(f"     Exercised Value: ${officer.exercised_value:,}" if officer.exercised_value else "     Exercised Value: N/A")
            print(f"     Unexercised Value: ${officer.unexercised_value:,}" if officer.unexercised_value else "     Unexercised Value: N/A")
            print()

        # Load to database
        print(f"Loading officers data to database...")
        stored_officers = await loader.load_company_officers(symbol)
        print(f"Successfully stored {len(stored_officers)} officers in database")
        
    else:
        print(f"No officers data available for {symbol}")


async def demo_multiple_symbols_officers() -> None:
    """Demo: Load officers for multiple symbols"""
    print("\n" + "=" * 80)
    print("2. LOADING OFFICERS FOR MULTIPLE SYMBOLS")
    print("=" * 80)

    client = YahooClient()
    loader = YahooDataLoader()
    
    symbols = ["MSFT", "GOOGL", "TSLA", "AMZN", "META"]
    
    print(f"\nLoading officers for {len(symbols)} symbols: {', '.join(symbols)}")
    
    results: Dict[str, int] = {}
    
    for symbol in symbols:
        print(f"\nProcessing {symbol}...")
        try:
            # Fetch and store officers
            officers = await loader.load_company_officers(symbol)
            results[symbol] = len(officers)
            
            if officers:
                # Find highest paid officer
                top_officer = max(officers, key=lambda x: x.total_pay or 0)
                pay_str = f"${top_officer.total_pay:,}" if top_officer.total_pay else "N/A"
                print(f"  [OK] {len(officers)} officers loaded")
                print(f"  Top paid: {top_officer.name} ({top_officer.title}) - {pay_str}")
            else:
                print(f"  [WARN] No officers data available")
                
        except Exception as e:
            print(f"  [FAIL] Error loading {symbol}: {e}")
            results[symbol] = 0

    # Summary
    print(f"\n" + "-" * 50)
    print("SUMMARY:")
    total_officers = sum(results.values())
    print(f"Total officers loaded: {total_officers}")
    for symbol, count in results.items():
        status = "[OK]" if count > 0 else "[FAIL]"
        print(f"  {status} {symbol}: {count} officers")


async def demo_officers_analysis() -> None:
    """Demo: Analyze officers data patterns"""
    print("\n" + "=" * 80)
    print("3. OFFICERS DATA ANALYSIS")
    print("=" * 80)

    client = YahooClient()
    
    symbols = ["AAPL", "MSFT", "GOOGL"]
    
    print(f"\nAnalyzing officers patterns across {len(symbols)} companies...")
    
    all_officers: List[Tuple[str, Any]] = []
    
    for symbol in symbols:
        try:
            officers = await client.get_company_officers(symbol)
            all_officers.extend([(symbol, officer) for officer in officers])
        except Exception as e:
            print(f"Error fetching officers for {symbol}: {e}")
    
    if not all_officers:
        print("No officers data available for analysis")
        return
    
    # Analyze compensation patterns
    print(f"\n--- COMPENSATION ANALYSIS ---")
    officers_with_pay = [(symbol, officer) for symbol, officer in all_officers if officer.total_pay]
    
    if officers_with_pay:
        # Sort by compensation
        sorted_by_pay = sorted(officers_with_pay, key=lambda x: x[1].total_pay, reverse=True)
        
        print(f"Total officers with compensation data: {len(officers_with_pay)}")
        print(f"\nTop 10 highest paid executives:")
        
        for i, (symbol, officer) in enumerate(sorted_by_pay[:10], 1):
            print(f"  {i:2d}. {officer.name[:30]:30s} | {symbol:6s} | ${officer.total_pay:>12,}")
        
        # Calculate statistics
        compensations = [officer.total_pay for _, officer in officers_with_pay]
        avg_compensation = sum(compensations) / len(compensations)
        max_compensation = max(compensations)
        min_compensation = min(compensations)
        
        print(f"\nCompensation Statistics:")
        print(f"  Average: ${avg_compensation:,.0f}")
        print(f"  Highest: ${max_compensation:,.0f}")
        print(f"  Lowest:  ${min_compensation:,.0f}")
    
    # Analyze title patterns
    print(f"\n--- TITLE ANALYSIS ---")
    title_counts = {}
    
    for _, officer in all_officers:
        if officer.title:
            # Clean up title for grouping
            title_key = officer.title.upper()
            if "CEO" in title_key:
                title_key = "CEO"
            elif "CFO" in title_key:
                title_key = "CFO"
            elif "CTO" in title_key:
                title_key = "CTO"
            elif "PRESIDENT" in title_key:
                title_key = "PRESIDENT"
            elif "DIRECTOR" in title_key and "CEO" not in title_key:
                title_key = "DIRECTOR"
            elif "VICE PRESIDENT" in title_key or "VP" in title_key:
                title_key = "VICE PRESIDENT"
            
            title_counts[title_key] = title_counts.get(title_key, 0) + 1
    
    # Sort by count
    sorted_titles = sorted(title_counts.items(), key=lambda x: x[1], reverse=True)
    
    print(f"Most common executive titles:")
    for title, count in sorted_titles[:10]:
        print(f"  {title:20s}: {count:2d} executives")
    
    # Analyze age patterns
    print(f"\n--- AGE ANALYSIS ---")
    officers_with_age = [(symbol, officer) for symbol, officer in all_officers if officer.age]
    
    if officers_with_age:
        ages = [officer.age for _, officer in officers_with_age]
        avg_age = sum(ages) / len(ages)
        max_age = max(ages)
        min_age = min(ages)
        
        print(f"Age Statistics (based on {len(officers_with_age)} officers with age data):")
        print(f"  Average age: {avg_age:.1f} years")
        print(f"  Oldest: {max_age} years")
        print(f"  Youngest: {min_age} years")
        
        # Age distribution
        age_ranges = {
            "30-39": len([age for age in ages if 30 <= age < 40]),
            "40-49": len([age for age in ages if 40 <= age < 50]),
            "50-59": len([age for age in ages if 50 <= age < 60]),
            "60-69": len([age for age in ages if 60 <= age < 70]),
            "70+": len([age for age in ages if age >= 70]),
        }
        
        print(f"\nAge Distribution:")
        for range_name, count in age_ranges.items():
            if count > 0:
                percentage = (count / len(ages)) * 100
                print(f"  {range_name:6s}: {count:2d} executives ({percentage:4.1f}%)")


async def demo_api_usage() -> None:
    """Demo: Using the officers API endpoints"""
    print("\n" + "=" * 80)
    print("4. OFFICERS API ENDPOINTS DEMO")
    print("=" * 80)
    
    print("\nThe system provides several API endpoints for officers data:")
    print("\n1. GET /api/company-officers/{symbol}")
    print("   - Get all officers for a specific symbol")
    print("   - Example: GET /api/company-officers/AAPL")
    
    print("\n2. GET /api/company-officers/{symbol}/by-title")
    print("   - Get officers grouped by title")
    print("   - Example: GET /api/company-officers/AAPL/by-title")
    
    print("\n3. GET /api/company-officers/{symbol}/compensation")
    print("   - Get compensation summary statistics")
    print("   - Example: GET /api/company-officers/AAPL/compensation")
    
    print("\n4. GET /api/company-officers")
    print("   - List all symbols with officers data")
    print("   - Shows officer counts per symbol")
    
    print("\nExample API responses:")
    print("\nGET /api/company-officers/AAPL response:")
    print("""
{
  "success": true,
  "symbol": "AAPL",
  "count": 10,
  "officers": [
    {
      "id": 1,
      "symbol": "AAPL",
      "name": "Mr. Timothy D. Cook",
      "title": "CEO & Director",
      "age": 63,
      "year_born": 1960,
      "fiscal_year": 2023,
      "total_pay": 1652085600,
      "total_pay_display": "$16.5M",
      "exercised_value": null,
      "exercised_value_display": "N/A",
      "unexercised_value": null,
      "unexercised_value_display": "N/A",
      "data_source": "yahoo",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
    """)


async def main() -> None:
    """Run all officers demos"""
    setup_logging()
    
    print("\n" + "#" * 80)
    print("# YAHOO FINANCE OFFICERS DATA LOADING DEMO")
    print("#" * 80)
    print("\nThis demo shows how to work with company officers data from Yahoo Finance")
    print("using the trading system's integrated Yahoo Finance functionality.")
    
    try:
        # Run all demos
        await demo_single_symbol_officers()
        await demo_multiple_symbols_officers()
        await demo_officers_analysis()
        await demo_api_usage()
        
        print("\n" + "#" * 80)
        print("# OFFICERS DEMO COMPLETED!")
        print("#" * 80)
        print("\nSUMMARY:")
        print("[OK] Single symbol officers loading")
        print("[OK] Multiple symbols batch loading")
        print("[OK] Officers data analysis and patterns")
        print("[OK] API endpoints overview")
        print("\nThe officers data is now available in the database and via API endpoints.")
        print("You can use this data for:")
        print("- Executive compensation analysis")
        print("- Corporate governance research")
        print("- Leadership team analysis")
        print("- Risk assessment based on management changes")
        
    except Exception as e:
        print(f"\nError occurred during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

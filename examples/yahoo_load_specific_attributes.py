"""
Yahoo Finance - Load Specific Data Attributes

Practical examples for loading specific data you need.
"""

import asyncio
from datetime import date, timedelta

from src.services.yahoo.client import YahooClient
from src.services.yahoo.loader import YahooDataLoader
from src.shared.logging import setup_logging


async def load_price_data_only(symbols: list[str]) -> None:
    """Load just price data (OHLCV) for multiple symbols"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Load Price Data Only")
    print("=" * 80)

    loader = YahooDataLoader(delay_between_requests=0.3)

    end_date = date.today()
    start_date = end_date - timedelta(days=90)  # 3 months

    for symbol in symbols:
        try:
            count = await loader.load_market_data(
                symbol=symbol, start_date=start_date, end_date=end_date, interval="1d"
            )
            print(f"[OK] {symbol}: Loaded {count} daily bars")
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[FAIL] {symbol}: {e}")


async def load_fundamental_ratios(symbols: list[str]) -> None:
    """Load key fundamental ratios for screening"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Load Fundamental Ratios for Screening")
    print("=" * 80)

    client = YahooClient()

    results = []

    for symbol in symbols:
        try:
            stats = await client.get_key_statistics(symbol)

            results.append(
                {
                    "symbol": symbol,
                    "pe_ratio": stats.trailing_pe,
                    "peg_ratio": stats.peg_ratio,
                    "price_to_book": stats.price_to_book,
                    "profit_margin": stats.profit_margin,
                    "roe": stats.return_on_equity,
                    "debt_to_equity": stats.debt_to_equity,
                    "dividend_yield": stats.dividend_yield,
                }
            )

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[FAIL] {symbol}: {e}")

    # Display results
    print(
        f"\n{'Symbol':<8} {'P/E':>8} {'PEG':>8} {'P/B':>8} {'Margin%':>8} {'ROE%':>8} {'D/E':>8} {'DivYld%':>8}"
    )
    print("-" * 80)
    for r in results:
        print(
            f"{r['symbol']:<8} " f"{r['pe_ratio']:>8.2f} "
            if r["pe_ratio"]
            else (
                f"{'N/A':>8} " f"{r['peg_ratio']:>8.2f} "
                if r["peg_ratio"]
                else (
                    f"{'N/A':>8} " f"{r['price_to_book']:>8.2f} "
                    if r["price_to_book"]
                    else (
                        f"{'N/A':>8} " f"{r['profit_margin']*100:>8.2f} "
                        if r["profit_margin"]
                        else (
                            f"{'N/A':>8} " f"{r['roe']*100:>8.2f} "
                            if r["roe"]
                            else (
                                f"{'N/A':>8} " f"{r['debt_to_equity']:>8.2f} "
                                if r["debt_to_equity"]
                                else (
                                    f"{'N/A':>8} " f"{r['dividend_yield']*100:>8.2f}"
                                    if r["dividend_yield"]
                                    else f"{'N/A':>8}"
                                )
                            )
                        )
                    )
                )
            )
        )


async def load_dividend_history(symbols: list[str]) -> None:
    """Load dividend payment history"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Load Dividend History")
    print("=" * 80)

    client = YahooClient()

    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2)  # 2 years

    for symbol in symbols:
        try:
            dividends = await client.get_dividends(symbol, start_date, end_date)

            if dividends:
                total = sum(d.amount for d in dividends)
                recent_annual = sum(
                    d.amount
                    for d in dividends
                    if d.ex_date >= date.today() - timedelta(days=365)
                )

                print(f"\n{symbol}:")
                print(f"  Total dividends (2 years): ${total:.2f}")
                print(f"  Last 12 months: ${recent_annual:.2f}")
                print(f"  Payments: {len(dividends)}")
                print(
                    f"  Latest: {dividends[-1].ex_date} - ${dividends[-1].amount:.4f}"
                )
            else:
                print(f"\n{symbol}: No dividends")

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"\n{symbol}: Error - {e}")


async def load_financial_health_metrics(symbols: list[str]) -> None:
    """Load financial health metrics for risk assessment"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Load Financial Health Metrics")
    print("=" * 80)

    client = YahooClient()

    for symbol in symbols:
        try:
            stats = await client.get_key_statistics(symbol)

            print(f"\n{symbol} Financial Health:")
            print(
                f"  Current Ratio: {stats.current_ratio:.2f}"
                if stats.current_ratio
                else "  Current Ratio: N/A"
            )
            print(
                f"  Quick Ratio: {stats.quick_ratio:.2f}"
                if stats.quick_ratio
                else "  Quick Ratio: N/A"
            )
            print(
                f"  Debt/Equity: {stats.debt_to_equity:.2f}"
                if stats.debt_to_equity
                else "  Debt/Equity: N/A"
            )
            print(f"  Interest Coverage: ", end="")

            # Get income statement for interest coverage
            income = await client.get_financial_statements(symbol, "income", "annual")
            if income and len(income) > 0:
                data = income[0].data
                if "Operating Income" in data and "Interest Expense" in data:
                    if data["Interest Expense"] and data["Interest Expense"] != 0:
                        coverage = data["Operating Income"] / abs(
                            data["Interest Expense"]
                        )
                        print(f"{coverage:.2f}x")
                    else:
                        print("N/A (no interest expense)")
                else:
                    print("N/A")
            else:
                print("N/A")

            print(
                f"  Free Cash Flow: ${stats.free_cash_flow:,.0f}"
                if stats.free_cash_flow
                else "  FCF: N/A"
            )
            print(
                f"  Total Cash: ${stats.total_cash:,.0f}"
                if stats.total_cash
                else "  Cash: N/A"
            )
            print(
                f"  Total Debt: ${stats.total_debt:,.0f}"
                if stats.total_debt
                else "  Debt: N/A"
            )

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"\n{symbol}: Error - {e}")


async def load_growth_metrics(symbols: list[str]) -> None:
    """Load growth metrics"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Load Growth Metrics")
    print("=" * 80)

    client = YahooClient()

    for symbol in symbols:
        try:
            stats = await client.get_key_statistics(symbol)

            print(f"\n{symbol} Growth:")
            print(
                f"  Revenue Growth: {stats.revenue_growth*100:.2f}%"
                if stats.revenue_growth
                else "  Revenue Growth: N/A"
            )
            print(
                f"  Earnings Growth: {stats.earnings_growth*100:.2f}%"
                if stats.earnings_growth
                else "  Earnings Growth: N/A"
            )

            # Get historical financials for trend
            income = await client.get_financial_statements(symbol, "income", "annual")
            if income and len(income) >= 2:
                current_rev = income[0].data.get("Total Revenue")
                prior_rev = income[1].data.get("Total Revenue")

                if current_rev and prior_rev:
                    yoy_growth = ((current_rev - prior_rev) / prior_rev) * 100
                    print(f"  Revenue YoY (from filings): {yoy_growth:.2f}%")

                current_income = income[0].data.get("Net Income")
                prior_income = income[1].data.get("Net Income")

                if current_income and prior_income and prior_income != 0:
                    income_growth = (
                        (current_income - prior_income) / prior_income
                    ) * 100
                    print(f"  Net Income YoY: {income_growth:.2f}%")

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"\n{symbol}: Error - {e}")


async def load_technical_levels(symbols: list[str]) -> None:
    """Load technical analysis levels"""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Load Technical Analysis Levels")
    print("=" * 80)

    client = YahooClient()

    for symbol in symbols:
        try:
            stats = await client.get_key_statistics(symbol)

            # Get recent price data
            bars = await client.get_historical_data(
                symbol,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
            )

            if bars:
                latest = bars[-1]

                print(f"\n{symbol} Technical Levels:")
                print(f"  Current Price: ${latest.close:.2f}")
                print(
                    f"  50-Day MA: ${stats.fifty_day_average:.2f}"
                    if stats.fifty_day_average
                    else "  50-Day MA: N/A"
                )
                print(
                    f"  200-Day MA: ${stats.two_hundred_day_average:.2f}"
                    if stats.two_hundred_day_average
                    else "  200-Day MA: N/A"
                )
                print(
                    f"  52-Week High: ${stats.fifty_two_week_high:.2f}"
                    if stats.fifty_two_week_high
                    else "  52W High: N/A"
                )
                print(
                    f"  52-Week Low: ${stats.fifty_two_week_low:.2f}"
                    if stats.fifty_two_week_low
                    else "  52W Low: N/A"
                )

                # Calculate position in range
                if stats.fifty_two_week_high and stats.fifty_two_week_low:
                    range_position = (
                        (latest.close - stats.fifty_two_week_low)
                        / (stats.fifty_two_week_high - stats.fifty_two_week_low)
                        * 100
                    )
                    print(f"  Position in 52W Range: {range_position:.1f}%")

                print(f"  Beta: {stats.beta:.2f}" if stats.beta else "  Beta: N/A")
                print(
                    f"  Average Volume: {stats.average_volume:,}"
                    if stats.average_volume
                    else "  Avg Volume: N/A"
                )
                print(f"  Recent Volume: {latest.volume:,}")

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"\n{symbol}: Error - {e}")


async def load_ownership_data(symbols: list[str]) -> None:
    """Load ownership and sentiment data"""
    print("\n" + "=" * 80)
    print("EXAMPLE 7: Load Ownership & Sentiment Data")
    print("=" * 80)

    client = YahooClient()

    for symbol in symbols:
        try:
            stats = await client.get_key_statistics(symbol)

            print(f"\n{symbol} Ownership:")
            print(
                f"  Insider Ownership: {stats.held_percent_insiders*100:.2f}%"
                if stats.held_percent_insiders
                else "  Insiders: N/A"
            )
            print(
                f"  Institutional: {stats.held_percent_institutions*100:.2f}%"
                if stats.held_percent_institutions
                else "  Institutions: N/A"
            )
            print(
                f"  Short Interest: {stats.shares_short:,} shares"
                if stats.shares_short
                else "  Short Interest: N/A"
            )
            print(
                f"  Short Ratio: {stats.short_ratio:.2f} days"
                if stats.short_ratio
                else "  Short Ratio: N/A"
            )

            # Get analyst recommendations
            recs = await client.get_analyst_recommendations(symbol)
            if recs and len(recs) > 0:
                latest = recs[0]
                total = latest.total_analysts

                if total > 0:
                    buy_pct = (latest.strong_buy + latest.buy) / total * 100
                    print(f"\n  Analyst Sentiment:")
                    print(f"    Total Analysts: {total}")
                    print(f"    Buy/Strong Buy: {buy_pct:.1f}%")
                    print(f"    Hold: {latest.hold/total*100:.1f}%")
                    print(
                        f"    Sell/Strong Sell: {(latest.sell + latest.strong_sell)/total*100:.1f}%"
                    )

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"\n{symbol}: Error - {e}")


async def main() -> None:
    """Run all examples"""
    setup_logging()

    print("\n" + "#" * 80)
    print("# YAHOO FINANCE - LOAD SPECIFIC DATA ATTRIBUTES")
    print("#" * 80)

    # Define symbols to analyze
    tech_stocks = ["AAPL", "MSFT", "GOOGL"]
    dividend_stocks = ["JNJ", "PG", "KO"]

    # Run examples
    await load_price_data_only(tech_stocks)
    await load_fundamental_ratios(tech_stocks)
    await load_dividend_history(dividend_stocks)
    await load_financial_health_metrics(["AAPL", "TSLA"])
    await load_growth_metrics(["AAPL", "NVDA"])
    await load_technical_levels(["AAPL", "SPY"])
    await load_ownership_data(["AAPL", "GME"])

    print("\n" + "#" * 80)
    print("# ALL EXAMPLES COMPLETED!")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

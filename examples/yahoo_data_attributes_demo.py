"""
Yahoo Finance - Complete Data Attributes Demo

Shows all available data types and attributes from Yahoo Finance.
"""

import asyncio
from datetime import date, timedelta

from src.services.yahoo.client import YahooClient
from src.shared.logging import setup_logging


async def demo_market_data(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Historical OHLCV market data"""
    print("\n" + "=" * 80)
    print("1. MARKET DATA (OHLCV)")
    print("=" * 80)

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    bars = await client.get_historical_data(symbol, start_date, end_date, interval="1d")

    if bars:
        bar = bars[-1]  # Latest bar
        print(f"\nSymbol: {bar.symbol}")
        print(f"Timestamp: {bar.timestamp}")
        print(f"Open: ${bar.open:.2f}")
        print(f"High: ${bar.high:.2f}")
        print(f"Low: ${bar.low:.2f}")
        print(f"Close: ${bar.close:.2f}")
        print(f"Volume: {bar.volume:,}")
        print(f"Dividends: ${bar.dividends:.4f}")
        print(f"Stock Splits: {bar.stock_splits}")
        print(f"\nTotal bars fetched: {len(bars)}")


async def demo_company_info(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Company profile and information"""
    print("\n" + "=" * 80)
    print("2. COMPANY INFO")
    print("=" * 80)

    info = await client.get_company_info(symbol)

    print(f"\nSymbol: {info.symbol}")
    print(f"Name: {info.name}")
    print(f"Sector: {info.sector}")
    print(f"Industry: {info.industry}")
    print(f"Website: {info.website}")
    print(f"Phone: {info.phone}")
    print(f"Address: {info.address}, {info.city}, {info.state} {info.zip}")
    print(f"Country: {info.country}")
    print(f"Employees: {info.employees:,}" if info.employees else "Employees: N/A")
    print(f"Market Cap: ${info.market_cap:,}" if info.market_cap else "Market Cap: N/A")
    print(f"Exchange: {info.exchange}")
    print(f"Currency: {info.currency}")
    print(f"\nDescription (first 200 chars):")
    if info.description:
        print(info.description[:200] + "...")


async def demo_key_statistics(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Key financial statistics"""
    print("\n" + "=" * 80)
    print("3. KEY STATISTICS")
    print("=" * 80)

    stats = await client.get_key_statistics(symbol)

    print("\n--- VALUATION METRICS ---")
    print(
        f"Market Cap: ${stats.market_cap:,}" if stats.market_cap else "Market Cap: N/A"
    )
    print(
        f"Enterprise Value: ${stats.enterprise_value:,}"
        if stats.enterprise_value
        else "Enterprise Value: N/A"
    )
    print(
        f"Trailing P/E: {stats.trailing_pe:.2f}"
        if stats.trailing_pe
        else "Trailing P/E: N/A"
    )
    print(
        f"Forward P/E: {stats.forward_pe:.2f}"
        if stats.forward_pe
        else "Forward P/E: N/A"
    )
    print(f"PEG Ratio: {stats.peg_ratio:.2f}" if stats.peg_ratio else "PEG Ratio: N/A")
    print(
        f"Price/Book: {stats.price_to_book:.2f}"
        if stats.price_to_book
        else "Price/Book: N/A"
    )
    print(
        f"Price/Sales: {stats.price_to_sales:.2f}"
        if stats.price_to_sales
        else "Price/Sales: N/A"
    )

    print("\n--- PROFITABILITY METRICS ---")
    print(
        f"Profit Margin: {stats.profit_margin*100:.2f}%"
        if stats.profit_margin
        else "Profit Margin: N/A"
    )
    print(
        f"Operating Margin: {stats.operating_margin*100:.2f}%"
        if stats.operating_margin
        else "Operating Margin: N/A"
    )
    print(
        f"Return on Assets: {stats.return_on_assets*100:.2f}%"
        if stats.return_on_assets
        else "ROA: N/A"
    )
    print(
        f"Return on Equity: {stats.return_on_equity*100:.2f}%"
        if stats.return_on_equity
        else "ROE: N/A"
    )
    print(
        f"Gross Margin: {stats.gross_margin*100:.2f}%"
        if stats.gross_margin
        else "Gross Margin: N/A"
    )

    print("\n--- FINANCIAL HEALTH ---")
    print(f"Total Revenue: ${stats.revenue:,}" if stats.revenue else "Revenue: N/A")
    print(
        f"Revenue Per Share: ${stats.revenue_per_share:.2f}"
        if stats.revenue_per_share
        else "Revenue Per Share: N/A"
    )
    print(
        f"EPS: ${stats.earnings_per_share:.2f}"
        if stats.earnings_per_share
        else "EPS: N/A"
    )
    print(
        f"Total Cash: ${stats.total_cash:,}" if stats.total_cash else "Total Cash: N/A"
    )
    print(
        f"Total Debt: ${stats.total_debt:,}" if stats.total_debt else "Total Debt: N/A"
    )
    print(
        f"Debt/Equity: {stats.debt_to_equity:.2f}"
        if stats.debt_to_equity
        else "Debt/Equity: N/A"
    )
    print(
        f"Current Ratio: {stats.current_ratio:.2f}"
        if stats.current_ratio
        else "Current Ratio: N/A"
    )
    print(
        f"Quick Ratio: {stats.quick_ratio:.2f}"
        if stats.quick_ratio
        else "Quick Ratio: N/A"
    )
    print(
        f"Free Cash Flow: ${stats.free_cash_flow:,}"
        if stats.free_cash_flow
        else "FCF: N/A"
    )

    print("\n--- GROWTH METRICS ---")
    print(
        f"Revenue Growth: {stats.revenue_growth*100:.2f}%"
        if stats.revenue_growth
        else "Revenue Growth: N/A"
    )
    print(
        f"Earnings Growth: {stats.earnings_growth*100:.2f}%"
        if stats.earnings_growth
        else "Earnings Growth: N/A"
    )

    print("\n--- TRADING METRICS ---")
    print(f"Beta: {stats.beta:.2f}" if stats.beta else "Beta: N/A")
    print(
        f"52 Week High: ${stats.fifty_two_week_high:.2f}"
        if stats.fifty_two_week_high
        else "52W High: N/A"
    )
    print(
        f"52 Week Low: ${stats.fifty_two_week_low:.2f}"
        if stats.fifty_two_week_low
        else "52W Low: N/A"
    )
    print(
        f"50 Day Average: ${stats.fifty_day_average:.2f}"
        if stats.fifty_day_average
        else "50D Avg: N/A"
    )
    print(
        f"200 Day Average: ${stats.two_hundred_day_average:.2f}"
        if stats.two_hundred_day_average
        else "200D Avg: N/A"
    )
    print(
        f"Average Volume: {stats.average_volume:,}"
        if stats.average_volume
        else "Avg Volume: N/A"
    )

    print("\n--- DIVIDEND METRICS ---")
    print(
        f"Dividend Yield: {stats.dividend_yield*100:.2f}%"
        if stats.dividend_yield
        else "Div Yield: N/A"
    )
    print(
        f"Dividend Rate: ${stats.dividend_rate:.2f}"
        if stats.dividend_rate
        else "Div Rate: N/A"
    )
    print(
        f"Payout Ratio: {stats.payout_ratio*100:.2f}%"
        if stats.payout_ratio
        else "Payout Ratio: N/A"
    )

    print("\n--- SHARE INFORMATION ---")
    print(
        f"Shares Outstanding: {stats.shares_outstanding:,}"
        if stats.shares_outstanding
        else "Shares Outstanding: N/A"
    )
    print(
        f"Float Shares: {stats.float_shares:,}" if stats.float_shares else "Float: N/A"
    )
    print(
        f"Shares Short: {stats.shares_short:,}"
        if stats.shares_short
        else "Shares Short: N/A"
    )
    print(
        f"Short Ratio: {stats.short_ratio:.2f}"
        if stats.short_ratio
        else "Short Ratio: N/A"
    )
    print(
        f"Held by Insiders: {stats.held_percent_insiders*100:.2f}%"
        if stats.held_percent_insiders
        else "Insiders: N/A"
    )
    print(
        f"Held by Institutions: {stats.held_percent_institutions*100:.2f}%"
        if stats.held_percent_institutions
        else "Institutions: N/A"
    )


async def demo_dividends(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Dividend history"""
    print("\n" + "=" * 80)
    print("4. DIVIDENDS")
    print("=" * 80)

    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    dividends = await client.get_dividends(symbol, start_date, end_date)

    if dividends:
        print(f"\nDividends in last year: {len(dividends)}")
        print("\nRecent dividends:")
        for div in dividends[-5:]:  # Last 5
            print(f"  {div.ex_date}: ${div.amount:.4f} ({div.dividend_type})")
    else:
        print(f"\nNo dividends found for {symbol} in the last year")


async def demo_stock_splits(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Stock split history"""
    print("\n" + "=" * 80)
    print("5. STOCK SPLITS")
    print("=" * 80)

    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 5)  # 5 years

    splits = await client.get_splits(symbol, start_date, end_date)

    if splits:
        print(f"\nStock splits in last 5 years: {len(splits)}")
        for split in splits:
            print(
                f"  {split.split_date}: {split.ratio_str} (ratio: {split.split_ratio})"
            )
    else:
        print(f"\nNo stock splits found for {symbol} in the last 5 years")


async def demo_institutional_holders(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Institutional holders"""
    print("\n" + "=" * 80)
    print("6. INSTITUTIONAL HOLDERS")
    print("=" * 80)

    holders = await client.get_institutional_holders(symbol)

    if holders:
        print(f"\nTop institutional holders: {len(holders)}")
        print("\nTop 10 holders:")
        for holder in holders[:10]:
            shares_str = f"{holder.shares:,}" if holder.shares else "N/A"
            value_str = f"${holder.value:,}" if holder.value else "N/A"
            pct_str = (
                f"{holder.percent_held*100:.2f}%" if holder.percent_held else "N/A"
            )
            print(
                f"  {holder.holder_name[:40]:40s} | Shares: {shares_str:15s} | Value: {value_str:15s} | Held: {pct_str}"
            )
    else:
        print(f"\nNo institutional holder data available for {symbol}")


async def demo_analyst_recommendations(
    client: YahooClient, symbol: str = "AAPL"
) -> None:
    """Demo: Analyst recommendations"""
    print("\n" + "=" * 80)
    print("7. ANALYST RECOMMENDATIONS")
    print("=" * 80)

    recommendations = await client.get_analyst_recommendations(symbol)

    if recommendations:
        print(f"\nAnalyst recommendation history: {len(recommendations)} periods")
        print("\nRecent recommendations:")
        for rec in recommendations[:5]:  # Show 5 most recent
            total = rec.total_analysts
            print(f"\nPeriod: {rec.period}")
            print(
                f"  Strong Buy: {rec.strong_buy:3d} ({rec.strong_buy/total*100:5.1f}%)"
                if total > 0
                else "  Strong Buy: N/A"
            )
            print(
                f"  Buy:        {rec.buy:3d} ({rec.buy/total*100:5.1f}%)"
                if total > 0
                else "  Buy: N/A"
            )
            print(
                f"  Hold:       {rec.hold:3d} ({rec.hold/total*100:5.1f}%)"
                if total > 0
                else "  Hold: N/A"
            )
            print(
                f"  Sell:       {rec.sell:3d} ({rec.sell/total*100:5.1f}%)"
                if total > 0
                else "  Sell: N/A"
            )
            print(
                f"  Strong Sell:{rec.strong_sell:3d} ({rec.strong_sell/total*100:5.1f}%)"
                if total > 0
                else "  Strong Sell: N/A"
            )
            print(f"  Total Analysts: {total}")
    else:
        print(f"\nNo analyst recommendations available for {symbol}")


async def demo_financial_statements(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Financial statements"""
    print("\n" + "=" * 80)
    print("8. FINANCIAL STATEMENTS")
    print("=" * 80)

    # Income statement
    print("\n--- INCOME STATEMENT (Annual) ---")
    income_stmts = await client.get_financial_statements(symbol, "income", "annual")
    if income_stmts:
        latest = income_stmts[0]
        print(f"\nPeriod End: {latest.period_end}")
        print(f"Statement Type: {latest.statement_type}")
        print(f"\nKey metrics (sample):")
        data = latest.data
        for key in ["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]:
            if key in data and data[key] is not None:
                print(f"  {key}: ${data[key]:,.0f}")
        print(f"\nTotal data points: {len(data)}")

    # Balance sheet
    print("\n--- BALANCE SHEET (Annual) ---")
    balance_stmts = await client.get_financial_statements(
        symbol, "balance_sheet", "annual"
    )
    if balance_stmts:
        latest = balance_stmts[0]
        print(f"\nPeriod End: {latest.period_end}")
        print(f"\nKey metrics (sample):")
        data = latest.data
        for key in [
            "Total Assets",
            "Total Liabilities Net Minority Interest",
            "Stockholders Equity",
        ]:
            if key in data and data[key] is not None:
                print(f"  {key}: ${data[key]:,.0f}")
        print(f"\nTotal data points: {len(data)}")

    # Cash flow
    print("\n--- CASH FLOW (Annual) ---")
    cashflow_stmts = await client.get_financial_statements(
        symbol, "cash_flow", "annual"
    )
    if cashflow_stmts:
        latest = cashflow_stmts[0]
        print(f"\nPeriod End: {latest.period_end}")
        print(f"\nKey metrics (sample):")
        data = latest.data
        for key in [
            "Operating Cash Flow",
            "Investing Cash Flow",
            "Financing Cash Flow",
            "Free Cash Flow",
        ]:
            if key in data and data[key] is not None:
                print(f"  {key}: ${data[key]:,.0f}")
        print(f"\nTotal data points: {len(data)}")


async def demo_esg_scores(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: ESG scores"""
    print("\n" + "=" * 80)
    print("9. ESG SCORES")
    print("=" * 80)

    esg = await client.get_esg_scores(symbol)

    if esg:
        print(f"\nSymbol: {esg.symbol}")
        print(f"Date: {esg.date}")
        print(
            f"\nTotal ESG Score: {esg.total_esg}"
            if esg.total_esg
            else "\nTotal ESG Score: N/A"
        )
        print(
            f"Environment Score: {esg.environment_score}"
            if esg.environment_score
            else "Environment Score: N/A"
        )
        print(
            f"Social Score: {esg.social_score}"
            if esg.social_score
            else "Social Score: N/A"
        )
        print(
            f"Governance Score: {esg.governance_score}"
            if esg.governance_score
            else "Governance Score: N/A"
        )
        print(
            f"Controversy Level: {esg.controversy_level}"
            if esg.controversy_level
            else "Controversy Level: N/A"
        )
        print(
            f"ESG Performance: {esg.esg_performance}"
            if esg.esg_performance
            else "ESG Performance: N/A"
        )
        print(f"Peer Group: {esg.peer_group}" if esg.peer_group else "Peer Group: N/A")
        print(f"Peer Count: {esg.peer_count}" if esg.peer_count else "Peer Count: N/A")
    else:
        print(f"\nNo ESG data available for {symbol}")


async def demo_company_officers(client: YahooClient, symbol: str = "AAPL") -> None:
    """Demo: Company officers/executives"""
    print("\n" + "=" * 80)
    print("10. COMPANY OFFICERS")
    print("=" * 80)

    officers = await client.get_company_officers(symbol)

    if officers:
        print(f"\nCompany officers: {len(officers)}")
        print("\nTop executives:")
        for officer in officers[:10]:
            pay_str = f"${officer.total_pay:,}" if officer.total_pay else "N/A"
            age_str = str(officer.age) if officer.age else "N/A"
            print(
                f"  {officer.name:30s} | {officer.title:40s} | Age: {age_str:3s} | Pay: {pay_str}"
            )
    else:
        print(f"\nNo officer data available for {symbol}")


async def main() -> None:
    """Run all demos"""
    setup_logging()

    print("\n" + "#" * 80)
    print("# YAHOO FINANCE - COMPLETE DATA ATTRIBUTES DEMO")
    print("#" * 80)
    print("\nThis demo shows ALL available data attributes from Yahoo Finance")

    client = YahooClient()
    symbol = "AAPL"  # Change this to any symbol you want

    print(f"\nFetching data for: {symbol}")

    try:
        # Run all demos
        await demo_market_data(client, symbol)
        await demo_company_info(client, symbol)
        await demo_key_statistics(client, symbol)
        await demo_dividends(client, symbol)
        await demo_stock_splits(client, symbol)
        await demo_institutional_holders(client, symbol)
        await demo_analyst_recommendations(client, symbol)
        await demo_financial_statements(client, symbol)
        await demo_esg_scores(client, symbol)
        await demo_company_officers(client, symbol)

    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "#" * 80)
    print("# DEMO COMPLETED!")
    print("#" * 80)
    print("\nSUMMARY OF AVAILABLE DATA ATTRIBUTES:")
    print(
        "1. Market Data: OHLCV bars with any interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)"
    )
    print("2. Company Info: Profile, sector, industry, description, contact details")
    print(
        "3. Key Statistics: 50+ metrics including valuation, profitability, growth, dividends"
    )
    print("4. Dividends: Historical dividend payments")
    print("5. Stock Splits: Historical split events")
    print("6. Institutional Holders: Major institutional ownership")
    print("7. Analyst Recommendations: Buy/sell/hold ratings")
    print(
        "8. Financial Statements: Income, balance sheet, cash flow (annual/quarterly)"
    )
    print("9. ESG Scores: Environmental, social, governance ratings")
    print("10. Company Officers: Executive team with compensation")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())

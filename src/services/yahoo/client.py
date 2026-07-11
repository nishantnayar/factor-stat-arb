"""
Yahoo Finance API Client

Client for fetching market data from Yahoo Finance using yfinance library.
"""

import warnings
from datetime import date, datetime, timezone
from typing import Any, List, Optional

import pandas as pd
import yfinance as yf
from loguru import logger

# yfinance 0.2.58 uses a NumPy timedelta pattern that NumPy >=2.5 flags as
# deprecated (bare-integer unit conversion). Upstream issue, not ours to fix.
warnings.filterwarnings(
    "ignore",
    message=r"The 'generic' unit for NumPy timedelta is deprecated.*",
    category=DeprecationWarning,
    module="yfinance.*",
)

from .exceptions import YahooAPIError, YahooDataError, YahooSymbolNotFoundError
from .models import (
    AnalystRecommendation,
    CompanyInfo,
    CompanyOfficer,
    Dividend,
    ESGScore,
    FinancialStatement,
    InstitutionalHolder,
    KeyStatistics,
    StockSplit,
    YahooBar,
    YahooHealthCheck,
)


class YahooClient:
    """Yahoo Finance API Client"""

    def __init__(self) -> None:
        """Initialize Yahoo Finance client"""
        logger.info("Yahoo Finance client initialized")

    async def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> List[YahooBar]:
        """
        Get historical OHLCV data

        Args:
            symbol: Stock symbol
            start_date: Start date for data
            end_date: End date for data
            interval: Data interval ('1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo')
            auto_adjust: If True, adjust OHLC for splits/dividends; if False, raw prices

        Returns:
            List of OHLCV bars
        """
        try:
            ticker = yf.Ticker(symbol)

            # Fetch history
            if start_date and end_date:
                hist = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    auto_adjust=auto_adjust,
                )
            else:
                # Default to 1 month if no dates provided
                hist = ticker.history(
                    period="1mo", interval=interval, auto_adjust=auto_adjust
                )

            if hist.empty:
                raise YahooDataError(f"No historical data available for {symbol}")

            # Convert to YahooBar objects
            bars = []
            for timestamp, row in hist.iterrows():
                try:
                    bar = YahooBar(
                        symbol=symbol,
                        timestamp=timestamp.to_pydatetime().replace(
                            tzinfo=timezone.utc
                        ),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        dividends=float(row.get("Dividends", 0.0)),
                        stock_splits=float(row.get("Stock Splits", 0.0)),
                    )
                    bars.append(bar)
                except Exception as e:
                    logger.warning(f"Failed to parse bar for {symbol}: {e}")
                    continue

            logger.info(f"Fetched {len(bars)} bars for {symbol}")
            return bars

        except YahooDataError:
            raise
        except Exception as e:
            raise YahooAPIError(f"Failed to get historical data for {symbol}: {str(e)}")

    async def get_company_info(self, symbol: str) -> CompanyInfo:
        """
        Get company profile and basic information

        Args:
            symbol: Stock symbol

        Returns:
            Company information
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or len(info) == 0:
                raise YahooSymbolNotFoundError(f"No info available for {symbol}")

            # Build with alias-aware keys using model_validate
            company_payload = {
                "symbol": symbol,
                "name": info.get("longName") or info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "longBusinessSummary": info.get("longBusinessSummary"),
                "website": info.get("website"),
                "phone": info.get("phone"),
                "address1": info.get("address1"),
                "city": info.get("city"),
                "state": info.get("state"),
                "zip": info.get("zip"),
                "country": info.get("country"),
                "fullTimeEmployees": info.get("fullTimeEmployees"),
                "marketCap": info.get("marketCap"),
                "currency": info.get("currency"),
                "exchange": info.get("exchange"),
                "quoteType": info.get("quoteType"),
                "additional_data": info,
            }
            company_info = CompanyInfo.model_validate(company_payload)
            return company_info

        except YahooSymbolNotFoundError:
            raise
        except Exception as e:
            raise YahooAPIError(f"Failed to get company info for {symbol}: {str(e)}")

    async def get_company_officers(self, symbol: str) -> List[CompanyOfficer]:
        """
        Get company officers/executives

        Args:
            symbol: Stock symbol

        Returns:
            List of company officers
        """
        try:
            symbol = symbol.upper().strip()
            if not symbol:
                raise ValueError("Symbol cannot be empty")

            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Check if symbol exists
            if not info or not info.get("symbol"):
                raise YahooSymbolNotFoundError(f"Symbol {symbol} not found")

            officers_data = info.get("companyOfficers", [])
            if not officers_data:
                logger.info(f"No officers data available for {symbol}")
                return []

            officers = []
            for i, officer_data in enumerate(officers_data):
                try:
                    # Validate and clean officer data
                    name = officer_data.get("name", "").strip()
                    if not name or name.lower() == "unknown":
                        logger.warning(f"Skipping officer {i+1} for {symbol}: invalid name")
                        continue

                    # Clean and validate compensation data
                    total_pay = self._clean_compensation_value(officer_data.get("totalPay"))
                    exercised_value = self._clean_compensation_value(officer_data.get("exercisedValue"))
                    unexercised_value = self._clean_compensation_value(officer_data.get("unexercisedValue"))

                    # Validate age and year_born
                    age = self._clean_age_value(officer_data.get("age"))
                    year_born = self._clean_year_value(officer_data.get("yearBorn"))
                    fiscal_year = self._clean_year_value(officer_data.get("fiscalYear"))

                    officer_payload = {
                        "symbol": symbol,
                        "name": name,
                        "title": officer_data.get("title", "").strip() or None,
                        "age": age,
                        "yearBorn": year_born,
                        "fiscalYear": fiscal_year,
                        "totalPay": total_pay,
                        "exercisedValue": exercised_value,
                        "unexercisedValue": unexercised_value,
                    }
                    officer = CompanyOfficer.model_validate(officer_payload)
                    officers.append(officer)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse officer {i+1} for {symbol}: {e}")
                    continue

            logger.info(f"Successfully fetched {len(officers)} officers for {symbol}")
            return officers

        except YahooSymbolNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get officers for {symbol}: {e}")
            raise YahooAPIError(f"Failed to get officers for {symbol}: {str(e)}")

    def _clean_compensation_value(self, value: Any) -> Optional[int]:
        """Clean and validate compensation values"""
        if value is None:
            return None
        
        try:
            # Convert to int if it's a number
            if isinstance(value, (int, float)):
                # Convert to cents and ensure it's reasonable
                cents_value = int(value * 100) if isinstance(value, float) else int(value)
                if cents_value < 0:
                    return None
                if cents_value > 10_000_000_000_000:  # 100 billion dollars in cents
                    logger.warning(f"Compensation value seems too high: {value}")
                    return None
                return cents_value
            return None
        except (ValueError, TypeError):
            return None

    def _clean_age_value(self, value: Any) -> Optional[int]:
        """Clean and validate age values"""
        if value is None:
            return None
        
        try:
            age = int(value)
            if 18 <= age <= 120:  # Reasonable age range
                return age
            return None
        except (ValueError, TypeError):
            return None

    def _clean_year_value(self, value: Any) -> Optional[int]:
        """Clean and validate year values"""
        if value is None:
            return None
        
        try:
            year = int(value)
            current_year = datetime.now().year
            if 1900 <= year <= current_year + 1:  # Reasonable year range
                return year
            return None
        except (ValueError, TypeError):
            return None

    async def get_key_statistics(self, symbol: str) -> KeyStatistics:
        """
        Get key financial statistics

        Args:
            symbol: Stock symbol

        Returns:
            Key statistics
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                raise YahooDataError(f"No statistics available for {symbol}")

            stats_payload = {
                "symbol": symbol,
                "date": date.today(),
                "marketCap": info.get("marketCap"),
                "enterpriseValue": info.get("enterpriseValue"),
                "trailingPE": info.get("trailingPE"),
                "forwardPE": info.get("forwardPE"),
                "pegRatio": info.get("pegRatio"),
                "priceToBook": info.get("priceToBook"),
                "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
                "enterpriseToRevenue": info.get("enterpriseToRevenue"),
                "enterpriseToEbitda": info.get("enterpriseToEbitda"),
                "profitMargins": info.get("profitMargins"),
                "operatingMargins": info.get("operatingMargins"),
                "returnOnAssets": info.get("returnOnAssets"),
                "returnOnEquity": info.get("returnOnEquity"),
                "grossMargins": info.get("grossMargins"),
                "ebitdaMargins": info.get("ebitdaMargins"),
                "totalRevenue": info.get("totalRevenue"),
                "revenuePerShare": info.get("revenuePerShare"),
                "trailingEps": info.get("trailingEps"),
                "totalCash": info.get("totalCash"),
                "totalDebt": info.get("totalDebt"),
                "debtToEquity": info.get("debtToEquity"),
                "currentRatio": info.get("currentRatio"),
                "quickRatio": info.get("quickRatio"),
                "freeCashflow": info.get("freeCashflow"),
                "operatingCashflow": info.get("operatingCashflow"),
                "revenueGrowth": info.get("revenueGrowth"),
                "earningsGrowth": info.get("earningsGrowth"),
                "beta": info.get("beta"),
                "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
                "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
                "fiftyDayAverage": info.get("fiftyDayAverage"),
                "twoHundredDayAverage": info.get("twoHundredDayAverage"),
                "averageVolume": info.get("averageVolume"),
                "dividendYield": info.get("dividendYield"),
                "dividendRate": info.get("dividendRate"),
                "payoutRatio": info.get("payoutRatio"),
                "sharesOutstanding": info.get("sharesOutstanding"),
                "floatShares": info.get("floatShares"),
                "sharesShort": info.get("sharesShort"),
                "shortRatio": info.get("shortRatio"),
                "heldPercentInsiders": info.get("heldPercentInsiders"),
                "heldPercentInstitutions": info.get("heldPercentInstitutions"),
            }
            stats = KeyStatistics.model_validate(stats_payload)

            logger.info(f"Fetched key statistics for {symbol}")
            return stats

        except YahooDataError:
            raise
        except Exception as e:
            raise YahooAPIError(f"Failed to get statistics for {symbol}: {str(e)}")

    async def get_dividends(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dividend]:
        """
        Get dividend history

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of dividends
        """
        try:
            ticker = yf.Ticker(symbol)

            # Fetch dividends
            if start_date and end_date:
                divs = ticker.dividends.loc[str(start_date) : str(end_date)]
            else:
                divs = ticker.dividends

            if divs.empty:
                logger.info(f"No dividends available for {symbol}")
                return []

            dividends = []
            for timestamp, amount in divs.items():
                try:
                    div = Dividend(
                        symbol=symbol,
                        ex_date=timestamp.date(),
                        amount=float(amount),
                    )
                    dividends.append(div)
                except Exception as e:
                    logger.warning(f"Failed to parse dividend: {e}")
                    continue

            logger.info(f"Fetched {len(dividends)} dividends for {symbol}")
            return dividends

        except Exception as e:
            raise YahooAPIError(f"Failed to get dividends for {symbol}: {str(e)}")

    async def get_splits(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[StockSplit]:
        """
        Get stock split history

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of stock splits
        """
        try:
            ticker = yf.Ticker(symbol)

            # Fetch splits
            if start_date and end_date:
                splits = ticker.splits.loc[str(start_date) : str(end_date)]
            else:
                splits = ticker.splits

            if splits.empty:
                logger.info(f"No splits available for {symbol}")
                return []

            split_list = []
            for timestamp, ratio in splits.items():
                try:
                    split = StockSplit(
                        symbol=symbol,
                        split_date=timestamp.date(),
                        split_ratio=float(ratio),
                        ratio_str=(
                            f"{int(ratio)}:1" if ratio >= 1 else f"1:{int(1 / ratio)}"
                        ),
                    )
                    split_list.append(split)
                except Exception as e:
                    logger.warning(f"Failed to parse split: {e}")
                    continue

            logger.info(f"Fetched {len(split_list)} splits for {symbol}")
            return split_list

        except Exception as e:
            raise YahooAPIError(f"Failed to get splits for {symbol}: {str(e)}")

    async def get_institutional_holders(self, symbol: str) -> List[InstitutionalHolder]:
        """
        Get institutional holders

        Args:
            symbol: Stock symbol

        Returns:
            List of institutional holders
        """
        try:
            ticker = yf.Ticker(symbol)
            holders_df = ticker.institutional_holders

            if holders_df is None or holders_df.empty:
                logger.info(f"No institutional holders data for {symbol}")
                return []

            holders = []
            for _, row in holders_df.iterrows():
                try:
                    holder_payload = {
                        "symbol": symbol,
                        "date_reported": pd.to_datetime(row["Date Reported"]).date(),
                        "holder_name": row["Holder"],
                        "shares": int(row["Shares"]) if pd.notna(row["Shares"]) else None,
                        "value": int(row["Value"]) if pd.notna(row["Value"]) else None,
                        "pctHeld": float(row["pctHeld"]) if pd.notna(row.get("pctHeld")) else None,
                        "pctChange": float(row["pctChange"]) if pd.notna(row.get("pctChange")) else None,
                    }
                    holder = InstitutionalHolder.model_validate(holder_payload)
                    holders.append(holder)
                except Exception as e:
                    logger.warning(f"Failed to parse holder: {e}")
                    continue

            logger.info(f"Fetched {len(holders)} institutional holders for {symbol}")
            return holders

        except Exception as e:
            raise YahooAPIError(
                f"Failed to get institutional holders for {symbol}: {str(e)}"
            )

    async def get_analyst_recommendations(
        self, symbol: str
    ) -> List[AnalystRecommendation]:
        """
        Get analyst recommendations

        Args:
            symbol: Stock symbol

        Returns:
            List of analyst recommendations
        """
        try:
            ticker = yf.Ticker(symbol)
            recs_df = ticker.recommendations_summary

            if recs_df is None or recs_df.empty:
                logger.info(f"No recommendations data for {symbol}")
                return []

            recommendations = []
            for _, row in recs_df.iterrows():
                try:
                    rec_payload = {
                        "symbol": symbol,
                        "date": date.today(),
                        "period": row["period"],
                        "strongBuy": int(row["strongBuy"]),
                        "buy": int(row["buy"]),
                        "hold": int(row["hold"]),
                        "sell": int(row["sell"]),
                        "strongSell": int(row["strongSell"]),
                    }
                    rec = AnalystRecommendation.model_validate(rec_payload)
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse recommendation: {e}")
                    continue

            logger.info(f"Fetched {len(recommendations)} recommendations for {symbol}")
            return recommendations

        except Exception as e:
            raise YahooAPIError(f"Failed to get recommendations for {symbol}: {str(e)}")

    async def get_financial_statements(
        self, symbol: str, statement_type: str, period_type: str = "annual"
    ) -> List[FinancialStatement]:
        """
        Get financial statements

        Args:
            symbol: Stock symbol
            statement_type: 'income', 'balance_sheet', or 'cash_flow'
            period_type: 'annual' or 'quarterly'

        Returns:
            List of financial statements
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get appropriate statement
            if statement_type == "income":
                df = (
                    ticker.quarterly_financials
                    if period_type == "quarterly"
                    else ticker.financials
                )
            elif statement_type == "balance_sheet":
                df = (
                    ticker.quarterly_balance_sheet
                    if period_type == "quarterly"
                    else ticker.balance_sheet
                )
            elif statement_type == "cash_flow":
                df = (
                    ticker.quarterly_cashflow
                    if period_type == "quarterly"
                    else ticker.cashflow
                )
            else:
                raise ValueError(f"Invalid statement type: {statement_type}")

            if df is None or df.empty:
                logger.info(f"No {statement_type} data for {symbol}")
                return []

            statements = []
            for col in df.columns:
                try:
                    # Convert column data to dict
                    data_dict = df[col].to_dict()
                    # Convert any NaN to None
                    data_dict = {
                        k: (
                            None
                            if pd.isna(v)
                            else float(v) if isinstance(v, (int, float)) else v
                        )
                        for k, v in data_dict.items()
                    }

                    stmt = FinancialStatement(
                        symbol=symbol,
                        period_end=pd.to_datetime(col).date(),
                        statement_type=statement_type,
                        period_type=period_type,
                        data=data_dict,
                    )
                    statements.append(stmt)
                except Exception as e:
                    logger.warning(f"Failed to parse statement: {e}")
                    continue

            logger.info(
                f"Fetched {len(statements)} {period_type} {statement_type} statements for {symbol}"
            )
            return statements

        except Exception as e:
            raise YahooAPIError(
                f"Failed to get {statement_type} for {symbol}: {str(e)}"
            )

    async def get_esg_scores(self, symbol: str) -> Optional[ESGScore]:
        """
        Get ESG scores

        Args:
            symbol: Stock symbol

        Returns:
            ESG scores or None if not available

        Note:
            HTTP 404 errors are expected and normal when ESG data is not available
            for a symbol. This is handled silently.
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Access sustainability data - this may raise HTTPError for 404
            try:
                esg_df = ticker.sustainability
            except Exception as http_error:
                # Handle HTTP errors (like 404) that occur when accessing sustainability
                error_str = str(http_error).lower()
                if "404" in error_str or "not found" in error_str or "http error" in error_str:
                    logger.debug(f"No ESG data available for {symbol} (404)")
                    return None
                # Re-raise if it's not a 404
                raise

            if esg_df is None or esg_df.empty:
                logger.debug(f"No ESG data for {symbol} (empty DataFrame)")
                return None

            # Transpose the DataFrame to access values by column name
            # The sustainability DataFrame has metrics as rows, values as columns
            # After transpose, we can access values by metric name
            esg_transposed = pd.DataFrame.transpose(esg_df)
            
            if esg_transposed.empty:
                logger.debug(f"Transposed ESG DataFrame is empty for {symbol}")
                return None

            # Get the first row which contains all the ESG values
            # The transposed DataFrame has one row with all the metric values
            esg_data = esg_transposed.iloc[0].to_dict() if not esg_transposed.empty else {}

            logger.debug(f"ESG data keys for {symbol}: {list(esg_data.keys())}")

            esg_payload = {
                "symbol": symbol,
                "date": date.today(),
                "totalEsg": esg_data.get("totalEsg"),
                "environmentScore": esg_data.get("environmentScore"),
                "socialScore": esg_data.get("socialScore"),
                "governanceScore": esg_data.get("governanceScore"),
                "highestControversy": esg_data.get("highestControversy"),
                "esgPerformance": esg_data.get("esgPerformance"),
                "peerGroup": esg_data.get("peerGroup"),
                "peerCount": esg_data.get("peerCount"),
            }
            esg = ESGScore.model_validate(esg_payload)

            logger.info(f"Fetched ESG scores for {symbol}: total_esg={esg.total_esg}")
            return esg

        except Exception as e:
            # HTTP 404 is expected when ESG data is not available for a symbol
            # This is normal behavior - not all symbols have ESG data
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str or "http error" in error_str:
                # Silently handle 404 - this is expected for symbols without ESG data
                logger.debug(f"No ESG data available for {symbol}")
            else:
                # Log other errors as warnings
                logger.warning(f"Failed to get ESG scores for {symbol}: {e}")
            return None

    async def health_check(self, test_symbol: str = "AAPL") -> YahooHealthCheck:
        """
        Check if Yahoo Finance API is accessible

        Args:
            test_symbol: Symbol to test with

        Returns:
            Health check result
        """
        try:
            ticker = yf.Ticker(test_symbol)
            info = ticker.info

            healthy = bool(info and len(info) > 0)

            return YahooHealthCheck(
                healthy=healthy,
                symbol_tested=test_symbol,
                data_available=healthy,
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            return YahooHealthCheck(
                healthy=False,
                symbol_tested=test_symbol,
                data_available=False,
                error_message=str(e),
                timestamp=datetime.now(timezone.utc),
            )

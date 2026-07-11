"""
Yahoo Finance Data Loader

Loads market data and fundamentals from Yahoo Finance into the database.
"""

import asyncio
import math
from datetime import date
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase

from src.services.data_ingestion.symbols import SymbolService
from src.shared.database.base import db_transaction
from src.shared.database.models.analyst_recommendations import AnalystRecommendation
from src.shared.database.models.company_info import CompanyInfo
from src.shared.database.models.company_officers import CompanyOfficer
from src.shared.database.models.dividends import Dividend
from src.shared.database.models.esg_scores import ESGScore
from src.shared.database.models.financial_statements import FinancialStatement
from src.shared.database.models.institutional_holders import InstitutionalHolder
from src.shared.database.models.key_statistics import KeyStatistics
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.stock_splits import StockSplit
from src.shared.database.models.symbols import Symbol

from .client import YahooClient
from .exceptions import YahooAPIError


def safe_float_conversion(
    value: Any, max_value: float = 999999999.99
) -> Optional[float]:
    """
    Safely convert a value to float, handling infinity and NaN cases.

    Args:
        value: The value to convert
        max_value: Maximum allowed value (default: 999999999.99 to fit NUMERIC(10,2))

    Returns:
        Converted float value or None if invalid/infinite
    """
    if value is None:
        return None

    try:
        float_val = float(value)

        if math.isinf(float_val) or math.isnan(float_val):
            logger.warning(
                f"Encountered invalid numeric value: {value}, converting to None"
            )
            return None

        if abs(float_val) > max_value:
            logger.warning(
                f"Value {float_val} exceeds maximum allowed value "
                f"{max_value}, converting to None"
            )
            return None

        return float_val

    except (ValueError, TypeError) as e:
        logger.warning(
            f"Failed to convert value {value} to float: {e}, converting to None"
        )
        return None


# Fiscal year end months for companies with non-standard fiscal years
# Default is December (month 12) for most companies
FISCAL_YEAR_END_MONTHS: Dict[str, int] = {
    "AAPL": 9,   # September
    "SBUX": 9,   # September
    "DIS": 9,    # September
    "FDX": 5,    # May
    "NKE": 5,    # May
    "WMT": 1,    # January
    "TGT": 1,    # January
    "HD": 1,     # January
    "LOW": 1,    # January
    "COST": 8,   # August
}


class YahooDataLoader:
    """Load data from Yahoo Finance into database"""

    def __init__(
        self,
        batch_size: int = 100,
        delay_between_requests: float = 0.5,
        data_source: str = "yahoo",
    ):
        """
        Initialize the Yahoo data loader

        Args:
            batch_size: Number of records to process in each batch
            delay_between_requests: Delay between requests (seconds)
            data_source: Data source identifier
        """
        self.client = YahooClient()
        self.batch_size = batch_size
        self.delay_between_requests = delay_between_requests
        self.data_source = data_source
        self.symbol_service = SymbolService()

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to uppercase and strip whitespace"""
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty or None")
        return symbol.upper().strip()

    async def _update_symbol_status(
        self,
        symbol: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update symbol data ingestion status"""
        try:
            await self.symbol_service.update_symbol_data_status(
                symbol=symbol,
                date=date.today(),
                data_source=self.data_source,
                status=status,
                error_message=error_message,
            )
        except Exception as e:
            logger.warning(f"Failed to update symbol status for {symbol}: {e}")

    def _upsert_records(
        self,
        model: Type[DeclarativeBase],
        records: List[Dict[str, Any]],
        index_elements: List[str],
        update_fields: Optional[List[str]] = None,
    ) -> int:
        """
        Generic upsert helper for database records.

        Args:
            model: SQLAlchemy model class
            records: List of record dictionaries
            index_elements: List of fields that form the unique constraint
            update_fields: List of fields to update on conflict (None = all fields)

        Returns:
            Number of records processed
        """
        if not records:
            return 0

        with db_transaction() as session:
            stmt = insert(model).values(records)

            if update_fields is None:
                # Update all fields except index elements
                set_dict = {
                    col.name: stmt.excluded[col.name]
                    for col in model.__table__.columns
                    if col.name not in index_elements
                }
            else:
                set_dict = {field: stmt.excluded[field] for field in update_fields}

            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=set_dict,
            )

            session.execute(stmt)
            session.commit()

        return len(records)

    async def load_market_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> int:
        """
        Load OHLCV market data for a symbol.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval (1d, 1h, etc.)
            auto_adjust: If True, load split/dividend-adjusted prices (stored as
                data_source 'yahoo_adjusted'); if False, raw prices (data_source 'yahoo').

        Returns:
            Number of records inserted/updated
        """
        symbol = self._normalize_symbol(symbol)
        data_source = "yahoo_adjusted" if auto_adjust else self.data_source
        logger.info(
            f"Loading market data for {symbol} from Yahoo Finance "
            f"(auto_adjust={auto_adjust}, data_source={data_source})"
        )

        try:
            bars = await self.client.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                auto_adjust=auto_adjust,
            )

            if not bars:
                logger.warning(f"No market data found for {symbol}")
                return 0

            records = [
                {
                    "symbol": symbol,
                    "timestamp": bar.timestamp,
                    "data_source": data_source,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in bars
            ]

            # Insert in batches
            inserted_count = 0
            for i in range(0, len(records), self.batch_size):
                batch = records[i : i + self.batch_size]
                self._upsert_records(
                    model=MarketData,
                    records=batch,
                    index_elements=["symbol", "timestamp", "data_source"],
                    update_fields=["open", "high", "low", "close", "volume"],
                )
                inserted_count += len(batch)

            logger.info(
                f"Loaded {inserted_count} market data records for {symbol} "
                f"(data_source={data_source})"
            )
            return inserted_count

        except YahooAPIError as e:
            logger.error(f"Yahoo API error for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load market data for {symbol}: {e}")
            raise

    async def load_company_info(self, symbol: str) -> bool:
        """Load company information"""
        symbol = self._normalize_symbol(symbol)
        logger.debug(f"Loading company info for {symbol} from Yahoo Finance")

        try:
            company_data = await self.client.get_company_info(symbol)

            with db_transaction() as session:
                company_info = CompanyInfo(
                    symbol=symbol,
                    name=company_data.name,
                    sector=company_data.sector,
                    industry=company_data.industry,
                    description=company_data.description,
                    website=company_data.website,
                    phone=company_data.phone,
                    address=company_data.address,
                    city=company_data.city,
                    state=company_data.state,
                    zip=company_data.zip,
                    country=company_data.country,
                    employees=company_data.employees,
                    market_cap=company_data.market_cap,
                    currency=company_data.currency,
                    exchange=company_data.exchange,
                    quote_type=company_data.quote_type,
                    data_source=self.data_source,
                    additional_data=company_data.additional_data,
                )
                session.merge(company_info)
                session.commit()

            logger.info(f"Successfully loaded company info for {symbol}")
            return True

        except YahooAPIError:
            raise
        except Exception as e:
            logger.error(f"Failed to load company info for {symbol}: {e}")
            raise YahooAPIError(f"Failed to load company info for {symbol}: {e}")

    async def load_key_statistics(
        self, symbol: str, stats_date: Optional[date] = None
    ) -> bool:
        """Load key financial statistics for a symbol"""
        symbol = self._normalize_symbol(symbol)
        stats_date = stats_date or date.today()
        logger.info(f"Loading key statistics for {symbol} from Yahoo Finance")

        try:
            stats_data = await self.client.get_key_statistics(symbol)

            # Map stats_data fields to database fields with safe conversion
            stats_dict = {
                "symbol": symbol,
                "date": stats_date,
                "data_source": self.data_source,
                "market_cap": stats_data.market_cap,
                "enterprise_value": stats_data.enterprise_value,
                "trailing_pe": safe_float_conversion(stats_data.trailing_pe),
                "forward_pe": safe_float_conversion(stats_data.forward_pe),
                "peg_ratio": safe_float_conversion(stats_data.peg_ratio),
                "price_to_book": safe_float_conversion(stats_data.price_to_book),
                "price_to_sales": safe_float_conversion(stats_data.price_to_sales),
                "enterprise_to_revenue": safe_float_conversion(
                    stats_data.enterprise_to_revenue
                ),
                "enterprise_to_ebitda": safe_float_conversion(
                    stats_data.enterprise_to_ebitda
                ),
                "profit_margin": safe_float_conversion(stats_data.profit_margin),
                "operating_margin": safe_float_conversion(stats_data.operating_margin),
                "return_on_assets": safe_float_conversion(stats_data.return_on_assets),
                "return_on_equity": safe_float_conversion(stats_data.return_on_equity),
                "gross_margin": safe_float_conversion(stats_data.gross_margin),
                "ebitda_margin": safe_float_conversion(stats_data.ebitda_margin),
                "revenue": stats_data.revenue,
                "revenue_per_share": safe_float_conversion(
                    stats_data.revenue_per_share
                ),
                "earnings_per_share": safe_float_conversion(
                    stats_data.earnings_per_share
                ),
                "total_cash": stats_data.total_cash,
                "total_debt": stats_data.total_debt,
                "debt_to_equity": safe_float_conversion(stats_data.debt_to_equity),
                "current_ratio": safe_float_conversion(stats_data.current_ratio),
                "quick_ratio": safe_float_conversion(stats_data.quick_ratio),
                "free_cash_flow": stats_data.free_cash_flow,
                "operating_cash_flow": stats_data.operating_cash_flow,
                "revenue_growth": safe_float_conversion(stats_data.revenue_growth),
                "earnings_growth": safe_float_conversion(stats_data.earnings_growth),
                "beta": safe_float_conversion(stats_data.beta),
                "fifty_two_week_high": safe_float_conversion(
                    stats_data.fifty_two_week_high
                ),
                "fifty_two_week_low": safe_float_conversion(
                    stats_data.fifty_two_week_low
                ),
                "fifty_day_average": safe_float_conversion(
                    stats_data.fifty_day_average
                ),
                "two_hundred_day_average": safe_float_conversion(
                    stats_data.two_hundred_day_average
                ),
                "average_volume": stats_data.average_volume,
                "dividend_yield": safe_float_conversion(stats_data.dividend_yield),
                "dividend_rate": safe_float_conversion(stats_data.dividend_rate),
                "payout_ratio": safe_float_conversion(stats_data.payout_ratio),
                "shares_outstanding": stats_data.shares_outstanding,
                "float_shares": stats_data.float_shares,
                "shares_short": stats_data.shares_short,
                "short_ratio": safe_float_conversion(stats_data.short_ratio),
                "held_percent_insiders": safe_float_conversion(
                    stats_data.held_percent_insiders
                ),
                "held_percent_institutions": safe_float_conversion(
                    stats_data.held_percent_institutions
                ),
            }

            self._upsert_records(
                model=KeyStatistics,
                records=[stats_dict],
                index_elements=["symbol", "date", "data_source"],
            )

            logger.info(f"Successfully loaded key statistics for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to load key statistics for {symbol}: {e}")
            return False

    async def load_institutional_holders(self, symbol: str) -> int:
        """Load institutional holders for a symbol"""
        symbol = self._normalize_symbol(symbol)
        logger.info(f"Loading institutional holders for {symbol} from Yahoo Finance")

        try:
            holders_data = await self.client.get_institutional_holders(symbol)

            if not holders_data:
                logger.warning(f"No institutional holders found for {symbol}")
                return 0

            with db_transaction() as session:
                records = []
                for holder in holders_data:
                    # Mark previous records as not latest
                    update_stmt = (
                        update(InstitutionalHolder)
                        .where(
                            InstitutionalHolder.symbol == symbol,
                            InstitutionalHolder.holder_name == holder.holder_name,
                        )
                        .values(is_latest=False)
                    )
                    session.execute(update_stmt)

                    # Calculate percent_change if not provided
                    percent_change_value = holder.percent_change
                    if percent_change_value is None and holder.percent_held is not None:
                        prev_stmt = (
                            select(InstitutionalHolder.percent_held)
                            .where(
                                InstitutionalHolder.symbol == symbol,
                                InstitutionalHolder.holder_name == holder.holder_name,
                                InstitutionalHolder.date_reported
                                < holder.date_reported,
                            )
                            .order_by(InstitutionalHolder.date_reported.desc())
                            .limit(1)
                        )
                        prev_result = session.execute(prev_stmt).scalar_one_or_none()
                        if prev_result is not None:
                            percent_change_value = (
                                float(holder.percent_held) - float(prev_result)
                            )

                    records.append({
                        "symbol": symbol,
                        "date_reported": holder.date_reported,
                        "holder_name": holder.holder_name,
                        "shares": holder.shares,
                        "value": holder.value,
                        "percent_held": (
                            float(holder.percent_held) if holder.percent_held else None
                        ),
                        "percent_change": (
                            float(percent_change_value)
                            if percent_change_value is not None
                            else None
                        ),
                        "is_latest": True,
                        "data_source": self.data_source,
                    })

                self._upsert_records(
                    model=InstitutionalHolder,
                    records=records,
                    index_elements=["symbol", "holder_name", "date_reported"],
                    update_fields=[
                        "shares", "value", "percent_held",
                        "percent_change", "is_latest"
                    ],
                )

            logger.info(
                f"Successfully loaded {len(holders_data)} "
                f"institutional holders for {symbol}"
            )
            return len(holders_data)

        except Exception as e:
            logger.error(f"Failed to load institutional holders for {symbol}: {e}")
            return 0

    async def load_dividends(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Load dividend history"""
        symbol = self._normalize_symbol(symbol)
        date_range = (
            f" from {start_date} to {end_date}" if start_date and end_date else ""
        )
        logger.info(
            f"Loading dividends for {symbol} from Yahoo Finance{date_range}"
        )

        try:
            dividends_data = await self.client.get_dividends(
                symbol=symbol, start_date=start_date, end_date=end_date
            )

            if not dividends_data:
                logger.info(f"No dividends found for {symbol}")
                return 0

            records = [
                {
                    "symbol": symbol,
                    "ex_date": dividend.ex_date,
                    "amount": dividend.amount,
                    "payment_date": dividend.payment_date,
                    "record_date": dividend.record_date,
                    "dividend_type": dividend.dividend_type,
                    "currency": dividend.currency,
                    "data_source": self.data_source,
                }
                for dividend in dividends_data
            ]

            self._upsert_records(
                model=Dividend,
                records=records,
                index_elements=["symbol", "ex_date", "data_source"],
                update_fields=[
                    "amount", "payment_date", "record_date",
                    "dividend_type", "currency"
                ],
            )

            logger.info(
                f"Successfully loaded {len(dividends_data)} dividends for {symbol}"
            )
            return len(dividends_data)

        except Exception as e:
            logger.error(f"Failed to load dividends for {symbol}: {e}")
            raise YahooAPIError(f"Failed to load dividends for {symbol}: {str(e)}")

    async def load_splits(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Load stock split history"""
        symbol = self._normalize_symbol(symbol)
        date_range = (
            f" from {start_date} to {end_date}" if start_date and end_date else ""
        )
        logger.info(
            f"Loading stock splits for {symbol} from Yahoo Finance{date_range}"
        )

        try:
            splits_data = await self.client.get_splits(
                symbol=symbol, start_date=start_date, end_date=end_date
            )

            if not splits_data:
                logger.info(f"No stock splits found for {symbol}")
                return 0

            records = [
                {
                    "symbol": symbol,
                    "split_date": split.split_date,
                    "split_ratio": split.split_ratio,
                    "ratio_str": split.ratio_str,
                    "data_source": self.data_source,
                }
                for split in splits_data
            ]

            self._upsert_records(
                model=StockSplit,
                records=records,
                index_elements=["symbol", "split_date", "data_source"],
                update_fields=["split_ratio", "ratio_str"],
            )

            logger.info(
                f"Successfully loaded {len(splits_data)} stock splits for {symbol}"
            )
            return len(splits_data)

        except Exception as e:
            logger.error(f"Failed to load stock splits for {symbol}: {e}")
            raise YahooAPIError(f"Failed to load stock splits for {symbol}: {str(e)}")

    async def load_financial_statements(
        self, symbol: str, include_annual: bool = True, include_quarterly: bool = True
    ) -> List[Any]:
        """Load financial statements for a symbol"""
        symbol = self._normalize_symbol(symbol)
        statements = []

        try:
            statement_types = ["income", "balance_sheet", "cash_flow"]
            period_types = []

            if include_annual:
                period_types.append("annual")
            if include_quarterly:
                period_types.append("quarterly")

            for stmt_type in statement_types:
                for period_type in period_types:
                    data = await self.client.get_financial_statements(
                        symbol, stmt_type, period_type
                    )
                    statements.extend(data)

            if not statements:
                logger.info(f"No financial statements found for {symbol}")
                return []

            # Store in database
            records = []
            for stmt_data in statements:
                fiscal_year, fiscal_quarter = self._detect_fiscal_year_quarter(
                    symbol, stmt_data.period_end
                ) if stmt_data.period_end else (None, None)

                stmt = FinancialStatement(
                    symbol=symbol,
                    period_end=stmt_data.period_end,
                    statement_type=stmt_data.statement_type,
                    period_type=stmt_data.period_type,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    data=stmt_data.data,
                )
                stmt.populate_common_metrics()

                records.append({
                    "symbol": stmt.symbol,
                    "period_end": stmt.period_end,
                    "statement_type": stmt.statement_type,
                    "period_type": stmt.period_type,
                    "fiscal_year": stmt.fiscal_year,
                    "fiscal_quarter": stmt.fiscal_quarter,
                    "data": stmt.data,
                    "total_revenue": stmt.total_revenue,
                    "net_income": stmt.net_income,
                    "gross_profit": stmt.gross_profit,
                    "operating_income": stmt.operating_income,
                    "ebitda": stmt.ebitda,
                    "total_assets": stmt.total_assets,
                    "total_liabilities": stmt.total_liabilities,
                    "total_equity": stmt.total_equity,
                    "cash_and_equivalents": stmt.cash_and_equivalents,
                    "total_debt": stmt.total_debt,
                    "operating_cash_flow": stmt.operating_cash_flow,
                    "free_cash_flow": stmt.free_cash_flow,
                    "basic_eps": stmt.basic_eps,
                    "diluted_eps": stmt.diluted_eps,
                    "book_value_per_share": stmt.book_value_per_share,
                    "data_source": "yahoo",
                    "updated_at": stmt.updated_at,
                })

            if records:
                self._upsert_records(
                    model=FinancialStatement,
                    records=records,
                    index_elements=[
                        "symbol", "period_end", "statement_type", "period_type"
                    ],
                )

            logger.info(f"Loaded {len(statements)} financial statements for {symbol}")
            return statements

        except Exception as e:
            logger.error(f"Failed to load financial statements for {symbol}: {e}")
            raise YahooAPIError(
                f"Failed to load financial statements for {symbol}: {str(e)}"
            )

    async def load_company_officers(self, symbol: str) -> List[Any]:
        """Load company officers for a symbol"""
        symbol = self._normalize_symbol(symbol)

        try:
            logger.info(f"Loading company officers for {symbol}")
            officers_data = await self.client.get_company_officers(symbol)

            if not officers_data:
                logger.info(f"No officers data available for {symbol}")
                return []

            records = []
            for officer_data in officers_data:
                if not officer_data.name or not officer_data.name.strip():
                    logger.warning(f"Skipping officer for {symbol}: empty name")
                    continue

                records.append({
                    "symbol": symbol,
                    "name": officer_data.name.strip(),
                    "title": officer_data.title.strip() if officer_data.title else None,
                    "age": officer_data.age,
                    "year_born": officer_data.year_born,
                    "fiscal_year": officer_data.fiscal_year,
                    "total_pay": officer_data.total_pay,
                    "exercised_value": officer_data.exercised_value,
                    "unexercised_value": officer_data.unexercised_value,
                    "data_source": self.data_source,
                })

            if records:
                self._upsert_records(
                    model=CompanyOfficer,
                    records=records,
                    index_elements=["symbol", "name", "title"],
                    update_fields=[
                        "age", "year_born", "fiscal_year", "total_pay",
                        "exercised_value", "unexercised_value"
                    ],
                )

            logger.info(
                f"Successfully loaded {len(records)}/{len(officers_data)} "
                f"company officers for {symbol}"
            )
            return officers_data

        except Exception as e:
            logger.error(f"Failed to load company officers for {symbol}: {e}")
            raise YahooAPIError(
                f"Failed to load company officers for {symbol}: {str(e)}"
            )

    async def load_analyst_recommendations(self, symbol: str) -> int:
        """Load analyst recommendations for a symbol"""
        symbol = self._normalize_symbol(symbol)
        logger.info(
            f"Loading analyst recommendations for {symbol} from Yahoo Finance"
        )

        try:
            recommendations_data = await self.client.get_analyst_recommendations(
                symbol=symbol
            )

            if not recommendations_data:
                logger.info(f"No analyst recommendations found for {symbol}")
                return 0

            records = [
                {
                    "symbol": symbol,
                    "date": rec.date,
                    "period": rec.period,
                    "strong_buy": rec.strong_buy,
                    "buy": rec.buy,
                    "hold": rec.hold,
                    "sell": rec.sell,
                    "strong_sell": rec.strong_sell,
                    "data_source": self.data_source,
                }
                for rec in recommendations_data
            ]

            self._upsert_records(
                model=AnalystRecommendation,
                records=records,
                index_elements=["symbol", "date", "period", "data_source"],
                update_fields=["strong_buy", "buy", "hold", "sell", "strong_sell"],
            )

            logger.info(
                f"Successfully loaded {len(recommendations_data)} "
                f"analyst recommendation records for {symbol}"
            )
            return len(recommendations_data)

        except Exception as e:
            logger.error(f"Failed to load analyst recommendations for {symbol}: {e}")
            raise YahooAPIError(
                f"Failed to load analyst recommendations for {symbol}: {str(e)}"
            )

    async def load_esg_scores(self, symbol: str) -> bool:
        """Load ESG scores for a symbol"""
        symbol = self._normalize_symbol(symbol)
        logger.info(f"Loading ESG scores for {symbol} from Yahoo Finance")

        try:
            esg_data = await self.client.get_esg_scores(symbol=symbol)

            if not esg_data:
                logger.debug(f"No ESG data available for {symbol} from Yahoo Finance")
                return False

            logger.debug(
                f"Fetched ESG data for {symbol}: total_esg={esg_data.total_esg}, "
                f"date={esg_data.date}"
            )

            record = {
                "symbol": symbol,
                "date": esg_data.date,
                "total_esg": esg_data.total_esg,
                "environment_score": esg_data.environment_score,
                "social_score": esg_data.social_score,
                "governance_score": esg_data.governance_score,
                "controversy_level": esg_data.controversy_level,
                "esg_performance": esg_data.esg_performance,
                "peer_group": esg_data.peer_group,
                "peer_count": esg_data.peer_count,
                "percentile": esg_data.percentile,
                "data_source": self.data_source,
            }

            self._upsert_records(
                model=ESGScore,
                records=[record],
                index_elements=["symbol", "date", "data_source"],
            )

            logger.info(f"Successfully loaded ESG scores for {symbol}")
            return True

        except YahooAPIError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to load ESG scores for {symbol}: {e}", exc_info=True
            )
            raise YahooAPIError(f"Failed to load ESG scores for {symbol}: {str(e)}")

    async def load_all_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_fundamentals: bool = False,
        include_key_statistics: bool = False,
        include_institutional_holders: bool = False,
        include_financial_statements: bool = False,
        include_company_officers: bool = False,
        include_dividends: bool = False,
        include_splits: bool = False,
        include_analyst_recommendations: bool = False,
        include_esg_scores: bool = False,
    ) -> Dict[str, int]:
        """Load all available data for a symbol"""
        symbol = self._normalize_symbol(symbol)
        logger.info(f"Loading all data for {symbol} from Yahoo Finance")

        results = {
            "market_data": 0,
            "market_data_adjusted": 0,
            "company_info": 0,
            "key_statistics": 0,
            "institutional_holders": 0,
            "financial_statements": 0,
            "company_officers": 0,
            "dividends": 0,
            "splits": 0,
            "analyst_recommendations": 0,
            "esg_scores": 0,
        }

        try:
            results["market_data"] = await self.load_market_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                auto_adjust=False,
            )
            results["market_data_adjusted"] = await self.load_market_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                auto_adjust=True,
            )

            # Load optional data types
            if include_fundamentals:
                success = await self.load_company_info(symbol)
                results["company_info"] = 1 if success else 0

            if include_key_statistics:
                success = await self.load_key_statistics(symbol)
                results["key_statistics"] = 1 if success else 0

            if include_institutional_holders:
                results["institutional_holders"] = (
                    await self.load_institutional_holders(symbol)
                )

            if include_financial_statements:
                statements = await self.load_financial_statements(symbol)
                results["financial_statements"] = len(statements)

            if include_company_officers:
                officers = await self.load_company_officers(symbol)
                results["company_officers"] = len(officers)

            if include_dividends:
                results["dividends"] = await self.load_dividends(
                    symbol, start_date, end_date
                )

            if include_splits:
                results["splits"] = await self.load_splits(
                    symbol, start_date, end_date
                )

            if include_analyst_recommendations:
                results["analyst_recommendations"] = (
                    await self.load_analyst_recommendations(symbol)
                )

            if include_esg_scores:
                success = await self.load_esg_scores(symbol)
                results["esg_scores"] = 1 if success else 0

            logger.info(f"Completed loading all data for {symbol}: {results}")
            return results

        except Exception as e:
            logger.error(f"Failed to load all data for {symbol}: {e}")
            raise

    async def load_all_symbols_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        interval: str = "1h",
        max_symbols: Optional[int] = None,
        include_fundamentals: bool = False,
        include_key_statistics: bool = False,
        include_institutional_holders: bool = False,
        include_financial_statements: bool = False,
        include_company_officers: bool = False,
        include_dividends: bool = False,
        include_splits: bool = False,
        include_analyst_recommendations: bool = False,
        include_esg_scores: bool = False,
    ) -> Dict[str, Any]:
        """Load market data for all active symbols"""
        logger.info("Loading data for all active symbols from Yahoo Finance")

        symbols = await self._get_active_symbols()
        if max_symbols:
            symbols = symbols[:max_symbols]

        logger.info(f"Processing {len(symbols)} symbols")

        stats: Dict[str, Any] = {
            "total_symbols": len(symbols),
            "successful": 0,
            "failed": 0,
            "total_records": 0,
            "errors": [],
        }

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"Processing symbol {i}/{len(symbols)}: {symbol}")

            try:
                records_count = await self.load_market_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    auto_adjust=False,
                )
                stats["total_records"] += records_count
                records_count_adj = await self.load_market_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    auto_adjust=True,
                )
                stats["total_records"] += records_count_adj

                # Load optional data types
                if include_fundamentals:
                    await self.load_company_info(symbol)
                if include_key_statistics:
                    await self.load_key_statistics(symbol)
                if include_institutional_holders:
                    await self.load_institutional_holders(symbol)
                if include_financial_statements:
                    await self.load_financial_statements(symbol)
                if include_company_officers:
                    await self.load_company_officers(symbol)
                if include_dividends:
                    await self.load_dividends(symbol, start_date, end_date)
                if include_splits:
                    await self.load_splits(symbol, start_date, end_date)
                if include_analyst_recommendations:
                    await self.load_analyst_recommendations(symbol)
                if include_esg_scores:
                    await self.load_esg_scores(symbol)

                stats["successful"] += 1
                await self._update_symbol_status(symbol, "success")

                if i < len(symbols):
                    await asyncio.sleep(self.delay_between_requests)

            except Exception as e:
                stats["failed"] += 1
                error_msg = f"Symbol {symbol}: {str(e)}"
                stats["errors"].append(error_msg)
                logger.error(error_msg)
                await self._update_symbol_status(symbol, "failed", error_msg)
                continue

        logger.info(f"Completed loading data. Stats: {stats}")
        return stats

    async def get_all_symbols(self) -> List[str]:
        """Get list of all symbols from database"""
        return await self._get_active_symbols()

    async def _get_active_symbols(self) -> List[str]:
        """Get list of active symbols from database, sorted alphabetically."""
        with db_transaction() as session:
            stmt = (
                select(Symbol.symbol)
                .where(Symbol.status == "active")
                .order_by(Symbol.symbol)
            )
            result = session.execute(stmt)
            return [row[0] for row in result.fetchall()]

    async def health_check(self) -> bool:
        """Check if Yahoo Finance is accessible"""
        try:
            result = await self.client.health_check()
            return result.healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def _detect_fiscal_year_quarter(
        self, symbol: str, period_end: date
    ) -> tuple[int, int]:
        """
        Detect fiscal year and quarter for a given symbol and period_end date.

        Args:
            symbol: Stock symbol
            period_end: Period end date

        Returns:
            Tuple of (fiscal_year, fiscal_quarter)
        """
        month = period_end.month
        year = period_end.year

        # Get fiscal year end month (default to December)
        fiscal_year_end_month = FISCAL_YEAR_END_MONTHS.get(symbol, 12)

        # Calculate fiscal year and quarter
        if month == fiscal_year_end_month:
            fiscal_quarter = 4
            fiscal_year = year
        else:
            months_since_fye = (month - fiscal_year_end_month) % 12

            if months_since_fye in [1, 2, 3]:
                fiscal_quarter = 1
            elif months_since_fye in [4, 5, 6]:
                fiscal_quarter = 2
            elif months_since_fye in [7, 8, 9]:
                fiscal_quarter = 3
            else:
                fiscal_quarter = 4

            fiscal_year = year + 1 if month > fiscal_year_end_month else year

        return fiscal_year, fiscal_quarter

"""
Basket trading ORMs (Johansen multi-asset cointegration).

Kept in a dedicated module so BasketRegistry is importable without loading
the full pairs strategy_models graph (avoids circular / partial imports).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base


class BasketRegistry(Base):
    """
    Validated N-stock basket definitions discovered via Johansen cointegration.

    Populated by scripts/discover_baskets.py.
    hedge_weights is the Johansen cointegrating vector, normalized so weights[0]=1.
    """

    __tablename__ = "basket_registry"
    __table_args__ = (
        Index("idx_basket_registry_active", "is_active"),
        Index("idx_basket_registry_sector", "sector"),
        {"schema": "strategy_engine"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    symbols: Mapped[dict] = mapped_column(JSON, nullable=False)
    hedge_weights: Mapped[dict] = mapped_column(JSON, nullable=False)

    half_life_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    coint_pvalue: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    min_correlation: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    z_score_window: Mapped[int] = mapped_column(Integer, nullable=False)
    z_score_abs_mean: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    rank_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))

    entry_threshold: Mapped[float] = mapped_column(
        Numeric(5, 2), default=2.0, nullable=False
    )
    exit_threshold: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.5, nullable=False
    )
    stop_loss_threshold: Mapped[float] = mapped_column(
        Numeric(5, 2), default=3.0, nullable=False
    )
    max_hold_hours: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    max_allocation_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_validated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    spreads: Mapped[list["BasketSpread"]] = relationship(
        "BasketSpread", back_populates="basket", cascade="all, delete-orphan"
    )
    trades: Mapped[list["BasketTrade"]] = relationship(
        "BasketTrade", back_populates="basket", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<BasketRegistry(id={self.id}, name={self.name}, "
            f"active={self.is_active}, half_life={self.half_life_hours}h)>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sector": self.sector,
            "symbols": self.symbols,
            "hedge_weights": self.hedge_weights,
            "half_life_hours": float(self.half_life_hours),
            "coint_pvalue": float(self.coint_pvalue),
            "min_correlation": float(self.min_correlation),
            "z_score_window": self.z_score_window,
            "z_score_abs_mean": (
                float(self.z_score_abs_mean) if self.z_score_abs_mean else None
            ),
            "rank_score": float(self.rank_score) if self.rank_score else None,
            "entry_threshold": float(self.entry_threshold),
            "exit_threshold": float(self.exit_threshold),
            "stop_loss_threshold": float(self.stop_loss_threshold),
            "max_hold_hours": (
                float(self.max_hold_hours) if self.max_hold_hours else None
            ),
            "max_allocation_pct": (
                float(self.max_allocation_pct) if self.max_allocation_pct else None
            ),
            "is_active": self.is_active,
            "last_validated": (
                self.last_validated.isoformat() if self.last_validated else None
            ),
            "notes": self.notes,
        }


class BasketSpread(Base):
    """Hourly spread and z-score time series for each basket."""

    __tablename__ = "basket_spread"
    __table_args__ = (
        Index("idx_basket_spread_basket_timestamp", "basket_id", "timestamp"),
        Index("idx_basket_spread_timestamp", "timestamp"),
        {"schema": "strategy_engine"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    basket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("strategy_engine.basket_registry.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    prices: Mapped[Optional[dict]] = mapped_column(JSON)
    spread: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    z_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    hedge_weights: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
    )

    basket: Mapped["BasketRegistry"] = relationship(
        "BasketRegistry", back_populates="spreads"
    )

    def __repr__(self) -> str:
        return (
            f"<BasketSpread(basket_id={self.basket_id}, ts={self.timestamp}, "
            f"z={self.z_score})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "basket_id": self.basket_id,
            "timestamp": self.timestamp.isoformat(),
            "prices": self.prices,
            "spread": float(self.spread) if self.spread is not None else None,
            "z_score": float(self.z_score) if self.z_score is not None else None,
            "hedge_weights": self.hedge_weights,
        }


class BasketTrade(Base):
    """
    Open and closed basket trades.

    legs JSON: [{"symbol": "EWBC", "qty": 100, "entry_price": 32.1, "order_id": "abc"}, ...]
    exit_legs JSON: [{"symbol": "EWBC", "exit_price": 33.0, "order_id": "xyz"}, ...]
    """

    __tablename__ = "basket_trade"
    __table_args__ = (
        Index("idx_basket_trade_basket_status", "basket_id", "status"),
        Index("idx_basket_trade_entry_time", "entry_time"),
        {"schema": "strategy_engine"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    basket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("strategy_engine.basket_registry.id", ondelete="CASCADE"),
        nullable=False,
    )

    entry_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    entry_z_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    side: Mapped[str] = mapped_column(String(20), nullable=False)
    legs: Mapped[dict] = mapped_column(JSON, nullable=False)

    exit_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    exit_z_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    exit_reason: Mapped[Optional[str]] = mapped_column(String(50))
    exit_legs: Mapped[Optional[dict]] = mapped_column(JSON)

    pnl: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    pnl_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(String(10), default="OPEN", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    basket: Mapped["BasketRegistry"] = relationship(
        "BasketRegistry", back_populates="trades"
    )

    def __repr__(self) -> str:
        return (
            f"<BasketTrade(id={self.id}, basket_id={self.basket_id}, "
            f"side={self.side}, status={self.status}, pnl={self.pnl})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "basket_id": self.basket_id,
            "entry_time": self.entry_time.isoformat(),
            "entry_z_score": (
                float(self.entry_z_score) if self.entry_z_score is not None else None
            ),
            "side": self.side,
            "legs": self.legs,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_z_score": (
                float(self.exit_z_score) if self.exit_z_score is not None else None
            ),
            "exit_reason": self.exit_reason,
            "exit_legs": self.exit_legs,
            "pnl": float(self.pnl) if self.pnl is not None else None,
            "pnl_pct": float(self.pnl_pct) if self.pnl_pct is not None else None,
            "status": self.status,
        }


__all__ = [
    "BasketRegistry",
    "BasketSpread",
    "BasketTrade",
]

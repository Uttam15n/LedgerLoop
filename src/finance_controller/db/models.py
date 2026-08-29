"""
SQLAlchemy ORM models — the three source tables that get staged in SQLite.

These classes are the Python-side mirror of the schemas defined in
config/settings.py. Keeping them as real ORM classes (not raw SQL strings
scattered around) means:
  - typos in column names fail at import time, not at query time
  - later phases (matcher, repository, agents) get autocomplete + type hints
  - swapping SQLite for Postgres later is a one-line change in session.py,
    nothing here needs to change

NOTE: this file defines DATABASE structure only. No LangGraph, no LangChain,
no LLM calls happen anywhere in db/ — that's reserved for agents/ (Phase 3).
"""

from datetime import datetime

from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared base class all tables inherit from."""
    pass


class Invoice(Base):
    """What was billed to a customer."""
    __tablename__ = "invoice"

    invoice_id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "open" | "paid" | "overdue"

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} {self.amount} {self.currency}>"


class Payment(Base):
    """A UPI payment event — should settle against an invoice."""
    __tablename__ = "payment"

    payment_id: Mapped[str] = mapped_column(String, primary_key=True)
    utr: Mapped[str] = mapped_column(String, nullable=False)              # UPI transaction reference
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payer_vpa: Mapped[str] = mapped_column(String, nullable=False)        # UPI virtual payment address
    invoice_reference: Mapped[str] = mapped_column(String, nullable=True)  # should match invoice.invoice_number
    # nullable=True is deliberate: a missing/blank invoice_reference is one
    # of our real-world exception cases, not a data error to reject at load time.

    def __repr__(self) -> str:
        return f"<Payment utr={self.utr} {self.amount} -> invoice_ref={self.invoice_reference}>"


class BankTransaction(Base):
    """What actually hit the bank statement."""
    __tablename__ = "bank_transaction"

    bank_txn_id: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    utr_reference: Mapped[str] = mapped_column(String, nullable=True)     # should match payment.utr, often truncated
    description: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<BankTransaction {self.bank_txn_id} {self.amount} utr_ref={self.utr_reference}>"


# Convenience lookup so other modules (repository.py, matcher) can go from
# a schema name (e.g. "invoice") straight to the matching ORM class,
# instead of hardcoding if/elif chains.
TABLE_MODELS = {
    "invoice": Invoice,
    "payment": Payment,
    "bank_transaction": BankTransaction,
}
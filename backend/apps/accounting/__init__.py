"""Central double-entry accounting engine (ADR-004).

Trade remains the operational source of truth; this app turns trade documents
(and standalone documents: expenses, payments, loans, bank lines) into
balanced, immutable vouchers. Every balance and report is a ledger query.
Licence CIF utilisation is never read or written here.
"""

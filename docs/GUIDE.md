# Nivesa · Guide

What each page shows, how the ledger is stored, and how to configure, back up and migrate it.
The [README](../README.md) is the overview; this is the detail.

## What You See

Nivesa wears the **Graphite** design system of the Tattva / Nishkarsh terminals, ported exactly:
Paper (light, default) and Slate (dark) appearances, Inter for prose and JetBrains Mono for every
number, colour that always carries a meaning (green income and gains, red losses, amber caution,
cobalt the system's voice), flat hairline panels, and one component per job. Nothing is collapsed
into a drop-down: messages and caveats appear in the notice rail under the command bar.

**The shell, on every page:** a tape of the next projected coupon and principal payments → the
command bar (the book, its cost, weighted yield to cost, duration, positions, as-of, and a chip:
CURRENT, or how many bonds have matured without their redemption recorded) → the notice rail
(form results, positions maturing within 30 days, matured-but-unredeemed bonds) → the page.
**The rail** holds the pages and the controls: Session (Refresh) → Appearance, pinned to the
rail's foot. The book itself is on every page's command bar.

| Section | Page | What it answers |
|---|---|---|
| — | **Overview** | What do we hold, and what does it earn? Cost, yield, coupon income, duration and composition; capital allocation by account; where the book sits by maturity. |
| Analytics | **Positions** | What exactly do we hold? Every position, with export. |
| | **Cashflows** | What comes in, and when? Future coupons and principal, month by month (the window looks forward), and every payment in the next twelve months. |
| | **Maturity** | When does capital come back? The maturity ladder and every bond in it. |
| | **Issuers** | Where is the book concentrated? Issuer weights (amber at 5% of cost, red at 10%) and issuer detail. |
| Operations | **Record Transaction** | Buy, Sell, Interest Receipt, Principal Repayment. |
| | **Ledger** | The audit trail, filtered and windowed, with CSV and Excel export. |
| | **Securities** | The securities master, with export. |
| | **Add Security** · **Edit Security** · **Edit Transaction** | Maintain the master and correct the ledger. |
| | **Audit Trail** | Who changed what? Every add, edit and delete, newest first, with CSV export. |

Account filters sit in a strip directly above the table or chart they filter.

## Database Schema

Nivesa uses SQLite with three book tables and the audit trail:

### `securities` — Bond Master
| Column | Type | Description |
|--------|------|-------------|
| bond_id | TEXT PK | UUID |
| issuer | TEXT | Issuer name |
| isin | TEXT UNIQUE | ISIN code |
| maturity_date | TEXT | ISO date |
| frequency | TEXT | Monthly/Quarterly/Semi-Annual/Annual |
| coupon_rate | REAL | Decimal (0.10 = 10%) |
| face_value | REAL | Per unit |

### `transactions` — Immutable Ledger
| Column | Type | Description |
|--------|------|-------------|
| transaction_id | TEXT PK | UUID |
| bond_id | TEXT FK | References securities |
| account | TEXT | Account name |
| trade_date | TEXT | ISO date |
| transaction_type | TEXT | Buy/Sell/Interest_Receipt/Principal_Repayment |
| units | REAL | Positive=buy, negative=sell |
| price | REAL | Per unit |
| amount | REAL | Total cash amount |
| notes | TEXT | Optional |

### `security_metadata` — Extended Attributes
| Column | Type | Description |
|--------|------|-------------|
| bond_id | TEXT PK/FK | References securities |
| bond_type | TEXT | NCD/Corporate/Government/SDL/etc. |
| credit_rating | TEXT | AAA through D, or Unrated |
| day_count | TEXT | 30/360, Actual/365, etc. |
| sector | TEXT | Financials, Infrastructure, etc. |
| listing | TEXT | Unlisted/NSE/BSE/Both |

### `audit_log` — Append-only Change Record
Written by triggers on the three tables above; UPDATE and DELETE on it are refused.

| Column | Type | Description |
|--------|------|-------------|
| audit_id | INTEGER PK | Increasing |
| changed_at | TEXT | UTC, ISO 8601 |
| table_name | TEXT | securities / transactions / security_metadata |
| action | TEXT | INSERT / UPDATE / DELETE |
| row_id | TEXT | bond_id or transaction_id |
| old_row · new_row | TEXT | The row before and after, as JSON |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NIVESA_DATA_DIR` | `data` | Base directory for database and logs |
| `NIVESA_PASSWORD` | *(unset)* | Sign-in password; or `[auth] password` in Streamlit secrets. Unset = open |

### Streamlit Config

Server settings and the Paper / Slate theme blocks are in `.streamlit/config.toml`; the in-app appearance switch lives at the foot of the rail.

## Backup and Recovery

### Manual Backup
```bash
cp data/db/portfolio.db data/db/portfolio_backup_$(date +%Y%m%d).db
```

## Migration from Nivesh v1

Nivesa v2 is fully backward-compatible with the original `portfolio.db`. On first run, it:
1. Detects existing `securities` and `transactions` tables
2. Creates the new `security_metadata` table
3. Auto-populates metadata rows for all existing securities (default: NCD, Unrated)
4. No data loss — your existing transactions and securities are preserved

Run `streamlit run app.py` against your existing `portfolio.db`.

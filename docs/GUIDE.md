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
| | **Add Security** · **Edit Security** · **Edit Transaction** | Maintain the master and correct the ledger. Both security forms take the bond's **repayment schedule**. |
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

### `redemption_schedule` — Contractual Principal Instalments
One row per instalment a bond is due to pay, from its offer document or the platform it was bought on.
Entered with the bond on **Add Security**, or later on **Edit Security**: lines of `date, ₹ per bond`, or N
equal instalments. Leave it empty for a bond that repays its whole face at maturity. The instalments
still to come may not add up to more than the bond's current face (any rest is repaid at maturity), so a
bond added part-way through its life takes its whole schedule, the instalments already behind it
included.

| Column | Type | Description |
|--------|------|-------------|
| schedule_id | INTEGER PK | Increasing |
| bond_id | TEXT FK | References securities |
| due_date | TEXT | ISO date (unique per bond) |
| principal_per_unit | REAL | Rupees per bond, against the face at issue |
| source | TEXT | Where the schedule came from |

With a schedule, the bond's projected principal, yield to cost and duration follow it; without one, the
principal is projected at maturity (or on the pattern of repayments already recorded). An instalment
whose date has passed with no repayment recorded (within 20 days) for an account that held the bond
then is shown in the notice rail and on **Record Transaction**, where one button records them all —
each through the same face step-down and balance check as the form.

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
| `NIVESA_STORE_REPO` · `NIVESA_STORE_TOKEN` | *(unset)* | The private store; or `[storage] github_repo` / `github_token` in secrets |
| `NIVESA_STORE_PATH` · `NIVESA_STORE_BRANCH` | `portfolio.db` · default branch | Optional: where in that repository |

### Streamlit Config

Server settings and the Paper / Slate theme blocks are in `.streamlit/config.toml`; the in-app appearance switch lives at the foot of the rail.

## Backup and Recovery

**Hosted with `[storage]`** (see the README, *Keeping the ledger*): every change is a commit in the
private repository, so its history is the backup. To restore, open `portfolio.db`'s history there,
revert to the state you want (or upload that version), then reboot the app.

**Local only:**
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

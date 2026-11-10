<div align="center">

# NIVESA (निवेसा)

### Bond Portfolio Ledger

**Institutional-grade fixed income portfolio management**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.52.2_(pinned)-2B5FD9?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-Proprietary-2B5FD9)](#license)
[![Version](https://img.shields.io/badge/Version-3.0.2-2B5FD9)](#)
[CHANGELOG](CHANGELOG.md) &nbsp;|&nbsp; Last Updated: 2026-11


*A Hemrek Capital Product*

---

</div>

## Overview

Nivesa is a bond portfolio ledger for tracking fixed income investments across the family's
accounts. It keeps one ledger of every bond and reads it as a book: what it cost, what it yields
to cost, what it pays and when, and when the capital comes back — with duration, maturity
profiling and issuer concentration.

## What you see

Nivesa wears the **Graphite** design system of the Tattva / Nishkarsh terminals, ported exactly:
Paper (light, default) and Slate (dark) appearances, Inter for prose and JetBrains Mono for every
number, colour that always carries a meaning (green income and gains, red losses, amber caution,
cobalt the system's voice), flat hairline panels, and one component per job. Nothing is collapsed
into a drop-down: messages and caveats appear in the notice rail under the command bar.

**The shell, on every page:** a tape of the next projected coupon and principal payments → the
command bar (the book, its cost, weighted yield to cost, duration, positions, as-of, and a chip:
CURRENT, or how many bonds have matured without their redemption recorded) → the notice rail
(form results, positions maturing within 30 days, matured-but-unredeemed bonds) → the page.
**The rail:** Book (a read-only readout: securities, transactions, accounts, last entry, database,
version) → Session (Refresh) → Appearance.

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

Account filters sit in a strip directly above the table or chart they filter.

## Features

### Portfolio intelligence
- **Yield analytics** — coupon, and yield to cost (IRR on the dirty price, nominal at the coupon frequency)
- **Duration engine** — Macaulay and modified duration per position and cost-weighted for the book, amortization-aware
- **Concentration risk** — issuer weights with caution / danger thresholds

### Cashflow & maturity
- **Cashflow projections** — monthly coupon and principal flows, amortizing bonds on their inferred cadence
- **Maturity ladder** — positions bucketed across seven horizons, plus matured
- **Nearterm schedule** — every payment in the next twelve months

### Operations
- **Securities master** — type, rating, sector, listing, day count
- **Transaction ledger** — the audit trail with filterable views and export
- **Principal repayment** — face value steps down once per bond and date, pro rata across accounts

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Streamlit is pinned to **exactly 1.52.2**: the design
system styles Streamlit's internal page structure, measured on that version — develop and deploy on
it.

## Project structure

```
nivesa/
├── app.py                 # Shell: appearance, rail, navigation, page shell, footer
├── core/                  # The ledger — unchanged logic from 2.8.0
│   ├── config.py          #   constants (accounts, frequencies, types, ratings, version)
│   ├── db.py              #   SQLite layer, migrations, chronology and face-adjustment checks
│   ├── bonds.py           #   accrued interest, duration, yield to cost, schedules
│   ├── book.py            #   positions engine, ledger frame
│   ├── formatting.py      #   ₹ formatting (Indian grouping), percentages
│   └── views.py           #   the page aggregates and the shell's figures (pure)
├── ui/                    # Graphite design system + one module per page
│   ├── theme.css · theme.py · palette.py · components.py · notices.py · book.py
│   └── pages/             #   page_overview … page_edit_transaction
├── tests/                 # golden book, source identity, write paths, pages, app
├── data/
│   ├── db/portfolio.db    # SQLite database (auto-created)
│   └── logs/nivesa.log    # Application log (auto-created)
├── requirements.txt
└── .streamlit/config.toml # server settings + the Paper/Slate theme blocks
```

## Testing

```bash
pip install pytest
python -m pytest -q
```

The suite runs offline on temporary copies of `data/` and never touches the live database:
- **Golden book** — every number the 2.8.0 app displayed, captured from the original code with
  the date frozen, reproduced exactly by the refactored code (skips with a re-capture command if
  the database changes).
- **Source identity** — every function moved out of the original `app.py` is byte-identical.
- **Write paths** — every form operation (and its rejections) run through the original 2.8.0 app
  and the new one on separate copies of the database; the resulting tables must match row for row.
- **Pages and app** — every page renders with no `nan`/`None` text and none of the retired widgets.

## Database Schema

Nivesa uses SQLite with three tables:

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

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NIVESA_DATA_DIR` | `data` | Base directory for database and logs |

### Streamlit Config

Server settings and the Paper / Slate theme blocks are in `.streamlit/config.toml`; the in-app appearance switch lives at the foot of the rail.

## Backup & Recovery

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

## Product Family

Nivesa is part of the **Hemrek Capital** product suite:

| Product | Purpose |
|---------|---------|
| **Swing** (स्विंग) | ETF portfolio tracker with real-time analytics |
| **Nivesa** (निवेसा) | Bond portfolio ledger with cashflow intelligence |

Nivesa shares the Graphite design system of the Tattva and Nishkarsh terminals: Paper and Slate appearances, Inter and JetBrains Mono, semantic colour, flat panels.

## License

Copyright © 2025 Hemrek Capital. All rights reserved.

This software is proprietary. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without written permission from Hemrek Capital.

## Support

For issues, feature requests, or support:
- Open an issue on GitHub
- Contact the development team

---

<div align="center">
<sub>Built with ☕ by Hemrek Capital</sub>
</div>

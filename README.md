<div align="center">

# NIVESA (निवेसा)

### Bond Portfolio Ledger

**Institutional-grade fixed income portfolio management**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-Proprietary-FFC300)](#license)
[![Version](https://img.shields.io/badge/Version-2.0.0-FFC300)](#)

*A Hemrek Capital Product*

---

</div>

## Overview

Nivesa is a comprehensive bond portfolio management system built for tracking fixed income investments across multiple accounts. It provides institutional-grade analytics including duration calculations, cashflow projections, maturity profiling, and concentration risk monitoring — all within a sleek, dark-themed interface from the Hemrek Capital product family.

## Features

### Portfolio Intelligence
- **10 dashboard metrics** — cost basis, face value, weighted yields, duration, P&L, accrued interest
- **Yield analytics** — nominal yield, yield-to-cost (YTC) with IRR-based computation
- **Duration engine** — Macaulay & modified duration per position and weighted portfolio-level
- **Concentration risk** — issuer weight bars with traffic-light thresholds

### Cashflow & Maturity
- **Cashflow projections** — monthly stacked bar chart of future coupon + principal flows
- **Maturity ladder** — positions bucketed across 7 time horizons (0-3M through 5Y+)
- **Upcoming schedule** — next 12 months of cashflows in detail

### Risk Analytics
- **Credit quality distribution** — visual breakdown by rating (AAA → D)
- **Yield vs Duration scatter** — bubble chart sized by position weight
- **Multi-account tracking** — REKHA, HEMANG, MANTHAN, HIMA

### Operations
- **Securities master** — full bond registry with type, rating, sector, day count
- **Transaction ledger** — immutable audit trail with filterable views
- **Principal repayment** — automatic face value adjustment
- **CSV export** — positions and ledger data

### Design
- **Hemrek Capital Design System** — consistent with Swing portfolio tracker
- **Dark theme** — `#0F0F0F` background, `#FFC300` gold accents
- **Responsive** — works on desktop and tablet
- **Inter font** — professional typography

## Quick Start

### Option 1: Local Python

```bash
# Clone the repository
git clone https://github.com/hemrek-capital/nivesa.git
cd nivesa

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run nivesa.py
```

The app will open at `http://localhost:8501`

### Option 2: Docker

```bash
# Build and run
docker compose up -d

# Or build manually
docker build -t nivesa .
docker run -p 8501:8501 -v nivesa_data:/app/data nivesa
```

### Option 3: Streamlit Community Cloud

1. Fork this repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy from your fork, pointing to `nivesa.py`

## Project Structure

```
nivesa/
├── nivesa.py              # Main application (single-file architecture)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container build
├── docker-compose.yml     # Orchestration
├── .streamlit/
│   └── config.toml        # Streamlit theme & server config
├── data/
│   ├── db/
│   │   └── portfolio.db   # SQLite database (auto-created)
│   └── logs/
│       └── nivesa.log     # Application logs (auto-created)
├── scripts/
│   └── backup.sh          # Database backup script
├── assets/                # Static assets (if needed)
├── .gitignore
├── LICENSE
└── README.md
```

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

Theme and server settings are in `.streamlit/config.toml`. The gold-on-black theme matches the Hemrek Capital design system used across Swing and Nivesa.

## Backup & Recovery

### Manual Backup
```bash
cp data/db/portfolio.db data/db/portfolio_backup_$(date +%Y%m%d).db
```

### Automated Backup
```bash
chmod +x scripts/backup.sh
# Add to crontab for daily backups:
# 0 2 * * * /path/to/nivesa/scripts/backup.sh
```

## Migration from Nivesh v1

Nivesa v2 is fully backward-compatible with the original `portfolio.db`. On first run, it:
1. Detects existing `securities` and `transactions` tables
2. Creates the new `security_metadata` table
3. Auto-populates metadata rows for all existing securities (default: NCD, Unrated)
4. No data loss — your existing transactions and securities are preserved

Simply replace your old `nivesh.py` with `nivesa.py` and run.

## Product Family

Nivesa is part of the **Hemrek Capital** product suite:

| Product | Purpose |
|---------|---------|
| **Swing** (स्विंग) | ETF portfolio tracker with real-time analytics |
| **Nivesa** (निवेसा) | Bond portfolio ledger with cashflow intelligence |

All products share the same design system: dark theme, gold accents, Inter typography, premium card layouts.

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

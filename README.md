<div align="center">

# NIVESA

**निवेसा**

Bond Portfolio Ledger · Yield to Cost · Cashflows · Duration

[![Version](https://img.shields.io/badge/version-3.0.23-2B5FD9)](CHANGELOG.md) [![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](requirements.txt) [![Streamlit](https://img.shields.io/badge/streamlit-1.52.2-FF4B4B)](requirements.txt) [![License](https://img.shields.io/badge/license-proprietary-6B7280)](LICENSE) [![Pragyam Family](https://img.shields.io/badge/pragyam-family-0F1217)](#the-pragyam-family)

</div>

> Nivesa keeps one ledger of every bond across the family's accounts, and reads it as a book:
> what it costs, what it yields, what it pays and when it comes back.

## Overview

Nivesa is a bond portfolio ledger for tracking fixed income investments across the family's
accounts. It keeps one ledger of every bond and reads it as a book: what it cost, what it yields
to cost, what it pays and when, and when the capital comes back — with duration, maturity
profiling and issuer concentration.

## What It Does

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

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Streamlit is pinned to **exactly 1.52.2**: the design
system styles Streamlit's internal page structure, measured on that version — develop and deploy on
it.

The app opens on an empty book: add a security under **Operations**, then record its purchase.
Set `NIVESA_DATA_DIR` to keep the database somewhere other than `data/`.

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

## Project Structure

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

## Documentation

| Document | What it covers |
|---|---|
| [Guide](docs/GUIDE.md) | Each page, the database schema, configuration, backup, and migrating from Nivesh v1 |
| [Changelog](CHANGELOG.md) | Every release, newest first |

## The Pragyam Family

Nine Streamlit applications built on one design system and one set of components, so a
panel, a table, a chart or a number reads the same in each.

| Product | What it is |
|---|---|
| [**Tattva**](https://github.com/thebullishvalue/Tattva) | Cross-asset fair value, with a call only where its own record supports one |
| [**Nishkarsh**](https://github.com/thebullishvalue/Nishkarsh) | Nifty 50 inference: a top-down forecast and bottom-up breadth, read as one |
| [**Arthagati**](https://github.com/thebullishvalue/Arthagati) | Valuation-anchored market sentiment, tested on data it never saw |
| [**Pragyam**](https://github.com/thebullishvalue/Pragyam) | Portfolio curation that spreads risk rather than predicting returns |
| [**Sanket**](https://github.com/thebullishvalue/Sanket) | A market signal screener: what fired, what is about to, and whether it has paid |
| [**Vaaydo**](https://github.com/thebullishvalue/Vaaydo) | An F&O trade screener on option positioning, with futures tickets |
| **Nivesa** · *this repository* | A bond portfolio ledger: cost, yield, duration and cashflows across accounts |
| [**Samhita**](https://github.com/thebullishvalue/Samhita) | A portfolio tracker: live prices, performance and risk against the benchmark |
| [**Swing**](https://github.com/thebullishvalue/Swing) | A portfolio tracker for the swing book, on the same engine as Samhita |

## License

Proprietary. © 2025–2026 @thebullishvalue. All rights reserved. The source is visible here
for reference only: viewing it grants no right to use, copy, modify or distribute it.
See [LICENSE](LICENSE).

## Disclaimer

Nivesa is a research and decision-support tool, not investment advice. Nothing it shows is
a recommendation to buy or sell any security, and past or measured results do not guarantee
future ones. Every decision made with it is your own.

---

<div align="center"><sub>© 2025–2026 @thebullishvalue · Part of the Pragyam product family</sub></div>

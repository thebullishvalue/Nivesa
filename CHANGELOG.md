# Changelog

All notable changes to Nivesa are documented here.

## [2.0.0] — 2025-07

### Added
- **Rebranded** from Nivesh to Nivesa (निवेसा)
- **Hemrek Capital Design System** — full Swing-family visual parity
- **Duration Engine** — Macaulay & modified duration per position and portfolio
- **Cashflow Intelligence** — projected monthly cashflows with stacked bar chart
- **Maturity Ladder** — 7-bucket maturity profiling (0-3M through 5Y+)
- **Concentration Risk** — issuer weight bars with traffic-light thresholds
- **Credit Quality Distribution** — bar chart by rating with color spectrum
- **Yield vs Duration Scatter** — bubble chart sized by position weight
- **Accrued Interest** — portfolio-wide estimated unreceived interest
- **Securities Master** — full read-only registry view
- **Extended Metadata** — bond type, credit rating, sector, listing, day count
- **Filterable Ledger** — filter by account, type, search by issuer
- **CSV Export** — positions and transaction ledger
- **Docker Support** — Dockerfile + docker-compose for containerized deployment
- **Backup Script** — automated database backup with retention policy
- **Collapsed Sidebar** — Swing-style navigation with gold-accented toggle
- **Auto-migration** — seamless upgrade from v1 database

### Changed
- Sidebar redesigned as radio navigation (from selectbox)
- All metric cards now have hover animations and gold glow
- Tables use consistent uppercase gold headers
- Buttons use gold outline with hover glow effect
- Navigation uses emoji prefixes for clarity

### Removed
- Market data / price update page (was already disabled)
- Old blue/navy color scheme

## [1.0.0] — 2025-01

### Initial Release
- Bond portfolio ledger with SQLite backend
- Buy/Sell/Interest/Principal transaction types
- Dashboard with 5 summary metrics
- YTC calculation using numpy-financial
- Account and issuer breakdown tables
- Edit security and transaction pages

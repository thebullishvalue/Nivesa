# Changelog

All notable changes to Nivesa are documented here.

## [2.8.0] — 2026-08

### Fixed
- **Yield compounding basis** — position YTC was returned as an effective annual rate while every other yield (coupon, `calc_yield_to_cost`) is nominal, compounded at the coupon frequency. The two were shown side by side and averaged together. On a monthly-pay book this overstated YTC by 50–92bps and made 32 of 36 premium-bought positions appear to yield *more* than their coupon, which is impossible. `_xirr` now takes the compounding frequency.
- **Phantom stub coupon** — the coupon grid is anchored at maturity, so the first projected coupon could fall a day after purchase and still pay a full period. Yields now solve against the dirty price (cost + accrued), the market-standard treatment. Worth up to 72bps on one position.
- **Duration ignored amortization** — `calc_macaulay_duration` always assumed a bullet, so a bond repaying principal was discounted as if the whole balance sat at maturity. One position measured 1.50y against a true 0.33y (+357%); another +40%. Duration, the today-anchored yield and the Cashflow tab now share one projected stream per position.
- **Interest receipts double-counted** — a recorded `Interest_Receipt` was booked as an inflow *and* re-projected as a future coupon, inflating YTC by +703bps on a 4y annual payer with two receipts on file. Projection now starts after the last recorded receipt.
- **Realized P&L on amortizing bonds** — principal repayments did not reduce the cost basis, so selling a half-amortized bond at fair value booked a phantom loss equal to the principal already returned. Repayments now reduce basis as received; capital returned beyond basis is a realized gain.
- **Matured bonds projected future cashflows** — `generate_amortizing_schedule` emitted the residual redemption at a past-dated maturity, adding phantom principal to "Principal Due" and to the cashflow chart. Matured positions now also get their own maturity-ladder bucket instead of showing as live 0-3M holdings.
- **Pro-rata redemption across accounts** — `face_value` steps down once per (bond, date) group, but the repayment cap checked later accounts against the already-reduced face. On a full redemption the second account could never record its share.
- **NPV solver** — both Newton solvers re-solved the rate mid-summation on the domain guard, mixing discount factors from two different rates into one NPV.

### Changed
- **"Nominal Yield" relabelled "Coupon"** — the column holds the coupon rate. Now that YTC is on a nominal basis too, the old label invited confusion between "nominal yield" (the coupon) and "nominal rate" (the compounding convention).

## [2.4.0] — 2026-07

### Fixed
- **Table Row Hover** — eliminated column shift by removing transform on hover for portfolio tables and markdown tables
- **Portfolio Composition Icon** — replaced grid icon with layers icon for better visual clarity
- **Vertical Rhythm** — standardized spacing between header, cards, and tabs using consistent design tokens

### Changed
- **Navigation Flow** — consolidated dual dropdowns (Analytics + Operations) into single unified Navigation dropdown for seamless user experience
- **Section Headers** — added descriptive subtitles to Capital Allocation, Concentration Risk, and Nearterm Cashflows sections
- **Section Headers** — renamed "Capital Allocation by Account" to "Capital Allocation" and "Upcoming Cashflows (Next 12 Months)" to "Nearterm Cashflows"

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

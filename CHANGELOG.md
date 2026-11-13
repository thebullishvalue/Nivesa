# Changelog

All notable changes to Nivesa are documented here.

## [3.0.6] — 2026-11-13
### Fixed
- **Nothing sits on a panel's edge.**
  - *Charts.* The chart box's 8px padding only displaced the figure, because Streamlit fixes that box
    at the figure's height: 8px out of its bottom (onto a footer's rule, or under the panel's
    clipping edge: the x labels, a bottom legend) and, on phones, 16px past the panel's right edge
    (the last x tick read "10(", the legend's end was cut). The top and bottom inset is now padding
    on the chart's container, and the figure fits inside it; the side inset is the figure's own
    margins (`PLOTLY_MARGIN` l/r +8; the issuer-concentration chart, which sets its own, the same).
  - *A panel's last line.* Streamlit gives every markdown block a -16px bottom margin, so a panel
    that clips at `overflow: hidden` ended 16px before its body did. Body markdown inside a panel
    keeps a zero margin, so a wrapped last line is no longer cut on a phone.
  - *Panel headers.* A long context line (instrument · window · units) wraps at word breaks instead
    of running off the panel on a phone.

## [3.0.5] — 2026-11-13

### Fixed
- **The chosen day reads as one disc.** The previous fix filled the day's inner box while BaseWeb
  still drew its own selection ring around it (a square inside a circle). The fill now goes on that
  ring (the cell's `::after`) and the inner box stays clear: one accent disc with a white number,
  in both appearances.

## [3.0.4] — 2026-11-13

### Fixed
- **The date picker's chosen day had no fill.** This BaseWeb build marks the chosen day with
  `aria-label="Selected. …"`, not `aria-selected`, so the calendar block's reinstatement never
  matched and its transparent reset wiped the fill. The chosen day is filled from the accent again,
  in both appearances.

## [3.0.3] — 2026-11-10

### Fixed
- **Black native surfaces on dark-mode phones.** With both `[theme.light]` and `[theme.dark]`
  in `.streamlit/config.toml`, Streamlit's native widgets followed the viewer's OS while the app
  follows its Paper/Slate toggle, so a dark-mode phone in Paper got near-black native surfaces.
  The config now has exactly one `[theme]` section (a fixed native layer for every viewer, as in
  Pragyam, Samhita and Swing), and the tab strip's overflow fade is painted from `var(--bg)`.
- The date picker is painted from the app's tokens in both appearances (Pragyam's calendar block),
  including the empty cells before the 1st and after the last day of the month.

## [3.0.2] — 2026-11-10 — *Tattva's tab icon*

### Changed
- The browser-tab icon is Tattva's exact mark — its cobalt ring-and-line in Tattva's own
  base64 encoding — so the three apps' tabs match. (Browsers that cached the old gold icon
  pick up the new one with the changed icon address.)

## [3.0.1] — 2026-11 — *iPad: the page fills the screen when the rail is collapsed*

### Fixed
- On iPad in portrait (and any window 1024px wide or less), collapsing the sidebar slid it
  off-screen but the page kept its 200px slot, leaving a blank strip. The narrow-rail width now
  applies only while the rail is open.

## [3.0.0] — 2026-11 — *The Graphite design system*

### Changed
- **The whole UI/UX is the Graphite design system of Tattva 2.8.0** (as ported to Nishkarsh),
  adapted to a bond ledger: Paper (light, default) and Slate (dark) appearances, Inter and
  JetBrains Mono, semantic colour, flat hairline panels, one component per job. The old
  dark-and-gold theme and every inline style are gone.
- **Navigation** is `st.navigation` pages in the rail: Overview · Analytics (Positions, Cashflows,
  Maturity, Issuers) · Operations (Record Transaction, Ledger, Securities, Add Security, Edit
  Security, Edit Transaction). The dashboard's six in-page tabs and the navigation dropdown are
  retired.
- **One page shell everywhere**: a tape of the next projected cashflows, the command bar (book,
  cost, weighted yield to cost, duration, positions, as-of, and a chip: CURRENT or n MATURED) and
  the notice rail, which now carries every form result and caveat (no pop-up success / error
  boxes).
- **Filters sit with what they filter**: each page's account filter is a strip directly above its
  panel; the Ledger's account / type / search filters likewise. The ledger page's "Record New
  Transaction" expander is removed — recording has its own page.
- **Code layout**: the single `app.py` is split into `core/` (the ledger's logic, moved unchanged)
  and `ui/` (design system and one module per page).

### Added
- Cashflows: a forward window (3M / 6M / 1Y / 2Y / ALL) on the monthly chart.
- Issuers: explicit concentration thresholds — caution at 5% of cost, danger at 10% (2.8.0's
  README described traffic lights the code never had).
- Securities: CSV export.
- Tests (none existed): a golden book of every number 2.8.0 displayed (date frozen), source
  identity of every moved function, and a write-path proof that every form operation leaves the
  database exactly as 2.8.0 did.

### Unchanged
- Every number: positions, yields, duration, P&L, accrued interest, cashflows, maturity buckets,
  allocation and concentration reproduce 2.8.0 exactly (golden test).
- The database schema, migrations, validation and every write path (write-path test).

### Dependencies
- `streamlit==1.52.2` pinned exactly, with `starlette>=0.46,<1.0`: the design system styles
  Streamlit's internal page structure, measured on this version.

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

# Changelog

All notable changes to Nivesa are documented here.

## [3.0.13] — 2026-11-14
### Fixed
- **The sidebar stays open while you use a pop-up drawn from it on a phone.** Below 768px
  Streamlit collapses the sidebar on any press outside it, so a tap on the page dismisses the
  rail. A date picker's calendar is drawn in a pop-up layer outside the sidebar, so on a phone the
  first tap on a day or a month arrow counted as "outside" and the whole sidebar closed under the
  finger. Every pop-up now keeps its presses to itself, as dropdown menus always did, and only
  below 768px; a tap on the page beside the sidebar still dismisses it. The script that does this
  rides in a zero-height frame lifted out of the layout, so no block on any page moves.

## [3.0.12] — 2026-11-14
### Fixed
- **Every label in the system's own faces.** Measured in all eight apps: every button, segmented
  control, tab and expander title rendered its label in Streamlit's Source Sans at 14-16px (the
  control was styled, but Streamlit wraps the label in a container that sets its own font). Labels
  now inherit their control's face; the ticker's separators, slider values and multiselect tags
  take the system's mono; one widget micro-label everywhere; page names at the rail's 12px; titles
  break into balanced lines instead of leaving one word on the last line.
- **One vertical rhythm.** A section's rule sat 24-72px below the block above it depending on what
  that block was; KPI cards sat flush on the panel below them; stacked card rows touched. Now:
  blocks in a section 16px apart, a boundary (section rule, page footer) 40px below the block
  above, a header 24px above its first block, a caption 8px under the block it describes. No
  doubled rule under a tab bar.
- **Rows keep one line and one height.** Cards in a row share the row's height (a row read
  162/132/132/147/147px); a row of buttons no longer drops its last button onto a line of its own
  on a tablet, and its buttons match when one label wraps.
- Section titles in Title Case and descriptions in sentence case throughout.

## [3.0.11] — 2026-11-14
### Fixed
- **Nothing hidden under a panel's header band.** Streamlit slides the element after a markdown
  header 16px up beneath it; once the header took Pragyam's opaque band, that covered the top of
  charts drawn right under it (subplot titles, the labels of reference lines placed above the
  plot). A chart under a header now starts below the band, with its own 8px of air.
- **Column headings sit on the band's rule.** A table under a header row that also holds the
  window strip started 10px below the band; it now sits directly on the rule, as under every
  other header.
- **Values and names at the plot's edge are drawn whole** (they were cut by Plotly's plot-area
  clip), and **reference-line labels take their tone at full strength** (some reused their line's
  25% tint).

## [3.0.10] — 2026-11-14
### Changed
- **Pragyam's panel chrome, across the family.** Every chart, table and readout panel's header
  (its context line, meta and chip) sits on a tinted band above a rule, as Pragyam's always did,
  so a panel reads as a labelled object and its content starts below the band; seven apps drew
  the header on the panel's own ground, where it ran into the first table row or the top of the
  plot. A header that shares its row with a window strip tints the whole row.
- **Pragyam's table rhythm.** Tables take 30px rows (were 27px in most apps) with the cell padding
  derived from the row height, so every row is exactly the height its frame is sized for: no
  clipped last row, and no blank strip under it.

## [3.0.9] — 2026-11-14
### Fixed
- **One button face across the family.** Measured in all eight apps, in Paper and Slate, at rest
  and on hover, the primary (run) button had drifted into several faces: a grey rim on the accent
  fill and a light-grey hover with dark type (Paper's generic button rules outranked the primary's
  own), a dark label on the accent (a Paper rule inking every markdown paragraph reached the
  button's label — Sanket's Run Screener), and Streamlit's own sans at 8px corners (Pragyam). The
  generic rules no longer match the primary at all, and one face is stated once: accent fill and
  rim, white mono label, uppercase, 6px corners, each appearance's own darker accent on hover.
- **One segmented control.** The appearance switch's idle segments are unfilled with tertiary ink
  in every app (one filled them grey, one white, with three different label inks).

## [3.0.8] — 2026-11-14
### Fixed
- **A panel's opening copy keeps its gap below the header's rule.** The header is markdown, and
  Streamlit's -16px bottom margin pulled the copy up under the rule: its first line sat 2px below
  the line. When text follows a header, the header keeps its full height, so the copy starts 18px
  below the rule, as in Arthagati's one-block panels. Charts and tables, which carry their own
  top inset, are unchanged.
- A toast's icon takes the accent (it kept the native near-white on Paper).

## [3.0.7] — 2026-11-14
### Fixed
- **A fidelity pass over every page.** Every page, tab and expander was scanned at 1440, 1024, 834
  and 390px in Paper and Slate for clipped or overlapping text, content past its panel or the
  page, chart-label collisions, native-theme colours on Paper and unreadable contrast; each
  defect was fixed at the rule that caused it.
  - *Panel header rows wrap.* On a phone a header's control (the 3M…ALL window strip) was pushed
    wholly outside its panel, invisible and untappable; it now drops to its own line.
  - *Nothing in the rail is cut with an ellipsis.* Page names on the 200px tablet rail, the
    tagline, and a select's value wrap instead.
  - *The page no longer drags sideways.* A KPI card's hidden tooltip opened to the right of an
    icon in the card's top-right corner and widened the page by 171px; it opens over its card.
  - *No native near-white or near-black on Paper.* The open-rail chevron (the only way to the
    navigation on a phone or tablet), help marks, slider min/max labels, expander rows and
    borders, toasts and unstyled widget labels are painted from tokens.
  - *Fields share one height.* A text input's wrapper kept a transparent 1px border, so every
    text field was 2px taller than the select or number field beside it.
  - *The instrument chip* no longer clips the tops of its capitals.
  - *Forms line up row for row:* text, date, number and select fields are all 38px, so a two-column
    form no longer drifts (it reached 4px by the third row).
  - *Issuer concentration:* the 5% and 10% threshold labels lean apart instead of colliding on a phone.

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

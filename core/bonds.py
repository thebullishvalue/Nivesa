# -*- coding: utf-8 -*-
"""
Nivesa — the bond maths: day counts, accrual, the maturity-anchored coupon grid, yield to cost
(bullet and money-weighted), Macaulay / modified duration, and the cashflow projections.

Moved byte-for-byte from the 2.8.0 single-file app (CHANGELOG 2.8.0 documents every fix in here).
``date`` is a module global on purpose: the golden test freezes it.
"""

from datetime import date
import calendar

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from core.config import FREQ_MAP


def _on_day(d, day):
    """``d`` moved to day ``day`` of its month (31 = the month's last day, clipped for short months)."""
    return d.replace(day=min(int(day), calendar.monthrange(d.year, d.month)[1]))


def _coupon_grid(maturity, months, after, coupon_day=None):
    """Coupon dates strictly after `after`, newest first: maturity, maturity - 1 period, ...

    Each date is measured from MATURITY (k periods back), never from the previous date. Stepping
    one period at a time let a month-end date stick to a shorter month's last day: a monthly bond
    maturing on the 31st drifted to the 30th for every month after the first November it met.

    `coupon_day` (1-31, 31 = month-end) is the day the bond pays interest when it is not the maturity
    date's day — many NCDs pay on the 1st or at month-end and make a last, broken-period payment at
    maturity. The regular date of the maturity month is kept when it falls before maturity."""
    dates, k = [], 0
    d = maturity
    while d > after:
        dates.append(d)
        k += 1
        d = maturity - relativedelta(months=months * k)
        if coupon_day is not None:
            d = _on_day(d, coupon_day)
    if coupon_day is not None:
        same = _on_day(maturity, coupon_day)
        if after < same < maturity:
            dates.insert(1, same)
    return dates


def _coupon_periods(maturity, months, after, coupon_day=None, issue=None):
    """[(start, end)] for every coupon date `end` after `after`, oldest first; `start` is the coupon
    date before it (the one at or before `after` for the first). No period starts before ``issue``:
    interest runs from allotment, so the first coupon after issue pays only from the issue date."""
    ends = sorted(_coupon_grid(maturity, months, after, coupon_day))
    if issue is not None:
        ends = [e for e in ends if e > issue]
    if not ends:
        return []
    first = prev_coupon_date(maturity, None, ends[0] - relativedelta(days=1), months=months, coupon_day=coupon_day)
    starts = [first] + ends[:-1]
    if issue is not None:
        starts = [max(s, issue) for s in starts]
    return list(zip(starts, ends))


def coupon_fraction(start, end, convention):
    """The year fraction one coupon pays for, ``start`` → ``end``.

    Actual/Actual is the Indian NCD convention (SEBI): the period's actual days over the days in the
    year of the PAYMENT (366 in a leap year) — verified against platform cashflow statements to the
    paisa, e.g. 31 days paid in Jan 2028 on Rs 2 lakh at 12% = 2,032.78 (31/366). The other
    conventions are the usual day-count fractions."""
    if convention == "Actual/Actual":
        e = pd.to_datetime(end).date()
        s = pd.to_datetime(start).date()
        return max(0.0, (e - s).days / (366 if calendar.isleap(e.year) else 365))
    return day_count_fraction(start, end, convention)


def _coupon(balance, coupon_rate, freq, start, end, coupon_dc):
    """One coupon: actual days when ``coupon_dc`` names a convention, else a flat rate ÷ frequency."""
    if coupon_dc:
        return balance * coupon_rate * coupon_fraction(start, end, coupon_dc)
    return balance * coupon_rate / freq


def day_count_fraction(start_date, end_date, convention="Actual/365"):
    try:
        sd = pd.to_datetime(start_date).date()
        ed = pd.to_datetime(end_date).date()
        if convention == "30/360":
            d1 = min(sd.day, 30)
            d2 = min(ed.day, 30) if d1 == 30 else ed.day
            days = 360 * (ed.year - sd.year) + 30 * (ed.month - sd.month) + (d2 - d1)
            return max(0, days / 360.0)
        elif convention == "Actual/360":
            return max(0, (ed - sd).days / 360.0)
        elif convention == "Actual/Actual":
            # Proper ISDA Actual/Actual: split the interval by calendar year and
            # divide each part's actual days by that year's length (365 or 366),
            # summing whole years between. The old 365.25 shortcut mis-priced
            # leap-year-spanning periods by ~0.2% (verified vs QuantLib ISDA).
            if ed <= sd:
                return 0.0
            if sd.year == ed.year:
                diy = 366 if calendar.isleap(sd.year) else 365
                return (ed - sd).days / diy
            frac = 0.0
            diy1 = 366 if calendar.isleap(sd.year) else 365
            frac += (date(sd.year + 1, 1, 1) - sd).days / diy1
            frac += (ed.year - sd.year - 1)
            diy2 = 366 if calendar.isleap(ed.year) else 365
            frac += (ed - date(ed.year, 1, 1)).days / diy2
            return max(0.0, frac)
        else: # Actual/365
            return max(0, (ed - sd).days / 365.0)
    except (ValueError, TypeError):
        return 0.0

def prev_coupon_date(maturity_str, frequency, as_of, months=None, coupon_day=None):
    """The coupon date on or immediately before `as_of`, walking the schedule
    back from maturity — the same maturity-anchored grid every projection in
    this module uses (with the bond's interest day, when it has one)."""
    mat = pd.to_datetime(maturity_str).date()
    months = months or 12 // FREQ_MAP.get(frequency, 1)
    if as_of >= mat:
        return mat
    if coupon_day is not None:
        same = _on_day(mat, coupon_day)
        if same < mat and same <= as_of:
            return same
    k, d = 0, mat
    while d > as_of:
        k += 1
        d = mat - relativedelta(months=months * k)
        if coupon_day is not None:
            d = _on_day(d, coupon_day)
    return d

def accrued_at(balance, coupon_rate, frequency, maturity_str, as_of, day_count="Actual/365", coupon_day=None,
               issue=None):
    """Interest accrued on `balance` between the previous coupon date and
    `as_of`.

    Added to the price when solving for a yield. Market convention is that the
    DIRTY price (clean + accrued) equals the PV of the full contractual
    coupons; without this term the solver hands the holder a whole coupon for a
    period they did not own. Because the coupon grid is anchored at MATURITY,
    the first projected coupon can fall a day after the purchase and still pay
    a full period — worth up to 72bps of phantom yield on a monthly payer
    (verified against a prorated-first-coupon reference across the book)."""
    pc = prev_coupon_date(maturity_str, frequency, as_of, coupon_day=coupon_day)
    if issue is not None:
        pc = max(pc, issue)
    return balance * coupon_rate * coupon_fraction(pc, as_of, day_count)

def calc_accrued_interest(face_value, coupon_rate, frequency, day_count="Actual/365", last_coupon_date=None, maturity_date=None):
    try:
        today = date.today()
        if maturity_date is not None:
            mat = pd.to_datetime(maturity_date).date()
            if mat <= today:
                return 0.0
        
        if last_coupon_date is None:
            freq = FREQ_MAP.get(frequency, 1)
            days = ((365.25 / freq) / 2)
            return face_value * coupon_rate / 365.25 * days
        
        frac = coupon_fraction(last_coupon_date, today, day_count)
        return face_value * coupon_rate * frac
    except (ValueError, TypeError):
        return 0.0

def calc_macaulay_duration(fv, coupon_rate, frequency, maturity_str, ytm, day_count="Actual/365",
                           schedule=None):
    """Macaulay duration of the REMAINING cashflows.

    `schedule` lets the caller supply the position's actual projected stream.
    Defaulting to a bullet for a bond that is amortizing overstates duration
    badly — an amortizer whose balance steps down monthly measured 1.50y as a
    phantom bullet against 0.33y on its real declining-balance stream (+357%).
    `fv`/`schedule` may be per-unit or position-level; duration is scale-free."""
    try:
        mat_date = pd.to_datetime(maturity_str).date()
        today = date.today()
        if mat_date <= today or ytm <= 0: return 0.0

        if schedule is None:
            schedule = generate_cashflow_schedule(fv, coupon_rate, frequency, maturity_str)
        if not schedule: return 0.0

        freq = FREQ_MAP.get(frequency, 1)
        pv_w = pv_s = 0.0
        for cf in schedule:
            t = day_count_fraction(today, cf['date'], day_count)
            if t > 0:
                pv = cf['total'] / ((1 + ytm / freq) ** (freq * t))
                pv_w += t * pv
                pv_s += pv
        return pv_w / pv_s if pv_s else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0

def calc_modified_duration(mac, ytm, frequency):
    freq = FREQ_MAP.get(frequency, 1)
    return mac / (1 + ytm / freq) if ytm > 0 else mac

def calc_yield_to_cost(fv, cost, coupon_rate, maturity_str, frequency, day_count="Actual/365",
                       as_of=None, schedule=None, coupon_day=None):
    """Yield locked in at `as_of`: the NOMINAL annual rate, compounded at the
    coupon frequency, equating the dirty price to the cashflows to maturity.

    `as_of` is the valuation/purchase anchor (default today). Anchoring at the
    purchase date is what makes this a true *yield-to-cost*: discounting only
    the REMAINING cashflows from today against the ORIGINAL cost — while
    dropping coupons already received — made the number drift as the bond
    seasoned (verified: +72bps on a seasoned discount bond, -66bps on a
    premium bond). Anchoring at purchase makes it invariant to seasoning.

    `schedule` overrides the default bullet projection (pass an amortizing
    stream for an amortizing bond). `fv`/`cost`/`schedule` must share a scale —
    all per-unit or all position-level; the IRR is scale-free either way."""
    try:
        mat_date = pd.to_datetime(maturity_str).date()
        anchor = as_of if as_of is not None else date.today()
        if mat_date <= anchor or cost <= 0: return 0.0

        if schedule is None:
            schedule = generate_cashflow_schedule(fv, coupon_rate, frequency, maturity_str, as_of=anchor)
        if not schedule: return 0.0

        freq = FREQ_MAP.get(frequency, 1)
        # Dirty price = clean cost + interest accrued since the last coupon.
        # The cashflows below are full contractual coupons, so the price they
        # are solved against must carry the accrued leg too (see accrued_at).
        price = cost + accrued_at(fv, coupon_rate, frequency, maturity_str, anchor, day_count, coupon_day)

        cfs = []
        for cf in schedule:
            t = day_count_fraction(anchor, cf['date'], day_count)
            if t > 0:
                cfs.append((t, cf['total']))

        if not cfs: return 0.0

        y = 0.08
        for _ in range(100):
            # Clamp BEFORE accumulating: re-solving `y` mid-summation mixed
            # discount factors from two different rates into one NPV.
            if 1 + y / freq <= 1e-4:
                y = freq * (1e-4 - 1)
            factor = 1 + y / freq

            npv = -price
            d_npv = 0.0
            for t, cf in cfs:
                npv += cf * factor ** (-freq * t)
                d_npv += -t * cf * factor ** (-freq * t - 1)

            if abs(d_npv) < 1e-12:
                break

            dy = npv / d_npv
            y -= dy
            if abs(dy) < 1e-10:
                break

        if np.isnan(y) or np.isinf(y) or y < -1.0 or y > 5.0:
            return 0.0
        return y
    except (ValueError, TypeError, FloatingPointError):
        return 0.0

def _xirr(cashflows, freq=1):
    """Money-weighted IRR of dated (date, amount) cashflows, returned as a
    NOMINAL annual rate compounded `freq` times a year.

    The compounding basis matters: an effective-annual IRR sitting in a column
    beside a nominal coupon rate is not comparable, and reporting one overstated
    YTC by 50-92bps across a monthly-pay book — enough to show 32 of 36
    premium-bought positions yielding MORE than their coupon, which is
    impossible. Newton on Actual/365 time from the earliest date; returns 0.0
    if degenerate."""
    if len(cashflows) < 2:
        return 0.0
    cfs = sorted(cashflows)
    d0 = cfs[0][0]
    ts = [(((d - d0).days) / 365.0, a) for d, a in cfs]
    # need at least one sign change to have a root
    signs = {1 if a > 0 else (-1 if a < 0 else 0) for _, a in ts}
    if not (1 in signs and -1 in signs):
        return 0.0
    m = max(1, int(freq))
    y = 0.10
    for _ in range(200):
        # Clamp before accumulating (see calc_yield_to_cost).
        if 1 + y / m <= 1e-6:
            y = m * (1e-6 - 1)
        base = 1 + y / m

        f = df = 0.0
        for t, a in ts:
            f  += a * base ** (-m * t)
            df += -t * a * base ** (-m * t - 1)
        if abs(df) < 1e-12:
            break
        step = f / df
        y -= step
        if abs(step) < 1e-10:
            break
    if np.isnan(y) or np.isinf(y) or y < -0.999 or y > 5.0:
        return 0.0
    return y

def calc_position_yield_to_cost(txns, coupon_rate, frequency, maturity_str,
                                face_value_pu, day_count="Actual/365", future_principal=None,
                                coupon_day=None, coupon_dc=None, issue_date=None):
    """True money-weighted yield-to-cost for a whole position, robust to
    principal amortization and multiple purchases. Returned as a NOMINAL annual
    rate compounded at the coupon frequency, directly comparable to the coupon
    rate and to calc_yield_to_cost.

    Cashflows: Buys are outflows; Sells, Interest_Receipts and
    Principal_Repayments are inflows (at their actual dates). Coupons are
    projected on the OUTSTANDING balance, which steps down at each recorded
    principal repayment — so an amortizing bond earns coupon on the declining
    balance, not on a phantom bullet. The remaining outstanding principal is
    redeemed at maturity.

    `face_value_pu` is the CURRENT outstanding face per unit. The prior engine
    computed remaining face as `units*face_value - principal_repaid`, which
    DOUBLE-COUNTED amortization when face_value already reflected the
    outstanding (post-repayment) balance — driving YTC negative. Reconstructing
    the original face as `outstanding + total_repaid` and treating repayments
    as the inflows they are removes that error. For a plain bullet bond (no
    repayments) this reduces exactly to the purchase-anchored bullet YTC.

    `future_principal` — [(date, amount)] for this position — is the bond's CONTRACTUAL schedule
    still to come (core.schedule): each instalment is an inflow on its date and the coupon runs on
    the balance left before it; what the schedule does not cover is redeemed at maturity. Without it
    the whole outstanding principal is redeemed at maturity, as before."""
    try:
        freq = FREQ_MAP.get(frequency, 1)
        months = 12 // freq
        mat = pd.to_datetime(maturity_str).date()
        # A matured bond has no future cashflows; an XIRR over purely historical
        # flows converges to a meaningless number. Report N/A instead.
        if mat <= date.today():
            return 0.0

        trade = txns[txns['transaction_type'].isin(['Buy', 'Sell'])]
        cur_u = trade['units'].sum()
        if cur_u <= 0:
            return 0.0
        total_repaid = txns[txns['transaction_type'] == 'Principal_Repayment']['amount'].sum()
        outstanding = cur_u * face_value_pu
        original_face = outstanding + total_repaid
        if outstanding <= 0:
            return 0.0

        reps = sorted(
            (pd.to_datetime(r['trade_date']).date(), r['amount'])
            for _, r in txns[txns['transaction_type'] == 'Principal_Repayment'].iterrows()
        )

        cfs = []
        for _, r in txns.iterrows():
            d = pd.to_datetime(r['trade_date']).date()
            tt = r['transaction_type']
            if tt == 'Buy':
                cfs.append((d, -r['amount']))
            elif tt == 'Sell':
                cfs.append((d, r['amount']))
            elif tt in ('Interest_Receipt', 'Principal_Repayment'):
                cfs.append((d, r['amount']))

        issue = pd.to_datetime(issue_date).date() if issue_date is not None and pd.notna(issue_date) else None

        # Project coupons only over the stretch the RECORDED receipts do not
        # already cover. Every Interest_Receipt above is already an inflow at
        # its actual date; projecting the same coupon again counted it twice
        # and inflated YTC by +703bps on a 4y annual payer with two receipts
        # recorded. With no receipts on file every coupon since the first buy is projected.
        rx = txns[txns['transaction_type'] == 'Interest_Receipt']
        first_buy = pd.to_datetime(txns[txns['transaction_type'] == 'Buy']['trade_date']).min().date()
        cutoff = first_buy
        if not rx.empty:
            cutoff = max(cutoff, pd.to_datetime(rx['trade_date']).max().date())

        # the contractual instalments still to come, capped at what is outstanding
        fut, left = [], outstanding
        for fd, fa in sorted(future_principal or []):
            if date.today() < fd < mat and fa > 0 and left > 1e-9:
                take = min(fa, left)
                fut.append((fd, take))
                left -= take

        # Each coupon is paid on the bonds actually held on its date, at the face per bond that period
        # carried — not on the whole position from an averaged buy date (3.5.0: a second lot bought
        # weeks after the first was credited coupons for a period it was not held, +26bp on one
        # position against the platform statement). The face per bond over a period is today's face
        # plus the per-bond repayments recorded on or after its end, less the scheduled instalments
        # still to come before it. A repayment ON a coupon date does not reduce that coupon (3.3.1).
        lots = sorted((pd.to_datetime(r['trade_date']).date(), float(r['units']))
                      for _, r in txns[txns['transaction_type'].isin(['Buy', 'Sell'])].iterrows())
        steps = [(pd.to_datetime(r['trade_date']).date(), float(r['price']))
                 for _, r in txns[txns['transaction_type'] == 'Principal_Repayment'].iterrows()]
        fut_pu = [(fd, fa / cur_u) for fd, fa in fut]

        def units_at(d):
            return sum(u for td, u in lots if td < d)

        def face_pu(d):
            return face_value_pu + sum(pr for rd, pr in steps if rd >= d) - sum(a for fd, a in fut_pu if fd < d)

        for ps, d in _coupon_periods(mat, months, cutoff, coupon_day, issue):
            bal = units_at(d) * face_pu(d)
            if bal > 0:
                cfs.append((d, _coupon(bal, coupon_rate, freq, ps, d, coupon_dc)))
        cfs.extend(fut)
        cfs.append((mat, left))  # redeem remaining principal at maturity

        # Each purchase pays the seller the interest accrued since the last coupon (and a sale receives
        # it): the coupons above are full ones, so the dirty price is what they are solved against.
        if rx.empty:
            for td, u in lots:
                acc = accrued_at(abs(u) * face_pu(td + relativedelta(days=1)), coupon_rate, frequency,
                                 maturity_str, td, day_count, coupon_day, issue)
                if acc > 0:
                    cfs.append((td, -acc if u > 0 else acc))

        return _xirr(cfs, freq)
    except (ValueError, TypeError, ZeroDivisionError, FloatingPointError):
        return 0.0

def generate_amortizing_schedule(outstanding, coupon_rate, frequency, maturity_str,
                                 installment, period_months, as_of=None, principal_plan=None,
                                 coupon_day=None, coupon_dc=None, issue_date=None):
    """Project an amortizing bond's remaining cashflows: coupons on the
    DECLINING balance plus principal installments on the inferred cadence,
    with any residual redeemed at maturity. `installment`/`period_months` are
    estimated from recorded repayment history; this is a projection, not a
    contractual schedule. Falls back to a bullet when no cadence is known
    (installment/period_months of 0), so this is the single projection entry
    point for both amortizing and bullet positions.

    `principal_plan` — [(date, amount)] — is the bond's CONTRACTUAL schedule (core.schedule), scaled
    to this position. When given it replaces the inferred cadence: each instalment after `as_of` is
    paid on its date (capped at what is outstanding) and any remainder at maturity."""
    try:
        mat = pd.to_datetime(maturity_str).date()
        anchor = as_of if as_of is not None else date.today()
        # A matured bond has no FUTURE cashflows. Without this guard the
        # residual redemption below was emitted at a past-dated maturity, so a
        # bond that had already redeemed still contributed its full outstanding
        # principal to "Principal Due" and to the projected cashflow chart.
        if mat <= anchor:
            return []
        freq = FREQ_MAP.get(frequency, 1)
        cmonths = 12 // freq

        # Future principal installment dates (inferred cadence), until balance
        # is exhausted or maturity is reached.
        prin_by_date = {}
        if principal_plan:
            bal = outstanding
            for d, amt in sorted(principal_plan):
                if anchor < d < mat and amt > 0 and bal > 1e-9:
                    pay = min(amt, bal)
                    prin_by_date[d] = prin_by_date.get(d, 0.0) + pay
                    bal -= pay
            residual = max(0.0, bal)
        elif installment and installment > 0 and period_months and period_months > 0:
            bal = outstanding
            guard = 1
            d = anchor + relativedelta(months=period_months)
            while d < mat and bal > 1e-6 and guard <= 600:
                pay = min(installment, bal)
                prin_by_date[d] = prin_by_date.get(d, 0.0) + pay
                bal -= pay
                guard += 1
                # measured from the anchor, not the previous date (see _coupon_grid)
                d = anchor + relativedelta(months=period_months * guard)
            residual = max(0.0, bal)
        else:
            residual = outstanding
        prin_by_date[mat] = prin_by_date.get(mat, 0.0) + residual

        # Coupon dates from maturity back to anchor, each with the period it pays for.
        periods = _coupon_periods(mat, cmonths, anchor, coupon_day,
                                  pd.to_datetime(issue_date).date() if issue_date is not None and pd.notna(issue_date) else None)
        start_of = {e: s for s, e in periods}
        cds = [e for _s, e in periods]

        # Merge coupon and principal dates; coupon accrues on the balance
        # outstanding just before each date.
        all_dates = sorted(set(cds) | set(prin_by_date.keys()))
        cfs = []
        bal = outstanding
        for d in all_dates:
            coupon = 0.0
            if d in start_of:
                coupon = _coupon(bal, coupon_rate, freq, start_of[d], d, coupon_dc)
            prin = prin_by_date.get(d, 0.0)
            cfs.append({'date': d, 'coupon': coupon, 'principal': prin,
                        'total': coupon + prin,
                        'type': 'Maturity + Coupon' if d == mat else ('Amortization' if prin > 0 else 'Coupon')})
            bal = max(0.0, bal - prin)
        return cfs
    except (ValueError, TypeError):
        return []

def calc_days_to_maturity(s):
    try:
        return max(0, (pd.to_datetime(s) - pd.to_datetime(date.today())).days)
    except (ValueError, TypeError):
        return 0

def generate_cashflow_schedule(fv_pu, coupon_rate, frequency, maturity_str, units=1, as_of=None,
                               coupon_day=None, coupon_dc=None, issue_date=None):
    """Coupon schedule anchored to maturity, stepping back one period at a
    time, emitting every cashflow strictly after `as_of` (default: today).
    Passing the purchase date reconstructs the full original stream (used to
    compute the yield actually locked in at cost)."""
    try:
        mat = pd.to_datetime(maturity_str).date()
        anchor = as_of if as_of is not None else date.today()
        freq = FREQ_MAP.get(frequency, 1)
        months = 12 // freq
        cfs = []
        for s, d in _coupon_periods(mat, months, anchor, coupon_day,
                                    pd.to_datetime(issue_date).date() if issue_date is not None and pd.notna(issue_date) else None):
            cpn = _coupon(fv_pu * units, coupon_rate, freq, s, d, coupon_dc)
            prin = fv_pu * units if d == mat else 0
            cfs.append({'date': d, 'coupon': cpn, 'principal': prin, 'total': cpn + prin,
                        'type': 'Maturity + Coupon' if d == mat else 'Coupon'})
        return cfs
    except (ValueError, TypeError):
        return []

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

def prev_coupon_date(maturity_str, frequency, as_of):
    """The coupon date on or immediately before `as_of`, walking the schedule
    back from maturity — the same maturity-anchored grid every projection in
    this module uses."""
    d = pd.to_datetime(maturity_str).date()
    months = 12 // FREQ_MAP.get(frequency, 1)
    while d > as_of:
        d -= relativedelta(months=months)
    return d

def accrued_at(balance, coupon_rate, frequency, maturity_str, as_of, day_count="Actual/365"):
    """Interest accrued on `balance` between the previous coupon date and
    `as_of`.

    Added to the price when solving for a yield. Market convention is that the
    DIRTY price (clean + accrued) equals the PV of the full contractual
    coupons; without this term the solver hands the holder a whole coupon for a
    period they did not own. Because the coupon grid is anchored at MATURITY,
    the first projected coupon can fall a day after the purchase and still pay
    a full period — worth up to 72bps of phantom yield on a monthly payer
    (verified against a prorated-first-coupon reference across the book)."""
    pc = prev_coupon_date(maturity_str, frequency, as_of)
    return balance * coupon_rate * day_count_fraction(pc, as_of, day_count)

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
        
        frac = day_count_fraction(last_coupon_date, today, day_count)
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
                       as_of=None, schedule=None):
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
        price = cost + accrued_at(fv, coupon_rate, frequency, maturity_str, anchor, day_count)

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
                                face_value_pu, day_count="Actual/365"):
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
    repayments) this reduces exactly to the purchase-anchored bullet YTC."""
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

        # Anchor coupon projection at the units-weighted average buy date, not
        # the first buy: when capital is deployed in staggered lots (e.g. a
        # small lot, then a larger lot months later), projecting coupons on the
        # full reconstructed balance from the earliest date would credit coupons
        # on capital not yet invested and overstate the yield. (Single-lot
        # positions collapse to the buy date, matching the bullet-bond YTC.)
        buys_df = txns[txns['transaction_type'] == 'Buy']
        bu = buys_df['units'].abs()
        word = (bu * buys_df['trade_date'].apply(lambda x: pd.to_datetime(x).toordinal())).sum()
        anchor = date.fromordinal(int(round(word / bu.sum()))) if bu.sum() > 0 else pd.to_datetime(buys_df['trade_date'].min()).date()

        # Project coupons only over the stretch the RECORDED receipts do not
        # already cover. Every Interest_Receipt above is already an inflow at
        # its actual date; projecting the same coupon again counted it twice
        # and inflated YTC by +703bps on a 4y annual payer with two receipts
        # recorded. With no receipts on file the cutoff is the anchor, so a
        # ledger that tracks only purchases is unaffected.
        rx = txns[txns['transaction_type'] == 'Interest_Receipt']
        cutoff = anchor
        if not rx.empty:
            cutoff = max(cutoff, pd.to_datetime(rx['trade_date']).max().date())

        cds, dd = [], mat
        while dd > cutoff:
            cds.append(dd)
            dd -= relativedelta(months=months)
        for d in sorted(cds):
            bal = original_face - sum(a for rd, a in reps if rd <= d)
            if bal > 0:
                cfs.append((d, bal * coupon_rate / freq))
        cfs.append((mat, outstanding))  # redeem remaining principal at maturity

        # The first projected coupon pays a FULL period even though the
        # position was held for only part of it (the grid is maturity-anchored).
        # Charge the unearned portion as an outflow at the cutoff — the
        # standard dirty-price treatment. See accrued_at.
        bal_at_cutoff = original_face - sum(a for rd, a in reps if rd <= cutoff)
        acc = accrued_at(bal_at_cutoff, coupon_rate, frequency, maturity_str, cutoff, day_count)
        if acc > 0:
            cfs.append((cutoff, -acc))

        return _xirr(cfs, freq)
    except (ValueError, TypeError, ZeroDivisionError, FloatingPointError):
        return 0.0

def generate_amortizing_schedule(outstanding, coupon_rate, frequency, maturity_str,
                                 installment, period_months, as_of=None):
    """Project an amortizing bond's remaining cashflows: coupons on the
    DECLINING balance plus principal installments on the inferred cadence,
    with any residual redeemed at maturity. `installment`/`period_months` are
    estimated from recorded repayment history; this is a projection, not a
    contractual schedule. Falls back to a bullet when no cadence is known
    (installment/period_months of 0), so this is the single projection entry
    point for both amortizing and bullet positions."""
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
        if installment and installment > 0 and period_months and period_months > 0:
            bal = outstanding
            d = anchor + relativedelta(months=period_months)
            guard = 0
            while d < mat and bal > 1e-6 and guard < 600:
                pay = min(installment, bal)
                prin_by_date[d] = prin_by_date.get(d, 0.0) + pay
                bal -= pay
                d += relativedelta(months=period_months)
                guard += 1
            residual = max(0.0, bal)
        else:
            residual = outstanding
        prin_by_date[mat] = prin_by_date.get(mat, 0.0) + residual

        # Coupon dates from maturity back to anchor.
        cds, d = [], mat
        while d > anchor:
            cds.append(d)
            d -= relativedelta(months=cmonths)
        cds = sorted(cds)

        # Merge coupon and principal dates; coupon accrues on the balance
        # outstanding just before each date.
        all_dates = sorted(set(cds) | set(prin_by_date.keys()))
        cfs = []
        bal = outstanding
        for d in all_dates:
            coupon = 0.0
            if d in cds:
                coupon = bal * coupon_rate / freq
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

def generate_cashflow_schedule(fv_pu, coupon_rate, frequency, maturity_str, units=1, as_of=None):
    """Coupon schedule anchored to maturity, stepping back one period at a
    time, emitting every cashflow strictly after `as_of` (default: today).
    Passing the purchase date reconstructs the full original stream (used to
    compute the yield actually locked in at cost)."""
    try:
        mat = pd.to_datetime(maturity_str).date()
        anchor = as_of if as_of is not None else date.today()
        freq = FREQ_MAP.get(frequency, 1)
        months = 12 // freq
        cpn = fv_pu * coupon_rate / freq * units
        dates = []
        d = mat
        while d > anchor:
            dates.append(d)
            d -= relativedelta(months=months)
        dates.sort()
        cfs = []
        for d in dates:
            prin = fv_pu * units if d == mat else 0
            cfs.append({'date': d, 'coupon': cpn, 'principal': prin, 'total': cpn + prin,
                        'type': 'Maturity + Coupon' if d == mat else 'Coupon'})
        return cfs
    except (ValueError, TypeError):
        return []

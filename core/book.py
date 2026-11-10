# -*- coding: utf-8 -*-
"""
Nivesa — the book: the positions engine (running average cost, realized P&L, one projected
stream per position, yield to cost, duration) with its cost-weighted totals, the transaction
ledger, and the maturity-ladder bucket rule.

Moved byte-for-byte from the 2.8.0 single-file app.
"""

from datetime import date

import pandas as pd

from core.bonds import (
    calc_accrued_interest, calc_days_to_maturity, calc_macaulay_duration, calc_modified_duration,
    calc_position_yield_to_cost, calc_yield_to_cost, generate_amortizing_schedule, prev_coupon_date,
)
from core.config import FLOW_ORDER, FREQ_MAP
from core.db import db_query


def get_positions_dataframe():
    secs = db_query("SELECT * FROM securities")
    if secs.empty: return pd.DataFrame(), {}
    secs['maturity_date'] = pd.to_datetime(secs['maturity_date'])

    txns = db_query("SELECT * FROM transactions")
    if txns.empty: return pd.DataFrame(), {}
    txns['trade_date'] = pd.to_datetime(txns['trade_date'])

    meta = db_query("SELECT * FROM security_metadata")
    positions = []

    for (bid, acct), grp in txns.groupby(['bond_id', 'account']):
        si = secs[secs['bond_id'] == bid]
        if si.empty: continue
        si = si.iloc[0]
        mi = meta[meta['bond_id'] == bid].iloc[0] if not meta.empty and bid in meta['bond_id'].values else None

        # Chronological running average-cost engine.
        # Realized P&L on a Sell must use the average cost of units held AT
        # THE TIME OF SALE — a lifetime buy-VWAP would let buys made AFTER a
        # sell retroactively change that sale's P&L (look-ahead).
        #
        # A Principal_Repayment is a RETURN OF CAPITAL, so it reduces the basis
        # as it is received. Leaving the basis at full original cost meant a
        # half-amortized bond sold at its (halved) fair value booked a phantom
        # loss equal to the principal already returned. Capital returned beyond
        # the remaining basis is a realized gain, and the basis floors at zero.
        # Same-day ties run Buy → Repayment → Sell: buy-before-sell matches
        # validate_ledger_chronology, and a repayment reduces the basis of units
        # still held before any same-day sale is struck against it.
        flows = grp[grp['transaction_type'].isin(FLOW_ORDER)].copy()
        flows['_ord'] = flows['transaction_type'].map(FLOW_ORDER)
        flows = flows.sort_values(['trade_date', '_ord'])

        units_held = cost_held = r_pnl = 0.0
        for _, tr in flows.iterrows():
            tt = tr['transaction_type']
            if tt == 'Buy':
                units_held += abs(tr['units'])
                cost_held  += tr['amount']
            elif tt == 'Principal_Repayment':
                applied    = min(tr['amount'], cost_held)
                cost_held -= applied
                r_pnl     += tr['amount'] - applied
            else:  # Sell (stored with negative units)
                su = abs(tr['units'])
                avg = cost_held / units_held if units_held > 0 else 0.0
                r_pnl      += tr['amount'] - su * avg
                cost_held  -= su * avg
                units_held -= su

        cur_u = units_held
        if cur_u <= 0: continue

        int_recv = grp[grp['transaction_type'] == 'Interest_Receipt']['amount'].sum()
        reps_df  = grp[grp['transaction_type'] == 'Principal_Repayment'].sort_values('trade_date')
        prin_rep = reps_df['amount'].sum()
        cost     = cost_held  # already net of principal returned, see above
        avg_px   = cost / units_held if units_held > 0 else 0.0

        # Infer the amortization cadence from recorded repayments so the cashflow
        # projection can step the remaining principal down realistically instead
        # of dropping it all at maturity as a phantom bullet. Estimate only —
        # the forward schedule is not stored. Zeroed when nothing has been
        # repaid, which makes generate_amortizing_schedule emit a plain bullet.
        if len(reps_df):
            amort_installment = float(reps_df['amount'].median())
            if len(reps_df) >= 2:
                gaps = reps_df['trade_date'].diff().dropna().dt.days
                amort_months = int(max(1, round(gaps.median() / 30.44)))
            else:
                amort_months = 12 // FREQ_MAP.get(si['frequency'], 1)
        else:
            amort_installment = 0.0
            amort_months = 0

        # Outstanding face = current units * current (post-amortization) face per
        # unit. face_value already reflects the outstanding balance, so it must
        # NOT be reduced by principal_repaid again — doing so double-counted
        # amortization and drove YTC negative on amortizing bonds.
        face     = cur_u * si['face_value']

        day_count = mi['day_count'] if mi is not None and pd.notna(mi['day_count']) else 'Actual/365'

        # ONE projected stream per position, shared by the duration engine, the
        # today-anchored yield and the Cashflow tab: declining balance when the
        # bond amortizes, bullet otherwise. Previously the risk metrics assumed
        # a bullet while the Cashflow tab projected the amortizing stream, so
        # the two disagreed by as much as ₹64k of principal on one position and
        # duration ran up to 357% too long.
        proj = generate_amortizing_schedule(
            face, si['coupon_rate'], si['frequency'], si['maturity_date'],
            amort_installment, amort_months,
        )

        # YTC = true money-weighted yield-to-cost over the position's actual
        # cashflows (repayments counted as inflows, coupons on the declining
        # balance). Seasoning-invariant; reduces to the bullet YTC when there is
        # no amortization.
        ytc = calc_position_yield_to_cost(grp, si['coupon_rate'], si['frequency'], si['maturity_date'], si['face_value'], day_count)
        # Duration is a TODAY risk metric: discount the REMAINING cashflows at a
        # today-anchored yield (best current-yield proxy absent a market mark).
        y_today = calc_yield_to_cost(face, cost, si['coupon_rate'], si['maturity_date'],
                                     si['frequency'], day_count, as_of=date.today(), schedule=proj)
        if y_today > 0:
            mac = calc_macaulay_duration(face, si['coupon_rate'], si['frequency'],
                                         si['maturity_date'], y_today, day_count, schedule=proj)
            mod = calc_modified_duration(mac, y_today, si['frequency'])
        else:
            mac = 0.0
            mod = 0.0

        dtm = calc_days_to_maturity(si['maturity_date'])
        ann_cpn = face * si['coupon_rate']

        # Compute real last coupon date
        mat_date = pd.to_datetime(si['maturity_date']).date()
        today = date.today()
        last_coupon = prev_coupon_date(si['maturity_date'], si['frequency'], today)

        # Cap last coupon at issue_date if available
        issue_date = pd.to_datetime(mi['issue_date']).date() if mi is not None and pd.notna(mi['issue_date']) else None
        if issue_date is not None:
            last_coupon = max(last_coupon, issue_date)

        # Set accrued interest to 0 if matured
        if mat_date <= today:
            acc_int = 0.0
        else:
            acc_int = calc_accrued_interest(face, si['coupon_rate'], si['frequency'], day_count, last_coupon, mat_date)

        first_buy = flows.loc[flows['transaction_type'] == 'Buy', 'trade_date'].min()
        hold_days = (pd.to_datetime(date.today()) - first_buy).days if pd.notna(first_buy) else 0

        positions.append({
            'bond_id': bid, 'account': acct,
            'issuer': si['issuer'], 'isin': si['isin'],
            'maturity_date': si['maturity_date'],
            'coupon_rate': si['coupon_rate'], 'frequency': si['frequency'],
            'current_units': cur_u, 'cost_basis': cost, 'avg_buy_price': avg_px,
            'realized_pnl': r_pnl, 'interest_received': int_recv,
            'principal_repaid': prin_rep, 'position_face_value': face,
            'amort_installment': amort_installment, 'amort_months': amort_months,
            'annual_coupon_income': ann_cpn, 'nominal_yield': si['coupon_rate'],
            'yield_to_cost': ytc, 'macaulay_duration': mac,
            'modified_duration': mod, 'days_to_maturity': dtm,
            'years_to_maturity': dtm / 365.25, 'accrued_interest': acc_int,
            'holding_days': hold_days,
            'bond_type':      mi['bond_type']      if mi is not None else 'NCD',
            'credit_rating':  mi['credit_rating']  if mi is not None else 'Unrated',
            'sector':         mi['sector']          if mi is not None else 'Financials',
        })

    if not positions: return pd.DataFrame(), {}
    df = pd.DataFrame(positions)
    
    # Portfolio averages are weighted by cost basis (invested capital — the
    # best available PV proxy in a ledger with no market marks). This matches
    # the cost-weighted NY/YC aggregation used in every dashboard table, so
    # headline and tables now share one statistical basis. Duration and YTC
    # are averaged over VALID observations only: a position whose solver
    # returned 0 renders as "N/A" in the table, so silently including it as
    # 0% in the weighted average would corrupt the headline number.
    tf = df['position_face_value'].sum()
    tc = df['cost_basis'].sum()
    df['weight'] = df['cost_basis'] / tc if tc > 0 else 0

    def w(col, valid_mask=None):
        sub = df if valid_mask is None else df[valid_mask]
        ws = sub['cost_basis'].sum()
        return (sub[col] * sub['cost_basis']).sum() / ws if ws > 0 else 0.0

    totals = {
        'Total Cost Basis':       tc,
        'Total Face Value':       tf,
        'Total Annual Coupon':    df['annual_coupon_income'].sum(),
        'Total Accrued Interest': df['accrued_interest'].sum(),
        'Total Interest Received':df['interest_received'].sum(),
        'Total Principal Repaid': df['principal_repaid'].sum(),
        'Total Realized PnL':    df['realized_pnl'].sum(),
        'Num Positions':          len(df),
        'Num Issuers':            df['issuer'].nunique(),
        'Num Accounts':           df['account'].nunique(),
        'Weighted Nominal Yield': w('nominal_yield'),
        'Weighted YTC':           w('yield_to_cost', df['yield_to_cost'] > 0),
        'Weighted Mac Duration':  w('macaulay_duration', df['macaulay_duration'] > 0),
        'Weighted Mod Duration':  w('modified_duration', df['macaulay_duration'] > 0),
        'Weighted Avg Maturity':  w('years_to_maturity'),
    }
    return df, totals

def get_transaction_ledger_dataframe():
    """Fetch all transactions joined with security master data."""
    query = """
    SELECT
        t.trade_date,
        s.issuer,
        s.isin,
        t.account,
        t.transaction_type,
        t.units,
        t.price,
        t.amount,
        t.notes
    FROM transactions t
    JOIN securities s ON t.bond_id = s.bond_id
    ORDER BY t.trade_date DESC
    """
    df = db_query(query)
    if not df.empty:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
    return df

def _maturity_bucket(days, matured=False):
    """Classify days-to-maturity into ladder buckets.

    `matured` is explicit because calc_days_to_maturity floors at 0, so a bond
    that redeemed last month is indistinguishable from one maturing today and
    was being shown as a live 0-3M holding."""
    if matured:      return "Matured"
    if days <= 90:   return "0-3M"
    if days <= 180:  return "3-6M"
    if days <= 365:  return "6-12M"
    if days <= 730:  return "1-2Y"
    if days <= 1095: return "2-3Y"
    if days <= 1825: return "3-5Y"
    return "5Y+"


MATURITY_BUCKET_ORDER = ["Matured", "0-3M", "3-6M", "6-12M", "1-2Y", "2-3Y", "3-5Y", "5Y+"]

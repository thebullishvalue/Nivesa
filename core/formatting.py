# -*- coding: utf-8 -*-
"""
Nivesa — number and text formatting: Indian-grouped rupees (₹1,23,456.78), the compact Cr/L
form, percentages, and the HTML escape. Moved byte-for-byte from the 2.8.0 single-file app.
"""

import html as _html


def esc(text):
    """HTML-escape user-entered text before interpolating into raw-HTML
    tables (unsafe_allow_html). Issuer names with '&' or '<' (e.g. 'M&M
    Financial') otherwise corrupt the rendered markup."""
    return _html.escape(str(text)) if text is not None else ''

def fmt_inr(amount):
    """Indian numbering: ₹1,23,456.78"""
    try:
        amount = float(amount)
        neg = amount < 0
        amount = abs(amount)
        parts = f"{amount:,.2f}".split('.')
        digits = parts[0].replace(',', '')
        dec = parts[1]
        if len(digits) <= 3:
            fmt = digits
        else:
            fmt = digits[-3:]
            rem = digits[:-3]
            while rem:
                fmt = rem[-2:] + ',' + fmt
                rem = rem[:-2]
        return f"{'-₹' if neg else '₹'}{fmt}.{dec}"
    except (ValueError, TypeError):
        return "₹0.00"

def fmt_inr_short(amount):
    """Compact: ₹1.23 Cr, ₹4.56 L"""
    try:
        v = float(amount)
        if abs(v) >= 1e7:   return f"₹{v/1e7:.2f} Cr"
        if abs(v) >= 1e5:   return f"₹{v/1e5:.2f} L"
        return fmt_inr(v)
    except (ValueError, TypeError):
        return "₹0"

def fmt_pct(value, decimals=2):
    try:
        return f"{float(value)*100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"

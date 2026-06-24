# finance/utils.py
import jdatetime
from datetime import date

def gregorian_to_jalali(gregorian_date: date) -> jdatetime.date:
    """تبدیل تاریخ میلادی به شمسی"""
    if not gregorian_date:
        return None
    return jdatetime.date.fromgregorian(date=gregorian_date)

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """تبدیل تاریخ شمسی به میلادی"""
    try:
        return jdatetime.date(jy, jm, jd).togregorian()
    except (ValueError, TypeError):
        return None
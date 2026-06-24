# finance/templatetags/jalali_filters.py
from django import template
from django.utils import timezone
import jdatetime

register = template.Library()

@register.filter
def jdate(value):
    """
    تبدیل تاریخ میلادی به شمسی با فرمت YYYY/MM/DD
    اگر مقدار None یا خالی باشد، رشته خالی برمی‌گرداند.
    """
    if not value:
        return ''
    
    # اگر مقدار از نوع datetime.date یا datetime.datetime است
    try:
        # تبدیل به jdatetime
        jalali_date = jdatetime.date.fromgregorian(date=value)
        return jalali_date.strftime('%Y/%m/%d')
    except (ValueError, TypeError, AttributeError):
        # اگر خطا رخ داد، مقدار اصلی را برگردان
        return str(value)
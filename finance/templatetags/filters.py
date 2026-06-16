from django import template

register = template.Library()

@register.filter
def intcomma(value):
    """تبدیل عدد به فرمت ۳,۰۰۰,۰۰۰"""
    try:
        value = int(value)
        return f"{value:,}"
    except (ValueError, TypeError):
        return value
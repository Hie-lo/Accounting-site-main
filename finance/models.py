from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
import datetime
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.BigIntegerField(default=0)  # موجودی به تومان

    def __str__(self):
        return f"کیف پول {self.user.username} - موجودی: {self.balance} تومان"

class Category(models.Model):
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    is_default = models.BooleanField(default=False)  # دسته پیش‌فرض سیستمی

    class Meta:
        unique_together = ('name', 'user')  # هر کاربر نمی‌تواند دو دسته با نام تکراری داشته باشد

    def __str__(self):
        return self.name

class Transaction(models.Model):
    TYPE_CHOICES = [
        ('topup', 'افزایش موجودی'),
        ('expense', 'خرج'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.PositiveIntegerField()  # مبلغ به تومان
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=False, default=datetime.date.today)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} تومان - {self.date}"

class ManualBalanceHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_balance_history')
    old_balance = models.BigIntegerField()
    new_balance = models.BigIntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.old_balance} → {self.new_balance} در {self.created_at}"
    
@receiver(post_save, sender=User)
def create_user_wallet_and_default_categories(sender, instance, created, **kwargs):
    if created:
        # ایجاد کیف پول
        Wallet.objects.create(user=instance)
        
        # لیست دسته‌بندی‌های پیش‌فرض
        default_categories = [
            'خوراک', 'مسکن', 'حمل‌ونقل', 'تفریح', 'بهداشت',
            'تحصیل', 'قبوض', 'خرید روزانه', 'هدیه', 'سایر'
        ]
        for cat_name in default_categories:
            Category.objects.create(name=cat_name, user=instance, is_default=True)


def recalculate_balance(user):
    total_topup = Transaction.objects.filter(user=user, type='topup').aggregate(s=Sum('amount'))['s'] or 0
    total_expense = Transaction.objects.filter(user=user, type='expense').aggregate(s=Sum('amount'))['s'] or 0
    balance = total_topup - total_expense
    wallet, created = Wallet.objects.get_or_create(user=user)
    wallet.balance = balance
    wallet.save()
    return balance

# مدل بودجه
class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    amount = models.PositiveIntegerField(verbose_name='بودجه ماهانه (تومان)')
    month = models.PositiveSmallIntegerField()  # 1 تا 12
    year = models.PositiveIntegerField()

    class Meta:
        unique_together = ('user', 'category', 'month', 'year')  # هر کاربر فقط یک بودجه برای هر دسته در هر ماه
        verbose_name = 'بودجه'
        verbose_name_plural = 'Budgets'

    def __str__(self):
        return f"{self.category.name} - {self.month}/{self.year}: {self.amount} تومان"
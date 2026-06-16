from django.contrib import admin
from .models import Budget, Wallet, Category, Transaction, ManualBalanceHistory

admin.site.register(Wallet)
admin.site.register(Category)
admin.site.register(Transaction)
admin.site.register(ManualBalanceHistory)
admin.site.register(Budget)
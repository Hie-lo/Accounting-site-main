from multiprocessing import context
from urllib import request

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Sum, Q ,Count
from .models import Transaction, Category, Wallet, recalculate_balance, ManualBalanceHistory , Budget
from .forms import TransactionForm, SignUpForm, BudgetForm
import openpyxl
from django.http import HttpResponse
from openpyxl.styles import Font
from .forms import CategoryForm
import json
from datetime import datetime, date ,timedelta
from django.utils import timezone
from calendar import monthrange
from django.db import models

def home(request):
    return render(request, 'home.html')

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def dashboard(request):
    # اطمینان از وجود کیف پول
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    if created:
        default_categories = [
            'خوراک', 'مسکن', 'حمل‌ونقل', 'تفریح', 'بهداشت',
            'تحصیل', 'قبوض', 'خرید روزانه', 'هدیه', 'سایر'
        ]
        for cat_name in default_categories:
            Category.objects.get_or_create(name=cat_name, user=request.user, defaults={'is_default': True})
    
    total_topup = Transaction.objects.filter(user=request.user, type='topup').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = Transaction.objects.filter(user=request.user, type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = wallet.balance
    recent_transactions = Transaction.objects.filter(user=request.user).order_by('-date', '-created_at')[:10]

    # داده‌های نمودار خرج بر اساس دسته
    expense_by_category = (
        Transaction.objects.filter(user=request.user, type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    
    # آماده‌سازی برای نمودار
    chart_labels = [item['category__name'] if item['category__name'] else 'بدون دسته' for item in expense_by_category]
    chart_data = [item['total'] for item in expense_by_category]
    
    # اگر هیچ خرجی وجود نداشت، یک پیام پیش‌فرض بدهید
    if not chart_labels:
        chart_labels = ['هیچ داده‌ای']
        chart_data = [0]
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    budget_alerts = []
    budgets = Budget.objects.filter(user=request.user, month=current_month, year=current_year)
    for b in budgets:
        spent = Transaction.objects.filter(
            user=request.user,
            type='expense',
            category=b.category,
            date__year=current_year,
            date__month=current_month
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        if b.amount > 0:
            percent = (spent / b.amount) * 100
            if percent >= 90:
                budget_alerts.append(
                    f"⚠️ بودجه دسته «{b.category.name}» به {percent:.0f}% رسیده است. "
                    f"(خرج شده: {spent:,} تومان / بودجه: {b.amount:,} تومان)"
                )

    categories = Category.objects.filter(user=request.user)
    today_date = timezone.now().date().isoformat() 
    context = {
        'total_topup': total_topup,
        'total_expense': total_expense,
        'balance': balance,
        'recent_transactions': recent_transactions,
        'budget_alerts': budget_alerts,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'categories': categories,
        'today': today_date,

    }
 
    return render(request, 'finance/dashboard.html', context)

@login_required
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            # اگر تاریخ خالی بود، امروز را بگذار
            if not transaction.date:
                transaction.date = timezone.now().date()
            # بررسی تاریخ آینده (سمت سرور)
            if transaction.date > timezone.now().date():
                messages.error(request, 'تاریخ نمی‌تواند در آینده باشد.')
                return render(request, 'finance/add_transaction.html', {'form': form})
            transaction.save()
            recalculate_balance(request.user)
            messages.success(request, 'تراکنش با موفقیت ثبت شد.')
            return redirect('dashboard')
    else:
        form = TransactionForm(user=request.user)
    return render(request, 'finance/add_transaction.html', {'form': form})

@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-date', '-created_at')
    
    # فیلتر بر اساس نوع
    type_filter = request.GET.get('type')
    if type_filter and type_filter in ['topup', 'expense']:
        transactions = transactions.filter(type=type_filter)
    
    # فیلتر بر اساس دسته‌بندی
    category_id = request.GET.get('category')
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    
    # فیلتر بازه تاریخ
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        transactions = transactions.filter(date__gte=from_date)
    if to_date:
        transactions = transactions.filter(date__lte=to_date)
    
    # جستجو در توضیحات
    search_text = request.GET.get('search')
    if search_text:
        transactions = transactions.filter(Q(description__icontains=search_text))
    
    # برای نمایش در قالب، لیست دسته‌بندی‌های کاربر را هم می‌فرستیم
    categories = Category.objects.filter(user=request.user)
    
    context = {
        'transactions': transactions,
        'categories': categories,
        'type_filter': type_filter,
        'category_id': category_id,
        'from_date': from_date,
        'to_date': to_date,
        'search_text': search_text,
    }
    return render(request, 'finance/transaction_list.html', context)

@login_required
def edit_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        if form.is_valid():
            form.save()
            recalculate_balance(request.user)
            messages.success(request, 'تراکنش با موفقیت ویرایش شد.')
            return redirect('transaction_list')
    else:
        form = TransactionForm(instance=transaction, user=request.user)
    return render(request, 'finance/edit_transaction.html', {'form': form, 'transaction': transaction})

@login_required
def delete_transaction(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        transaction.delete()
        recalculate_balance(request.user)
        messages.success(request, 'تراکنش حذف شد.')
        return redirect('transaction_list')
    return render(request, 'finance/confirm_delete.html', {'transaction': transaction})


@login_required
def manual_adjust_balance(request):
    wallet = Wallet.objects.get(user=request.user)
    
    # ایجاد یا بازیابی دسته‌بندی ویژه «تنظیم دستی موجودی» برای کاربر
    manual_category, created = Category.objects.get_or_create(
        user=request.user,
        name='تنظیم دستی موجودی',
        defaults={'is_default': False}
    )
    
    if request.method == 'POST':
        new_balance_str = request.POST.get('new_balance')
        reason = request.POST.get('reason')
        if new_balance_str and reason:
            try:
                new_balance = int(new_balance_str)
                old_balance = wallet.balance
                diff = new_balance - old_balance
                
                if diff != 0:
                    # ثبت تراکنش جبرانی با دسته‌بندی مشخص
                    transaction = Transaction.objects.create(
                        user=request.user,
                        amount=abs(diff),
                        type='topup' if diff > 0 else 'expense',
                        category=manual_category,
                        date=timezone.now().date(),
                        description=f"تنظیم دستی موجودی: {reason} (از {old_balance} به {new_balance} تومان)"
                    )
                    recalculate_balance(request.user)
                    ManualBalanceHistory.objects.create(
                        user=request.user,
                        old_balance=old_balance,
                        new_balance=new_balance,
                        reason=reason
                    )
                    messages.success(request, f'موجودی کیف پول از {old_balance:,} به {new_balance:,} تومان تنظیم شد. تراکنش ثبت شد.')
                else:
                    messages.info(request, 'مقدار جدید با موجودی فعلی برابر است.')
            except ValueError:
                messages.error(request, 'مبلغ وارد شده معتبر نیست.')
        else:
            messages.error(request, 'لطفاً مبلغ جدید و دلیل را وارد کنید.')
        return redirect('dashboard')
    
    context = {
        'wallet': wallet,
        'manual_category': manual_category
    }
    return render(request, 'finance/manual_adjust.html', context)

@login_required
def export_excel(request):
    # دریافت فیلترهای مشابه transaction_list (اختیاری)
    transactions = Transaction.objects.filter(user=request.user).order_by('-date')
    
    # اعمال فیلترها (اگر از همان پارامترهای GET استفاده کنیم)
    type_filter = request.GET.get('type')
    if type_filter and type_filter in ['topup', 'expense']:
        transactions = transactions.filter(type=type_filter)
    category_id = request.GET.get('category')
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        transactions = transactions.filter(date__gte=from_date)
    if to_date:
        transactions = transactions.filter(date__lte=to_date)
    search_text = request.GET.get('search')
    if search_text:
        transactions = transactions.filter(description__icontains=search_text)
    
    # اگر پارامترهای year و month وجود داشت، بازه آن ماه را اعمال کن
    year = request.GET.get('year')
    month = request.GET.get('month')
    if year and month:
        try:
            year = int(year)
            month = int(month)
            first_day = date(year, month, 1)
            # محاسبه آخرین روز ماه
            if month == 12:
                last_day = date(year, month, 31)
            else:
                last_day = date(year, month + 1, 1) - timedelta(days=1)
            transactions = transactions.filter(date__gte=first_day, date__lte=last_day)
        except (ValueError, TypeError):
            pass
        
    # ایجاد کتاب کار و برگه
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "تراکنش‌ها"
    
    # هدرها
    headers = ['نوع', 'مبلغ (تومان)', 'دسته', 'تاریخ', 'توضیحات']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
    
    # پر کردن داده‌ها
    for row, t in enumerate(transactions, start=2):
        ws.cell(row=row, column=1, value=t.get_type_display())
        ws.cell(row=row, column=2, value=t.amount)
        ws.cell(row=row, column=3, value=t.category.name if t.category else 'بدون دسته')
        ws.cell(row=row, column=4, value=str(t.date))
        ws.cell(row=row, column=5, value=t.description)
    

    
    # تنظیم پاسخ HTTP برای دانلود
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=transactions.xlsx'
    wb.save(response)
    return response


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, 'finance/category_list.html', {'categories': categories})

@login_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, 'دسته جدید اضافه شد.')
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'finance/category_form.html', {'form': form, 'title': 'افزودن دسته'})

@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'دسته ویرایش شد.')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'finance/category_form.html', {'form': form, 'title': 'ویرایش دسته'})

@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'دسته حذف شد.')
        return redirect('category_list')
    # اگر درخواست GET بود (مثلاً از طریق لینک مستقیم)، خطای 405 بدهید
    from django.http import HttpResponseNotAllowed
    return HttpResponseNotAllowed(['POST'])

@login_required
def monthly_report(request):
    # ========== تعریف ماه‌ها در ابتدا ==========
    month_names = {
        1: 'ژانویه', 2: 'فوریه', 3: 'مارس', 4: 'آوریل',
        5: 'مه', 6: 'ژوئن', 7: 'ژوئیه', 8: 'اوت',
        9: 'سپتامبر', 10: 'اکتبر', 11: 'نوامبر', 12: 'دسامبر'
    }
    months_choices = [(num, month_names[num]) for num in range(1, 13)]
    # =========================================
    
    # گرفتن ماه و سال از GET (پیش‌فرض: ماه جاری)
    now = timezone.now()
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))
    selected_month_name = month_names.get(selected_month, '')
    
    # ساخت بازه تاریخ اول و آخر ماه
    first_day = date(selected_year, selected_month, 1)
    last_day = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
    
    # تراکنش‌های آن ماه
    transactions = Transaction.objects.filter(
        user=request.user,
        date__gte=first_day,
        date__lte=last_day
    ).order_by('date')
    
    # محاسبه مجموع topup و expense در این ماه
    total_topup = transactions.filter(type='topup').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = transactions.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # محاسبه موجودی ابتدای ماه (مجموع تراکنش‌های قبل از first_day)
    balance_before = Transaction.objects.filter(
        user=request.user,
        date__lt=first_day
    ).aggregate(
        net=Sum('amount', filter=models.Q(type='topup')) - Sum('amount', filter=models.Q(type='expense'))
    )['net'] or 0
    # موجودی انتهای ماه = موجودی قبل + مجموع topup ماه - مجموع expense ماه
    balance_end = balance_before + total_topup - total_expense
    
    # داده‌های نمودار خرج بر اساس دسته در این ماه
    expense_by_category = (
        transactions.filter(type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    chart_labels = [item['category__name'] if item['category__name'] else 'بدون دسته' for item in expense_by_category]
    chart_data = [item['total'] for item in expense_by_category]
    if not chart_labels:
        chart_labels = ['هیچ داده‌ای']
        chart_data = [0]
    
    # داده‌های نمودار افزایش موجودی بر اساس دسته
    topup_by_category = (
        transactions.filter(type='topup')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    chart_labels_topup = [item['category__name'] if item['category__name'] else 'بدون دسته' for item in topup_by_category]
    chart_data_topup = [item['total'] for item in topup_by_category]
    if not chart_labels_topup:
        chart_labels_topup = ['هیچ داده‌ای']
        chart_data_topup = [0]
    
    # لیست سال‌های موجود برای انتخاب (از اولین تراکنش کاربر تا الان)
    first_transaction_date = Transaction.objects.filter(user=request.user).order_by('-date', '-created_at').first()
    if first_transaction_date:
        min_year = first_transaction_date.date.year
    else:
        min_year = now.year
    years = range(min_year, now.year + 1)
    
    context = {
        'transactions': transactions,
        'total_topup': total_topup,
        'total_expense': total_expense,
        'balance_before': balance_before,
        'balance_end': balance_end,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_name': selected_month_name,
        'months': months_choices,
        'years': years,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_labels_topup': json.dumps(chart_labels_topup),
        'chart_data_topup': json.dumps(chart_data_topup),
    }
    return render(request, 'finance/monthly_report.html', context)



@login_required
def budget_list(request):
    budgets = Budget.objects.filter(user=request.user).select_related('category')
    
    # دیکشنری نام ماه‌های میلادی به فارسی
    month_names = {
        1: 'ژانویه', 2: 'فوریه', 3: 'مارس', 4: 'آوریل',
        5: 'مه', 6: 'ژوئن', 7: 'ژوئیه', 8: 'اوت',
        9: 'سپتامبر', 10: 'اکتبر', 11: 'نوامبر', 12: 'دسامبر'
    }
    months_choices = [(num, name) for num, name in month_names.items()]
    
    now = timezone.now()
    current_month = now.month
    current_year = now.year
    
    # محاسبه spent و percent و اضافه کردن month_name به هر بودجه
    for budget in budgets:
        spent = Transaction.objects.filter(
            user=request.user,
            type='expense',
            category=budget.category,
            date__year=budget.year,
            date__month=budget.month
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        budget.spent = spent
        budget.percent = (spent / budget.amount * 100) if budget.amount > 0 else 0
        budget.month_name = month_names.get(budget.month, '')  # اضافه شد
    
    categories = Category.objects.filter(user=request.user)
    
    context = {
        'budgets': budgets,
        'current_month': current_month,
        'current_year': current_year,
        'categories': categories,
        'months': months_choices,        # کلید months برای استفاده در حلقه قالب
    }
    return render(request, 'finance/budget_list.html', context)

@login_required
def add_budget(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, 'بودجه با موفقیت ثبت شد.')
            return redirect('budget_list')
    else:
        form = BudgetForm(user=request.user)
    return render(request, 'finance/budget_form.html', {'form': form, 'title': 'افزودن بودجه'})

@login_required
def edit_budget(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'بودجه ویرایش شد.')
            return redirect('budget_list')
    else:
        form = BudgetForm(instance=budget, user=request.user)
    return render(request, 'finance/budget_form.html', {'form': form, 'title': 'ویرایش بودجه'})

@login_required
def delete_budget(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'بودجه حذف شد.')
        return redirect('budget_list')
    # در صورت درخواست GET، خطای 405
    from django.http import HttpResponseNotAllowed
    return HttpResponseNotAllowed(['POST'])
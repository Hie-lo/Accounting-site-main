import jdatetime

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Transaction, Category ,Budget

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
    

    
class TransactionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label='تاریخ'
    )
    class Meta:
        jalali_year = forms.IntegerField(label='سال', min_value=1300, max_value=1500, required=True)
        jalali_month = forms.IntegerField(label='ماه', min_value=1, max_value=12, required=True)
        jalali_day = forms.IntegerField(label='روز', min_value=1, max_value=31, required=True)
        model = Transaction
        fields = ['amount', 'type', 'category', 'date', 'description','rating']
        widgets = {
            'date': forms.HiddenInput(),  # مخفی کردن فیلد date
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'rating': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
            self.fields['category'].empty_label = "بدون دسته"
        if self.instance and self.instance.pk:
            jalali_date = jdatetime.date.fromgregorian(date=self.instance.date)
            self.fields['jalali_year'].initial = jalali_date.year
            self.fields['jalali_month'].initial = jalali_date.month
            self.fields['jalali_day'].initial = jalali_date.day

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['month'].choices = [
            (1, 'فروردین'), (2, 'اردیبهشت'), (3, 'خرداد'), (4, 'تیر'),
            (5, 'مرداد'), (6, 'شهریور'), (7, 'مهر'), (8, 'آبان'),
            (9, 'آذر'), (10, 'دی'), (11, 'بهمن'), (12, 'اسفند')
        ]


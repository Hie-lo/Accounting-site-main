// static/js/theme.js
(function() {
    const themeToggle = document.getElementById('themeToggle');
    if (!themeToggle) return;

    // تابع تشخیص تم سیستم (مرورگر/گوشی)
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    // دریافت تم ذخیره شده کاربر
    let storedTheme = localStorage.getItem('theme');
    let currentTheme;

    // اگر کاربر قبلاً تمی انتخاب کرده، از همان استفاده کن
    // در غیر این صورت، تم سیستم را بگیر
    if (storedTheme) {
        currentTheme = storedTheme;
    } else {
        currentTheme = getSystemTheme();
        localStorage.setItem('theme', currentTheme);
    }

    // اعمال تم به صفحه
    document.documentElement.setAttribute('data-theme', currentTheme);
    themeToggle.textContent = currentTheme === 'dark' ? '☀️' : '🌙';

    // گوش دادن به تغییرات تم سیستم (وقتی کاربر دارک مود گوشی رو عوض می‌کنه)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        // فقط اگر کاربر تم دستی انتخاب نکرده باشه (یعنی localStorage خالی باشه)
        if (!localStorage.getItem('theme')) {
            const newTheme = e.matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
        }
    });

    // رویداد کلیک دکمه تغییر تم (اولویت با انتخاب دستی کاربر)
    themeToggle.addEventListener('click', function() {
        const current = document.documentElement.getAttribute('data-theme');
        const newTheme = current === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    });
})();

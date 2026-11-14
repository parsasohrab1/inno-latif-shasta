"""ابزار مشترک برای مدیریت فونت Vazirmatn در اسکریپت‌های نمودار.

این ماژول از شکست اسکریپت‌ها در محیط‌های بدون فونت (مانند CI) جلوگیری می‌کند
با جستجوی فونت در مسیرهای رایج و fallback به DejaVu Sans.
"""

import os
import matplotlib.font_manager as fm


def setup_vazirmatn():
    """جستجوی امن فونت Vazirmatn و تنظیم rcParams.

    Returns:
        bool: True اگر Vazirmatn پیدا شد، False در غیر این صورت (fallback به DejaVu Sans).
    """
    candidates = [
        # مسیر محلی توسعه‌دهنده
        os.path.expanduser("~/.local/share/fonts/Vazirmatn-Regular.ttf"),
        os.path.expanduser("~/.local/share/fonts/Vazirmatn-Bold.ttf"),
        os.path.expanduser("~/.local/share/fonts/Vazirmatn-Medium.ttf"),
        # مسیرهای سیستم رایج
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Medium.ttf",
        "/usr/share/fonts/Vazirmatn/Vazirmatn-Regular.ttf",
        "/usr/share/fonts/Vazirmatn/Vazirmatn-Bold.ttf",
        "/usr/share/fonts/Vazirmatn/Vazirmatn-Medium.ttf",
        # مسیر نصب‌شده با apt
        "/usr/share/fonts/TTF/Vazirmatn-Regular.ttf",
        "/usr/share/fonts/TTF/Vazirmatn-Bold.ttf",
        "/usr/share/fonts/TTF/Vazirmatn-Medium.ttf",
    ]
    found = False
    for path in candidates:
        if os.path.isfile(path):
            try:
                fm.fontManager.addfont(path)
                found = True
            except Exception:
                pass
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = (['Vazirmatn', 'DejaVu Sans']
                                        if found else ['DejaVu Sans'])
    plt.rcParams['axes.unicode_minus'] = False
    return found

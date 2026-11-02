# logging_utils.py
# Version: final_version (1.0.0)
# Centralized logging and error counters for all modules.
# This module provides a single source of truth for error tracking
# and consistent logging across the entire arbitrage bot.

import logging
import time
import traceback
from datetime import datetime

# ============= شمارنده‌های سراسری خطا =============
# این شمارنده‌ها در تمام ماژول‌ها مشترک هستند و به‌روزرسانی می‌شوند
error_counter = {}
consecutive_error_counter = {}
last_error_reset = time.time()

def add_log_context(block=None, chain_id=None):
    """
    ایجاد زمینه (context) برای لاگ‌ها با اطلاعات اضافی مانند شماره بلوک و chain ID.
    """
    return {'block': block if block else 'N/A', 'chain_id': chain_id if chain_id else 'N/A'}

async def log_error(func_name, error_msg, exc=None, extra_context=None):
    """
    تابع متمرکز ثبت خطا با شمارنده‌های سراسری.
    
    پارامترها:
        func_name (str): نام تابعی که خطا در آن رخ داده است.
        error_msg (str): پیام خطا.
        exc (Exception, optional): شیء استثنا برای ثبت جزئیات بیشتر.
        extra_context (dict, optional): اطلاعات اضافی برای زمینه لاگ (مانند block, chain_id).
    
    رفتار:
        - شمارنده‌های error_counter و consecutive_error_counter را به‌روز می‌کند.
        - هر ۱ ساعت، error_counter را ریست می‌کند.
        - اگر تعداد خطاهای متوالی برای یک تابع به ۲۰ برسد، یک پیام بحرانی ثبت می‌کند.
        - پس از ثبت خطای بحرانی، شمارنده متوالی آن تابع را ریست می‌کند.
    """
    global error_counter, consecutive_error_counter, last_error_reset
    
    # ریست دوره‌ای شمارنده‌ها (هر ساعت)
    now = time.time()
    if now - last_error_reset > 3600:
        error_counter.clear()
        last_error_reset = now
    
    # تعیین نوع خطا
    error_type = type(exc).__name__ if exc else 'UnknownError'
    error_counter[error_type] = error_counter.get(error_type, 0) + 1
    consecutive_error_counter[func_name] = consecutive_error_counter.get(func_name, 0) + 1
    
    # ساخت زمینه لاگ
    context = add_log_context()
    if extra_context:
        context.update(extra_context)
    
    # ثبت خطا در لاگ
    logging.error(f"[{datetime.now()}] Error in {func_name}: {error_msg}", extra=context)
    if exc:
        logging.error(traceback.format_exc(), extra=context)
    
    # بررسی خطاهای متوالی بحرانی
    if consecutive_error_counter[func_name] >= 20:
        logging.critical(
            f"Critical error: {func_name} failed {consecutive_error_counter[func_name]} "
            f"times consecutively: {error_msg}",
            extra=context
        )
        # در صورت نیاز، می‌توان در اینجا ارسال پیام تلگرام را اضافه کرد
        # اما این کار به عهده ماژول main_bot است که تابع send_message را فراخوانی کند
        consecutive_error_counter[func_name] = 0
    
    # ریست شمارنده‌های متوالی برای سایر توابع
    for key in list(consecutive_error_counter.keys()):
        if key != func_name:
            consecutive_error_counter[key] = 0

def reset_error_counters():
    """
    ریست کردن تمام شمارنده‌های خطا به‌صورت دستی.
    """
    global error_counter, consecutive_error_counter, last_error_reset
    error_counter.clear()
    consecutive_error_counter.clear()
    last_error_reset = time.time()

def get_error_stats():
    """
    بازگرداندن آمار فعلی خطاها به‌صورت یک دیکشنری.
    مفید برای گزارش‌گیری یا نمایش وضعیت.
    """
    return {
        "error_counter": dict(error_counter),
        "consecutive_error_counter": dict(consecutive_error_counter),
        "last_error_reset": datetime.fromtimestamp(last_error_reset).isoformat()
    }
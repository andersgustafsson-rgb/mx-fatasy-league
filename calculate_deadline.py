#!/usr/bin/env python3
"""Calculate time until 9:30 AM PT on next Saturday"""
from datetime import datetime, timedelta
import sys

try:
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except ImportError:
    try:
        import pytz
        USE_ZONEINFO = False
    except ImportError:
        print("Error: Need either zoneinfo (Python 3.9+) or pytz")
        sys.exit(1)

# Get current time
if USE_ZONEINFO:
    now_utc = datetime.now(ZoneInfo('UTC'))
    pt_tz = ZoneInfo('America/Los_Angeles')
else:
    now_utc = datetime.now(pytz.UTC)
    pt_tz = pytz.timezone('America/Los_Angeles')

now_pt = datetime.now(pt_tz)

# Find next Saturday at 9:30 AM PT
today_pt = now_pt.replace(hour=0, minute=0, second=0, microsecond=0)
days_until_saturday = (5 - today_pt.weekday()) % 7

# If it's Saturday and past 9:30 AM, go to next Saturday
if days_until_saturday == 0:
    if now_pt.hour > 9 or (now_pt.hour == 9 and now_pt.minute >= 30):
        days_until_saturday = 7

# Calculate next Saturday at 9:30 AM PT
next_saturday_pt = today_pt.replace(hour=9, minute=30, second=0, microsecond=0) + timedelta(days=days_until_saturday)

# Convert to UTC
if USE_ZONEINFO:
    next_saturday_utc = next_saturday_pt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    now_utc_naive = now_utc.replace(tzinfo=None)
else:
    next_saturday_utc = next_saturday_pt.astimezone(pytz.UTC).replace(tzinfo=None)
    now_utc_naive = now_utc.replace(tzinfo=None)

# Calculate difference
diff = next_saturday_utc - now_utc_naive

days = diff.days
hours = diff.seconds // 3600
minutes = (diff.seconds % 3600) // 60
seconds = diff.seconds % 60

print(f"\n📅 Nästa lördag: {next_saturday_pt.strftime('%Y-%m-%d')}")
print(f"⏰ Tid: 9:30 AM PT")
print(f"\n⏳ Tid kvar:")
print(f"   {days} dagar")
print(f"   {hours} timmar")
print(f"   {minutes} minuter")
print(f"\n📊 Totalt: {diff.total_seconds() / 3600:.2f} timmar")
print(f"   ({diff.total_seconds() / 86400:.2f} dagar)")

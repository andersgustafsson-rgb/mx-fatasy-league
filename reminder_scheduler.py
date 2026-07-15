"""Inbyggd påminnelse-klocka — körs i web-tjänsten på Render (ingen separat cron)."""
from __future__ import annotations

import os
import threading
import time

_started = False
_start_lock = threading.Lock()


def _scheduler_enabled() -> bool:
    mode = (os.getenv("REMINDER_SCHEDULER") or "auto").strip().lower()
    if mode in ("0", "false", "off", "no"):
        return False
    if mode in ("1", "true", "on", "yes"):
        return True
    # auto: på Render, av lokalt
    return bool(os.getenv("RENDER"))


def start_reminder_scheduler(app) -> None:
    global _started
    if not _scheduler_enabled():
        return
    with _start_lock:
        if _started:
            return
        _started = True

    def loop() -> None:
        time.sleep(20)
        while True:
            try:
                with app.app_context():
                    from reminder_service import process_due_reminders

                    result = process_due_reminders()
                    sent = int(result.get("sent") or 0)
                    if sent:
                        print(f"Reminder scheduler sent={sent} {result}")
            except Exception as ex:
                print(f"Reminder scheduler error: {ex}")
            time.sleep(60)

    threading.Thread(
        target=loop, daemon=True, name="mx-reminder-scheduler"
    ).start()
    print("Reminder scheduler started (in-app, every 60s)")

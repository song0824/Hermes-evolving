# ⚠️ Peak Hour Drill-Down Timestamp Pitfall

## Problem

When using SLS SQL `date_format(from_unixtime(__time__ + 28800), '%H:00')` to get hourly distribution, the resulting hour strings (e.g. `"05:00"`) are in **CST (UTC+8)**. But the query's `from`/`to` timestamps are in **UTC**.

If you naively calculate drill-down timestamps as:
```python
peak_start = base_utc_ts + int(cst_hour_str.split(":")[0]) * 3600  # WRONG
```
...you query the wrong UTC hour and get **empty results**.

## Root Cause

The SQL converts UTC to CST by adding 28800 seconds. The hour string represents the **CST hour**, not the UTC hour.

Example: SQL returns `"05:00"` with 94 errors.
- **Wrong**: `base_utc + 5 * 3600` → queries UTC 05:00 (= CST 13:00), gets 0 errors
- **Correct**: `base_utc + ((5 - 8) % 24) * 3600 = base_utc + 21 * 3600` → queries UTC 21:00 (= CST 05:00 next day), gets 94 errors

## Fix

```python
def cst_hour_to_utc_ts(base_utc_ts, cst_hour_str):
    """Convert SQL CST hour (e.g. '05:00') to correct UTC timestamp."""
    cst_h = int(cst_hour_str.split(":")[0])
    utc_h = (cst_h - 8) % 24
    return base_utc_ts + utc_h * 3600
```

## Mapping Table (for a UTC midnight-to-midnight query)

When query range is UTC Day-N 00:00 → Day-N+1 00:00 (= CST Day-N 08:00 → Day-N+1 08:00):

| SQL Hour | CST Time | UTC Time | UTC Offset from Base |
|---|---|---|---|
| 00:00 | Day-N+1 00:00 | Day-N 16:00 | +16h |
| 05:00 | Day-N+1 05:00 | Day-N 21:00 | +21h |
| 08:00 | Day-N 08:00 | Day-N 00:00 | +0h |
| 14:00 | Day-N 14:00 | Day-N 06:00 | +6h |
| 23:00 | Day-N 23:00 | Day-N 15:00 | +15h |

## Symptom

`GetHistograms` confirms errors exist in a given hour, but `GetLogs` with SQL drill-down returns empty list. Always verify drill-down results against histogram totals.

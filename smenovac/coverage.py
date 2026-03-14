"""Výpočet pokrytí otevírací doby směnami – optimalizovaný pro měsíční přehled."""
from datetime import datetime
from calendar import monthrange
from sqlalchemy import or_, and_


def _time_to_minutes(t):
    """'08:30' -> 510"""
    if not t:
        return 0
    parts = str(t).split(":")
    return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)


def _minutes_to_time(m):
    """510 -> '08:30'"""
    h, mn = divmod(m, 60)
    return f"{h:02d}:{mn:02d}"


def _compute_coverage_gaps(open_min, close_min, shifts):
    """Vrátí mezery v pokrytí. shifts = [(start_min, end_min), ...]."""
    if open_min >= close_min:
        return []  # 24h nebo neplatná doba = bez mezer
    intervals = []
    for s in shifts:
        start_min = max(s[0], open_min)
        end_min = min(s[1], close_min)
        if start_min < end_min:
            intervals.append((start_min, end_min))
    if not intervals:
        return [(_minutes_to_time(open_min), _minutes_to_time(close_min))]
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for a, b in intervals[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    gaps = []
    if merged[0][0] > open_min:
        gaps.append((_minutes_to_time(open_min), _minutes_to_time(merged[0][0])))
    for i in range(len(merged) - 1):
        gaps.append((_minutes_to_time(merged[i][1]), _minutes_to_time(merged[i + 1][0])))
    if merged[-1][1] < close_min:
        gaps.append((_minutes_to_time(merged[-1][1]), _minutes_to_time(close_min)))
    return gaps


def _effective_branch_id(shift):
    """Vrátí branch_id směny (shift.branch_id nebo employee.branch_id)."""
    if shift.branch_id is not None:
        return shift.branch_id
    return shift.employee.branch_id if shift.employee else None


def compute_coverage_month(Branch, Shift, Employee, owner_id, month_str):
    """
    Spočítá pokrytí pro všechny pobočky a všechny dny v měsíci.
    2 dotazy: branches, shifts (s joinem na Employee).

    Vrací:
        {
            "branch_data": {branch_id: {day: {covered, gaps, shifts, openTime, closeTime}}},
            "dates": ["2026-02-01", ...],
            "branches": [(id, name), ...],
            "alerts": [{"branchId", "branchName", "date", "openTime", "closeTime", "gaps"}, ...]
        }
    """
    from datetime import timedelta

    try:
        y, m = map(int, month_str.split("-"))
        first = datetime(y, m, 1).date()
        last_day = monthrange(y, m)[1]
        last = datetime(y, m, last_day).date()
        dates = [(first + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(last_day)]
    except (ValueError, KeyError):
        return None

    first_str, last_str = dates[0], dates[-1]

    # 1. Dotaz: pobočky
    branches = list(Branch.query.filter_by(user_id=owner_id).order_by(Branch.name).all())
    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "branch_data": {},
            "dates": dates,
            "branches": [],
            "alerts": [],
        }

    # 2. Dotaz: všechny směny pro měsíc
    shifts = Shift.query.join(Employee).filter(
        or_(
            Shift.branch_id.in_(branch_ids),
            and_(Shift.branch_id.is_(None), Employee.branch_id.in_(branch_ids)),
        ),
        Shift.date >= first_str,
        Shift.date <= last_str,
    ).order_by(Shift.date, Shift.start_time).all()

    # Seskupit směny: branch_id -> date -> [shift, ...]
    by_branch_date = {bid: {d: [] for d in dates} for bid in branch_ids}
    for s in shifts:
        bid = _effective_branch_id(s)
        if bid and bid in by_branch_date and s.date in by_branch_date[bid]:
            by_branch_date[bid][s.date].append(s)

    # Výpočet pro každou pobočku a den
    branch_data = {}
    alerts = []

    for branch in branches:
        bid = branch.id
        branch_data[bid] = {}
        day_shifts = by_branch_date.get(bid, {})

        for date in dates:
            d = datetime.strptime(date, "%Y-%m-%d").date()
            wd = d.weekday()
            if wd >= 5 and branch.open_time_weekend and branch.close_time_weekend:
                open_t, close_t = branch.open_time_weekend, branch.close_time_weekend
            else:
                open_t = branch.open_time or "08:00"
                close_t = branch.close_time or "20:00"
            open_min = _time_to_minutes(open_t)
            close_min = _time_to_minutes(close_t)

            shift_list = day_shifts.get(date, [])
            intervals = [(_time_to_minutes(s.start_time), _time_to_minutes(s.end_time)) for s in shift_list]
            gaps = _compute_coverage_gaps(open_min, close_min, intervals)
            shifts_data = [
                {"employeeName": s.employee.name, "startTime": s.start_time, "endTime": s.end_time}
                for s in shift_list
            ]

            covered = len(gaps) == 0
            branch_data[bid][date] = {
                "covered": covered,
                "gaps": [{"from": g[0], "to": g[1]} for g in gaps],
                "shifts": shifts_data,
                "openTime": open_t,
                "closeTime": close_t,
            }
            if not covered:
                alerts.append({
                    "branchId": str(bid),
                    "branchName": branch.name,
                    "date": date,
                    "openTime": open_t,
                    "closeTime": close_t,
                    "gaps": [{"from": g[0], "to": g[1]} for g in gaps],
                })

    return {
        "branch_data": branch_data,
        "dates": dates,
        "branches": [(b.id, b.name) for b in branches],
        "alerts": alerts,
    }


def coverage_month_to_grid_response(data):
    """Převede výstup compute_coverage_month na formát očekávaný UI (grid)."""
    if not data:
        return {"dates": [], "grid": [], "alerts": []}
    return {
        "dates": data["dates"],
        "grid": [
            {
                "branchId": str(bid),
                "branchName": name,
                "days": data["branch_data"].get(bid, {}),
            }
            for bid, name in data["branches"]
        ],
        "alerts": data["alerts"],
    }

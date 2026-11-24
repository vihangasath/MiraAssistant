"""Deterministic pricing. The LLM never does arithmetic: it can only *call* this.

Implements the 11 rules on the workbook's READ ME tab. All money is held as
fractions.Fraction so there is no float rounding anywhere until the explicit
"round up to next USD 5" / "round deposit up to whole USD" steps.

If any input needed for a price is missing, expired, ambiguous or out of range,
the result is a NeedsSpecialist with machine-readable reasons, never a number.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction
from typing import Literal

from mira.data.rates_loader import RateBook, TourRate

INFANT_MAX_AGE = 1   # under 2: free
CHILD_MAX_AGE = 11   # 2–11: child rates; 12+: adult


@dataclass(frozen=True)
class Party:
    adults: int
    child_ages: tuple[int, ...] = ()

    @property
    def children(self) -> int:
        """Children aged 2–11 (they pay child rates and count for the vehicle)."""
        return sum(1 for a in self.child_ages if INFANT_MAX_AGE < a <= CHILD_MAX_AGE)

    @property
    def infants(self) -> int:
        return sum(1 for a in self.child_ages if a <= INFANT_MAX_AGE)

    @property
    def paying_adults(self) -> int:
        """Adults plus any 'child' aged 12 or over, who pays adult rates."""
        return self.adults + sum(1 for a in self.child_ages if a > CHILD_MAX_AGE)

    @property
    def group_size(self) -> int:
        """Adults + children 2–11 (infants have no seat)."""
        return self.paying_adults + self.children


@dataclass(frozen=True)
class FlagReason:
    code: str
    detail: str


@dataclass(frozen=True)
class CostLine:
    label: str
    lkr: Fraction


@dataclass(frozen=True)
class NightDetail:
    night: int
    date: date
    hotel_id: str
    hotel_name: str
    season: str
    doubles: int
    singles: int
    extra_beds: int
    lkr: Fraction


@dataclass(frozen=True)
class Quote:
    status: Literal["priced"]
    tour_id: str
    tour_name: str
    start_date: date
    end_date: date
    party: Party
    vehicle: str
    cost_lines: tuple[CostLine, ...]
    nights: tuple[NightDetail, ...]
    total_cost_lkr: Fraction
    total_cost_usd: Fraction
    margin: Fraction
    price_usd: int
    deposit_usd: int
    pay_in_full: bool
    balance_due: date | None

    @property
    def gross_profit_usd(self) -> Fraction:
        return self.price_usd - self.total_cost_usd

    @property
    def gross_profit_pct(self) -> Fraction:
        return self.gross_profit_usd / self.price_usd

    def traveller_view(self) -> dict:
        """What a traveller may see: price and deposit only. No costs, no margin."""
        return {
            "tour_id": self.tour_id,
            "tour_name": self.tour_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "adults": self.party.paying_adults,
            "children": self.party.children,
            "infants": self.party.infants,
            "price_usd": self.price_usd,
            "deposit_usd": self.deposit_usd,
            "pay_in_full": self.pay_in_full,
            "balance_usd": self.price_usd - self.deposit_usd,
            "balance_due": self.balance_due.isoformat() if self.balance_due else None,
        }

    def staff_view(self) -> dict:
        """Full breakdown for the private enquiry record."""
        return {
            **self.traveller_view(),
            "vehicle": self.vehicle,
            "cost_lines_lkr": {c.label: float(c.lkr) for c in self.cost_lines},
            "nights": [
                {"night": n.night, "date": n.date.isoformat(), "hotel": n.hotel_name, "season": n.season,
                 "doubles": n.doubles, "singles": n.singles, "extra_beds": n.extra_beds, "lkr": float(n.lkr)}
                for n in self.nights
            ],
            "total_cost_lkr": float(self.total_cost_lkr),
            "total_cost_usd": round(float(self.total_cost_usd), 2),
            "margin": float(self.margin),
            "gross_profit_usd": round(float(self.gross_profit_usd), 2),
            "gross_profit_pct": round(float(self.gross_profit_pct) * 100, 2),
        }


@dataclass(frozen=True)
class NeedsSpecialist:
    status: Literal["needs_specialist"]
    tour_id: str
    tour_name: str | None
    start_date: date | None
    party: Party | None
    reasons: tuple[FlagReason, ...] = field(default_factory=tuple)

    def staff_view(self) -> dict:
        return {
            "tour_id": self.tour_id,
            "tour_name": self.tour_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "adults": self.party.paying_adults if self.party else None,
            "children": self.party.children if self.party else None,
            "infants": self.party.infants if self.party else None,
            "reasons": [{"code": r.code, "detail": r.detail} for r in self.reasons],
        }


@dataclass(frozen=True)
class InvalidRequest:
    """The request itself is wrong (no adults, date in the past). Mira asks again; no flag."""
    status: Literal["invalid"]
    code: str
    message: str


PriceResult = Quote | NeedsSpecialist | InvalidRequest


@dataclass(frozen=True)
class PricingOverrides:
    """Business-rule overrides staff can change live (the workbook stays untouched)."""
    margin_day: Fraction | None = None
    margin_multi: Fraction | None = None
    margin_by_tour: dict[str, Fraction] = field(default_factory=dict)


def round_up_to(value: Fraction, step: int) -> int:
    return int(math.ceil(value / step)) * step


def price_tour(
    book: RateBook,
    tour_id: str,
    start_date: date,
    party: Party,
    today: date,
    overrides: PricingOverrides | None = None,
) -> PriceResult:
    overrides = overrides or PricingOverrides()
    s = book.settings
    tour: TourRate | None = book.tours.get(tour_id)

    def flag(*reasons: FlagReason) -> NeedsSpecialist:
        return NeedsSpecialist("needs_specialist", tour_id, tour.name if tour else None, start_date, party, tuple(reasons))

    # ---- request validation (traveller can fix these themselves)
    if party.adults < 1:
        return InvalidRequest("invalid", "NO_ADULT", "At least one adult must travel.")
    if any(a < 0 or a > 17 for a in party.child_ages):
        return InvalidRequest("invalid", "BAD_CHILD_AGE", "Children's ages must be between 0 and 17.")
    if start_date < today:
        return InvalidRequest("invalid", "DATE_IN_PAST", f"The start date {start_date.isoformat()} is in the past.")

    # ---- does a rate exist at all?
    if tour is None:
        return flag(FlagReason("NO_RATES_FOR_TOUR", f"{tour_id} is not in the rate workbook."))
    if tour.notes and "not launched" in tour.notes.lower():
        return flag(FlagReason("TOUR_NOT_LAUNCHED", f"Workbook note: {tour.notes}"))

    reasons: list[FlagReason] = []
    end_date = start_date + timedelta(days=tour.days - 1)

    if party.group_size > s.max_group_size:
        reasons.append(FlagReason("GROUP_TOO_LARGE", f"{party.group_size} travellers; private tours take at most {s.max_group_size}."))
    if s.fx_valid_until and end_date > s.fx_valid_until:
        reasons.append(FlagReason("RATES_EXPIRED", f"Trip ends {end_date.isoformat()}; rates and FX are only fixed until {s.fx_valid_until.isoformat()}."))

    vehicle = next((v for v in book.vehicles if v.min_travellers <= party.group_size <= v.max_travellers), None)
    if vehicle is None and not any(r.code == "GROUP_TOO_LARGE" for r in reasons):
        reasons.append(FlagReason("NO_VEHICLE_RATE", f"No vehicle covers a group of {party.group_size}."))

    for label, value in (("guide fee", tour.guide_per_day), ("adult entrance", tour.entrance_adult),
                         ("meals", tour.meals_per_adult_day)):
        if value is None:
            reasons.append(FlagReason("MISSING_TOUR_RATE", f"{tour_id} has no {label} in the workbook."))
    if party.children and tour.entrance_child is None:
        reasons.append(FlagReason("MISSING_TOUR_RATE", f"{tour_id} has no child entrance fee."))

    # ---- hotels, night by night (night 1 = start date)
    adults = party.paying_adults
    doubles, singles, beds = adults // 2, adults % 2, party.children
    nights: list[NightDetail] = []
    for i, hotel_id in enumerate(tour.hotels_by_night):
        night_date = start_date + timedelta(days=i)
        rows = [r for r in book.hotel_rows(hotel_id) if r.covers(night_date)]
        name = book.hotel_name(hotel_id)
        if not book.hotel_rows(hotel_id):
            reasons.append(FlagReason("UNKNOWN_HOTEL", f"Night {i + 1}: hotel {hotel_id} is not in the Hotels tab."))
            continue
        if not rows:
            reasons.append(FlagReason("HOTEL_RATE_MISSING", f"Night {i + 1} ({night_date.isoformat()}): no {name} rate covers this date (expired or not loaded)."))
            continue
        if len(rows) > 1:
            reasons.append(FlagReason("RATE_CONFLICT", f"Night {i + 1} ({night_date.isoformat()}): {name} has {len(rows)} conflicting rates (rows {', '.join(str(r.row) for r in rows)})."))
            continue
        r = rows[0]
        missing = []
        if doubles and r.double_lkr is None:
            missing.append("double room")
        if singles and r.single_lkr is None:
            missing.append("single room")
        if beds and r.extra_bed_lkr is None:
            missing.append("child extra bed")
        if missing:
            reasons.append(FlagReason("HOTEL_RATE_MISSING", f"Night {i + 1} ({night_date.isoformat()}): {name} has no {', '.join(missing)} rate."))
            continue
        lkr = doubles * (r.double_lkr or 0) + singles * (r.single_lkr or 0) + beds * (r.extra_bed_lkr or 0)
        nights.append(NightDetail(i + 1, night_date, hotel_id, name, r.season, doubles, singles, beds, Fraction(lkr)))

    if reasons:
        # Collapse repeats (e.g. the same expired hotel on six nights) into one reason, keeping order.
        seen, unique = set(), []
        for reason in reasons:
            key = (reason.code, reason.detail.split("): ", 1)[-1])
            if key not in seen:
                seen.add(key)
                unique.append(reason)
        return flag(*unique)

    assert vehicle is not None
    days = tour.days
    lines = [
        CostLine("Guide", tour.guide_per_day * days),
        CostLine(f"Vehicle ({vehicle.name.lower()})", vehicle.lkr_per_day * days),
        CostLine("Entrance", tour.entrance_adult * adults + (tour.entrance_child or 0) * party.children),
        CostLine("Meals", tour.meals_per_adult_day * days * (adults + Fraction(1, 2) * party.children)),
    ]
    if nights:
        lines.append(CostLine("Hotels", sum((n.lkr for n in nights), Fraction(0))))
    total_lkr = sum((line.lkr for line in lines), Fraction(0))
    total_usd = total_lkr / s.fx_lkr_per_usd

    if tour_id in overrides.margin_by_tour:
        margin = overrides.margin_by_tour[tour_id]
    elif tour.is_day_tour:
        margin = overrides.margin_day if overrides.margin_day is not None else s.margin_day
    else:
        margin = overrides.margin_multi if overrides.margin_multi is not None else s.margin_multi

    sell = total_usd / (1 - margin)
    price = round_up_to(sell, s.round_up_to_usd)

    days_to_start = (start_date - today).days
    if tour.is_day_tour or days_to_start <= s.full_payment_within_days:
        deposit, in_full, balance_due = price, True, None
    else:
        deposit = int(math.ceil(price * s.deposit_pct_multi))
        in_full, balance_due = False, start_date - timedelta(days=s.full_payment_within_days)

    return Quote(
        status="priced", tour_id=tour_id, tour_name=tour.name, start_date=start_date, end_date=end_date,
        party=party, vehicle=vehicle.name, cost_lines=tuple(lines), nights=tuple(nights),
        total_cost_lkr=total_lkr, total_cost_usd=total_usd, margin=margin,
        price_usd=price, deposit_usd=deposit, pay_in_full=in_full, balance_due=balance_due,
    )

"""Loads the sales team's costing workbook *as-is* and normalises it.

The workbook is deliberately imperfect. Instead of hand-editing it we parse
defensively and record every oddity as a DataIssue, which the staff page shows.
Nothing here guesses a value: an unparseable or missing number stays None and
the pricing engine turns that into a "specialist will confirm" flag.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

import openpyxl


@dataclass(frozen=True)
class DataIssue:
    sheet: str
    cell: str
    kind: str
    message: str


@dataclass(frozen=True)
class RateSettings:
    fx_lkr_per_usd: Fraction
    fx_valid_until: date | None
    margin_day: Fraction
    margin_multi: Fraction
    deposit_pct_multi: Fraction
    full_payment_within_days: int
    max_group_size: int
    round_up_to_usd: int


@dataclass(frozen=True)
class TourRate:
    tour_id: str          # normalised, e.g. "T13"
    raw_id: str           # as written in the workbook, e.g. "T-13"
    name: str
    tour_type: str        # "Day tour" | "Multi-day"
    days: int
    nights: int
    guide_per_day: Fraction | None
    entrance_adult: Fraction | None
    entrance_child: Fraction | None
    meals_per_adult_day: Fraction | None
    hotels_by_night: tuple[str, ...]
    notes: str | None

    @property
    def is_day_tour(self) -> bool:
        return self.tour_type.strip().lower().startswith("day")


@dataclass(frozen=True)
class HotelRate:
    hotel_id: str
    name: str
    season: str
    valid_from: date | None
    valid_to: date | None
    double_lkr: Fraction | None   # always converted to LKR
    single_lkr: Fraction | None
    extra_bed_lkr: Fraction | None
    currency: str                 # currency the row was written in
    notes: str | None
    row: int

    def covers(self, night: date) -> bool:
        return self.valid_from is not None and self.valid_to is not None and self.valid_from <= night <= self.valid_to


@dataclass(frozen=True)
class Vehicle:
    name: str
    min_travellers: int
    max_travellers: int
    lkr_per_day: Fraction


@dataclass
class RateBook:
    settings: RateSettings
    tours: dict[str, TourRate]
    hotels: list[HotelRate]
    vehicles: list[Vehicle]
    seasons: list[tuple[str, date, date]]
    issues: list[DataIssue] = field(default_factory=list)

    def hotel_rows(self, hotel_id: str) -> list[HotelRate]:
        return [h for h in self.hotels if h.hotel_id == hotel_id]

    def hotel_name(self, hotel_id: str) -> str:
        rows = self.hotel_rows(hotel_id)
        return rows[0].name if rows else hotel_id

    def season_for(self, day: date) -> str | None:
        for name, start, end in self.seasons:
            if start <= day <= end:
                return name
        return None


# ---------------------------------------------------------------- parsing helpers

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def normalise_tour_id(raw: str) -> str:
    """'T-13' -> 'T13', ' t01 ' -> 'T01'."""
    return re.sub(r"[^A-Z0-9]", "", str(raw).upper())


def _parse_money(value, sheet: str, cell: str, issues: list[DataIssue]) -> Fraction | None:
    if value is None or (isinstance(value, str) and value.strip() in ("", "–", "-")):
        return None
    if isinstance(value, bool):
        issues.append(DataIssue(sheet, cell, "bad_number", f"Boolean {value!r} where a number was expected; treated as missing."))
        return None
    if isinstance(value, (int, float)):
        return Fraction(str(value))
    if isinstance(value, str):
        match = _NUM_RE.search(value)
        if match:
            parsed = Fraction(match.group(0).replace(",", ""))
            issues.append(DataIssue(sheet, cell, "text_number", f"Number stored as text {value!r}; read as {parsed}."))
            return parsed
    issues.append(DataIssue(sheet, cell, "bad_number", f"Could not read {value!r} as a number; treated as missing."))
    return None


def _parse_date(value, sheet: str, cell: str, issues: list[DataIssue]) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
            try:
                parsed = datetime.strptime(text, fmt).date()
            except ValueError:
                continue
            issues.append(DataIssue(sheet, cell, "text_date", f"Date stored as text {value!r}; read as {parsed.isoformat()} (day first, as used in Sri Lanka)."))
            return parsed
    issues.append(DataIssue(sheet, cell, "bad_date", f"Could not read {value!r} as a date; row ignored for pricing."))
    return None


def _header_index(row) -> dict[str, int]:
    return {str(c.value).strip(): i for i, c in enumerate(row) if c.value is not None}


def _find(headers: dict[str, int], startswith: str) -> int:
    for name, idx in headers.items():
        if name.lower().startswith(startswith.lower()):
            return idx
    raise KeyError(f"Column starting with {startswith!r} not found in {list(headers)}")


# ---------------------------------------------------------------- sheet loaders

def _load_settings(ws, issues) -> RateSettings:
    values: dict[str, tuple] = {}
    for row in ws.iter_rows(min_row=2):
        if row[0].value is None:
            continue
        key = str(row[0].value).strip().lower().replace("–", "-").replace("—", "-")
        values[key] = (row[1].value, row[2].value if len(row) > 2 else None, row[1].coordinate)

    def get(prefix: str):
        for key, val in values.items():
            if key.startswith(prefix):
                return val
        raise KeyError(prefix)

    fx_value, fx_note, fx_cell = get("fx rate")
    fx_valid_until = None
    if fx_note:
        m = re.search(r"until\s+(\d{1,2}\s+\w+\s+\d{4})", str(fx_note))
        if m:
            for fmt in ("%d %b %Y", "%d %B %Y"):
                try:
                    fx_valid_until = datetime.strptime(m.group(1), fmt).date()
                    break
                except ValueError:
                    pass

    def num(prefix):
        value, _, cell = get(prefix)
        parsed = _parse_money(value, "Settings", cell, issues)
        if parsed is None:
            raise ValueError(f"Settings value {prefix!r} is missing; cannot price anything.")
        return parsed

    return RateSettings(
        fx_lkr_per_usd=num("fx rate"),
        fx_valid_until=fx_valid_until,
        margin_day=num("margin - day"),
        margin_multi=num("margin - multi"),
        deposit_pct_multi=num("deposit"),
        full_payment_within_days=int(num("full payment")),
        max_group_size=int(num("max group")),
        round_up_to_usd=int(num("round")),
    )


def _load_seasons(ws, issues):
    seasons = []
    for row in ws.iter_rows(min_row=2):
        if row[0].value is None:
            continue
        start = _parse_date(row[1].value, "Seasons", row[1].coordinate, issues)
        end = _parse_date(row[2].value, "Seasons", row[2].coordinate, issues)
        if start and end:
            seasons.append((str(row[0].value).strip(), start, end))
    return seasons


def _load_tours(ws, issues) -> dict[str, TourRate]:
    rows = list(ws.iter_rows())
    headers = _header_index(rows[0])
    c_id, c_name, c_type = _find(headers, "Tour ID"), _find(headers, "Tour"), _find(headers, "Type")
    # "Tour" also matches "Tour ID"; pick the exact column instead.
    c_name = headers.get("Tour", c_name)
    c_days, c_nights = _find(headers, "Days"), _find(headers, "Nights")
    c_guide, c_ent_a, c_ent_c = _find(headers, "Guide"), _find(headers, "Entrance adult"), _find(headers, "Entrance child")
    c_meals, c_hotels, c_notes = _find(headers, "Meals"), _find(headers, "Hotels"), _find(headers, "Notes")

    tours: dict[str, TourRate] = {}
    for row in rows[1:]:
        raw_id = row[c_id].value
        if raw_id is None:
            continue
        raw_id = str(raw_id).strip()
        tour_id = normalise_tour_id(raw_id)
        if tour_id != raw_id:
            issues.append(DataIssue("Tours", row[c_id].coordinate, "id_format", f"Tour ID {raw_id!r} normalised to {tour_id!r} to match the content pages."))
        hotels_raw = row[c_hotels].value
        hotels: tuple[str, ...] = ()
        if hotels_raw and str(hotels_raw).strip() not in ("–", "-"):
            hotels = tuple(h.strip() for h in str(hotels_raw).split(",") if h.strip())
        nights = int(row[c_nights].value or 0)
        if len(hotels) != nights:
            issues.append(DataIssue("Tours", row[c_hotels].coordinate, "hotel_count", f"{tour_id}: {nights} nights but {len(hotels)} hotels listed."))
        sheet = "Tours"
        tours[tour_id] = TourRate(
            tour_id=tour_id,
            raw_id=raw_id,
            name=str(row[c_name].value).strip(),
            tour_type=str(row[c_type].value).strip(),
            days=int(row[c_days].value),
            nights=nights,
            guide_per_day=_parse_money(row[c_guide].value, sheet, row[c_guide].coordinate, issues),
            entrance_adult=_parse_money(row[c_ent_a].value, sheet, row[c_ent_a].coordinate, issues),
            entrance_child=_parse_money(row[c_ent_c].value, sheet, row[c_ent_c].coordinate, issues),
            meals_per_adult_day=_parse_money(row[c_meals].value, sheet, row[c_meals].coordinate, issues),
            hotels_by_night=hotels,
            notes=str(row[c_notes].value).strip() if row[c_notes].value else None,
        )
    return tours


def _load_hotels(ws, fx: Fraction, issues) -> list[HotelRate]:
    rows = list(ws.iter_rows())
    header_row = next(i for i, r in enumerate(rows) if r[0].value and str(r[0].value).strip() == "Hotel ID")
    headers = _header_index(rows[header_row])
    c_id, c_name, c_season = _find(headers, "Hotel ID"), headers["Hotel"], _find(headers, "Season")
    c_from, c_to = _find(headers, "Valid from"), _find(headers, "Valid to")
    c_dbl, c_sgl, c_bed, c_notes = _find(headers, "Double"), _find(headers, "Single"), _find(headers, "Extra bed"), _find(headers, "Notes")

    hotels: list[HotelRate] = []
    for row in rows[header_row + 1:]:
        if row[c_id].value is None:
            continue
        sheet = "Hotels"
        notes = str(row[c_notes].value).strip() if row[c_notes].value else None
        currency = "USD" if notes and re.search(r"\bUSD\b", notes) else "LKR"
        dbl = _parse_money(row[c_dbl].value, sheet, row[c_dbl].coordinate, issues)
        sgl = _parse_money(row[c_sgl].value, sheet, row[c_sgl].coordinate, issues)
        bed = _parse_money(row[c_bed].value, sheet, row[c_bed].coordinate, issues)
        if currency == "USD":
            issues.append(DataIssue(sheet, f"A{row[0].row}", "currency", f"{row[c_id].value} {row[c_season].value}: rates are in USD ({notes}); converted to LKR at the fixed FX rate."))
            dbl, sgl, bed = (v * fx if v is not None else None for v in (dbl, sgl, bed))
        if sgl is None:
            issues.append(DataIssue(sheet, row[c_sgl].coordinate, "missing_rate", f"{row[c_id].value} {row[c_season].value}: no single-room rate. Odd-adult bookings are sent to a specialist."))
        hotels.append(HotelRate(
            hotel_id=str(row[c_id].value).strip(),
            name=str(row[c_name].value).strip(),
            season=str(row[c_season].value).strip(),
            valid_from=_parse_date(row[c_from].value, sheet, row[c_from].coordinate, issues),
            valid_to=_parse_date(row[c_to].value, sheet, row[c_to].coordinate, issues),
            double_lkr=dbl, single_lkr=sgl, extra_bed_lkr=bed,
            currency=currency, notes=notes, row=row[0].row,
        ))

    # Overlapping validity windows for the same hotel = conflicting contracts.
    for i, a in enumerate(hotels):
        for b in hotels[i + 1:]:
            if a.hotel_id == b.hotel_id and a.valid_from and a.valid_to and b.valid_from and b.valid_to:
                if a.valid_from <= b.valid_to and b.valid_from <= a.valid_to:
                    issues.append(DataIssue("Hotels", f"rows {a.row} & {b.row}", "rate_conflict",
                                            f"{a.hotel_id} has overlapping rates {a.valid_from}..{a.valid_to} and {b.valid_from}..{b.valid_to}. Nights in the overlap are sent to a specialist."))
    return hotels


def _load_transport(ws, issues) -> list[Vehicle]:
    vehicles = []
    for row in ws.iter_rows(min_row=2):
        if row[0].value is None:
            continue
        rate = _parse_money(row[3].value, "Transport", row[3].coordinate, issues)
        if rate is None:
            continue
        vehicles.append(Vehicle(str(row[0].value).strip(), int(row[1].value), int(row[2].value), rate))
    return vehicles


def load_ratebook(path: Path) -> RateBook:
    # read_only=False so we can see cell coordinates; data_only=True to read cached formula results.
    wb = openpyxl.load_workbook(path, data_only=True)
    issues: list[DataIssue] = []
    settings = _load_settings(wb["Settings"], issues)
    book = RateBook(
        settings=settings,
        tours=_load_tours(wb["Tours"], issues),
        hotels=_load_hotels(wb["Hotels"], settings.fx_lkr_per_usd, issues),
        vehicles=_load_transport(wb["Transport"], issues),
        seasons=_load_seasons(wb["Seasons"], issues),
        issues=issues,
    )
    for tour in book.tours.values():
        if tour.notes and re.search(r"not launched", tour.notes, re.I):
            issues.append(DataIssue("Tours", tour.raw_id, "not_launched", f"{tour.tour_id}: '{tour.notes}' – never quoted."))
    return book

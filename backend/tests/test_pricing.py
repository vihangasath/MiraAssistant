"""Unit tests for the deterministic pricing function.

Expected numbers come from (a) the eval seed, (b) the sales team's sample quotes
and (c) hand calculations written out in the comments, so a reviewer can check
each one against the READ ME rules without running code.
"""
from __future__ import annotations

from datetime import date
from fractions import Fraction

import pytest

from mira.catalog import Catalog
from mira.config import settings
from mira.data.rates_loader import load_ratebook, normalise_tour_id
from mira.pricing.engine import Party, PricingOverrides, price_tour, round_up_to

TODAY = date(2026, 11, 19)


@pytest.fixture(scope="module")
def book():
    return load_ratebook(settings.rate_workbook)


@pytest.fixture(scope="module")
def catalog():
    return Catalog(today=TODAY)


def priced(book, tour, start, party, today=TODAY, overrides=None):
    result = price_tour(book, tour, start, party, today, overrides)
    assert result.status == "priced", getattr(result, "reasons", result)
    return result


def flagged(book, tour, start, party, today=TODAY):
    result = price_tour(book, tour, start, party, today)
    assert result.status == "needs_specialist", result
    return {r.code for r in result.reasons}


# ---------------------------------------------------------------- eval seed + sample quotes

def test_s02_q1041_sigiriya_day_tour_two_adults(book):
    # 9,000 + 18,000 + 2×16,500 + 2×3,000 = 66,000 LKR = 220 USD; 220/0.7 = 314.29 -> 315; day tour pays in full
    q = priced(book, "T01", date(2027, 1, 10), Party(2))
    assert q.total_cost_lkr == 66_000
    assert (q.price_usd, q.deposit_usd) == (315, 315)
    assert q.pay_in_full


def test_s13_q1042_cultural_triangle_two_adults(book):
    q = priced(book, "T09", date(2027, 5, 3), Party(2))
    lines = {c.label: c.lkr for c in q.cost_lines}
    assert lines == {"Guide": 66_500, "Vehicle (car)": 126_000, "Entrance": 76_000, "Meals": 63_000, "Hotels": 146_000}
    assert (q.price_usd, q.deposit_usd) == (2125, 532)


def test_s13_cultural_triangle_four_adults_uses_van_and_two_doubles(book):
    q = priced(book, "T09", date(2027, 5, 3), Party(4))
    assert q.vehicle == "Van"
    assert all(n.doubles == 2 and n.singles == 0 for n in q.nights)
    assert (q.price_usd, q.deposit_usd) == (3640, 910)


def test_s03_family_includes_child_extra_beds(book):
    # Sample quote Q-1043 says USD 2,680 but forgot the children's extra beds
    # (2 kids × (4,500×2 + 6,000×2 + 5,500×2) = 64,000 LKR). Eval seed expects 2,965.
    q = priced(book, "T09", date(2027, 4, 12), Party(2, (7, 10)))
    lines = {c.label: c.lkr for c in q.cost_lines}
    assert lines["Hotels"] == 146_000 + 64_000
    assert lines["Meals"] == 94_500  # children pay 50% of adult meals
    assert lines["Entrance"] == 114_000
    assert q.total_cost_lkr == 667_000
    assert (q.price_usd, q.deposit_usd) == (2965, 742)


def test_q1044_highlights_within_30_days_pays_in_full(book):
    # Starts 1 Dec 2026, 12 days after "today" -> full payment.
    q = priced(book, "T08", date(2026, 12, 1), Party(2))
    assert q.total_cost_lkr == 563_000
    assert (q.price_usd, q.deposit_usd) == (2505, 2505)
    assert q.pay_in_full and q.balance_due is None


def test_s15_infant_is_free_and_has_no_seat(book):
    q = priced(book, "T05", date(2027, 3, 15), Party(2, (1,)))
    assert q.party.group_size == 2 and q.party.infants == 1
    assert q.total_cost_lkr == 57_000
    assert (q.price_usd, q.deposit_usd) == (275, 275)


# ---------------------------------------------------------------- flags: never guess

def test_s04_solo_on_treasures_needs_single_rate_that_is_missing(book):
    assert "HOTEL_RATE_MISSING" in flagged(book, "T12", date(2027, 4, 10), Party(1))


def test_s05_mirissa_villas_rates_expired(book):
    assert flagged(book, "T11", date(2027, 1, 20), Party(2)) == {"HOTEL_RATE_MISSING"}


def test_s06_tour_without_rates(book):
    assert flagged(book, "T10", date(2027, 2, 10), Party(2)) == {"NO_RATES_FOR_TOUR"}


def test_hotel_suisse_overlapping_peak_rows_are_a_conflict(book):
    assert "RATE_CONFLICT" in flagged(book, "T07", date(2027, 2, 10), Party(2))


def test_hotel_suisse_before_overlap_is_priced(book):
    # 15–31 Dec 2026 is covered only by the original Peak row.
    q = priced(book, "T07", date(2026, 12, 20), Party(2))
    assert all(n.lkr == 30_000 for n in q.nights)


def test_trip_ending_after_fx_validity_is_flagged(book):
    assert "RATES_EXPIRED" in flagged(book, "T01", date(2027, 11, 5), Party(2))


def test_multiday_trip_running_past_rate_end_is_flagged(book):
    # Starts 28 Oct 2027, nights run into November where no hotel rate exists.
    codes = flagged(book, "T09", date(2027, 10, 28), Party(2))
    assert {"RATES_EXPIRED", "HOTEL_RATE_MISSING"} <= codes


def test_group_over_20_goes_to_sales(book):
    assert "GROUP_TOO_LARGE" in flagged(book, "T01", date(2027, 2, 1), Party(21))


def test_draft_tour_never_quoted(book):
    assert flagged(book, "T15", date(2027, 5, 10), Party(2)) == {"TOUR_NOT_LAUNCHED"}


# ---------------------------------------------------------------- workbook quirks

def test_t13_id_normalised_and_usd_hotel_converted(book):
    # Guide 77,000 + car 126,000 + entrance 90,000 + meals 63,000
    # + hotels 2×22,000 + 4×(USD 125 × 300) = 194,000  => 550,000 LKR = 1,833.33 USD
    # 1,833.33 / 0.75 = 2,444.44 -> 2,445; deposit 25% = 611.25 -> 612
    assert normalise_tour_id("T-13") == "T13"
    q = priced(book, "T13", date(2027, 5, 10), Party(2))
    assert q.total_cost_lkr == 550_000
    assert (q.price_usd, q.deposit_usd) == (2445, 612)


def test_text_number_and_text_date_cells_are_parsed(book):
    h02 = [h for h in book.hotel_rows("H02") if h.season == "Shoulder"]
    assert all(h.double_lkr == 28_000 for h in h02)
    h08_peak = next(h for h in book.hotel_rows("H08") if h.season == "Peak")
    assert h08_peak.valid_from == date(2026, 12, 15)
    kinds = {i.kind for i in book.issues}
    assert {"text_number", "text_date", "currency", "rate_conflict", "id_format"} <= kinds


# ---------------------------------------------------------------- rules

def test_odd_adult_takes_single_room(book):
    q = priced(book, "T09", date(2027, 5, 3), Party(3))
    assert all(n.doubles == 1 and n.singles == 1 for n in q.nights)


def test_child_aged_12_pays_adult_rates(book):
    a = priced(book, "T01", date(2027, 1, 10), Party(2, (12,)))
    b = priced(book, "T01", date(2027, 1, 10), Party(3))
    assert a.price_usd == b.price_usd


def test_child_aged_2_pays_child_rates(book):
    q = priced(book, "T01", date(2027, 1, 10), Party(2, (2,)))
    lines = {c.label: c.lkr for c in q.cost_lines}
    assert lines["Entrance"] == 2 * 16_500 + 8_250
    assert lines["Meals"] == 3_000 * 2.5


def test_vehicle_bands(book):
    assert priced(book, "T01", date(2027, 1, 10), Party(3)).vehicle == "Car"
    assert priced(book, "T01", date(2027, 1, 10), Party(2, (5, 6))).vehicle == "Van"
    assert priced(book, "T01", date(2027, 1, 10), Party(9)).vehicle == "Mini coach"
    assert priced(book, "T01", date(2027, 1, 10), Party(20)).vehicle == "Mini coach"


def test_deposit_boundary_30_days(book):
    # 30 days before start -> pay in full; 31 days -> 25% deposit.
    in_full = priced(book, "T08", date(2026, 12, 19), Party(2))
    deposit = priced(book, "T08", date(2026, 12, 20), Party(2))
    assert in_full.pay_in_full and in_full.deposit_usd == in_full.price_usd
    assert not deposit.pay_in_full
    assert deposit.deposit_usd == -(-deposit.price_usd * 25 // 100)


def test_round_up_to_five():
    assert round_up_to(Fraction(31429, 100), 5) == 315
    assert round_up_to(Fraction(315), 5) == 315   # exact multiples stay
    assert round_up_to(Fraction(31501, 100), 5) == 320


def test_gross_profit_is_on_selling_price(book):
    q = priced(book, "T01", date(2027, 1, 10), Party(2))
    assert q.gross_profit_pct == (Fraction(315) - Fraction(220)) / 315
    assert q.gross_profit_pct >= Fraction(30, 100)  # rounding up never lowers the margin


def test_traveller_view_has_no_costs_or_margin(book):
    view = priced(book, "T09", date(2027, 5, 3), Party(2)).traveller_view()
    assert not any(k in view for k in ("total_cost_lkr", "margin", "gross_profit_pct", "cost_lines_lkr"))
    assert view["price_usd"] == 2125 and view["deposit_usd"] == 532


def test_margin_override_is_applied(book):
    q = priced(book, "T01", date(2027, 1, 10), Party(2), overrides=PricingOverrides(margin_day=Fraction(35, 100)))
    # 220 / 0.65 = 338.46 -> 340
    assert q.price_usd == 340


def test_invalid_requests(book):
    assert price_tour(book, "T01", date(2026, 11, 1), Party(2), TODAY).status == "invalid"
    assert price_tour(book, "T01", date(2027, 1, 10), Party(0, (5,)), TODAY).status == "invalid"


# ---------------------------------------------------------------- catalog-level checks

def test_catalog_flags_duration_mismatch(catalog):
    r = catalog.quote("T06", date(2027, 2, 10), Party(2))
    assert r.status == "needs_specialist" and r.reasons[0].code == "CONTENT_RATE_MISMATCH"


def test_catalog_flags_stale_offer(catalog):
    r = catalog.quote("T14", date(2027, 2, 10), Party(2))
    assert r.status == "needs_specialist" and r.reasons[0].code == "STALE_OFFER"


def test_catalog_unknown_tour(catalog):
    assert catalog.quote("T99", date(2027, 2, 10), Party(2)).status == "invalid"

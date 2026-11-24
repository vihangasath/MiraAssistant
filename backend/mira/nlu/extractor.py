"""Rule-based slot extraction (no LLM).

Pulls the trip slots Mira needs out of one traveller message: tour, party, children's ages, dates, duration,
places. It is deliberately conservative: whenever something looks like a slot but cannot be read with
certainty ("next month", "the kids", "the second one"), it records an `ambiguity` so the caller hands the
turn to Gemini instead of guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
NUMBER_WORDS.update({"thirty": 30, "forty": 40})
_NUM = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"

MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
_MONTH = r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")"

# Tour aliases. Longest match wins; two different tours in one message is an ambiguity.
TOUR_ALIASES: dict[str, list[str]] = {
    "T01": ["sigiriya and minneriya day tour", "sigiriya and minneriya", "sigiriya day tour", "sigiriya day trip"],
    "T02": ["kandy city tour"],
    "T03": ["colombo city tour"],
    "T04": ["galle fort walking tour", "galle fort tour", "galle fort walk"],
    "T05": ["whale and dolphin watching", "whale and dolphin", "whale watching", "dolphin watching"],
    "T06": ["train and day tour from kandy to nuwara eliya", "kandy to nuwara eliya train", "train and day tour"],
    "T07": ["kandy heritage stay"],
    "T08": ["highlights of sri lanka"],
    "T09": ["cultural triangle sri lanka package", "cultural triangle package"],
    "T10": ["instafamous sri lanka", "instafamous"],
    "T11": ["sri lanka beach stay mirissa", "beach stay mirissa", "beach stay in mirissa", "sri lanka beach stay"],
    "T12": ["treasures of sri lanka"],
    "T13": ["wildlife photography tour", "wildlife photography"],
    "T14": ["popular stays winter", "popular stays", "winter early bird", "early bird deal"],
    "T16": ["cultural triangle tour"],
}
_AMBIGUOUS_TOUR_PHRASES = [r"\bcultural triangle\b"]   # only counts when no alias above matched

PLACES = {
    "sigiriya": "sigiriya", "minneriya": "minneriya", "kandy": "kandy", "nuwara eliya": "nuwara-eliya",
    "galle": "galle", "colombo": "colombo", "mirissa": "mirissa", "ella": "ella", "yala": "yala",
    "udawalawe": "udawalawe", "anuradhapura": "anuradhapura", "polonnaruwa": "polonnaruwa",
    "hikkaduwa": "hikkaduwa", "jaffna": "jaffna", "trincomalee": "trincomalee", "negombo": "negombo",
    "bentota": "bentota", "arugam bay": "arugam-bay", "dambulla": "dambulla", "unawatuna": "unawatuna",
}
INTERESTS = {
    r"\bbeach(es)?\b": "beach", r"\bwildlife\b|\bsafari\b|\belephants?\b|\bleopards?\b": "wildlife",
    r"\bwhales?\b|\bdolphins?\b": "whales", r"\bculture\b|\bcultural\b|\bheritage\b|\bhistory\b|\bancient\b": "culture",
    r"\bphotograph\w*\b": "photography", r"\btrains?\b|\brailway\b": "train", r"\bhik(e|ing)\b|\btrek\w*\b": "hiking",
    r"\btea\b": "tea", r"\bfood\b|\bcuisine\b": "food", r"\brelax\w*\b": "relaxation",
}

_CHILD_WORD = r"(kids?|child(?:ren)?|toddlers?|babies|baby|infants?|daughters?|sons?|teens?|teenagers?)"
_LIST = r"(\d{1,2}(?:\s*(?:,|and|&|\+)\s*(?:and\s+)?\d{1,2})*)"
_FUTURE_WORDS = re.compile(r"\b(next|this|coming|tomorrow|tonight|weekend|christmas|new year|easter|soon|later|"
                           r"in (a|an|\d+) (week|weeks|month|months|day|days)|end of|beginning of|(early|late|mid)[- ]" + _MONTH + r")\b", re.I)


@dataclass
class Extraction:
    tour_id: str | None = None
    trip_type: str | None = None
    traveller_type: str | None = None
    adults: int | None = None
    child_ages: list[int] | None = None
    start_date: str | None = None
    duration_days: int | None = None
    destinations: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    wants_price: bool = False
    mentions_children: bool = False
    ambiguities: list[str] = field(default_factory=list)

    def slots(self) -> dict:
        return {"tour_id": self.tour_id, "trip_type": self.trip_type, "traveller_type": self.traveller_type,
                "adults": self.adults, "child_ages": self.child_ages, "start_date": self.start_date,
                "duration_days": self.duration_days, "destinations": self.destinations, "interests": self.interests,
                "wants_price": self.wants_price}


def _num(tok: str) -> int | None:
    tok = tok.lower()
    return int(tok) if tok.isdigit() else NUMBER_WORDS.get(tok)


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("–", "-")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9'/:+&,.\- ]", " ", text))


def _extract_tour(text: str, published: set[str], out: Extraction) -> None:
    found: dict[str, tuple[int, int]] = {}
    for tid, aliases in TOUR_ALIASES.items():
        if tid not in published:
            continue
        for alias in aliases:
            m = re.search(r"\b" + re.escape(alias) + r"\b", text)
            if m and (tid not in found or m.end() - m.start() > found[tid][1] - found[tid][0]):
                found[tid] = m.span()
    for m in re.finditer(r"\bt-?(\d{2})\b", text):
        tid = f"T{m.group(1)}"
        if tid in published:
            found[tid] = m.span()
    # drop tours whose match lies inside a longer match of another tour
    for a in list(found):
        for b in found:
            if a != b and found[b][0] <= found[a][0] and found[a][1] <= found[b][1] and found[b] != found[a]:
                found.pop(a, None)
                break
    if len(found) == 1:
        out.tour_id = next(iter(found))
    elif len(found) > 1:
        out.ambiguities.append("several tours mentioned")
    elif any(re.search(p, text) for p in _AMBIGUOUS_TOUR_PHRASES):
        out.ambiguities.append("tour name is ambiguous")


def _extract_children(text: str, out: Extraction) -> None:
    ages: list[int] = []
    for m in re.finditer(r"(\d{1,2})[- ]?(?:year|yr)s?[- ]?old", text):
        ages.append(int(m.group(1)))
    for m in re.finditer(r"(\d{1,2})[- ]?months?[- ]?old", text):
        ages.append(0)
    for m in re.finditer(r"\b" + _CHILD_WORD + r"\b", text):
        out.mentions_children = True
        tail = text[m.end(): m.end() + 40]
        lm = re.match(r"\W*(?:who\s+)?(?:are|is|aged|age|ages|of ages?|:)?\s*" + _LIST, tail)
        if lm and not re.match(r"\W*\d+\s*(adults?|people|nights?|days?)", tail):
            ages += [int(x) for x in re.findall(r"\d{1,2}", lm.group(1))]
    if re.search(r"\b(baby|babies|infant|toddler)s?\b", text) and not ages:
        ages.append(0)          # "A baby with no age is age 0" (same rule as the LLM prompt)
    ages = list(dict.fromkeys(ages)) if len(set(ages)) == len(ages) else ages
    if ages:
        if any(a >= 12 for a in ages):
            out.ambiguities.append("age 12+ counts as an adult")
        out.child_ages = ages
    elif out.mentions_children:
        out.ambiguities.append("children without ages")


def _extract_adults(text: str, out: Extraction) -> None:
    m = re.search(r"\b" + _NUM + r"\s+(?:adults?|grown[- ]?ups?)\b", text)
    if m:
        out.adults = _num(m.group(1))
    elif not out.mentions_children:
        m = re.search(r"\b" + _NUM + r"\s+(?:of us|people|persons|travell?ers|guests|pax)\b", text) or \
            re.search(r"\b(?:group|party) of " + _NUM + r"\b", text) or re.search(r"\bfor " + _NUM + r"\b(?!\s*(?:days?|nights?|weeks?))", text)
        if m:
            out.adults = _num(m.group(1))
    if re.search(r"\b(just me|only me|myself|solo|by myself|on my own|travelling alone|traveling alone|just one person|for one)\b", text):
        out.traveller_type = "solo"
        out.adults = out.adults or 1
    elif re.search(r"\b(couple|my wife|my husband|my partner|girlfriend|boyfriend|honeymoon|the two of us|me and my (wife|husband|partner))\b", text) \
            and not out.mentions_children:
        out.traveller_type = "couple"
        out.adults = out.adults or 2
    elif out.mentions_children or re.search(r"\bfamily\b", text):
        out.traveller_type = "family"
    m = re.search(r"\bfamily of " + _NUM, text)
    if m and not out.adults:
        out.ambiguities.append("family size without breakdown")
    if re.search(r"\b" + _NUM + r"\s+(?:kids?|children|child)\b", text) and not out.child_ages:
        pass                      # covered by "children without ages"
    if out.adults is not None and not 0 < out.adults <= 50:
        out.adults = None
        out.ambiguities.append("implausible party size")
    if out.adults and not out.traveller_type and not out.mentions_children:
        out.traveller_type = "solo" if out.adults == 1 else "couple" if out.adults == 2 else "group"


def _extract_date(text: str, today: date, out: Extraction) -> None:
    found: list[date] = []
    spans = 0
    for pat, order in ((r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MONTH + r"\b\.?(?:,?\s+(\d{4}))?", "dm"),
                       (r"\b" + _MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?", "md")):
        for m in re.finditer(pat, text):
            spans += 1
            if order == "dm":
                d, mo, y = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
            else:
                mo, d, y = MONTHS[m.group(1)], int(m.group(2)), m.group(3)
            try:
                if y:
                    found.append(date(int(y), mo, d))
                else:
                    cand = date(today.year, mo, d)
                    found.append(cand if cand >= today else date(today.year + 1, mo, d))
            except ValueError:
                out.ambiguities.append("invalid date")
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        spans += 1
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            out.ambiguities.append("invalid date")
    if re.search(r"\b\d{1,2}[/.]\d{1,2}([/.]\d{2,4})?\b", text):
        out.ambiguities.append("numeric date")
    if _FUTURE_WORDS.search(text):
        out.ambiguities.append("relative date")
    if re.search(r"\b" + _MONTH + r"\b", text) and not spans:
        out.ambiguities.append("month without day")
    if len(set(found)) > 1:
        out.ambiguities.append("several dates")
    elif found:
        out.start_date = found[0].isoformat()


def _extract_duration(text: str, out: Extraction) -> None:
    m = re.search(r"\b" + _NUM + r"[- ](day|days|night|nights)\b", text)
    if m and _num(m.group(1)):
        n = _num(m.group(1))
        out.duration_days = n + 1 if m.group(2).startswith("night") else n
    elif re.search(r"\b(a|one|1) week\b", text):
        out.duration_days = 7
    elif re.search(r"\b(two|2) weeks\b", text):
        out.duration_days = 14


def extract(text: str, published: set[str], tour_categories: dict[str, str], today: date) -> Extraction:
    t = _norm(text)
    out = Extraction()
    _extract_tour(t, published, out)
    _extract_children(t, out)
    _extract_adults(t, out)
    _extract_date(t, today, out)
    _extract_duration(t, out)
    out.destinations = sorted({v for k, v in PLACES.items() if re.search(r"\b" + k + r"\b", t)})
    out.interests = sorted({v for pat, v in INTERESTS.items() if re.search(pat, t)})
    out.wants_price = bool(re.search(r"\b(how much|price|prices|pricing|cost|costs|quote|quotation|total|rate|rates|fee|fees)\b", t))
    if out.tour_id:
        cat = (tour_categories.get(out.tour_id) or "").lower()
        out.trip_type = "day_tour" if cat in ("day tour", "city tour") else "multi_day"
    elif re.search(r"\b(day trip|day tour|day-trip|one day|half day|a day out)\b", t):
        out.trip_type = "day_tour"
    elif re.search(r"\b(custom|tailor\w*|bespoke|own itinerary|design (my|our|a))\b", t):
        out.trip_type = "custom"
    elif out.duration_days and out.duration_days > 1 or re.search(r"\b(round trip|package|multi-day|multi day|week)\b", t):
        out.trip_type = "multi_day"
    return out

"""MCP server (bonus): lets another AI agent search, quote and enquire with the same
rules as the website. It calls the very same Catalog.quote() and Store as Mira, so
there is one pricing implementation, one flag path and one enquiry table.

Run (stdio):           uv run python -m mira.mcp_server
Run (streamable HTTP): uv run python -m mira.mcp_server --http   (http://localhost:8001/mcp)
"""
from __future__ import annotations

import sys
from datetime import date

from mcp.server.mcpserver import MCPServer

from mira.catalog import get_catalog
from mira.pricing.engine import Party
from mira.store.db import get_store
from mira.ui.builder import tour_summary

server = MCPServer(
    name="ceylon-compass",
    title="Ceylon Compass Holidays",
    instructions=("Search Ceylon Compass tours, get exact quotes from the rate workbook, and create enquiries. "
                  "Prices only ever come from get_quote. If get_quote returns needs_specialist, do not estimate a price."),
)


@server.tool()
def search_tours(query: str = "", destination: str | None = None, max_days: int | None = None) -> list[dict]:
    """Search published tours by free text, destination (e.g. 'kandy') and/or maximum length in days."""
    catalog = get_catalog()
    tours = catalog.published_tours()
    if query.strip():
        hit_ids = []
        for h in catalog.index.search(query, k=30):
            if h.chunk.doc_type == "tour" and h.chunk.doc_id not in hit_ids:
                hit_ids.append(h.chunk.doc_id)
        order = {tid: i for i, tid in enumerate(hit_ids)}
        tours = sorted([t for t in tours if t.tour_id in order], key=lambda t: order[t.tour_id])
    if destination:
        tours = [t for t in tours if destination.lower() in [d.lower() for d in t.destinations]]
    out = []
    for t in tours:
        from mira.catalog import content_days
        days = content_days(t.duration)
        if max_days and days and days > max_days:
            continue
        out.append({"tour_id": t.tour_id, "title": t.title, "category": t.category, "duration": t.duration,
                    "destinations": t.destinations, "summary": tour_summary(catalog.docs[t.tour_id]),
                    "priced_online": t.has_rates, "source": t.source})
    return out[:10]


@server.tool()
def get_quote(tour_id: str, start_date: str, adults: int, child_ages: list[int] | None = None,
              agent_name: str = "external-agent") -> dict:
    """Exact price for a tour. start_date is YYYY-MM-DD; child_ages lists every child's age (infants 0–1).
    Returns price and deposit only (never costs). Every quote is saved as a private enquiry for staff."""
    catalog = get_catalog()
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        return {"status": "invalid", "message": "start_date must be YYYY-MM-DD"}
    party = Party(int(adults), tuple(int(a) for a in child_ages or []))
    result = catalog.quote(tour_id, start, party)
    store = get_store()
    request = {"tour_id": tour_id, "start_date": start_date, "adults": party.paying_adults,
               "child_ages": list(party.child_ages), "channel": f"mcp:{agent_name}"}
    if result.status == "priced":
        staff = result.staff_view()
        ref = store.create_enquiry(visitor_id=f"mcp:{agent_name}", kind="quote", tour_id=tour_id, tour_name=result.tour_name,
                                   request=request, trace_id=None, status="new", price_usd=result.price_usd,
                                   deposit_usd=result.deposit_usd, cost_usd=staff["total_cost_usd"],
                                   gross_profit_pct=staff["gross_profit_pct"], staff_quote=staff)
        return {"status": "priced", "quote_ref": ref, **result.traveller_view()}
    if result.status == "needs_specialist":
        ref = store.create_enquiry(visitor_id=f"mcp:{agent_name}", kind="flag", tour_id=tour_id, tour_name=result.tour_name,
                                   request=request, trace_id=None, status="needs_specialist",
                                   flag_reasons=[{"code": r.code, "detail": r.detail} for r in result.reasons])
        return {"status": "needs_specialist", "reference": ref,
                "message": "No price can be given for this request; a Ceylon Compass specialist will confirm it.",
                "reason_codes": [r.code for r in result.reasons]}
    return {"status": "invalid", "code": result.code, "message": result.message}


@server.tool()
def create_enquiry(summary: str, adults: int | None = None, child_ages: list[int] | None = None,
                   start_date: str | None = None, tour_id: str | None = None, agent_name: str = "external-agent") -> dict:
    """Pass a custom request (or anything without a price) to the sales team. Do not include personal contact details."""
    from mira.privacy import scrub
    ref = get_store().create_enquiry(
        visitor_id=f"mcp:{agent_name}", kind="custom", tour_id=tour_id, tour_name="Custom request via MCP",
        request={"summary": scrub(summary)[:1000], "adults": adults, "child_ages": child_ages or [], "start_date": start_date},
        trace_id=None, status="new")
    return {"status": "received", "reference": ref, "message": "Our team will follow up on this request."}


if __name__ == "__main__":
    if "--http" in sys.argv:
        server.run(transport="streamable-http", port=8001)
    else:
        server.run()

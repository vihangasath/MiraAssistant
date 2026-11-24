"""The MCP tools use the same pricing function and rules as the website."""
import asyncio

from mira.mcp_server import create_enquiry, get_quote, search_tours, server


def test_tools_are_registered():
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"search_tours", "get_quote", "create_enquiry"} <= names


def test_search_and_quote_match_website_rules():
    assert any(t["tour_id"] == "T01" for t in search_tours("Sigiriya elephants day trip"))
    assert not any(t["tour_id"] == "T15" for t in search_tours("Jaffna"))       # drafts never exposed
    q = get_quote("T01", "2027-01-10", 2)
    assert (q["status"], q["price_usd"], q["deposit_usd"]) == ("priced", 315, 315)
    assert "total_cost_lkr" not in q and "margin" not in q
    assert get_quote("T11", "2027-01-20", 2)["status"] == "needs_specialist"
    assert create_enquiry("Ten days, Kandy and Ella", adults=2)["status"] == "received"

"""tests/test_session_store.py — per-user source tool registry lifecycle."""
from app.services import session_store as ss


class FakeTool:
    pass


class TestSessionLifecycle:
    def test_get_session_creates_isolated_scopes(self):
        s = ss.get_session("u1")
        assert s == {"url_sources": {}, "pdf_sources": {}}

    def test_sources_are_isolated_per_user(self):
        ss.register_url_tool("u1", "https://a.com", FakeTool(), "h1", "T1", "tool_u1_a")
        ss.register_url_tool("u2", "https://a.com", FakeTool(), "h2", "T2", "tool_u2_a")

        assert ss.pop_url("u2", "https://a.com") == "h2"
        # u1's registration for the same URL is untouched
        assert ss.pop_url("u1", "https://a.com") == "h1"

    def test_pop_returns_none_for_missing(self):
        assert ss.pop_url("nobody", "https://x.com") is None
        assert ss.pop_pdf("nobody", "f.pdf") is None

    def test_pop_pdf_and_clear(self):
        ss.register_pdf_tool("u3", "f.pdf", FakeTool(), "h3", "tool_u3_f")
        assert ss.pop_pdf("u3", "f.pdf") == "h3"
        assert not ss.get_all_tools("u3")

    def test_clear_session_drops_everything(self):
        ss.register_url_tool("u4", "https://b.com", FakeTool(), "h4", "T", "tool_x")
        ss.register_pdf_tool("u4", "g.pdf", FakeTool(), "h5", "tool_y")
        assert ss.has_user_session("u4")

        ss.clear_session("u4")
        assert not ss.has_user_session("u4")
        assert ss.get_all_tools("u4") == []
        assert ss.get_source_lines("u4") == []

    def test_get_all_tools_lists_both_types(self):
        ss.clear_session("u5")
        t_url, t_pdf = FakeTool(), FakeTool()
        ss.register_url_tool("u5", "https://c.com", t_url, "h6", "T", "tool_a")
        ss.register_pdf_tool("u5", "h.pdf", t_pdf, "h7", "tool_b")
        assert set(ss.get_all_tools("u5")) == {t_url, t_pdf}

    def test_source_lines_render(self):
        ss.clear_session("u6")
        ss.register_url_tool("u6", "https://d.com", FakeTool(), "h8", "My Page", "tool_p")
        lines = ss.get_source_lines("u6")
        assert len(lines) == 1 and "My Page" in lines[0] and "https://d.com" in lines[0]

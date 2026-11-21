import pandas as pd

from retail_pipeline.reports import bars_html, money, pct, render_page, table_html


def test_formatters():
    assert money(1234.5) == "$1,234" or money(1234.5) == "$1,235"
    assert pct(12.34) == "+12.3%" and pct(float("nan")) == "-"


def test_html_is_escaped():
    html = table_html(pd.DataFrame({"name": ["<script>alert(1)</script>"]}))
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_page_and_bars_render():
    bars = bars_html(pd.DataFrame({"d": ["a", "b"], "v": [10.0, 5.0]}), "d", "v")
    page = render_page("T", "sub", [("k", "v")], [("Section", bars)])
    assert "width:100%" in bars and "width:50%" in bars and "<h2>Section</h2>" in page


def test_empty_table_message():
    assert "No rows" in table_html(pd.DataFrame())

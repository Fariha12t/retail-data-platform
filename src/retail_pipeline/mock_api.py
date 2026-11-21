"""A tiny stand-in for a marketing-platform REST API (stdlib only).

GET /v1/marketing/spend?start=YYYY-MM-DD&end=YYYY-MM-DD   (end is exclusive)

Data is generated deterministically per date. Set MOCK_API_FLAKY=0.2 to make 20% of calls
return HTTP 503 so you can watch the retry logic work. A few rows are deliberately dirty
(duplicates, non-numeric spend) to exercise validation.
"""
from __future__ import annotations

import json
import os
import random
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

CAMPAIGNS = {
    "paid_search": ["brand_search", "generic_search"],
    "social": ["reels_awareness", "retargeting"],
    "email": ["newsletter"],
    "affiliate": ["partner_network"],
}


def rows_for_day(day: date) -> list[dict]:
    rng = random.Random(f"mkt-{day.isoformat()}")
    weekend = 0.85 if day.weekday() >= 5 else 1.0
    rows = []
    for channel, campaigns in CAMPAIGNS.items():
        for campaign in campaigns:
            base = {"paid_search": 1800, "social": 1300, "email": 250, "affiliate": 700}[channel]
            spend = round(base * weekend * rng.uniform(0.75, 1.25), 2)
            cpc = rng.uniform(0.35, 1.1)
            clicks = int(spend / cpc)
            impressions = int(clicks / rng.uniform(0.012, 0.04))
            rows.append(
                {
                    "spend_date": day.isoformat(), "channel": channel, "campaign": campaign,
                    "impressions": impressions, "clicks": clicks, "spend": spend, "currency": "USD",
                }
            )
    # dirty data: duplicate row (API retries upstream) and an unparseable spend value
    if rng.random() < 0.15:
        rows.append(dict(rows[0]))
    if rng.random() < 0.08:
        rows.append({**rows[1], "campaign": "broken_feed", "spend": "n/a"})
    return rows


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/health":
            return self._send(200, {"status": "ok"})
        if url.path != "/v1/marketing/spend":
            return self._send(404, {"error": "not found"})
        if random.random() < float(os.environ.get("MOCK_API_FLAKY", "0")):
            return self._send(503, {"error": "temporarily unavailable"})
        q = parse_qs(url.query)
        try:
            start = date.fromisoformat(q["start"][0])
            end = date.fromisoformat(q["end"][0])
        except (KeyError, ValueError):
            return self._send(400, {"error": "start and end (YYYY-MM-DD) are required"})
        data, day = [], start
        while day < end:
            data.extend(rows_for_day(day))
            day += timedelta(days=1)
        self._send(200, {"data": data})

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):  # keep the console quiet
        pass


def serve(host: str = "0.0.0.0", port: int = 8000) -> HTTPServer:  # noqa: S104
    return HTTPServer((host, port), Handler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"mock marketing API on :{port}")
    serve(port=port).serve_forever()

"""Synthetic source systems for the demo: an operational Postgres DB plus CSV drops.

`seed_history` builds N days of history; `simulate_day` then advances the world by one day
(new orders, status changes, customer profile changes, price changes, stock movements) so the
incremental pipeline and the SCD Type 2 dimensions have something real to capture.
A small share of records is intentionally dirty (duplicates, bad values) - see docs/DATA_QUALITY.md.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

CHANNELS = ["organic", "paid_search", "social", "email", "affiliate"]
CHANNEL_W = [0.35, 0.25, 0.20, 0.10, 0.10]
METHODS = ["card", "upi", "wallet", "cod", "netbanking"]
METHOD_W = [0.35, 0.35, 0.10, 0.10, 0.10]
CITIES = [
    ("Bengaluru", "IN"), ("Mumbai", "IN"), ("Delhi", "IN"), ("Hyderabad", "IN"), ("Chennai", "IN"),
    ("Dubai", "AE"), ("Riyadh", "SA"), ("Doha", "QA"), ("London", "GB"), ("Singapore", "SG"),
]
SEGMENTS = ["consumer", "premium", "business"]
SEGMENT_W = [0.75, 0.15, 0.10]
FIRST = ["Aisha", "Rohan", "Fatima", "Arjun", "Zara", "Imran", "Priya", "Kabir", "Sana", "Vikram", "Meera", "Omar",
         "Nisha", "Karan", "Layla", "Dev", "Anika", "Yusuf", "Ishaan", "Noor"]
LAST = ["Khan", "Sharma", "Iyer", "Reddy", "Patel", "Ahmed", "Nair", "Gupta", "Shaikh", "Menon", "Rao", "Das"]
CATALOGUE = {
    "Electronics": (["Zenith", "Voltix", "Nimbus"], ["Headphones", "Smartwatch", "Power Bank", "Speaker", "Webcam"], (15, 220)),
    "Home & Kitchen": (["Hearth", "Casa", "Brewly"], ["Air Fryer", "Kettle", "Blender", "Cookware Set", "Lamp"], (10, 120)),
    "Fashion": (["Loom", "Urbane", "Thread"], ["Jacket", "Sneakers", "Backpack", "Watch", "Sunglasses"], (8, 90)),
    "Beauty": (["Glow", "Pure", "Aura"], ["Serum", "Moisturiser", "Perfume", "Hair Dryer"], (5, 60)),
    "Sports": (["Stride", "Peak", "Flex"], ["Yoga Mat", "Dumbbell Set", "Running Shoes", "Water Bottle"], (6, 80)),
}
WAREHOUSES = [("BLR", 0.6), ("DXB", 0.4)]
SOURCE_TABLES = ["customers", "orders", "order_items", "payments"]
WEEKDAY = [0.95, 0.95, 1.0, 1.0, 1.1, 1.25, 1.2]


class Simulator:
    def __init__(self, engine: Engine, landing_dir: Path, seed: int = 42, base_orders: int = 70):
        self.engine = engine
        self.landing = Path(landing_dir)
        self.landing.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.base_orders = base_orders

    # ---------------------------------------------------------------- helpers
    @property
    def _state_path(self) -> Path:
        return self.landing / ".inventory_state.json"

    def _rng(self, day: date, salt: str = "") -> random.Random:
        return random.Random(f"{self.seed}-{day.isoformat()}-{salt}")

    @staticmethod
    def _ts(day: date, rng: random.Random, lo: float = 0.0, hi: float = 24.0) -> datetime:
        hour = rng.triangular(lo, hi, 20 if hi >= 20 else (lo + hi) / 2)
        return datetime.combine(day, time.min) + timedelta(hours=min(hour, 23.99))

    def _max_id(self, table: str, col: str, floor: int) -> int:
        with self.engine.connect() as c:
            return int(c.execute(text(f"select coalesce(max({col}), :f) from source.{table}"), {"f": floor}).scalar())

    def _append(self, table: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        with self.engine.begin() as c:
            df.to_sql(table, c, schema="source", if_exists="append", index=False, method="multi", chunksize=2000)

    def _products(self) -> pd.DataFrame:
        df = pd.read_csv(self.landing / "products.csv", keep_default_na=False)
        df["product_id"] = df["product_id"].astype(int)
        df["list_price"] = df["list_price"].astype(float)
        df["unit_cost"] = df["unit_cost"].astype(float)
        df["updated_at"] = pd.to_datetime(df["updated_at"])
        return df

    def latest_date(self) -> date | None:
        with self.engine.connect() as c:
            v = c.execute(text("select max(order_ts)::date from source.orders")).scalar()
        return v

    # ---------------------------------------------------------------- bootstrap
    def reset(self) -> None:
        with self.engine.begin() as c:
            for t in SOURCE_TABLES:
                c.execute(text(f"truncate source.{t}"))
        for p in self.landing.glob("inventory_*.csv"):
            p.unlink()
        for p in (self.landing / "products.csv", self._state_path):
            p.unlink(missing_ok=True)

    def _bootstrap(self, first_day: date) -> None:
        rng = random.Random(self.seed)
        rows, pid = [], 0
        for category, (brands, nouns, (lo, hi)) in CATALOGUE.items():
            for brand in brands:
                for noun in nouns:
                    pid += 1
                    price = round(rng.uniform(lo, hi), 2)
                    rows.append({
                        "product_id": pid, "sku": f"SKU-{pid:04d}", "product_name": f"{brand} {noun}",
                        "category": category, "brand": brand, "unit_cost": round(price * rng.uniform(0.45, 0.7), 2),
                        "list_price": price, "updated_at": datetime.combine(first_day, time.min),
                    })
        pd.DataFrame(rows).to_csv(self.landing / "products.csv", index=False)

        customers = []
        for i in range(1, 1201):
            city, country = rng.choice(CITIES)
            signup = first_day - timedelta(days=rng.randint(1, 400))
            first, last = rng.choice(FIRST), rng.choice(LAST)
            customers.append({
                "customer_id": i, "email": f"{first}.{last}{i}@example.com".lower(), "full_name": f"{first} {last}",
                "city": city, "country": country, "segment": rng.choices(SEGMENTS, SEGMENT_W)[0],
                "signup_date": signup, "updated_at": datetime.combine(signup, time.min),
            })
        self._append("customers", pd.DataFrame(customers))

    # ---------------------------------------------------------------- public API
    def seed_history(self, end: date, days: int) -> date:
        start = end - timedelta(days=days - 1)
        self.reset()
        self._bootstrap(start)
        for i in range(days):
            self.simulate_day(start + timedelta(days=i))
        return start

    def simulate_day(self, day: date) -> None:
        rng = self._rng(day)
        self._new_customers(day, rng)
        self._customer_changes(day, rng)
        self._advance_orders(day, rng)
        sold = self._new_orders(day, rng)
        self._product_changes(day, rng)
        self._write_inventory(day, rng, sold)

    # ---------------------------------------------------------------- daily steps
    def _new_customers(self, day: date, rng: random.Random) -> None:
        start_id = self._max_id("customers", "customer_id", 0) + 1
        rows = []
        for i in range(rng.randint(5, 14)):
            cid = start_id + i
            city, country = rng.choice(CITIES)
            first, last = rng.choice(FIRST), rng.choice(LAST)
            email = f"{first}.{last}{cid}@example.com".lower()
            if rng.random() < 0.04:
                email = email.replace("@", "#")  # dirty: malformed email
            rows.append({
                "customer_id": cid, "email": email, "full_name": f"{first} {last}", "city": city, "country": country,
                "segment": rng.choices(SEGMENTS, SEGMENT_W)[0], "signup_date": day, "updated_at": self._ts(day, rng),
            })
        self._append("customers", pd.DataFrame(rows))

    def _customer_changes(self, day: date, rng: random.Random) -> None:
        """Profile changes (move city / upgrade segment) -> new SCD2 versions downstream."""
        with self.engine.connect() as c:
            ids = [r[0] for r in c.execute(text("select customer_id from source.customers where updated_at < :d"), {"d": datetime.combine(day, time.min)})]
        if not ids:
            return
        changes = []
        for cid in rng.sample(ids, min(len(ids), rng.randint(4, 9))):
            ts = self._ts(day, rng, 6, 22)
            if rng.random() < 0.5:
                city, country = rng.choice(CITIES)
                changes.append({"id": cid, "city": city, "country": country, "segment": None, "ts": ts})
            else:
                changes.append({"id": cid, "city": None, "country": None, "segment": "premium", "ts": ts})
        with self.engine.begin() as c:
            c.execute(text(
                """update source.customers set city = coalesce(:city, city), country = coalesce(:country, country),
                   segment = coalesce(:segment, segment), updated_at = :ts where customer_id = :id"""
            ), changes)

    def _advance_orders(self, day: date, rng: random.Random) -> None:
        """Order lifecycle: placed -> shipped/cancelled -> delivered -> (rarely) returned."""
        midnight = datetime.combine(day, time.min)
        with self.engine.connect() as c:
            placed = c.execute(text(
                """select distinct o.order_id, coalesce(p.status, 'captured') from source.orders o
                   left join source.payments p on p.order_id = o.order_id
                   where o.status = 'placed' and o.order_ts < :m"""), {"m": midnight}).all()
            shipped = [r[0] for r in c.execute(text(
                "select distinct order_id from source.orders where status='shipped' and order_ts < :m"),
                {"m": midnight - timedelta(days=2)})]
            returns = [r[0] for r in c.execute(text(
                "select distinct order_id from source.orders where status='delivered' and order_ts::date = :d"),
                {"d": day - timedelta(days=7)})]
        updates = []
        for oid, pstatus in placed:
            new = "cancelled" if pstatus == "failed" or rng.random() < 0.04 else "shipped"
            updates.append({"id": oid, "st": new, "ts": self._ts(day, rng, 1, 12)})
        updates += [{"id": o, "st": "delivered", "ts": self._ts(day, rng, 8, 20)} for o in shipped if rng.random() < 0.6]
        updates += [{"id": o, "st": "returned", "ts": self._ts(day, rng, 8, 20)} for o in returns if rng.random() < 0.04]
        if not updates:
            return
        refunds = [u for u in updates if u["st"] in ("cancelled", "returned")]
        with self.engine.begin() as c:
            c.execute(text("update source.orders set status = :st, updated_at = :ts where order_id = :id"), updates)
            if refunds:
                c.execute(text(
                    "update source.payments set status = 'refunded', updated_at = :ts where order_id = :id and status = 'captured'"
                ), refunds)

    def _new_orders(self, day: date, rng: random.Random) -> dict[int, int]:
        products = self._products()
        growth = 1 + 0.0015 * max(0, (day - date(2025, 1, 1)).days)
        season = 1.3 if (day.month == 11 and day.day >= 20) else 1.0
        n = max(5, int(rng.gauss(self.base_orders * WEEKDAY[day.weekday()] * growth * season, 6)))
        with self.engine.connect() as c:
            cust_ids = [r[0] for r in c.execute(text("select distinct customer_id from source.customers"))]
        oid0 = self._max_id("orders", "order_id", 1_000_000) + 1
        iid0 = self._max_id("order_items", "order_item_id", 5_000_000) + 1
        pid0 = self._max_id("payments", "payment_id", 9_000_000) + 1
        pweights = [1 / (i + 1) ** 0.8 for i in range(len(products))]
        prices = {int(r.product_id): float(r.list_price) for r in products.itertuples()}
        order_rows, item_rows, pay_rows, sold = [], [], [], {}
        for i in range(n):
            oid, ts = oid0 + i, self._ts(day, rng)
            order_rows.append({"order_id": oid, "customer_id": rng.choice(cust_ids), "order_ts": ts, "status": "placed",
                               "channel": rng.choices(CHANNELS, CHANNEL_W)[0], "updated_at": ts})
            if rng.random() < 0.005:  # dirty: duplicate delivery of the same order
                order_rows.append({**order_rows[-1], "updated_at": ts + timedelta(minutes=3)})
            total = 0.0
            for pid in set(rng.choices(list(products["product_id"]), pweights, k=rng.choices([1, 2, 3, 4], [.5, .3, .15, .05])[0])):
                qty = rng.choices([1, 2, 3, 5], [.7, .2, .07, .03])[0]
                disc = rng.choice([0, 0, 0, 0.05, 0.1, 0.2])
                price = prices[int(pid)]
                total += qty * price * (1 - disc)
                sold[int(pid)] = sold.get(int(pid), 0) + qty
                item_rows.append({"order_item_id": iid0 + len(item_rows), "order_id": oid, "product_id": int(pid),
                                  "quantity": 0 if rng.random() < 0.003 else qty,  # dirty: zero quantity
                                  "unit_price": price, "discount": disc, "updated_at": ts})
            paid_at = ts + timedelta(minutes=rng.randint(1, 30))
            pay_rows.append({"payment_id": pid0 + i, "order_id": oid, "method": rng.choices(METHODS, METHOD_W)[0],
                             "amount": -round(total, 2) if rng.random() < 0.004 else round(total, 2),  # dirty: negative amount
                             "status": "failed" if rng.random() < 0.05 else "captured", "paid_at": paid_at, "updated_at": paid_at})
        self._append("orders", pd.DataFrame(order_rows))
        self._append("order_items", pd.DataFrame(item_rows))
        self._append("payments", pd.DataFrame(pay_rows))
        return sold

    def _product_changes(self, day: date, rng: random.Random) -> None:
        """Price changes + occasional new product, delivered as an updated CSV catalogue."""
        df = self._products()
        for idx in rng.sample(range(len(df)), max(1, len(df) // 40)):
            factor = rng.uniform(0.9, 1.12)
            df.loc[idx, "list_price"] = round(float(df.loc[idx, "list_price"]) * factor, 2)
            df.loc[idx, "updated_at"] = self._ts(day, rng, 0, 6)
        if rng.random() < 0.12:
            cat = rng.choice(list(CATALOGUE))
            brands, nouns, (lo, hi) = CATALOGUE[cat]
            price, pid = round(rng.uniform(lo, hi), 2), int(df["product_id"].max()) + 1
            df.loc[len(df)] = [pid, f"SKU-{pid:04d}", f"{rng.choice(brands)} {rng.choice(nouns)} {pid}", cat,
                               rng.choice(brands), round(price * 0.55, 2), price, self._ts(day, rng, 0, 6)]
        df.to_csv(self.landing / "products.csv", index=False)

    def _write_inventory(self, day: date, rng: random.Random, sold: dict[int, int]) -> None:
        products = self._products()
        state = json.loads(self._state_path.read_text()) if self._state_path.exists() else {}
        rows = []
        for pid in products["product_id"]:
            pid = int(pid)
            reorder = 20 + (pid % 5) * 10
            for wh, share in WAREHOUSES:
                key = f"{pid}|{wh}"
                stock = state.get(key, rng.randint(150, 400))
                stock = max(0, stock - int(sold.get(pid, 0) * share))
                if stock < reorder * 3 and rng.random() < 0.5:
                    stock += rng.randint(100, 300)
                state[key] = stock
                rows.append({"snapshot_date": day.isoformat(), "product_id": str(pid), "warehouse": wh,
                             "stock_on_hand": str(stock), "reorder_level": str(reorder)})
        # dirty rows: duplicate line, 'N/A', negative stock, blank product id
        for _ in range(rng.randint(0, 2)):
            rows.append(dict(rng.choice(rows)))
        if rng.random() < 0.5:
            rows[rng.randrange(len(rows))]["stock_on_hand"] = "N/A"
        if rng.random() < 0.4:
            rows[rng.randrange(len(rows))]["stock_on_hand"] = "-5"
        if rng.random() < 0.3:
            rows[rng.randrange(len(rows))]["product_id"] = ""
        pd.DataFrame(rows).to_csv(self.landing / f"inventory_{day.isoformat()}.csv", index=False)
        self._state_path.write_text(json.dumps(state))

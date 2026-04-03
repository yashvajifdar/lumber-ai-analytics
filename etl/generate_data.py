"""
Synthetic lumber business data generator.
Produces realistic CSVs: customers, products, orders, order_items, inventory.
Run: python etl/generate_data.py
"""

import csv
import random
import os
from datetime import date, timedelta

OUTPUT_DIR = "data/raw"

# ── config ─────────────────────────────────────────────────────────────────
START_DATE = date(2024, 1, 1)
END_DATE   = date(2025, 3, 31)
LOCATIONS  = ["Yard A - Providence", "Yard B - Boston", "Yard C - Hartford"]

CUSTOMER_TYPES = ["Contractor", "Retail"]

PRODUCTS = [
    # name, category, cost, price
    ("2x4x8 Framing Lumber",      "Dimensional Lumber", 3.50,  6.99),
    ("2x6x8 Framing Lumber",      "Dimensional Lumber", 5.00,  9.99),
    ("2x8x16 Lumber",             "Dimensional Lumber", 9.00, 16.99),
    ("4x4x8 Post",                "Dimensional Lumber", 6.00, 11.50),
    ("3/4 Plywood Sheet",         "Sheet Goods",       18.00, 32.99),
    ("1/2 OSB Sheet",             "Sheet Goods",        9.00, 17.50),
    ("LP SmartSide Panel",        "Siding",            22.00, 41.00),
    ("Cedar Decking 5/4x6",       "Decking",            4.50,  8.25),
    ("Pressure Treated 2x6x12",   "Treated Lumber",     7.00, 14.99),
    ("Pressure Treated 4x4x8",    "Treated Lumber",     8.50, 16.50),
    ("LVL Beam 3.5x9.5x20",       "Engineered Wood",   95.00,165.00),
    ("I-Joist 9.5\" x 16'",       "Engineered Wood",   38.00, 64.00),
    ("Drywall 4x8 1/2\"",         "Drywall",            8.00, 13.50),
    ("Cement Board 3x5",          "Drywall",           10.00, 17.00),
    ("House Wrap 9x100",          "Insulation",        45.00, 79.00),
    ("Fiberglass Batts R-19",     "Insulation",        32.00, 54.99),
    ("Roofing Nails 50lb",        "Fasteners",         38.00, 62.00),
    ("Framing Screws 5lb",        "Fasteners",          9.00, 16.50),
    ("Concrete Anchor Bolts",     "Fasteners",         12.00, 21.00),
    ("Door Pre-hung Interior",    "Doors & Windows",   85.00,149.00),
]


def daterange(start: date, end: date):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)


def seasonal_weight(d: date) -> float:
    """Higher volume in spring/summer (construction season)."""
    month = d.month
    if month in (3, 4, 5, 6, 7, 8):
        return 1.6
    if month in (9, 10):
        return 1.1
    return 0.6


# ── name lists ────────────────────────────────────────────────────────────────
FIRST = ["James","Maria","Kevin","Susan","Robert","Lisa","David","Nancy","Carlos","Beth",
         "Tom","Angela","Frank","Diana","Scott","Helen","Mike","Rachel","Paul","Amy"]
LAST  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez",
         "Wilson","Anderson","Taylor","Thomas","Moore","Jackson","White","Harris","Martin","Lee","Perez"]
COMPANIES = ["BuildRight","ProCraft","SunriseDev","AceContracting","BlueSky Build",
             "Cornerstone","Summit Build","DuraBuild","First Choice","AllStar"]


def generate(output_dir: str = OUTPUT_DIR) -> None:
    """Generate all raw CSV files. Safe to call programmatically."""
    random.seed(42)
    os.makedirs(output_dir, exist_ok=True)

    # ── customers ─────────────────────────────────────────────────────────────
    customers = []
    for i in range(1, 201):
        ctype = "Contractor" if i <= 120 else "Retail"
        if ctype == "Contractor":
            name = f"{random.choice(COMPANIES)} {random.choice(['LLC','Inc','Co','Construction'])}"
        else:
            name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        customers.append({
            "customer_id": f"C{i:04d}",
            "name": name,
            "type": ctype,
            "location": random.choice(LOCATIONS),
            "since": START_DATE - timedelta(days=random.randint(0, 730)),
        })

    with open(f"{output_dir}/customers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["customer_id","name","type","location","since"])
        w.writeheader(); w.writerows(customers)
    print(f"customers.csv  →  {len(customers)} rows")

    # ── products ──────────────────────────────────────────────────────────────
    products = []
    for i, (name, cat, cost, price) in enumerate(PRODUCTS, 1):
        products.append({
            "product_id": f"P{i:03d}",
            "name": name,
            "category": cat,
            "cost": cost,
            "list_price": price,
        })

    with open(f"{output_dir}/products.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["product_id","name","category","cost","list_price"])
        w.writeheader(); w.writerows(products)
    print(f"products.csv   →  {len(products)} rows")

    # ── orders + order_items ──────────────────────────────────────────────────
    orders, items = [], []
    order_id = 1

    contractor_ids = [c["customer_id"] for c in customers if c["type"] == "Contractor"]
    retail_ids     = [c["customer_id"] for c in customers if c["type"] == "Retail"]

    for d in daterange(START_DATE, END_DATE):
        sw = seasonal_weight(d)
        n_orders = int(random.gauss(8 * sw, 2))
        n_orders = max(1, n_orders)

        for _ in range(n_orders):
            if random.random() < 0.70:
                cid = random.choice(contractor_ids)
            else:
                cid = random.choice(retail_ids)

            ctype = next(c["type"] for c in customers if c["customer_id"] == cid)
            location = random.choice(LOCATIONS)
            oid = f"O{order_id:06d}"

            orders.append({
                "order_id": oid,
                "customer_id": cid,
                "order_date": d.isoformat(),
                "location": location,
                "status": random.choices(["completed","completed","completed","returned"], weights=[9,9,9,1])[0],
            })

            n_items = random.randint(1, 5) if ctype == "Retail" else random.randint(2, 10)
            picked = random.sample(products, min(n_items, len(products)))

            for prod in picked:
                qty = random.randint(1, 20) if ctype == "Retail" else random.randint(5, 200)
                actual_cost = round(prod["cost"] * random.uniform(0.90, 1.15), 2)
                discount = round(random.uniform(0.05, 0.15), 2) if ctype == "Contractor" and random.random() < 0.4 else 0.0
                unit_price = round(prod["list_price"] * (1 - discount), 2)

                items.append({
                    "order_id": oid,
                    "product_id": prod["product_id"],
                    "quantity": qty,
                    "unit_price": unit_price,
                    "unit_cost": actual_cost,
                    "discount": discount,
                })

            order_id += 1

    with open(f"{output_dir}/orders.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["order_id","customer_id","order_date","location","status"])
        w.writeheader(); w.writerows(orders)
    print(f"orders.csv     →  {len(orders)} rows")

    with open(f"{output_dir}/order_items.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["order_id","product_id","quantity","unit_price","unit_cost","discount"])
        w.writeheader(); w.writerows(items)
    print(f"order_items.csv →  {len(items)} rows")

    # ── inventory ─────────────────────────────────────────────────────────────
    inventory = []
    for prod in products:
        for loc in LOCATIONS:
            stock = random.randint(50, 2000)
            reorder = random.randint(50, 200)
            inventory.append({
                "product_id": prod["product_id"],
                "location": loc,
                "stock_level": stock,
                "reorder_point": reorder,
                "last_updated": END_DATE.isoformat(),
            })

    with open(f"{output_dir}/inventory.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["product_id","location","stock_level","reorder_point","last_updated"])
        w.writeheader(); w.writerows(inventory)
    print(f"inventory.csv  →  {len(inventory)} rows")

    print("\nAll files written to data/raw/")


if __name__ == "__main__":
    generate()

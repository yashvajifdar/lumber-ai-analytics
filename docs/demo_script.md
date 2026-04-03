# Lumber AI Analytics — Demo Script

**Audience:** Mid-market lumber / building supply owner or operator
**Duration:** 10–12 minutes
**Format:** Live demo, screen share, Chat page

---

## Setup Before You Start

- App running at your shareable URL (or localhost:8501)
- Navigate to the **Chat** page
- Clear any prior conversation (refresh the tab)
- Have this script open on a second monitor or printed

---

## The Narrative

You are walking a business owner through their own data for the first time.
The story arc: *we start at the top, find something interesting, drill into it, find a problem, then show them inventory before they even asked.*

This is the "aha" moment — the system anticipates what a smart analyst would ask next.

---

## Question Flow

### 1. Open with revenue — establish the business

**Type:** `Which category drives the most revenue?`

**What you'll see:**
- Engineered Wood is #1 at $17.5M revenue, 38.2% margin
- Doors & Windows #2 at $11.7M
- Treated Lumber is smallest by revenue but highest margin at 47.4%

**What to say:**
> "Right away we can see the shape of the business. Engineered Wood drives the most volume — LVL beams, I-joists — but look at Treated Lumber down here. Smallest revenue category, highest margin. That's a signal worth paying attention to."

**Pause here.** Let them read the chart. Don't rush past it.

---

### 2. Follow the margin signal

**Type:** `Which products have the highest margin?`

**What you'll see:**
- Pressure Treated 2x6x12 at 49.8% — highest margin in the business
- 2x6x8 and 2x4x8 Framing Lumber at 46-47%
- All top-margin products are Treated Lumber and Dimensional Lumber

**What to say:**
> "Treated Lumber keeps showing up. Pressure Treated 2x6x12 is nearly 50% margin — that's exceptional for building materials. These aren't your biggest revenue drivers, but every dollar of revenue here converts better than anywhere else in the business."

**The insight to land:**
> "If you want to grow profit without growing volume, this is where you focus — pricing power, inventory availability, and making sure your sales team knows these are your highest-value SKUs."

---

### 3. Flip it — find the margin problem

**Type:** `Which products have the lowest margin?`

**What you'll see:**
- Roofing Nails 50lb at 34.3% — $5M in revenue, worst margin
- I-Joist 9.5" x 16' at 36.4% — $4.8M revenue
- These are high-volume, low-margin products

**What to say:**
> "Now the other side. Roofing Nails are doing $5M in revenue — your fourth-biggest product — but at only 34 cents of margin on every dollar. That's a pricing conversation or a supplier negotiation. High volume, low return."

**The contrast to make:**
> "You're selling almost as many Roofing Nails as LVL Beams, but LVL Beams earn you 38 cents on the dollar versus 34. That gap compounds at scale."

---

### 4. Shift to customers — who is actually buying this

**Type:** `What is the split between contractor and retail customers?`

**What you'll see:**
- Contractors: $63M revenue, 120 customers, 2,642 orders
- Retail: $1.4M revenue, 80 customers, 1,131 orders

**What to say:**
> "This tells you everything about the business model. Contractors are 60% of the customer base but 97% of revenue. This is a B2B business that happens to have a retail counter — not the other way around."

**Follow up immediately:**
> "And your repeat rate is 100% on both segments — every single customer has come back more than once. That's not luck, that's relationship. The risk here isn't churn, it's concentration — what happens if two or three of your top contractors switch suppliers?"

---

### 5. Close with inventory — the operational risk

**Type:** `What inventory is running low?`

**What you'll see:**
- Pressure Treated 4x4x8 is below reorder point — 77 units vs 152 reorder point

**What to say:**
> "Remember Treated Lumber? Highest margin category in the business. And right now you have one SKU — Pressure Treated 4x4x8 — sitting at half its reorder point. That's a margin dollar you can't sell."

**The landing:**
> "This is what an analytics platform does that a spreadsheet can't. It connects the dots — margin, volume, inventory — so you see the business as a system, not as separate reports."

---

## Closing the Demo

> "Everything you just saw — five questions, five different angles on your business — took about three minutes. The numbers are live. They update as orders come in. And every answer is backed by a pre-built, tested calculation — not an AI making its best guess.

> The way I built this: the AI handles language, the functions handle math. You ask a question in plain English, it routes to the right calculation, and you get a number you can trust."

If they push on what happens with questions outside the current scope:

> "Right now the system covers the eleven most important metrics for a business like this. When a client needs something new, we build the function, test it, and add it. You never get a wrong number you don't know is wrong."

---

## Questions They Will Ask

**"Can it connect to my actual data?"**
> Yes. This runs on SQLite for the demo — the architecture is identical to Postgres or your ERP's database. Connecting to a real source is a configuration change, not a rebuild.

**"How long to set this up for my business?"**
> Depends on data availability. If you have clean transaction history in a database or can export it, we can have a working demo on your data in two to three weeks.

**"What does it cost?"**
> [Your call on pricing — but frame it as a platform subscription + setup fee, not a one-time build.]

**"What if I want to ask something it can't answer yet?"**
> It tells you. It doesn't guess. We can show you that right now if you want — ask it something outside the scope and watch what happens.

---

## Notes

- Don't demo the Dashboard, Products, Customers, or Inventory pages unless asked — they're supporting evidence, not the main story. The Chat page is the product.
- If anything loads slowly, narrate what's happening — "it's querying the database and generating the explanation in real time."
- The goal of the demo is not to show every feature. It is to make them say: "I want this for my business."

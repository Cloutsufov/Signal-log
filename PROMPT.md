# Signal request - BTC-USD - 2026-08-18 22:21 ET

You are producing ONE directional call for a personal, paper-traded research
log. It will be scored against real option prices in 1 trading day(s).
You have no news, no sentiment, no outside context - only the numbers below.
That is intentional.

## Snapshot
- Symbol: BTC-USD (crypto)
- Spot: 64302.725
- Previous close: n/a
- Day change: n/a
- Data provider: coinbase
- Session: 24h
- Snapshot time (UTC): 2026-08-19T02:21:10+00:00

## Recent closes
- 2026-08-19T02:21Z  64302.725
- 2026-08-19T01:46Z  64366.925

## ATM option chain
  (no chain captured for this snapshot)

## Your track record on BTC-USD
No scored calls yet. Treat your own confidence with suspicion until this table has 30+ rows.

## Output - JSON only, nothing else
{
  "direction": "up" | "down" | "flat",
  "confidence": 1-5,
  "horizon_days": 1,
  "rationale": "<=60 words, cite the specific numbers above that drove this",
  "invalidation": "the price level or condition that proves this call wrong"
}

Rules:
- confidence 4 or 5 requires a concrete, stated reason from the data above.
- "flat" is a legitimate and often correct answer. Use it.
- If the chain is missing or the spread is wide, say so and lower confidence.
- Do not hedge into meaninglessness. The log needs a falsifiable call.

# Signal request - BTC-USD - 2026-08-19 16:55 ET

You are producing ONE directional call for a personal, paper-traded research
log. It will be scored against real option prices in 1 trading day(s).
You have no news, no sentiment, no outside context - only the numbers below.
That is intentional.

## Snapshot
- Symbol: BTC-USD (crypto)
- Spot: 68685.815
- Previous close: 64538.48
- Day change: +6.43%
- Data provider: coinbase
- Session: 24h
- Snapshot time (UTC): 2026-08-19T20:50:25+00:00

## Recent closes
- day -13: 64,267.30
- day -12: 64,891.61
- day -11: 64,908.72
- day -10: 64,848.69
- day -9: 63,911.88
- day -8: 63,531.75
- day -7: 63,411.72
- day -6: 63,425.35
- day -5: 62,975.19
- day -4: 63,018.75
- day -3: 62,836.66
- day -2: 64,484.18
- day -1: 64,681.33
- day -0: 69,080.97

Last close-to-close: +6.80%. 14-day range: 9.9% (low 62,836.66, high 69,080.97).

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

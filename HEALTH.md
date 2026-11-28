# Last run

`2026-11-28 03:36 UTC` · trigger: `*/30 * * * *`

```
trigger: action=(none) schedule=*/30 * * * *
ET now:  2026-11-27 22:36 (postclose)
plan:    4 step(s)
  - fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
  - fetch_news.py
  - score.py
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
  ok  BTC-USD: 59896.605 via coinbase (-2.34%)
  ok  ETH-USD: 1662.88 via coinbase (-3.68%)

$ /home/runner/work/Signal-log/Signal-log/scripts/fetch_news.py
  ok    Fed - Monetary Policy    15 items, 0 new
  ok    SEC Press                25 items, 0 new
  ok    BEA News                 50 items, 0 new
  ok    NPR Business             10 items, 0 new
  ok    CNBC Top News            16 items, 1 new
  ok    CNBC Markets             30 items, 0 new
  ok    MarketWatch              10 items, 0 new
  ok    Fox Business             25 items, 1 new
  ok    BBC Business             53 items, 0 new
  ok    Al Jazeera               4 items, 2 new
  ok    DW Business              20 items, 0 new
  ok    CoinDesk                 25 items, 0 new
  ok    Cointelegraph            30 items, 0 new
  ok    Fed - Speeches           15 items, 0 new
  ok    Fed - Enforcement        15 items, 0 new
  ok    EIA Today in Energy      33 items, 0 new  [1 undated]
  ok    AP Business (Google)     0 items, 0 new

17 feeds alive, 0 dead, 4 new headlines, 35 filtered as off-topic, 0 purged from history
dead: none

$ /home/runner/work/Signal-log/Signal-log/scripts/score.py
no matured calls to score

--- record ---
  BTC-USD    1 calls | direction   0.0% | avg option P&L n/a | profitable 0/1
  reminder: option P&L is marked mid-to-mid. Reality is worse.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,018 bytes)
wrote docs/record.html (13,410 bytes)
wrote docs/news.html (43,731 bytes)

done
```

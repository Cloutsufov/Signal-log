# Last run

`2026-08-25 23:15 UTC` · trigger: `*/30 * * * *`

```
trigger: action=(none) schedule=*/30 * * * *
ET now:  2026-08-25 19:15 (postclose)
plan:    4 step(s)
  - fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
  - fetch_news.py
  - score.py
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
  ok  BTC-USD: 78941.15 via coinbase (-0.05%)
  ok  ETH-USD: 2453.83 via coinbase (-1.14%)

$ /home/runner/work/Signal-log/Signal-log/scripts/fetch_news.py
  ok    Federal Reserve          20 items, 0 new
  ok    Fed - Monetary Policy    15 items, 0 new
  ok    SEC Press                25 items, 0 new
  ok    BEA News                 47 items, 0 new
  ok    NPR Business             10 items, 1 new
  ok    Guardian Business        39 items, 0 new
  ok    CNBC Top News            21 items, 1 new
  ok    CNBC Markets             30 items, 0 new
  ok    MarketWatch              10 items, 0 new
  ok    Yahoo Finance            50 items, 7 new
  ok    Fox Business             25 items, 0 new
  ok    BBC Business             53 items, 4 new
  ok    Al Jazeera               12 items, 0 new
  ok    DW Business              20 items, 0 new
  ok    CoinDesk                 25 items, 0 new
  ok    Cointelegraph            30 items, 0 new
  ok    Fed - Speeches           15 items, 0 new
  ok    Fed - Enforcement        15 items, 0 new
  ok    EIA Today in Energy      19 items, 0 new
  ok    Reuters Business (Google) 0 items, 0 new
  ok    AP Business (Google)     0 items, 0 new

21 feeds alive, 0 dead, 13 new headlines, 22 filtered as off-topic, 0 purged from history
dead: none

$ /home/runner/work/Signal-log/Signal-log/scripts/score.py
no matured calls to score

--- record ---
  BTC-USD    1 calls | direction   0.0% | avg option P&L n/a | profitable 0/1
  reminder: option P&L is marked mid-to-mid. Reality is worse.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,006 bytes)
wrote docs/record.html (13,410 bytes)
wrote docs/news.html (43,082 bytes)

done
```

# Last run

`2026-10-19 18:44 UTC` · trigger: `17 12 * * 1`

```
trigger: action=(none) schedule=17 12 * * 1
ET now:  2026-10-19 14:44 (open)
plan:    2 step(s)
  - doctor.py --prune
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/doctor.py --prune
=== quotes ===
  OK    coinbase BTC-USD                     165ms  spot 81832.225
  OK    coinbase ETH-USD                     150ms  spot 2397.85

=== options ===

=== news feeds ===
  OK    Fed - Monetary Policy [data]          91ms  15 items | Minutes of the Board's discount rate meeting
  OK    SEC Press [data]                      99ms  25 items | SEC Announces Roundtable on Machine-Understa
  OK    BEA News [data]                      362ms  48 items | U.S. International Trade in Goods and Servic
  OK    NPR Business [left]                  364ms  10 items | Noah Adams, longtime host of NPR's All Thing
  OK    Guardian Business [left]             220ms  40 items | France hit by debt sell-off as violent prote
  OK    CNBC Top News [center]               105ms  30 items | OpenAI bugging suspect's conduct could pose 
  OK    CNBC Markets [center]                 68ms  30 items | Women may be at greater risk of AI job losse
  OK    MarketWatch [center]                 179ms  10 items | One of this year’s most important relationsh
  OK    Fox Business [right]                  95ms  25 items | Tesla's long-awaited Roadster gets its momen
  OK    BBC Business [intl]                  126ms  47 items | Vinted blocks French looters listing stolen 
  OK    Al Jazeera [intl]                    151ms  25 items | Ex-OpenAI employee accused of planting devic
  OK    DW Business [intl]                   709ms  20 items | EU promotes sovereign, trusted AI as it stru
  OK    CoinDesk [crypto]                    232ms  25 items | U.S. CFTC rebuffs CME legal stance in conseq
  OK    Cointelegraph [crypto]               178ms  30 items | Revolut secures Gibraltar crypto license to 
  OK    Fed - Speeches [data]                 74ms  15 items | Bowman, Supervisory Modernization After Sili
  OK    Fed - Enforcement [data]             134ms  15 items | Federal Reserve Board announces termination 
  OK    EIA Today in Energy [data]          8152ms  19 items | Hybrid sales rise while battery electric sal
  OK    Reuters Business (Google) [center]   276ms  0 items | EMPTY
  OK    AP Business (Google) [center]        219ms  0 items | EMPTY

=== summary ===
  quotes:  2/2 provider+symbol combinations alive
  options: 0/0 chains alive - scoring degrades to spot-only
  news:    19/19 feeds alive

  NOTE: without a chain, calls still record and score on spot,
  but option P&L will be blank. That is a degraded mode, not a
  broken one. Check if Yahoo now requires a cookie+crumb.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,072 bytes)
wrote docs/record.html (13,468 bytes)
wrote docs/news.html (43,467 bytes)

done
```

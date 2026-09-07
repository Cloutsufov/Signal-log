# Last run

`2026-09-07 17:45 UTC` · trigger: `17 12 * * 1`

```
trigger: action=(none) schedule=17 12 * * 1
ET now:  2026-09-07 13:45 (open)
plan:    2 step(s)
  - doctor.py --prune
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/doctor.py --prune
=== quotes ===
  OK    coinbase BTC-USD                     113ms  spot 79163.025
  OK    coinbase ETH-USD                      70ms  spot 2493.405

=== options ===

=== news feeds ===
  OK    Federal Reserve [data]                75ms  20 items | Federal Reserve Board announces termination 
  OK    Fed - Monetary Policy [data]          42ms  15 items | Minutes of the Board's discount rate meeting
  OK    SEC Press [data]                      58ms  25 items | SEC Proposes Rescission of Political Contrib
  OK    BEA News [data]                      426ms  48 items | U.S. International Trade in Goods and Servic
  OK    NPR Business [left]                   57ms  10 items | Trump issues new executive orders on beef sa
  OK    Guardian Business [left]              67ms  40 items | Jaguar Land Rover confirms plan to cut 4,000
  OK    CNBC Top News [center]                93ms  30 items | Oil prices rise to 6-week high after Iran an
  OK    CNBC Markets [center]                128ms  30 items | Japan's foreign reserves drop by a record $8
  OK    MarketWatch [center]                  43ms  10 items | Why does almost nobody want to befriend olde
  OK    Yahoo Finance [center]                42ms  50 items | Loss of Costco deal helps push beverage bran
  OK    Fox Business [right]                 114ms  25 items | Amazon says it’s 'working closely' with auth
  OK    BBC Business [intl]                   88ms  52 items | Next wins key appeal to overturn £30m equal 
  OK    Al Jazeera [intl]                    122ms  25 items | Serbian government sets up snap vote with ca
  OK    DW Business [intl]                  1119ms  20 items | Germany: Is Saxony-Anhalt's economy really s
  OK    CoinDesk [crypto]                    224ms  25 items | Hunter Biden debuts 'LAPTOP' memecoin target
  OK    Cointelegraph [crypto]               111ms  30 items | Bitcoin fund flows show investors trading Fe
  OK    Fed - Speeches [data]                 58ms  15 items | Waller, The Economic Outlook and Some Commen
  OK    Fed - Enforcement [data]             132ms  15 items | Federal Reserve Board announces termination 
  OK    EIA Today in Energy [data]         10177ms  13 items | Elevated crack spreads and crude oil prices 
  OK    Reuters Business (Google) [center]   180ms  0 items | EMPTY
  OK    AP Business (Google) [center]        186ms  0 items | EMPTY

=== summary ===
  quotes:  2/2 provider+symbol combinations alive
  options: 0/0 chains alive - scoring degrades to spot-only
  news:    21/21 feeds alive

  NOTE: without a chain, calls still record and score on spot,
  but option P&L will be blank. That is a degraded mode, not a
  broken one. Check if Yahoo now requires a cookie+crumb.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,072 bytes)
wrote docs/record.html (13,468 bytes)
wrote docs/news.html (43,102 bytes)

done
```

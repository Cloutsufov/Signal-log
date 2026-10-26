# Last run

`2026-10-26 18:42 UTC` · trigger: `17 12 * * 1`

```
trigger: action=(none) schedule=17 12 * * 1
ET now:  2026-10-26 14:42 (open)
plan:    2 step(s)
  - doctor.py --prune
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/doctor.py --prune
=== quotes ===
  OK    coinbase BTC-USD                     149ms  spot 80098.955
  OK    coinbase ETH-USD                      66ms  spot 2320.175

=== options ===

=== news feeds ===
  OK    Fed - Monetary Policy [data]          59ms  15 items | Minutes of the Board's discount rate meeting
  OK    SEC Press [data]                      64ms  25 items | SEC Announces Fiscal Year 2027 Examination P
  OK    BEA News [data]                       65ms  48 items | U.S. International Trade in Goods and Servic
  OK    NPR Business [left]                   70ms  10 items | AI giant Anthropic files for an IPO that cou
  OK    Guardian Business [left]              87ms  40 items | Anthropic reveals rapid revenue gains and la
  OK    CNBC Top News [center]                46ms  30 items | Microsoft offers voluntary buyouts to 60,000
  OK    CNBC Markets [center]                 49ms  30 items | Jobless claims near the lowest since the 196
  OK    MarketWatch [center]                 107ms  10 items | Nvidia, AMD and Broadcom could buy Meta shar
  OK    Fox Business [right]                  46ms  25 items | Anthropic files SEC paperwork as AI giant pr
  OK    BBC Business [intl]                  121ms  56 items | Anthropic warns of 'catastrophic risk' to hu
  OK    Al Jazeera [intl]                    185ms  25 items | Trump faces private citizens lawsuit over li
  OK    DW Business [intl]                   359ms  20 items | What Germany thinks of carmaker Audi's $4 bi
  OK    CoinDesk [crypto]                    153ms  25 items | Tom Lee's Bitmine favors share buybacks to e
  OK    Cointelegraph [crypto]                65ms  30 items | NBA names Kalshi, Polymarket preferred excha
  OK    Fed - Speeches [data]                 60ms  15 items | Bowman, Supervisory Modernization After Sili
  OK    Fed - Enforcement [data]              61ms  15 items | Federal Reserve Board announces termination 
  OK    EIA Today in Energy [data]            68ms  20 items | U.S. refineries have been running at very hi
  OK    Reuters Business (Google) [center]   238ms  0 items | EMPTY
  OK    AP Business (Google) [center]        222ms  0 items | EMPTY

=== summary ===
  quotes:  2/2 provider+symbol combinations alive
  options: 0/0 chains alive - scoring degrades to spot-only
  news:    19/19 feeds alive

  NOTE: without a chain, calls still record and score on spot,
  but option P&L will be blank. That is a degraded mode, not a
  broken one. Check if Yahoo now requires a cookie+crumb.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,071 bytes)
wrote docs/record.html (13,468 bytes)
wrote docs/news.html (43,127 bytes)

done
```

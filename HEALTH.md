# Last run

`2026-09-28 19:42 UTC` · trigger: `17 12 * * 1`

```
trigger: action=(none) schedule=17 12 * * 1
ET now:  2026-09-28 15:42 (open)
plan:    2 step(s)
  - doctor.py --prune
  - build_site.py

$ /home/runner/work/Signal-log/Signal-log/scripts/doctor.py --prune
=== quotes ===
  OK    coinbase BTC-USD                     175ms  spot 83168.985
  OK    coinbase ETH-USD                     112ms  spot 2668.365

=== options ===

=== news feeds ===
  OK    Federal Reserve [data]                77ms  20 items | Federal Reserve Board announces approval of 
  OK    Fed - Monetary Policy [data]          61ms  15 items | Federal Reserve issues FOMC statement
  OK    SEC Press [data]                      63ms  25 items | SEC Charges Registered Investment Adviser Zo
  OK    BEA News [data]                      192ms  48 items | U.S. International Transactions and Investme
  OK    NPR Business [left]                  116ms  10 items | The Trump administration weakens fuel effici
  OK    Guardian Business [left]             127ms  40 items | Healey signals welfare reform push and new a
  OK    CNBC Top News [center]               179ms  30 items | Trump announces plan for $15 billion steel p
  OK    CNBC Markets [center]                190ms  30 items | China posts weakest industrial profit growth
  OK    MarketWatch [center]                 129ms  10 items | PepsiCo plans to raise prices on sodas, chip
  OK    Yahoo Finance [center]                68ms  49 items | Ennis (EBF) Grows Sales but Earns Less. Are 
  OK    Fox Business [right]                 318ms  25 items | Nvidia launches security platform to keep AI
  OK    BBC Business [intl]                  152ms  51 items | UK tries to stop Trump's diesel export ban
  OK    Al Jazeera [intl]                    136ms  25 items | American and six Ukrainians released by Indi
  OK    DW Business [intl]                   562ms  20 items | Diesel prices are surging putting further pr
  OK    CoinDesk [crypto]                    325ms  25 items | Goldman Sachs brings $100 billion Treasury f
  OK    Cointelegraph [crypto]                96ms  30 items | Here’s what happened in crypto today
  OK    Fed - Speeches [data]                 80ms  15 items | Cook, An Update on AI and the Economy
  OK    Fed - Enforcement [data]              95ms  15 items | Federal Reserve Board issues enforcement act
  OK    EIA Today in Energy [data]          8214ms  19 items | Henry Hub natural gas prices this summer wer
  OK    Reuters Business (Google) [center]   300ms  0 items | EMPTY
  OK    AP Business (Google) [center]        239ms  0 items | EMPTY

=== summary ===
  quotes:  2/2 provider+symbol combinations alive
  options: 0/0 chains alive - scoring degrades to spot-only
  news:    21/21 feeds alive

  NOTE: without a chain, calls still record and score on spot,
  but option P&L will be blank. That is a degraded mode, not a
  broken one. Check if Yahoo now requires a cookie+crumb.

$ /home/runner/work/Signal-log/Signal-log/scripts/build_site.py
wrote docs/index.html (20,067 bytes)
wrote docs/record.html (13,468 bytes)
wrote docs/news.html (43,226 bytes)

done
```

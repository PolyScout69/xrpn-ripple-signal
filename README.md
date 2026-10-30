# Signal — investor intelligence

**Live dashboard:** https://polyscout69.github.io/xrpn-ripple-signal/

Independent investor news for **Evernorth Holdings (XRPN)**, **Ripple**, **Strategy (MSTR)**, **Lite Strategy (LITS)**, **Hyperliquid Strategies (PURR)**, **SharpLink Gaming (SBET)**, and **Forward Industries (FWDI)**.

## Sources and publishing

- **Three times daily, at approximately 09:15, 14:35 and 23:35 UTC**, GitHub Actions runs `scripts/scan.py`, updates `data/news.json`, and deploys GitHub Pages. The 09:15 scan focuses on early UK and continental European announcements after their opening release window, the 14:35 scan catches US pre-market/early-session headlines, and the 23:35 scan captures US market-close and evening releases. Scans run every day, including weekends. GitHub Actions schedules can start late during platform congestion and use fixed UTC hours (so local times vary with daylight saving). Pushes to `main` and manual dispatches also run the workflow. Queued scans check out the current `main` head when they start, so a completed scan's snapshot commit is not overwritten by a stale queued checkout.
- Signal monitors official Ripple, Evernorth, Lite Strategy, Hyperliquid Strategies, SharpLink and Forward Industries releases, plus targeted company news covering XRPN, MSTR, LITS, PURR, SBET and FWDI. Lite Strategy specialises in LTC treasury accumulation, covered calls and share repurchases; generic Litecoin headlines are not automatically labelled LITS.
- **Standalone SEC filing records are intentionally excluded** from news cards, source monitoring and the Moon Meter. A news report about material financing, partnerships, regulation or other events may still appear, but standalone filing entries do not.
- Multiple publications of the same event are grouped with additional source links.
- Source Health reflects **seven** channels: Ripple official, Evernorth official, Lite Strategy official, Hyperliquid Strategies official, SharpLink official, Forward Industries official, and company investor news. Lite Strategy's GCS-Web investor-relations archive has a verified alternate company archive address if one domain is inaccessible; a source outage is displayed rather than silently reported as successful.

## Lite Strategy (LITS) treasury coverage

Lite Strategy, Inc. (Nasdaq: LITS, formerly MEI Pharma) uses **Litecoin (LTC)** as its principal crypto reserve asset. Signal monitors its issuer releases (including its investor-relations archive), LITS-specific reporting, share count, LTC per diluted share, covered-call/option premium income, buybacks, LitVM-related strategic investments and significant financing or treasury risks. Moon Meters are **LITS stock** scenarios, not predictions of Litecoin token returns. The website uses the same TradingView widget for LITS as for XRPN and MSTR; quotes may be delayed. The 30-day LITS Moon Sentiment card shows **No coverage** rather than manufacturing a neutral sentiment if no dated, eligible stories are available.

## Hyperliquid Strategies (PURR) treasury coverage

[Hyperliquid Strategies Inc](https://hypestrat.xyz/) is a Nasdaq-listed **HYPE treasury company**, ticker **PURR**. It is a separate public-company investment, **not stock in Hyperliquid Labs or ownership of the HYPE protocol**. Signal monitors issuer releases via its [official PR Newswire archive](https://www.prnewswire.com/news/hyperliquid-strategies-inc/), plus targeted PURR reporting. Material topics include HYPE tokens held and **HYPE per diluted PURR share**, staking and validator income, custody and withdrawal controls, institutional partnerships, equity facilities, dilution, stock repurchases, governance and financial results.

- The **PURR share price** uses the same delayed TradingView Nasdaq quote widget and daily % change as XRPN/MSTR/LITS. The company-specific link points to `NASDAQ:PURR`.
- **PURR Moon Meter** scores potential if-true impacts on *PURR equity*, not direct price moves in HYPE. A buyback authorization is different from an executed, NAV-accretive repurchase; generic HYPE market headlines are not automatically attributed to PURR.
- **PURR Moon Sentiment** aggregates last-30-day company-specific events with the existing impact, freshness, source and duplicate discounting. Limited/no coverage is labelled instead of manufacturing certainty.
- Market Pulse and Moon Sentiment share the order **MSTR, XRPN, SBET, PURR, FWDI, LITS**. Mobile sentiment cards form MSTR/XRPN, SBET/PURR and FWDI/LITS pairs in that reading order; stock quotes stack one per row on small phones.
- Each sentiment card shows its underlying crypto logo: BTC, XRP, ETH, HYPE, SOL or LTC. SVGs are served locally; source and licence details are preserved in `assets/crypto/SOURCES.md`.

## SharpLink (SBET) and Forward Industries (FWDI)

**SharpLink Gaming**, now branded **Sharplink, Inc.**, is tracked as **SBET / ETH**. Its [official investor page](https://www.sharplink.com/investors) publishes a public b2i press-release archive. Signal reads the dated archive and links to the original HTML releases; the release ID stays in each URL so distinct announcements are not merged. Company-specific media searches include the old and current names plus SBET.

**Forward Industries, Inc.** is tracked as **FWDI / SOL**. Signal reads the issuer's GlobeNewswire RSS channel embedded in its [official investor page](https://forwardindustries.com/investors), together with company-specific media searches. If the syndicator is unavailable, it reads up to 16 dated first-party `/insights/` releases from the company sitemap and marks Source Health as **Partial** because the bounded archive may lag the RSS. Previously verified releases remain in the merged archive. The ordinary word “Forward” and the former FORD symbol do not qualify a story on their own.

Both companies have Nasdaq USD quote widgets, entity filters, article Moon Meters, 30-day Moon Sentiment and Source Health entries. Ratings assess the stock: ETH or SOL per diluted share, treasury acquisitions, staking income, share issuance, executed buybacks, custody and counterparty risks. Generic Ethereum and Solana stories are not automatically assigned to either company. Authorising a buyback is distinct from executing an accretive repurchase; staking deployment is distinct from income already earned.

The separate **XRP Ecosystem** channel has been retired, including standalone XRP/XRPL/ETF discovery queries and its navigation/filter labels. Company-specific XRP news remains under Ripple and Evernorth. On archive refresh, network-only stories are removed, valid company tags are retained, and article Moon Meters and sentiment are recalculated. The browser also filters legacy snapshots so a delayed refresh cannot restore the retired category.

## Top Investor Signal — ranked recent developments

The highlighted story on the Overview page is **not** simply the article with the highest original 0–99 score. Only articles published in the last **72 hours** can occupy this position. Each eligible article is ranked by:

- **35% investor importance** — High impact receives full weight, Medium 68% and Low 35%.
- **30% freshness** — linearly declines as an article approaches 72 hours old.
- **20% Moon Meter magnitude** — the highest absolute asset score among the story's Moon Meters; an exceptional **−3** matters just as much as **+3** for choosing the important lead.
- **15% credibility** — issuer announcements rank above media-only reporting. Unverified rumours and assumptions retain their *if-true* Moon scores but receive a source-reliability discount.

The algorithm favours high-impact **new** information and does not arbitrarily boost bullish news. Ties favour the most recently published story. Articles older than 72 hours stay in the regular feed but cannot remain featured. If no eligible recent article exists, the featured section is empty. An issuer story with only a calendar date is eligible on that date even though the collector may normalise its time to noon UTC. The ranking recalculates on page load or user refresh/filter changes.

## Homepage share-price widgets

The top of the homepage shows **XRPN (Evernorth)**, **MSTR (Strategy)**, **LITS (Lite Strategy)**, **PURR (Hyperliquid Strategies)**, **SBET (SharpLink)** and **FWDI (Forward Industries)** in separate compact USD quote widgets, including each stock's **daily percentage change**. These are the official free [TradingView Single Ticker](https://www.tradingview.com/widget-docs/widgets/tickers/single-ticker/) web components, configured for `NASDAQ:XRPN`, `NASDAQ:MSTR`, `NASDAQ:LITS`, `NASDAQ:PURR`, `NASDAQ:SBET` and `NASDAQ:FWDI`; no paid API key is required. Quotes are fetched in the visitor's browser independently of the three daily news scans. TradingView supplies **delayed US stock quotes** in public widgets; do not label them real-time Nasdaq prices. A direct link to each stock page remains available if the third-party widget cannot load. The widget may issue requests to TradingView and follows TradingView's third-party privacy practices.

## Moon Sentiment — XRPN, MSTR, LITS, PURR, SBET and FWDI, 30 days

The six sentiment cards of the homepage score **weighted 30-day Moon Sentiment** for MSTR, XRPN, SBET, PURR, FWDI and LITS, replacing the old **Treasury News** and **Source Coverage** cards. Individual Moon Meters remain visible on every story; source-health remains available in its existing monitoring panel.

The calculation runs during each of the three daily news scans and publishes `sentiment_30d` into `data/news.json`, including the rounded −3 to +3 score, raw score, source counts and top contributing stories. If a new snapshot is delayed, the site shows a clearly labelled **provisional** calculation from the previous published Moon Meter values. **A 0 headline is not a negative vote**: neutral articles only add 8% of their normal weight to the denominator. Only evidence with a signed directional Moon Meter contributes directly to the numerator.

For each unique event the model uses:

- **Impact:** High 4.5×, Medium 2.25×, Low 1×. This is not the same as source confidence or a probability of the event happening.
- **Freshness:** exponentially decaying weight with a **17-day half-life**, limited to news from the last 30 days.
- **Reporting / assumption status:** official sources 1.15×, other publishers 1×; reported events 1×, forward-looking assumptions 0.90×, and rumours 0.72×. The lower confidence on rumours limits their dominance over independently corroborated news, while their **if-true** impact rating is retained.
- **Strength of a catalyst:** ±2 signals gain a 1.2× magnitude weighting, ±3 a 1.4× magnitude weighting. Genuine major negative news offsets positive news rather than being discarded.
- **One economic event, one major contribution:** reports covering the same identifiable event family and ISO week are grouped by asset and sign, using the strongest specific report. Syndication cannot inflate the score by repeating a headline.

The index is the directional weighted mean, mildly damped by routine news. Approximate integer levels are assigned from this continuous value (0 below ±0.35, ±1 up to 1.35, ±2 from 1.35, ±3 from 2.3 **only when at least two independent directional events support that extreme**). When there are fewer than 3 directional events in a month, the card shows **Limited coverage**. Scores are **not price forecasts**, and claims—particularly rumours—can be false. No arbitrary bullish offset is added.

## Moon Meter calibration

The `scripts/moon_meter.py` headline rules now recognise the potential if-true effect of real stock-listing milestones, XRP-per-diluted-share growth targets, wider share distribution, institutional execution partnerships and scaled XRP treasury yield opportunities. Exceptional +3 is possible for a large, multi-partner XRP yield-deployment scenario, but does **not** imply that revenue, profits or risk-adjusted value have been realised. SEC registration, financing dilution and large treasury drawdowns remain potentially bearish. MSTR preferred-stock repurchases are assessed conditionally: pausing BTC purchases can offset part of their potential benefit. +3 is not a target quota: some months will have none, and a neutral headline without a clear catalyst stays neutral.

## Moon Meter (−3 to +3)

The Moon Meter is a calibrated **IF-TRUE scenario gauge**, scoring the potential directional impact on **XRP**, **XRPN**, **MSTR**, **LITS**, **PURR**, **SBET** or **FWDI** if a published report, rumour or forward-looking assumption were to prove true. Scores run from −3 (very bearish) to +3 (very bullish). A +3 does **not** mean a rumour is likely true, nor predict a price move. Each meter independently shows whether its source is a **reported development**, **assumption** or **unverified rumour**. A neutral 0 means no clear impact even if true; **Not rated (—)** is reserved for headlines too thin to assess. Investor-news impact is separate from price direction. Pure price-target speculation remains filtered out.

## Run locally

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/scan.py
python -m http.server 8000
```

The site is static HTML/CSS/JS; Python is used only for the scheduled collector. Sources can be delayed or incomplete; always verify underlying reports before any investment decision.


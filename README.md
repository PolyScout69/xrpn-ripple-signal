# Signal — investor intelligence

**Live dashboard:** https://polyscout69.github.io/xrpn-ripple-signal/

Independent investor news for **Evernorth Holdings (XRPN)**, **Ripple**, **XRP Ecosystem (XRPL)**, and **Strategy (MSTR)**.

## Sources and publishing

- **Three times daily, at approximately 09:15, 14:35 and 23:35 UTC**, GitHub Actions runs `scripts/scan.py`, updates `data/news.json`, and deploys GitHub Pages. The 09:15 scan focuses on early UK and continental European announcements after their opening release window, the 14:35 scan catches US pre-market/early-session headlines, and the 23:35 scan captures US market-close and evening releases. Scans run every day, including weekends. GitHub Actions schedules can start late during platform congestion and use fixed UTC hours (so local times vary with daylight saving). Pushes to `main` and manual dispatches also run the workflow.
- Signal monitors Ripple and Evernorth official announcements and targeted business and ecosystem news feeds, including Strategy's Bitcoin treasury activity and company developments.
- **Standalone SEC filing records are intentionally excluded** from news cards, source monitoring and the Moon Meter. A news report about material financing, partnerships, regulation or other events may still appear, but standalone filing entries do not.
- Multiple publications of the same event are grouped with additional source links.
- Source Health reflects **three** channels: Ripple official, Evernorth official, and issuer/ecosystem news.

## Homepage share-price widgets

The top of the homepage shows **XRPN (Evernorth)** and **MSTR (Strategy)** in separate compact USD quote widgets, including each stock's **daily percentage change**. These are the official free [TradingView Single Ticker](https://www.tradingview.com/widget-docs/widgets/tickers/single-ticker/) web components, configured for `NASDAQ:XRPN` and `NASDAQ:MSTR`; no paid API key is required. Quotes are fetched in the visitor's browser independently of the three daily news scans. TradingView supplies **delayed US stock quotes** in public widgets; do not label them real-time Nasdaq prices. A direct link to each stock page remains available if the third-party widget cannot load. The widget may issue requests to TradingView and follows TradingView's third-party privacy practices.

## Moon Sentiment — XRPN and MSTR, 30 days

The two bottom cards of the homepage score **weighted 30-day Moon Sentiment** for XRPN and MSTR, replacing the old **Treasury News** and **Source Coverage** cards. Individual Moon Meters remain visible on every story; source-health remains available in its existing monitoring panel.

The calculation runs during each of the three daily news scans and publishes \`sentiment_30d\` into \`data/news.json\`, including the rounded −3 to +3 score, raw score, source counts and top contributing stories. **A 0 headline is not a negative vote**: neutral articles only add 8% of their normal weight to the denominator. Only evidence with a signed directional Moon Meter contributes directly to the numerator.

For each unique event the model uses:

- **Impact:** High 4.5×, Medium 2.25×, Low 1×. This is not the same as source confidence or a probability of the event happening.
- **Freshness:** exponentially decaying weight with a **17-day half-life**, limited to news from the last 30 days.
- **Reporting / assumption status:** official sources 1.15×, other publishers 1×; reported events 1×, forward-looking assumptions 0.90×, and rumours 0.72×. The lower confidence on rumours limits their dominance over independently corroborated news, while their **if-true** impact rating is retained.
- **Strength of a catalyst:** ±2 signals gain a 1.2× magnitude weighting, ±3 a 1.4× magnitude weighting. Genuine major negative news offsets positive news rather than being discarded.
- **One economic event, one major contribution:** reports covering the same identifiable event family and ISO week are grouped by asset and sign, using the strongest specific report. Syndication cannot inflate the score by repeating a headline.

The index is the directional weighted mean, mildly damped by routine news. Approximate integer levels are assigned from this continuous value (0 below ±0.35, ±1 up to 1.35, ±2 from 1.35, ±3 from 2.3 **only when at least two independent directional events support that extreme**). When there are fewer than 3 directional events in a month, the card shows **Limited coverage**. Scores are **not price forecasts**, and claims—particularly rumours—can be false. No arbitrary bullish offset is added.

## Moon Meter calibration

The \`scripts/moon_meter.py\` headline rules now recognise the potential if-true effect of real stock-listing milestones, XRP-per-diluted-share growth targets, wider share distribution, institutional execution partnerships and scaled XRP treasury yield opportunities. Exceptional +3 is possible for a large, multi-partner XRP yield-deployment scenario, but does **not** imply that revenue, profits or risk-adjusted value have been realised. SEC registration, financing dilution and large treasury drawdowns remain potentially bearish. +3 is not a target quota: some months will have none, and a neutral headline without a clear catalyst stays neutral.

## Moon Meter (−3 to +3)

The Moon Meter is a calibrated **IF-TRUE scenario gauge**, scoring the potential directional impact on **XRP**, **XRPN** or **MSTR** if a published report, rumour or forward-looking assumption were to prove true. Scores run from −3 (very bearish) to +3 (very bullish). A +3 does **not** mean a rumour is likely true, nor predict a price move. Each meter independently shows whether its source is a **reported development**, **assumption** or **unverified rumour**. A neutral 0 means no clear impact even if true; **Not rated (—)** is reserved for headlines too thin to assess. Investor-news impact is separate from price direction. Pure price-target speculation remains filtered out.

## Run locally

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/scan.py
python -m http.server 8000
```

The site is static HTML/CSS/JS; Python is used only for the scheduled collector. Sources can be delayed or incomplete; always verify underlying reports before any investment decision.

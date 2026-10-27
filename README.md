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

## Moon Meter (−3 to +3)

The Moon Meter is an **IF-TRUE scenario gauge**, scoring the potential directional impact on **XRP**, **XRPN** or **MSTR** if a published report, rumour or forward-looking assumption were to prove true. Scores run from −3 (very bearish) to +3 (very bullish). A +3 does **not** mean a rumour is likely true, nor predict a price move. Each meter independently shows whether its source is a **reported development**, **assumption** or **unverified rumour**. A neutral 0 means no clear impact even if true; **Not rated (—)** is reserved for headlines too thin to assess. Investor-news impact is separate from price direction. Pure price-target speculation remains filtered out.

## Run locally

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/scan.py
python -m http.server 8000
```

The site is static HTML/CSS/JS; Python is used only for the scheduled collector. Sources can be delayed or incomplete; always verify underlying reports before any investment decision.

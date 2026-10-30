"""Scenario-based, transparent headline Moon Meter for Signal.

Direction scores estimate potential asset impact IF the reported claim, rumour
or assumption proves true. This is not a probability-of-truth estimate,
price prediction, trade recommendation or examination of full filing contents.
"""
from __future__ import annotations

import re

ENTITY_ASSETS = {
    'Ripple': 'XRP',
    'Evernorth': 'XRPN',
    'Strategy': 'MSTR',
    'Lite Strategy': 'LITS',
    'Hyperliquid Strategies': 'PURR',
    'SharpLink Gaming': 'SBET',
    'Forward Industries': 'FWDI',
}
STOCK_ASSETS = ('MSTR', 'XRPN', 'LITS', 'PURR', 'SBET', 'FWDI')
LABELS = {
    -3: 'Very bearish',
    -2: 'Bearish',
    -1: 'Slightly bearish',
     0: 'Neutral',
     1: 'Slightly bullish',
     2: 'Bullish',
     3: 'Very bullish',
}


def _contains(text: str, *expressions: str) -> bool:
    return any(re.search(exp, text, re.IGNORECASE) for exp in expressions)



def scenario_kind(item: dict) -> str:
    """Keep verification separate from potential impact if the claim is true."""
    text = re.sub(r'\s+', ' ', str(item.get('title', '')) + ' ' + str(item.get('excerpt', '')))
    if _contains(text, r'\brumou?rs?\b', r'\bunconfirmed\b', r'\bnot confirmed\b',
                 r'\bspeculat(?:ion|ive|es?)\b', r'\breportedly\b', r'\bunverified\b',
                 r'\bunnamed sources?\b'):
        return 'rumour'
    if _contains(text, r'\b(?:could|might|may|would|potential(?:ly)?|possible)\b',
                 r'\b(?:considering|exploring|in talks)\b', r'\bplans? to\b',
                 r'\bpropos(?:al|ed)\b', r'\bassum(?:e|ing|ption)\b'):
        return 'assumption'
    return 'reported'


def _assess(item: dict, asset: str) -> tuple[int, str]:
    title = str(item.get('title', '')).lower()
    excerpt = str(item.get('excerpt', '')).lower()
    # Do not consider the generic investor-angle commentary: it frequently
    # mentions risks even when the underlying headline contains no such news.
    combined = re.sub(r'\s+', ' ', title + ' ' + excerpt)
    official = item.get('source_type') in ('Official', 'SEC')
    stock = asset in STOCK_ASSETS
    is_sec = item.get('source_type') == 'SEC'

    # Primary SEC entry titles list forms and item numbers, NOT what a filing
    # actually establishes; do not derive bullishness from form numbers.
    if is_sec and re.search(r'\bfiles? form\b', title):
        return 0, 'Filing type and item numbers alone do not establish a price direction; read the filing and exhibits.'

    if _contains(combined,
                 r'\bchapter 11\b', r'\bbankrupt(?:cy)?\b', r'\binsolvenc\w*\b',
                 r'\bgoing.concern warning\b', r'\bdefaults? on (?:its |the )?debt\b',
                 r'\bsec (?:charges|sues)\b', r'\bfraud charges\b',
                 r'\blicen[cs]e revoked\b', r'\btrading (?:halted|suspended)\b'):
        return (-3 if official else -2), 'Severe solvency, enforcement or trading risk reported; confirm the primary disclosure.'

    if _contains(combined,
                 r'\b(?:security )?(?:hack|exploit|breach)\b',
                 r'\bnetwork (?:halt|outage)\b',
                 r'\betf (?:rejected|denied)\b',
                 r'\b(?:application|approval) denied\b',
                 r'\bcourt rules? against\b',
                 r'\bregulatory (?:ban|penalty|sanction)\b',
                 r'\b(?:earnings|revenue|profit) (?:miss|plunge|falls?|declines?)\b',
                 r'\b(?:material|major) loss\b'):
        return -2, 'Adverse security, regulatory or financial event; scope and permanence need verification.'

    if stock and _contains(combined,
                           r'\bdilut(?:ion|ive|ed)\b',
                           r'\bequity (?:purchase )?facility\b',
                           r'\bat.the.market (?:offering|program|equity)\b',
                           r'\b(?:new|additional) (?:common )?shares? issued\b',
                           r'\bsecondary (?:stock )?offering\b', r'\bshare sale\b',
                           r'\b(?:stock|share) offering\b',
                           r'\b(?:convertible|preferred) (?:stock|notes?|shares?) (?:issued|offering|sale)\b'):
        if _contains(combined, r'\b(?:deep|heavy|steep) discount\b', r'\bmassive dilution\b'):
            return -2, 'Discounted issuance could materially dilute existing shareholders; assess fully diluted shares.'
        return -1, 'Potential issuance or dilution weighs on per-share value; proceeds and accretion may offset it.'

    if _contains(combined, r'\b(?:ceo|cfo|chief executive) resigns?\b',
                 r'\bexecutive (?:departure|resignation)\b',
                 r'\b(?:guidance|forecast) cut\b', r'\b(?:btc|xrp|ltc|litecoin|hype|eth|ether|ethereum|sol|solana) (?:sold|liquidated)\b'):
        return -1, 'Leadership, outlook or treasury reduction may be a headwind; materiality is not yet established.'

    # Reserve +3 for unambiguous, exceptional earnings evidence (not generic
    # press adjectives like 'game-changing partnership').
    if stock and _contains(combined, r'\b(?:audited|reported|reports|report) (?:record|strongest) (?:net )?(?:profit|earnings)\b') and _contains(combined,
               r'\b(?:beats?|exceeds?) (?:analyst )?(?:expectations|estimates|guidance)\b'):
        return (3 if official else 2), 'Exceptional reported profitability beating expectations; verify earnings and sustainability.'

    if _contains(combined,
                 r'\bsec approves? (?:spot )?xrp etf\b', r'\bspot xrp etf (?:approved|authori[sz]ed)\b',
                 r'\b(?:xrp )?etf approval granted\b',
                 r'\bcourt (?:rules?|ruling) in (?:ripple.s|xrp.s) favou?r\b',
                 r'\b(?:sec|lawsuit) (?:dismissed|settled in ripple.s favor)\b') and asset == 'XRP':
        return 2, 'A confirmed XRP-related regulatory catalyst could improve access or reduce uncertainty.'

    if stock and _contains(combined,
                          r'\b(?:completes?|completed|announces?) (?:a )?(?:major )?(?:share )?buyback\b',
                          r'\b(?:repurchased|repurchases) (?:its )?(?:common )?shares?\b',
                          r'\b(?:net )?(?:profit|earnings|free cash flow) (?:jumps?|surges?|beats?)\b'):
        return 2, 'Stronger per-share economics or operating results may support the shares; verify amounts.'

    if _contains(combined, r'\b(?:signed|completed) (?:a )?(?:multi.year|long.term) (?:commercial )?(?:contract|agreement)\b',
                 r'\b(?:records?|reports?) (?:higher|record) (?:revenue|transaction volume|adoption)\b'):
        if asset == 'XRP' and not _contains(combined,r'\bxrp\b',r'\bxrpl\b',r'\bxrp ledger\b'):
            return 0, 'Commercial growth for Ripple does not necessarily translate into XRP-token demand.'
        return 2, 'Evidence of sustained commercial use or contracted business could improve economics.'

    if stock and _contains(combined,
                          r'\b(?:buys?|purchases?|acquires?|adds?) (?:\d[\d,.]* )?(?:more )?(?:bitcoin|btc|xrp|ltc|litecoin|hype|eth|ether|ethereum|sol|solana)\b',
                          r'\b(?:increases?|boosts?|expands?) (?:its )?(?:bitcoin|btc|xrp|ltc|litecoin|hype|eth|ether|ethereum|sol|solana) (?:holdings|treasury|reserves)\b',
                          r'\b(?:bitcoin|btc|xrp|ltc|litecoin|hype|eth|ether|ethereum|sol|solana) per share (?:rises?|increases?)\b'):
        return 1, 'Treasury growth could help if it is accretive per diluted share after funding and risk.'

    if asset == 'XRP':
        has_xrp = _contains(combined,r'\bxrp\b',r'\bxrpl\b',r'\bxrp ledger\b')
        if _contains(combined,
                     r'\b(?:xrp ledger|xrpl) (?:amendment |upgrade )?(?:activated|goes live|adopted)\b',
                     r'\b(?:xrp ledger|xrpl) (?:settles?|processes?)\b',
                     r'\b(?:spot )?xrp etf (?:launches?|listed|goes live)\b'):
            return 1, 'An implemented XRP-network or market-access milestone could improve utility or access.'
        if has_xrp and _contains(combined,r'\b(?:partnership|partners?|integration|integrates?)\b',
                                r'\b(?:institutional|network) adoption\b',
                                r'\b(?:launches?|introduces?) (?:a |an )?(?:new )?(?:on.chain|xrp|xrpl)\b',
                                r'\b(?:record|all.time high) (?:wallets?|users?|transactions?)\b'):
            return 1, 'Possible XRP ecosystem adoption; actual XRP usage and lasting demand remain unproven.'
        if not has_xrp and _contains(combined,r'\brlusd\b',r'\bripple\b'):
            return 0, 'Ripple business or RLUSD news may have only indirect, unquantified effects on XRP.'

    if stock and _contains(combined,
                           r'\b(?:partners?|partnership|collaborat\w*)\b',
                           r'\b(?:product|platform) launch\b'):
        return 1, 'Potential operational opportunity, but revenue and per-share value remain unquantified.'

    if item.get('category') == 'SEC filings':
        return 0, 'A filing is significant to review, but its form or headline alone is directionally inconclusive.'
    return 0, 'No clear asset-specific price catalyst established by this headline and summary.'



def _assess_v2(item: dict, asset: str) -> tuple[int | None, str, str]:
    """Asset-specific upside/downside IF the story or hypothesis proves true."""
    title = str(item.get('title', '')).lower()
    excerpt = str(item.get('excerpt', '')).lower()
    combined = re.sub(r'\s+', ' ', title + ' ' + excerpt)
    official = item.get('source_type') in ('Official', 'SEC')
    scenario = scenario_kind(item)
    evidence = ('Unverified' if scenario == 'rumour' else
                'Conditional' if scenario == 'assumption' else
                'High' if official else 'Medium')
    stock = asset in STOCK_ASSETS

    # Filing indexes contain form names and item numbers, not the facts inside.
    if item.get('source_type') == 'SEC' and _contains(title,
           r'\bfiles? (?:a )?form\b', r'\bform (?:8-k|10-k|10-q|s-3|s-1|4)\b.*\breported items\b',
           r'\bsec (?:8-k|10-k|10-q|s-3|s-1) filed\b'):
        return None, 'Filing index only: its contents have not been analysed, so no defensible direction can be inferred.', 'Insufficient'
    # Unverified claims are rated for their IF-TRUE impact and tagged as rumours.
    # Never present a directional score as evidence that the rumour is true.

    # Editorial price speculation has no new issuer/network fact to rate.
    if _contains(title, r'\bbubble bursting\?', r'\bis (?:the )?(?:mstr|xrpn|xrp) (?:bubble|rally) (?:bursting|over)\?'):
        return None, 'Speculative market commentary, not a verified company or network development.', 'Insufficient'

    # Obvious solvency disasters must outrank positive-looking partnership
    # language in the same headline, including in unverified rumours.
    if _contains(combined, r'\bchapter 11\b', r'\bbankrupt(?:cy)?\b',
                 r'\binsolven\w*\b', r'\bgoing.concern\b', r'\bfraud charges\b'):
        return -3, 'If a severe solvency or enforcement crisis is genuine, substantial downside is possible.', evidence

    # Material mark-to-market losses still matter to a coin-backed stock,
    # even where they are not realised cash losses. Do not treat a daily
    # stock-price move alone as a fresh operating catalyst.
    if stock and _contains(combined, r'\b(?:xrp|bitcoin|btc|ltc|litecoin|hype|hyperliquid|eth|ether|ethereum|sol|solana|treasury)\b') and _contains(combined,
                      r'\b(?:lose|lost|loss|drop|fall|down)\b') and _contains(combined,
                      r'\$\s*[\d,.]+\s*(?:million|m|billion|bn)\b'):
        return -2, 'If the reported large treasury drawdown is correct, lower asset backing could materially affect shareholder value.', evidence

    if asset in ('SBET', 'FWDI'):
        coin = r'(?:eth|ether|ethereum)' if asset == 'SBET' else r'(?:sol|solana)'
        if _contains(combined,
                     rf'\b(?:abandons?|ends?|exits?|liquidates?)\b.{{0,55}}\b{coin}\b.{{0,25}}\btreasury\b'):
            return -3, f'If the issuer abandons its core crypto treasury strategy, the {asset} investment thesis could be severely impaired.', evidence
        # Staking and custody failures take priority over yield or partnership
        # language in the same report. Merely discussing a risk is not a loss.
        if _contains(combined,
                     r'\b(?:hack|exploit|breach|slashed|slashing loss)\b',
                     r'\b(?:withdrawals?|custody assets?)\b.{0,35}\b(?:frozen|suspended|blocked)\b',
                     r'\b(?:custodian|counterparty|validator)\b.{0,35}\b(?:defaults?|fails?|failure)\b'):
            return -2, f'If the reported custody, counterparty or staking failure affects treasury assets, {asset} backing and access to funds could suffer.', evidence

    if stock and _contains(title, r'\b(?:registers?|registered|registration)\b') and _contains(title,
                         r'\bshares?\b') and _contains(title,r'\b(?:warrants?|issuance|new)\b'):
        return -1, 'Registered shares or warrants create potential future dilution; net treasury accretion is unknown.', evidence

    # Completion of the issuer's public listing removes execution/access
    # risk, but does not by itself prove appreciation per diluted share.
    if asset == 'XRPN':
        if _contains(title, r'\b(?:completes?|completed)\s+(?:its\s+)?(?:business combination|merger)\b'):
            return 2, 'If the transaction closes as reported, listing/treasury-access risk falls; valuation remains uncertain.', evidence
        if _contains(title, r'\b(?:nasdaq|go(?:es|ing)? public)\b') and _contains(title,
                            r'\b(?:debut|debuts|lists?|listing|begins trading|went public|go public)\b'):
            return 2, 'If completed, public-market access and XRP treasury exposure could broaden the investor base.', evidence
        if _contains(title, r'\bsec (?:nod|clearance|approval)\b', r'\bsec approves?\b') and _contains(title,
                            r'\b(?:nasdaq|listing|go public)\b'):
            return 2, 'If the necessary listing approvals hold, a material execution hurdle is reduced.', evidence
        if _contains(title, r'\buphold\b') and _contains(title,
                            r'\b(?:lists?|listing|available|access)\b'):
            return 1, 'If distribution broadens investor access to XRPN shares, demand could improve modestly.', evidence
        if _contains(combined, r'\b(?:targets?|targeting|higher|grow|boost|increase)\b') and _contains(combined,
                            r'\bxrp per (?:(?:fully )?diluted )?share\b'):
            return 2, 'If the strategy increases XRP per diluted share, treasury accretion could create meaningful upside.', evidence
        if _contains(combined, r'\binaugural institutional execution partners?\b',
                     r'\bnames? institutional execution partners?\b'):
            return 2, 'If the institutional execution relationships deliver scalable, economical XRP deployment, they could improve XRPN operations.', evidence

    if asset == 'MSTR':
        if _contains(combined, r'\bhidden dependency\b',
                     r'\breliance on (?:its |own )?buybacks?\b',
                     r'\bartificially supported by (?:its |own )?buybacks?\b'):
            return -1, 'If STRC liquidity or its market price depends materially on issuer buybacks, financing fragility could weigh on MSTR.', evidence
        if _contains(combined, r'\brepurchas\w*\b', r'\bredeem\w*\b', r'\bbuybacks?\b') and _contains(combined,
                            r'\b(?:strc|strk|strf|preferred (?:stock|shares?))\b'):
            if _contains(combined,
                         r'\bpaus\w*\b.{0,45}\b(?:bitcoin|btc)\b',
                         r'\b(?:bitcoin|btc)\b.{0,45}\bpaus\w*\b'):
                return 1, 'If preferred buybacks reduce financing costs, they may help, but paused BTC accumulation offsets some upside.', evidence
            return 2, 'If the preferred-share repurchase reduces financing obligations without undue cost, per-share economics could benefit.', evidence

    if asset == 'PURR':
        # PURR is equity in the independent HYPE treasury issuer, not the
        # Hyperliquid protocol token. Only issuer-specific news is routed here.
        if _contains(combined,
            r'\b(?:abandons?|exits?|liquidates?)\b.{0,55}\b(?:hype|hyperliquid)\b.{0,25}\btreasury\b'):
            return -3, 'If the issuer abandons its HYPE treasury strategy, the PURR investment thesis could be severely impaired.', evidence
        if _contains(combined, r'\b(?:100|100\.0)\s*(?:million|m)\b') and _contains(combined,
            r'\b(?:stock|share)\s+repurchase\b', r'\bbuy[\s-]?back\b') and _contains(combined,
            r'\b(?:program|authoriz\w*|increase|raises?|expand\w*)\b'):
            return 1, 'If the enlarged PURR buyback authorisation is used prudently below asset value, per-share backing may improve; approval alone is not an executed repurchase.', evidence
        if _contains(combined,
            r'\b(?:repurchas\w*|buy[\s-]?backs?|bought back)\b') and _contains(combined,
            r'\b(?:purr|shares?|common stock)\b'):
            if _contains(combined,r'\b(?:below|discount to)\b.{0,25}\b(?:nav|net asset value)\b',
                         r'\bhype per (?:fully diluted |diluted )?share\b'):
                return 3, 'If material repurchases below NAV increase HYPE per diluted share substantially, PURR could experience exceptional accretion.', evidence
            return 2, 'If executed at an attractive discount to HYPE-backed NAV, share repurchases could increase PURR treasury backing per share.', evidence
        if _contains(combined, r'\bstaking revenue\b',r'\bvalidator commissions?\b') and _contains(combined,
            r'\b(?:9\.5\s*million|[1-9]\d?\.\d\s*million|material|record|grew|increased|earns?|generated)\b'):
            return 2, 'If material recurring HYPE staking and validator income is sustainable after costs and risks, PURR could benefit.', evidence
        if _contains(combined,r'\b(?:launch(?:es|ed)?|announc\w*|operat\w*|activat\w*)\b') and _contains(combined,
            r'\bvalidator\b',r'\bstaking\b'):
            return 1, 'If the HYPE validator or staking operation generates reliable net yield, it could incrementally compound the treasury.', evidence
        if _contains(combined,r'\b(?:hype|hyperliquid)\b') and _contains(combined,
            r'\b(?:staking yield|treasury yield|validator income|defi optimization)\b'):
            return 2, 'If active deployment of the HYPE treasury generates material risk-adjusted income, PURR economics could improve.', evidence

    if asset == 'LITS':
        # Company-specific signals: LTC/share and capital allocation matter
        # more to LITS than general LTC network headlines or MEI-era biotech.
        if _contains(combined,
                    r'\b(?:abandons?|ends?|exits?|liquidates?)\b.{0,55}\b(?:ltc|litecoin)\b.{0,20}\btreasury\b'):
            return -3, 'Abandoning or liquidating the Litecoin treasury would undermine the central LITS investment thesis.', evidence
        if _contains(combined, r'\b(?:repurchas\w*|buy[\s-]?backs?|bought back)\b') and _contains(
                combined, r'\b(?:shares?|stock)\b'):
            percent_match = re.search(
                r'\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:its\s+|the\s+)?(?:outstanding\s+)?shares?\b',
                combined)
            percent = float(percent_match.group(1)) if percent_match else 0.0
            if percent >= 10 and _contains(combined,r'\b(?:ltc|litecoin)\b') and _contains(
                    combined,r'\b(?:per share|backing|holdings)\b'):
                return 3, ('If retiring 10%+ of outstanding shares meaningfully increases LTC '
                           'backing per diluted share without damaging liquidity, LITS upside could be exceptional.'), evidence
            return 2, 'If LITS repurchases shares at an attractive discount to LTC NAV, holdings per share may improve.', evidence
        if _contains(combined,r'\b(?:covered call|covered-call|options? premiums?)\b') and _contains(
                combined,r'\b(?:ltc|litecoin|treasury|yield)\b'):
            if _contains(combined,r'\b(?:generat\w*|earns?|earned|proceeds|receiv\w*)\b'):
                return 2, 'If repeatable covered-call income exceeds trading, tax and option risks, LTC treasury yield could benefit LITS.', evidence
            return 1, 'If adopted prudently, covered-call treasury income may help LITS, with upside caps and counterparty risks.', evidence
        if _contains(combined,r'\blitvm\b') and _contains(combined,r'\b(?:invest\w*|partner\w*|stake)\b'):
            return 1, 'If LitVM adoption materialises, the strategic investment may add ecosystem optionality; value remains uncertain.', evidence
        if _contains(combined,r'\b(?:litecoin|ltc)\b') and _contains(
                combined,r'\b(?:yield|treasury income|lending|income generat\w*)\b'):
            return 2, 'If active Litecoin treasury deployment creates material net income, LITS economics could improve.', evidence

    # Financing terms matter more than planned gross coin accumulation.
    if stock and _contains(title,
           r'\bnew (?:xrpn |mstr |lits |purr |sbet |fwdi )?(?:stock )?shares\b',
           r'\bfiling for [\d,.]+m? new (?:xrpn |mstr |lits |purr |sbet |fwdi )?(?:stock )?shares\b'):
        return -1, 'New shares may dilute holders even if the proceeds acquire more cryptocurrency; check the diluted share count.', evidence
    if stock and _contains(title, r'\brais(?:e|es|ing) funds? to (?:buy|purchase) (?:more )?(?:xrp|bitcoin|btc|ltc|litecoin|hype|eth|ether|ethereum|sol|solana)\b'):
        return 0, 'Planned funding and buying alone do not establish net accretion or dilution per share.', evidence

    # Treasury-company signal: coins per diluted share, not total coins acquired.
    if stock:
        coin = ('xrp' if asset == 'XRPN' else
                r'(?:ltc|litecoin)' if asset == 'LITS' else
                'hype' if asset == 'PURR' else
                r'(?:eth|ether|ethereum)' if asset == 'SBET' else
                r'(?:sol|solana)' if asset == 'FWDI' else r'(?:bitcoin|btc)')
        if _contains(combined, rf'\b{coin} per (?:(?:fully )?diluted )?share\b'):
            percent = re.search(r'\b(?:by |up |down )?(\d{1,3}(?:\.\d+)?)\s*%', combined)
            amount = float(percent.group(1)) if percent else None
            fully = _contains(combined, r'\bfully diluted\b', r'\bafter dilution\b', r'\bnet of issuance\b')
            down = _contains(combined, r'\b(?:down|fall|falls|fell|drop|drops|dropped|decline|declines|declined|decrease|decreases|decreased)\b')
            up = _contains(combined, r'\b(?:up|rise|rises|rose|increase|increases|increased|grow|grows|grew)\b')
            if down:
                if amount is not None and amount >= 40 and official and fully:
                    return -3, 'Primary source reports a severe decline in coin holdings per diluted share.', evidence
                if amount is not None and amount >= 10:
                    return -2, 'Material decline in coin holdings per share; assess the fully diluted share count.', evidence
                return -1, 'Reported decline in coin holdings per share; materiality remains uncertain.', evidence
            if up:
                if amount is not None and amount >= 20 and fully:
                    return 3, 'If realised, 20%+ growth in coin holdings per diluted share would be exceptionally accretive.', evidence
                if amount is not None and amount >= 5:
                    return 2, 'If realised, meaningful coin-per-share growth would be bullish; verify dilution and funding.', evidence
                return 1, 'Coin holdings per share may have improved, subject to dilution and funding costs.', evidence
        if official and _contains(combined, r'\b(?:severe|massive) dilution (?:confirmed|completed)\b',
                          r'\bshares? issued at (?:a )?(?:deep|steep) discount\b'):
            return -2, 'Confirmed materially discounted issuance threatens per-share value.', evidence

    if asset in ('SBET', 'FWDI'):
        # Only company-tagged stories reach this branch. A token rally or a
        # network staking headline cannot create an equity Moon Meter by itself.
        fallback_score, fallback_reason = _assess(item, asset)
        if fallback_score < 0:
            return fallback_score, fallback_reason, evidence
        repurchase = _contains(combined, r'\brepurchas\w*\b', r'\bbuy[\s-]?backs?\b', r'\bbought back\b')
        if repurchase and _contains(combined, r'\b(?:shares?|stock|sbet|fwdi)\b'):
            executed = _contains(combined,
                r'\b(?:repurchased|repurchases|bought back)\b',
                r'\bcompleted\b.{0,35}\b(?:repurchase|buy[\s-]?back)\b')
            if not executed:
                return 1, f'If the {asset} buyback plan is executed prudently below asset value, backing per share may improve; authorisation alone is not a completed repurchase.', evidence
            if _contains(combined, r'\b(?:below|discount to)\b.{0,25}\b(?:nav|net asset value)\b'):
                return 2, f'If completed repurchases below NAV improve net crypto backing per diluted share, {asset} shareholders could benefit.', evidence
            return 1, 'Executed repurchases may improve per-share value, but price paid, funding and remaining treasury liquidity determine accretion.', evidence
        staking_income = _contains(combined,
            r'\bstaking (?:rewards?|revenue|income|yield)\b', r'\bvalidator (?:revenue|income|commissions?)\b')
        if staking_income and _contains(combined,
            r'\b(?:earns?|earned|generat\w*|receiv\w*|record|increas\w*|grew)\b'):
            return 2, f'If recurring staking income exceeds fees, custody and validator risks, it could compound {asset} treasury backing; verify net income and diluted shares.', evidence
        if _contains(combined, r'\b(?:staking|restaking|validator|liquid staking)\b') and _contains(combined,
            r'\b(?:launch\w*|deploy\w*|stake[sd]?|partner\w*|announc\w*|operat\w*|activat\w*)\b'):
            return 1, f'If the staking or validator deployment produces sustainable net yield after counterparty and lock-up risks, {asset} could benefit incrementally.', evidence
    if asset == 'XRP':
        if official and _contains(combined, r'\b(?:sec|regulator) approves? (?:spot )?xrp etf\b',
                                 r'\bspot xrp etf approved\b') and _contains(combined, r'\b(?:net|verified|confirmed) (?:fund )?inflows?\b'):
            return 3, 'Primary reporting confirms regulated XRP access and observed net investment flows.', evidence
        if official and _contains(combined, r'\bpermanent (?:xrp ledger|xrpl|network) (?:halt|shutdown|failure)\b'):
            return -3, 'Verified extraordinary XRPL network disruption threatens token utility.', evidence
        if _contains(combined, r'\b(?:xrpl|xrp ledger) (?:bug fix|amendment|upgrade) (?:is )?(?:delayed|postponed|stalled)\b',
                     r'\b(?:bug fix|amendment|upgrade) (?:is )?(?:delayed|postponed|stalled)\b'):
            return -1, 'Delay or validator friction could modestly slow XRPL functionality.', evidence
    # IF-TRUE upside: rate plausible material scenarios without requiring
    # revenues, token flows or transaction volumes to have happened already.
    # These scores do NOT indicate that the claim itself is credible.
    if asset == 'XRP':
        direct_xrp = _contains(combined, r'\bxrp\b', r'\bxrpl\b', r'\bxrp ledger\b')
        adoption = _contains(combined, r'\bpartner(?:ship|s|ed)?\b',
                             r'\bintegrat(?:e|es|ed|ion)\b', r'\bsettle(?:ment|s|d)?\b',
                             r'\badopt(?:s|ed|ion)?\b', r'\btokeniz\w*\b',
                             r'\buse(?:s|d)?\b')
        systemic = _contains(combined, r'\bswift\b', r'\bblackrock\b',
                             r'\bfederal reserve\b', r'\bcentral banks?\b',
                             r'\bmajor global banks?\b', r'\bglobal settlement\b')
        if direct_xrp and systemic and adoption:
            return 3, 'A major financial-network integration using XRP, if realised, could transform adoption and demand.', evidence
        if direct_xrp and _contains(combined,
            r'\b(?:sec|regulator) approves? (?:spot )?xrp etf\b',
            r'\bspot xrp etf (?:approved|authori[sz]ed)\b',
            r'\bxrp etf approval granted\b'):
            return 3, 'If realised, regulated spot ETF access could unlock substantial demand; future flows remain unknown.', evidence
        if direct_xrp and adoption:
            return 2, 'If implemented at scale, direct XRP/XRPL adoption could increase utility and potential token demand.', evidence
        if _contains(combined, r'\bripple\b', r'\brlusd\b') and _contains(combined,
            r'\bpartner(?:ship|s|ed)?\b', r'\bplatform\b', r'\btreasury\b',
            r'\bproduct\b', r'\blaunch(?:es|ed)?\b', r'\bpayments?\b',
            r'\bcustody\b', r'\bcommercial\b'):
            return 1, 'Assuming Ripple business expansion ultimately benefits XRP usage, the indirect upside could be positive.', evidence

    if asset == 'XRPN':
        # Exceptional IF-TRUE upside requires *both* unusually large balance-
        # sheet exposure and multiple institutional execution relationships.
        # This is a scenario score, never a claim of realised yield or profit.
        yield_plan = _contains(combined, r'\byield\b', r'\blending\b',
                               r'\b(?:treasury|xrp)\b.{0,50}\b(?:to work|put to work|deployment)\b')
        usd_sizes = [float(x) * (1000 if unit in ('billion','bn') else 1)
                     for x, unit in re.findall(
                         r'\$\s*(\d+(?:\.\d+)?)\s*(million|m|billion|bn)\b', combined)]
        xrp_sizes = [float(x) for x in re.findall(
                         r'\b(\d+(?:\.\d+)?)\s*(?:million|m)\s+xrp\b', combined)]
        multiple_partners = (
            sum(p in combined for p in ('ripple','coinbase','kraken','bitgo')) >= 2 or
            _contains(combined, r'\b(?:four|4|multiple)\s+institutional\s+partners?\b')
        )
        if yield_plan and multiple_partners and (
                any(x >= 500 for x in usd_sizes) or any(x >= 400 for x in xrp_sizes)):
            return 3, ('If large-scale institutional XRP yield deployment produces material, '
                       'sustainable net income after risk and funding costs, the impact on XRPN could be exceptional.'), evidence
        if _contains(combined, r'\bmerger\b', r'\bbusiness combination\b') and _contains(combined,
            r'\bvote\b', r'\bshareholders?\b') and _contains(combined,
            r'\bpasses?\b', r'\bapproved?\b', r'\bwins?\b'):
            return 2, 'If the reported merger approval is valid and closes, it could remove uncertainty and improve XRPN market access.', evidence
        if _contains(combined, r'\bxrp\b') and _contains(combined,
            r'\byield\b', r'\blending\b', r'\blends?\b', r'\bcollateral\b',
            r'\bearn(?:s|ing)? interest\b', r'\bincome from (?:its )?treasury\b'):
            return 2, 'If XRP treasury assets generate material net income without offsetting dilution or losses, XRPN could benefit.', evidence
        if _contains(combined, r'\bpartner(?:ship|s|ed)?\b',
            r'\bacqui(?:re|res|red|sition)\b', r'\bcommercial (?:deal|agreement)\b') and _contains(combined,
            r'\bxrp\b', r'\btreasury\b', r'\binstitution\b', r'\bbank\b'):
            return 2, 'If the proposed relationship produces material treasury or commercial value per share, XRPN could benefit.', evidence

    score, reason = _assess(item, asset)
    if scenario == 'rumour' and score <= -2 and _contains(combined, r'\bbankrupt(?:cy)?\b', r'\binsolvenc\w*\b', r'\bfraud charges\b'):
        return -3, 'If this severe solvency or enforcement claim were true, the downside could be extreme.', evidence
    # Do not equate non-cash, mark-to-market accounting profit with exceptional
    # accretion in crypto-treasury vehicles.
    if stock and score == 3:
        return 1, 'Strong reported profit may include crypto fair-value changes; cash earnings and dilution need review.', evidence
    if asset == 'XRP' and score == 2 and not official:
        return 1, 'Potentially favourable regulatory/commercial report; secondary-source headline requires verification.', evidence
    if stock and score == 2 and not official:
        return 1, 'Reported potential accretion requires a primary disclosure and materiality check.', evidence
    return score, reason, evidence


def moon_for_story(item: dict) -> list[dict]:
    """Produce one Moon Meter per distinct asset affected by item entities.

    Values are integers [-3, 3]; labels and rationale are explanatory, and
    never extrapolate a particular percentage move or prediction horizon.
    """
    if (item.get('category')=='SEC filings' or item.get('source_type')=='SEC'
            or str(item.get('source_id','')).startswith('sec_')):
        return []
    assets = []
    for entity in item.get('entities') or []:
        asset = ENTITY_ASSETS.get(entity)
        if asset and asset not in assets:
            assets.append(asset)
    output = []
    for asset in assets:
        value, reason, confidence = _assess_v2(item, asset)
        scenario = scenario_kind(item)
        if value is not None:
            value = max(-3, min(3, int(value)))
            if scenario == 'rumour':
                reason = 'IF THE RUMOUR IS TRUE: ' + reason
            elif scenario == 'assumption':
                reason = 'IF THE ASSUMPTION HOLDS: ' + reason
        output.append({
            'asset': asset,
            'value': value,
            'label': LABELS.get(value, 'Not rated'),
            'confidence': confidence,
            'scenario': scenario,
            'if_true': True,
            'reason': reason,
            'method': 'headline_if_true_v4',
        })
    return output


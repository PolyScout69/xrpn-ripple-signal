"""Scenario-based, transparent headline Moon Meter for Signal.

Direction scores estimate potential asset impact IF the reported claim, rumour
or assumption proves true. This is not a probability-of-truth estimate,
price prediction, trade recommendation or examination of full filing contents.
"""
from __future__ import annotations

import re

ENTITY_ASSETS = {
    'Ripple': 'XRP',
    'XRP Ecosystem': 'XRP',
    'Evernorth': 'XRPN',
    'Strategy': 'MSTR',
}
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
    stock = asset in ('MSTR', 'XRPN')
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
                 r'\b(?:guidance|forecast) cut\b', r'\b(?:btc|xrp) (?:sold|liquidated)\b'):
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
                          r'\b(?:buys?|purchases?|acquires?|adds?) (?:\d[\d,.]* )?(?:more )?(?:bitcoin|btc|xrp)\b',
                          r'\b(?:increases?|boosts?|expands?) (?:its )?(?:bitcoin|btc|xrp) (?:holdings|treasury|reserves)\b',
                          r'\b(?:bitcoin|btc|xrp) per share (?:rises?|increases?)\b'):
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
    stock = asset in ('MSTR', 'XRPN')

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

    # Financing terms matter more than planned gross coin accumulation.
    if stock and _contains(title,
           r'\bnew (?:xrpn |mstr )?(?:stock )?shares\b',
           r'\bfiling for [\d,.]+m? new (?:xrpn |mstr )?(?:stock )?shares\b'):
        return -1, 'New shares may dilute holders even if the proceeds acquire more cryptocurrency; check the diluted share count.', evidence
    if stock and _contains(title, r'\brais(?:e|es|ing) funds? to (?:buy|purchase) (?:more )?(?:xrp|bitcoin|btc)\b'):
        return 0, 'Planned funding and buying alone do not establish net accretion or dilution per share.', evidence

    # Treasury-company signal: coins per diluted share, not total coins acquired.
    if stock:
        coin = 'xrp' if asset == 'XRPN' else r'(?:bitcoin|btc)'
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
            'method': 'headline_if_true_v3',
        })
    return output

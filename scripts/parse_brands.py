#!/usr/bin/env python3
"""Musinsa ranking API JSON files -> domestic-brand TSV (filters known globals).
Usage: parse_brands.py page1.json page2.json ... > brands.tsv
Output cols: code \\t brandName \\t freq  (sorted by frequency desc)
"""
import json, sys, glob

GLOBAL = set('''nike adidas puma converse vans newbalance nb asics salomon oakley
underarmour ua reebok fila champion carhartt carharttwip stussy supreme
thenorthface northface patagonia columbia arcteryx hugoboss lacoste ralphlauren
ralphlaurenpolo calvinklein calvinkleinjeans tommyhilfiger tommy gshock casio
swatch levis leviskids dickies chanel dior gucci louisvuitton lv prada hermes
balenciaga givenchy offwhite fearofgod essentials coach mcm fendi valentino
versace dolcegabbana miumiu saintlaurent loewe ugg uggs drmartens timberland
clarks crocs birkenstock hoka onrunning bape snowpeak snowpeakapparel descente
massimodutti massimodutti2 umbro lululemon skechers jeep biotherm pleasing
rockfish oofos
mizuno onitsuka onitsukatiger uniqlo gu muji beams unitedarrows urbanresearch
gap zara hm cos arket superdry gstar diesel dsquared nautica lecoqsportif
fredperry bensherman ecco geox fossil katespade toryburch longchamp samsonite
rimowa eastpak herschel fidlock kappa diadora Ellesse macpac aritzia jcrew
bananarepublic oldnavy abercrombie holister''' .split())

brands = {}
files = []
for pat in sys.argv[1:]:
    files += glob.glob(pat)
for f in files:
    try:
        d = json.load(open(f))
    except Exception:
        continue
    for m in d.get('data', {}).get('modules', []):
        for it in (m.get('items') or []):
            info = it.get('info') or {}
            bn = info.get('brandName')
            onb = info.get('onClickBrandName') or {}
            url = onb.get('url', '') if isinstance(onb, dict) else ''
            bid = (url.split('/brand/')[-1].split('?')[0].rstrip('/')
                   if '/brand/' in url else None)
            if bn and bid:
                e = brands.setdefault(bid, [bn, 0]); e[1] += 1

for bid, (bn, fq) in sorted(brands.items(), key=lambda x: -x[1][1]):
    lb = bid.lower()
    if lb in GLOBAL: continue
    if 'blackpink' in lb or 'hearts2hearts' in lb or 'republicofkorea' in lb:
        continue
    print(f'{bid}\t{bn}\t{fq}')

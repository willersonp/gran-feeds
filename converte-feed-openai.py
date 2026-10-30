"""Converte o XML "GPT - OpenAI Ads" do Gestor XML da Wake (Cris & Cia) no CSV do OpenAI Ads.

Origem: https://download-xml.fbits.net/Crisecia-184.xml (estrutura "GPT | OpenAI Ads", todos os produtos ativos)
Uso: python3 converte-feed-openai.py <xml ou url> <saida.csv>
"""
import sys, csv, json, re, urllib.request, gzip, io, collections, xml.etree.ElementTree as ET

COLS = ['item_id', 'title', 'description', 'url', 'brand', 'seller_name', 'seller_url', 'image_url',
        'additional_image_urls', 'availability', 'price', 'sale_price', 'condition', 'group_id',
        'listing_has_variations', 'variant_dict', 'gtin', 'mpn', 'color', 'size', 'age_group', 'material',
        'product_category', 'is_ads_eligible']
IDADE = {'adult': 'adult', 'kids': 'kids', 'infantil': 'kids'}

def abrir(src):
    if src.startswith('http'):
        req = urllib.request.Request(src, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'GRAN-feed'})
        raw = urllib.request.urlopen(req, timeout=600).read()
        return io.BytesIO(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
    return open(src, 'rb')

def url(s):
    return (s or '').strip().replace(',', '%2C')

def dinheiro(v):
    try:
        return f'{float(v):.2f} BRL' if float(v) > 0 else ''
    except ValueError:
        return ''

def gtin_ok(g):
    # GTIN válido com dígito verificador; prefixo 2 (e 02) é código interno da loja, não vai
    if not re.fullmatch(r'\d{8}|\d{12,14}', g or '') or g.lstrip('0').startswith('2'):
        return ''
    soma = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(g[:-1])))
    return g if (10 - soma % 10) % 10 == int(g[-1]) else ''

itens = []
for ev, el in ET.iterparse(abrir(sys.argv[1])):
    if el.tag != 'item':
        continue
    d = {c.tag: (c.text or '').strip() for c in el if c.tag != 'additional_image'}
    d['_imgs'] = [(a.findtext('url') or '').strip() for a in el.findall('additional_image')]
    itens.append(d)
    el.clear()

por_grupo = collections.Counter(d['group_id'] for d in itens)
stats = collections.Counter()
with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for d in itens:
        preco, promo = dinheiro(d.get('price')), dinheiro(d.get('sale_price'))
        if not preco or not d.get('image_url') or not d.get('url') or not d.get('brand'):
            stats['descartado'] += 1
            continue
        estoque = int(d.get('stock') or 0)
        img = url(d['image_url'])
        r = {
            'item_id': d['item_id'], 'title': d['title'][:150],
            'description': (d.get('description') or d['title'])[:5000],
            'url': url(d['url']), 'brand': d['brand'],
            'seller_name': 'Cris & Cia', 'seller_url': 'https://www.crisecia.com.br',
            'image_url': img,
            'additional_image_urls': ','.join(u for u in map(url, d['_imgs']) if u and u != img),
            'availability': 'in_stock' if estoque > 0 else 'out_of_stock',
            'price': preco,
            'sale_price': promo if promo and float(promo.split()[0]) < float(preco.split()[0]) else '',
            'condition': 'new', 'gtin': gtin_ok(d.get('gtin')), 'mpn': d.get('sku', ''),
            'color': d.get('color', ''), 'size': d.get('size', ''),
            'age_group': IDADE.get((d.get('age_group') or '').lower(), ''),
            'material': d.get('material', ''), 'product_category': d.get('product_category', ''),
            'is_ads_eligible': 'true',
        }
        gid = d.get('group_id')
        if gid and gid != d['item_id'] and por_grupo[gid] > 1:
            r['group_id'] = gid
            if d.get('size'):
                r['listing_has_variations'] = 'true'
                r['variant_dict'] = json.dumps({'Tamanho': d['size']}, ensure_ascii=False)
                stats['variantes'] += 1
        w.writerow(r)
        stats['linhas'] += 1
        stats['promo'] += bool(r['sale_price'])
print(dict(stats))

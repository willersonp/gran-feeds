"""Limpa o XML "Google Shopping - GRAN" do Gestor XML da Wake (Cris & Cia) para o Google Merchant Center.

Origem: https://download-xml.fbits.net/Crisecia-185.xml (estrutura "Google Shopping | GRAN", todos os produtos ativos, sem Pix)
Corrige o que o cadastro da Wake manda fora do padrão do Google:
- g:gender só male / female / unisex (cadastro tem "unissex", "Homens", "Meninas", "famale"...)
- g:age_group só adult / kids (cadastro tem "infantil", "Adulto", "adult " com espaço...)
- g:google_product_category pelo ID oficial da taxonomia, a partir do título e da categoria
- g:sale_price só quando é menor que g:price
- etiquetas para as campanhas: custom_label_0 = categoria GRAN, custom_label_1 = faixa de preço, custom_label_2 = promo
- preço do Pix (desde 2026-11-12, decisão do Will): se passar o 3º argumento (XML 184 da Wake, que traz o
  preço do Pix em <sale_price>), o g:sale_price vira o preço do Pix quando ele é menor. custom_label_2 = promo
  continua marcando só promoção de verdade (a do 185), não o desconto do Pix.
Uso: python3 limpa-feed-google.py <xml ou url> <saida.xml> [xml-com-pix ou url]
"""
import sys, io, gzip, re, urllib.request, collections, xml.etree.ElementTree as ET

NS = 'http://base.google.com/ns/1.0'
G = '{%s}' % NS
ET.register_namespace('g', NS)

GENERO = {'male': 'male', 'masculino': 'male', 'homens': 'male', 'meninos': 'male',
          'female': 'female', 'famale': 'female', 'mulheres': 'female', 'meninas': 'female',
          'unissex': 'unisex', 'unisex': 'unisex', 'unisse': 'unisex', 'uni': 'unisex'}
INFANTIL = {'infantil', 'infanil', 'kids', 'meninos', 'meninas'}
ADULTO = {'adult', 'adul', 'adulto'}

# primeira palavra do título > ID da taxonomia do Google (taxonomy-with-ids.pt-BR.txt)
CATEGORIA = {
    'bota': 187, 'botina': 187, 'coturno': 187, 'tênis': 187, 'sapato': 187, 'sapatilha': 187, 'chinelo': 187, 'mocassim': 187,
    'chapéu': 173, 'boné': 173, 'gorro': 173,
    'cinto': 169, 'óculos': 178, 'fivela': 167, 'bandana': 167,
    'calça': 204, 'jeans': 204,
    'camiseta': 212, 'camisa': 212, 'camisete': 212, 't-shirt': 212, 'polo': 212, 'regata': 212, 'cropped': 212, 'body': 212, 'blusa': 212,
    'jaqueta': 5598, 'moletom': 5598, 'colete': 5598, 'casaco': 5598,
    'shorts': 207, 'bermuda': 207, 'saia': 1581, 'vestido': 2271,
}
SELARIA = 5593  # Artigos esportivos > Atividades ao ar livre > Esportes equestres > Equipamentos para cavalos

# custom_label_0: categoria GRAN (usada nos filtros das PMax), pela primeira palavra do título
GRUPO = {187: 'botas', 173: 'chapeus', 169: 'cintos', 167: 'acessorios', 178: 'acessorios',
         204: 'calcas', 212: 'camisas', 5598: 'jaquetas', 207: 'shorts', 1581: 'saias', 2271: 'vestidos',
         SELARIA: 'selaria'}
FAIXAS = [(200, 'ate-199'), (400, '200-399'), (700, '400-699'), (1000, '700-999')]

def faixa(preco):
    for teto, nome in FAIXAS:
        if preco < teto:
            return nome
    return '1000-mais'

def abrir(src):
    if src.startswith('http'):
        req = urllib.request.Request(src, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'GRAN-feed'})
        raw = urllib.request.urlopen(req, timeout=600).read()
        return io.BytesIO(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
    return open(src, 'rb')

def valor(item, tag):
    el = item.find(G + tag)
    return (el.text or '').strip() if el is not None else ''

def definir(item, tag, v):
    el = item.find(G + tag)
    if not v:
        if el is not None:
            item.remove(el)
        return
    if el is None:
        el = ET.SubElement(item, G + tag)
    el.text = v

def numero(preco):
    try:
        return float(preco.split()[0])
    except (ValueError, IndexError):
        return 0.0

def precos_pix(src):
    """Lê o XML 184 (sem namespace: item_id, price, sale_price) e devolve {id: preço do Pix}."""
    pix = {}
    for _, el in ET.iterparse(abrir(src)):
        if el.tag == 'item':
            pid = (el.findtext('item_id') or '').strip()
            venda = numero((el.findtext('sale_price') or '').strip())
            if pid and venda:
                pix[pid] = venda
            el.clear()
    return pix

PIX = precos_pix(sys.argv[3]) if len(sys.argv) > 3 else {}
if len(sys.argv) > 3 and len(PIX) < 5000:
    sys.exit('Feed do Pix com menos de 5000 preços, não publica')

arvore = ET.parse(abrir(sys.argv[1]))
canal = arvore.getroot().find('channel')
stats = collections.Counter()
for item in list(canal.findall('item')):
    if not valor(item, 'price') or not valor(item, 'image_link') or not item.findtext('link'):
        canal.remove(item)
        stats['descartado'] += 1
        continue
    titulo = (item.findtext('title') or '').strip()
    raiz = valor(item, 'product_type').split(' > ')[0].strip().lower()
    genero_bruto = valor(item, 'gender').lower()
    idade_bruta = valor(item, 'age_group').lower()

    genero = GENERO.get(genero_bruto) or GENERO.get(raiz) or 'unisex'
    infantil = genero_bruto in INFANTIL or idade_bruta in INFANTIL or raiz in ('infantil', 'meninos')
    idade = 'kids' if infantil else 'adult'
    stats['genero_corrigido'] += genero != genero_bruto
    stats['idade_corrigida'] += idade != idade_bruta
    definir(item, 'gender', genero)
    definir(item, 'age_group', idade)

    cat = CATEGORIA.get(titulo.split(' ')[0].lower()) if titulo else None
    if cat is None and raiz == 'selaria':
        cat = SELARIA
    definir(item, 'google_product_category', str(cat) if cat else '')
    stats['com_categoria'] += bool(cat)

    preco_final = numero(valor(item, 'price'))
    promo_valor = numero(valor(item, 'sale_price'))
    if not promo_valor or promo_valor >= preco_final:
        definir(item, 'sale_price', '')
        promo = ''
    else:
        preco_final = numero(valor(item, 'sale_price'))
        promo = 'promo'
        stats['promo'] += 1
    pix = PIX.get(valor(item, 'id'))
    if pix and pix < preco_final and pix < numero(valor(item, 'price')):
        definir(item, 'sale_price', '%.2f BRL' % pix)  # custom_label_1 segue pelo preço sem Pix (grupos das PMax não mudam)
        stats['com_pix'] += 1
    elif PIX:
        stats['sem_pix'] += 1
    grupo = 'bones' if titulo.split(' ')[0].lower() in ('boné', 'gorro') else GRUPO.get(cat, 'outros')
    definir(item, 'custom_label_0', grupo)
    definir(item, 'custom_label_1', faixa(preco_final))
    definir(item, 'custom_label_2', promo)
    stats['grupo_' + grupo] += 1
    for tag in ('color', 'size', 'material', 'brand', 'product_type'):
        definir(item, tag, valor(item, tag))
    stats['itens'] += 1

arvore.write(sys.argv[2], encoding='utf-8', xml_declaration=True)
print(dict(stats))

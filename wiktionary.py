import re
import requests
import json

def dewikify(w):
    return w.lstrip('[').rstrip(']')

def getPrefix(w):
    r = requests.get('https://nl.wiktionary.org/w/api.php?action=query&format=json&list=allpages&aplimit=max&apprefix={}'.format(w))
    prefixes = json.loads(r.text)['query']['allpages']
    if len(prefixes) == 0:
        return []
    # zet alle pagina's behalve verkleinwoorden en simpele meervouden in een array. We zoeken samenstellingen,
    # dus meervouden en verkleinwoorden zijn niet nuttig. 
    pages = [(p['title'], p['pageid']) for p in prefixes if not p['title'].endswith('je') and p['title'] not in [w + 'en', w + 's', w + "'s"]]
    return pages

def wordData(w):
    prefixes = getPrefix(w)
    titles = '|'.join([p[0] for p in prefixes])
    if titles == '':
        # geen pagina met deze titel gevonden
        return False
    url = 'https://nl.wiktionary.org/w/api.php?action=query&prop=revisions&rvslots=main&rvprop=content&format=json&titles={}'.format(titles)
    #print(url)
    r = requests.get(url)
    pgs = json.loads(r.text)['query']['pages']
    txt = pgs[str(prefixes[0][1])]['revisions'][0]['slots']['main']['*']
    return txt.replace('{{pn}}', w);

print(wordData('vereniging'))

def wordToObj(text, pn, base):
    try:
        frm = text.index('{{=nld=}}')
    except:
        return {'wikt': False}
    frm = text.index('\n', frm)
    to = re.compile(r'{{=.+=}}|$').search(text, frm+1).start()
    if to > len(text):
        to = len(text)
    txt = text[frm:to]
    dic = {'wikt': True}
    m, f, n = '{{m}}' in txt, '{{f}}' in txt, '{{n}}' in txt
    # geslacht van het woord:
    if (m and f):
        dic['gender'] = 'mf'
    elif m:
        dic['gender'] = 'm'
    elif f:
        dic['gender'] = 'f'
    else:
        dic['gender'] = 'n'

    # is een woord een afkorting?
    if '{{initiaalwoord' in txt:
        # alleen initiaalworden markeren; bij '{{afkorting' wordt o.a. ook 'vrij' als afkorting gezien.
        dic['afkorting'] = True
    else:
        dic['afkorting'] = False

    # de waarde van een getal
    dec_re = r"\[\[([0-9\.]+)\]\].*\[\[decimaal\]\]" # punt is duizendtal-scheiding
    getal_re = r"het getal \[{0,2}([0-9\.]+)\]{0,2}"
    if '{{soroban|' in txt:
        dic['num'] = re.findall(r"{{soroban\|(\d+)}}", txt)[0]
    elif re.search(dec_re, txt.lower()):
        dic['num'] = re.findall(dec_re, txt.lower())[0]
    elif re.search(getal_re, txt.lower()):
        dic['num'] = re.findall(getal_re, txt.lower())[0]
    elif '{{-num-' in txt or '{{nld-telw' in txt:
        print(re.match(getal_re, txt.lower()), re.match(dec_re, txt.lower()))
        dic['num'] = True
    
    if 'num' in dic and dic['num'] != True:
        dic['num'] = int(dic['num'].replace('.', ''))

    try:
        # andere vormen van het begrip
        forms = getParams(txt, r"\w-form")
        dic['rel'] = {}
        for i in forms:
            j = i[1].split('|')
            if i[0] in dic['rel']:
                dic['rel'][i[0]].append(j[0])
            else:
                dic['rel'][i[0]] = [j[0]]
    except:
        pass

    try:
        # verwante begrippen
        verw = getInfo(txt, 'rel')
        dic['verw'] = verw
    except:
        pass

    try:
        # meervoud en verkleiningsvormen
        meer = getParam(txt, '-nlnoun-')
        dic['meer'] = {
            'enkel': meer[0],
            'mv': re.split(r'\]\].*?\[\[', dewikify(meer[1])), # split meerdere mv-vormen
            'klein': dewikify(meer[2]),
            'mv-klein': dewikify(meer[3]),
        }
    except:
        try:
            meer = getParam(txt, 'noun-pl')
            dic['meer'] = {
                'enkel': meer[0],
                'mv': pn,
                'klein': None,
                'mv-klein': None,
            }
        except:
            pass

    try:
        # vervoeging van bvnw
        adj = getParam(txt, 'adjcomp')
        dic['bvnw'] = {
            '-': adj[1],
            'e': adj[2],
            'er': adj[3],
            'ere': adj[4],
            'st': adj[5],
            'ste': adj[6]
        }
    except:
        pass

    try:
        # afgeleide begrippen
        drv = getInfo(txt, 'drv')
        dic['drv'] = drv
    except:
        pass

    dic['wt'] = {}
    dic['wt']['N'] = '{{-nlnoun-' in txt
    dic['wt']['ADJ'] = '{{-adjc-' in txt
    dic['wt']['WW'] = '{{-verb-' in txt

    return dic

def getInfo(text, sect, sep=r"\[\]"):
    frm = text.index('{{-'+sect+'-')
    frm = text.index('\n', frm)
    to = text.index('{{-', frm+1)
    txt = text[frm:to]
    links = re.findall(sep[0:2] + r"{2}(.*?)" + sep[2:4] + r"{2}", txt)
    return [l for l in links if not l.lower().startswith('categorie:')]

def getParam(text, sect):
    return [dewikify(r) for r in re.findall(r'\{\{'+sect+r'\|(.*)\}\}', text)[0].split('|')]

def getParams(text, sect):
    return re.findall(r'\{\{('+sect+r')\|(.*)\}\}', text)

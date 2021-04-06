import re
import requests
import random
from bs4 import BeautifulSoup
from html2text import html2text
import interpreteer as inter
import wiktionary as wikt
# voor klinkerbotsingen:
from unidecode import unidecode
import sys
import os.path

lookup = {}

# TODO: spacy confidence ophalen (onmogelijk?)

######### Checks voor woordeigenschappen #########

def isCijfer(w):
    if re.match(r'^[0-9.,]+$', w.woord):
        return True
    else:
        return False

def grootGetal(w):
    if not 'num' in w.wobj:
        return False
    elif w.wobj['num'] == True:
        # alle grotere woorden dan duizend worden los geschreven
        return 'iljoen' in w.woord or 'iljard' in w.woord
    elif w.wobj['num'] > 1000:
        return True
    return False

def isPrefix(w):
    # kut, rot
    return w.woord in 'ex,oud,vice,pseudo,mega,giga,super,anti'.split(',')

def isSuffix(w):
    return w.woord in ['vrij', 'vrije', 'loos', 'loze']

def isAfkorting(w):
    if 'afkorting' in w.wobj and w.wobj['afkorting']:
        # wiktionary zegt dat het een afkorting is
        return True
    if w.orig.upper() == w.orig:
        # woorden met alleen hoofdletters zijn afkortingen
        return True
    if not set('aeiouy').intersection(w.woord):
        # neem aan dat woorden zonder klinkers afkortingen zijn
        return True
    # alle andere woorden kunnen niet als afkorting verondersteld worden
    return False

def isInconsistent(w):
    pat = r"^(hel(le)?|zon(ne)?|maan|mane|(onze-?)?lieve-?vrouwe|lieve-?heers?)$"
    return re.match(pat, w.woord)

def zoekKoppelS(w):
    # Bepaal of er een koppel-S in een samenvoeging moet worden gezet
    # Geen duidelijke rule-based voorwaarden
    return False

######### Samenvoegingsfuncties #########

def plakvast(a, b):
    # behoud eigenschappen van het tweede woord; samenstellingen volgen grammatica
    # van het tweede woord (geslacht, samenvoeging, etc).
    b.orig = a.orig.rstrip() + b.orig.lstrip()
    b.comp = a.orig.rstrip()
    if 'num' in a.wobj and 'num' in b.wobj:
        # honderd (100) drie (3) -> 103
        b.wobj['num'] += a.wobj['num']
    elif 'num' in a.wobj:
        # drie (3) en twintig (20) -> drieën (3) twintig (20)
        b.wobj['num'] = a.wobj['num']
    a.woord = ''
    a.orig = ''
    a.func = None

def klinkerbotsing(a, b):
    # normaliseer zonder accenten
    l, r = unidecode(a.orig[-1]), unidecode(b.orig[0])
    # https://woordenlijst.org/leidraad/7/1
    if l == 'a' and r in 'aeiu':
        koppelstreep(a, b)
    elif l == 'e' and r in 'eiu':
        koppelstreep(a, b)
    elif l == 'i' and r in 'eji':
        # i+j en i+i zijn bij samenvoegingen altijd klinkerbotsingen
        koppelstreep(a, b)
    elif l == 'o' and r in 'eiou':
        koppelstreep(a, b)
    elif l == 'u' and r in 'iu':
        koppelstreep(a, b)
    else:
        plakvast(a, b)

def compound(a, b):
    if a.wobj['compound'] == None:
        klinkerbotsing(a, b)
    a.orig = a.comp + a.wobj['compound']
    klinkerbotsing(a, b)

def koppelstreep(a, b):
    a.orig = a.orig.rstrip() + '-'
    plakvast(a, b)

def koppeltrema(a, b):
    # alleen ë is nodig, maar laten we dit netjes doen:
    charmap = {'a':'ä', 'e':'ë', 'i':'ï', 'o':'ö', 'u':'ü'}
    b.orig = b.orig.lstrip()
    b.orig = charmap[b.orig[0]] + b.orig[1:]
    plakvast(a, b)

def koppelS(a, b):
    if zoekKoppelS(a):
        a.orig = a.orig.rstrip() + 's'
        return
    # geen tussen-s? dan klinkerbotsingen afhandelen
    klinkerbotsing(a, b)

def koppelE(a, b):
    a.orig = a.orig.rstrip() + 'e'
    # asperge-ei heeft klinkerbotsing, moeten dus wel worden afgehandeld.
    klinkerbotsing(a, b)

def koppelN(a, b):
    a.orig = a.orig.rstrip()
    if a.woord[-1] == 'n':
        plakvast(a, b)
    elif a.woord[-1] == 'e':
        # Niet triviaal. Gemeenteraad is zonder -n-. Dit is dus niet altijd correct. Doe een 'best guess'
        a.orig += 'n'
        plakvast(a, b)
    else:
        if 'meer' in a.wobj and a.wobj['meer']['enkel'] + 'en' != a.wobj['meer']['mv']:
            # moeilijke meervoudsvorm; 'koeien', 'eieren', etc.
            # neem meervoudsvorm over van wiktionary.
            # kan mogelijk fouten opleveren als w.norm_ iets belangrijk heeft weggenormaliseerd.
            # neem de eerste (gangbaardere) meervoudsvorm.
            if len(a.comp) > 0:
                # woord is al eerder samengesteld. Niet de eerste letter door de war halen.
                a.orig = a.comp + a.wobj['meer']['mv'][0]
            else:
                a.orig = a.orig[0] + a.wobj['meer']['mv'][0][1:]
        else:
            a.orig += 'en'
        plakvast(a, b)

def koppelInconsistent(a, b):
    # neem eerste teken van originele woord over om hoofdletters intact te houden.
    if a.woord in ['hel', 'helle']:
        a.woord = a.orig = a.orig[0] + 'elle'
        klinkerbotsing(a, b)
    elif a.woord in ['zon', 'zonne']:
        a.woord = a.orig = a.orig[0] + 'onne'
        klinkerbotsing(a, b)
    elif a.woord in ['maan', 'mane']:
        a.woord = a.orig = a.orig[0] + 'ane'
        klinkerbotsing(a, b)
    elif re.match(r"^(onze-?)?lieve-?vrouwe?$", a.woord):
        if a.woord.startswith('onze'):
            a.woord = a.orig = a.orig[0] + 'nzelievevrouwe'
        else:
            a.woord = a.orig = a.orig[0] + 'ievevrouwe'
        klinkerbotsing(a, b)
    elif re.match(r"^lieve-?heers?$", a.woord):
        a.woord = a.orig = a.orig[0] + 'ieveheers';
        plakvast(a, b)

def koppel(a, b, c = None):
    """ Zorg dat woorden correct worden samengevoegd
        Deze functie checkt niet óf, maar hóé iets moet worden samengevoegd."""
    #print('koppel:', a.orig, b.orig)
    if a.woord == '[' and b.woord == '[':
        return
    if c != None and b.woord == 'en':
        # vijfentwintig
        if a.woord[-1] == 'e':
            koppeltrema(a, b)
        else:
            plakvast(a, b)
        plakvast(b, c)
    elif c != None:
        # drie delen koppelen betekent 'laagsteprijsgarantie'-achtige constructie.
        # Geen tussenletters, wel klinkerbotsingen
        klinkerbotsing(a, b)
        klinkerbotsing(b, c)
    elif a.woord in ['ex', 'oud', 'anti']:
        # worden altijd met streepje geschreven
        koppelstreep(a, b)
    elif isAfkorting(a) or isAfkorting(b):
        koppelstreep(a, b)
    elif isInconsistent(a):
        koppelInconsistent(a, b)
    elif 'dim__Number=Plur' in a.tag:
        # verkleinwoord in meervoudsvorm eindigt al op -s, dus kan vastgeplakt
        plakvast(a, b)
    elif 'dim' in a.tag:
        # verkleinwoord links krijgt altijd een koppel-s
        # belangrijker dan gebrek aan meervoud; 'watertje' moet met -s samengevoegd.
        koppelS(a, b)
    elif not a.wobj['wikt']:
        # woord staat niet in wiktionary; verder dan dit kunnen we niets doen.
        # TODO: linkerdeel opsplitsen in subwoorden om zo die woorden in wiktionary op te zoeken
        koppelS(a, b)
    elif b.func == 'WW':
        # avondvullend, bandplakkende, rondlopend; niet avondenvullend, bandenplakkende
        plakvast(a, b)
    elif isSuffix(b):
        # schoolvrij, gedachteloos; niet scholenvrij, gedachtenloos.
        plakvast(a, b)
    elif a.wobj['compound'] != None:
        compound(a, b)

    # vanaf hier alle speciale gevallen afgehandeld;
    # volg nu:
    # deels https://woordenlijst.org/leidraad/8/1 (maar geen -en betekent niet -e-; appel-, radio-, bureau-)
    # deels https://www.vlaanderen.be/taaladvies/tussenletters-e-en-en-in-samenstellingen (niet heel algoritmisch omschreven)
    # niet https://onzetaal.nl/taaladvies/tussen-n/ (geen concrete regels)
    elif a.orig[-2:].lower() == 'en':
        # werk is al gedaan voor ons; als iets eindigt op -en kan het gewoon vast.
        plakvast(a, b)
    else:
        if 'rel' in a.wobj and 'm-form' in a.wobj['rel'] or 'f-form' in a.wobj['rel']:
            # een vrouwelijke nevenvorm bestaat; handel dit eerst af
            if 'm-form' in a.wobj['rel']:
                man, vr = [a.woord], a.wobj['rel']['m-form']
            else:
                man, vr = a.wobj['rel']['f-form'], [a.woord]
            neven_e = False
            for m in man:
                if neven_e:
                    break
                for v in vr:
                    if m + 'e' == v:
                        neven_e = True
                        break
            if neven_e:
                koppelN(a, b)
                return
            # else: nevenvorm is niet relevant voor tussenletters; handel de rest af.
        if 'meer' in a.wobj:
            if a.wobj['meer']['mv'] == ['-'] or a.wobj['meer']['mv'] == ['']:
                # expliciet gebrek aan meervoud; geen tussenletters, ook geen tussen-s.
                # TODO sommige woorden hierin krijgen een tussen-e (snottebel, gerstenat, rijstebrij)
                klinkerbotsing(a, b)
            else:
                en, es = False, False
                for mv in a.wobj['meer']['mv']:
                    if mv[-2:] == 'es':
                        es = True
                        break
                    if mv[-1:] == 'n':
                        en = True
                        break
                if not en and not es:
                    # geen vorm met -en of -es.
                    # negeer woordenlijst.org; dit moet gewoon vastgeplakt; vb:
                    # appelmoes, radiostilte, bingokaart, bureaustoel, metselaarsgilde
                    # woorden als 'gerstenat' zijn uitzonderingen, niet regels.
                    koppelS(a, b)
                elif en:
                    # wel vorm met -en, maar niet met -es:
                    # controleer vrouwelijke nevenvorm
                    koppelN(a, b)
                else:
                    koppelS(a, b)
        else:
            # geen regels gevonden die van toepassing zijn; kan dus alleen tussen-s hebben
            koppelS(a, b)

######### Hoofdfunctie #########

def isCNOM(n):
    if not n:
        return False
    # is core nominal?
    # obl functioneert vaak hetzelfde als core nominals, dus worden hier ook meegenomen
    return n.split(':')[0] in ['nsubj', 'obj', 'iobj', 'obl']

#prev en cur zijn woord-objecten, nxt is de array met alle daaropvolgende woorden
def checkCompound(prev, cur, nxt):
    if cur.woord == None:
        # we zijn bij het laatste woord aangekomen.
        return
    # X.dep uitgelegd op https://universaldependencies.org/u/dep/
    if prev.func == None:
        # als in de vorige iteratie nxt[0] is afgehandeld, doe dan niets
        # dit gebeurt bijvoorbeeld bij 'vijf en twintig' -> 'vijfentwintig'.
        return;

    if isPrefix(prev):
        if cur.func == 'N' or cur.func == 'ADJ' or prev.functype == cur.functype == 'deeleigen':
            # pseudo-intelligent, ex-coach
            return koppel(prev, cur)
    elif isSuffix(cur):
        if prev.func == 'N':
            return koppel(prev, cur)

    if prev.func == 'TW' and prev.functype == 'hoofd' and prev.dep != 'punct':
        # niet "de eerste drie" en "In het jaar '95" matchen.
        # vorige woord is telwoord
        if cur.func == 'TW':
            # honderddrie, duizendtwee, honderdduizend, 300 000
            if not grootGetal(prev) and not grootGetal(cur) and not prev.woord.endswith('duizend'):
                # behoud nodige spaties bij grote getallen:
                # vijf_miljoen_en_drie; vijf_miljoen_vierenveertig, drieduizend_zes;
                return koppel(prev, cur)
        elif cur.woord == 'en' and nxt[0].func == 'TW' and not grootGetal(prev):
            # drieëntwintig, eenenveertig
            return koppel(prev, cur, nxt[0])

    if prev.func == 'N':
        if cur.dep == 'compound:prt':
            if prev.dep == 'appos':
                # Spacy vindt dat dit een compound-part is
                return koppelstreep(prev, cur)
        if isSuffix(cur):
            return koppelstreep(prev, cur)
        if (cur.dep == 'ROOT' and cur.func == 'N') or (isCNOM(cur.dep) and cur.func in ['N', 'ADJ']):
            if prev.dep in ['amod', 'nmod']:
                # bijv maximumgewicht, oud-coach, reclamebord. Als prev ADJ is niet koppelen (bijvoorbeeld 'een rood huis')
                # soms wordt een znw als ww herkend, zoals 'dit is een lading honden poep'. De syntactische analyse is dan nauwkeuriger.
                koppel(prev, cur)

        if cur.func == 'N':
            if prev.dep == cur.dep and isCNOM(cur.dep):
                # twee ZNWs achter elkaar met dezelfde functie als ow/lv/mwvw in de zin
                return koppel(prev, cur)
        
        if prev.dep == 'obl' and (cur.dep == 'amod' or isCNOM(cur.dep)):
            # avondvullend programma
            koppel(prev, cur)

    if prev.func == 'ADJ':
        if ('met-e' in prev.tag or 'sup' in prev.tag) and not isPrefix(prev):
            # bvnw vervoegd met -e(r) of -st(e) worden niet samengesteld; voorbeelden:
            # De groter wordende man, het grootste gewicht, de vreemde markt, de roodst gloeiende lamp.
            # bvnw in standaardvorm moeten wel samengevoegd; voorbeelden:
            # De grootwordende man, het grootgewicht, de vreemdmarkt, de roodgloeiende.
            return
        if cur.func == 'N':
            if prev.dep in ['amod', 'nmod'] and prev.functype == 'prenom':
                if (isCNOM(cur.dep) or cur.dep in ['amod', 'nmod']) and nxt[0].func == 'N' and cur.functype == nxt[0].functype == 'soort' and (nxt[0].dep in ['ROOT', 'xcomp', 'compound:prt'] or isCNOM(nxt[0].dep)):
                    # woorden zoals laagsteprijsgarantie, langeafstandsloper, etc.
                    return koppel(prev, cur, nxt[0])
            if prev.dep == cur.dep and isCNOM(cur.dep):
                return koppel(prev, cur)
            if prev.functype == 'prenom':
                if prev.dep in ['nmod', 'amod']:
                    if isCNOM(cur.dep) and isPrefix(prev):
                        # 'De _oud voetballer_ is blij.', maar moet prefix zijn, anders 'We hebben een avond vullendprogramma gemaakt'.
                        return koppel(prev, cur)
                    if cur.dep in ['nmod', 'amod']:
                        # EHBO diploma in voorbeeldzinnen
                        return koppel(prev, cur)

    if prev.func == 'BW':
        if cur.func == 'WW':
            if prev.dep == 'compound:prt':
                # weg gesleurd, door gehaald, bij gevoegd, etc.
                return plakvast(prev, cur)

    if prev.func == cur.func and prev.func in ['N', 'ADJ']:
        if prev.dep in ['nmod', 'amod'] and cur.dep in ['nmod', 'amod']:
            # twee ZNWs of BVNWs achter elkaar met een 'modifyer'-functie op het volgende woord.
            return koppel(prev, cur)
        # prev is in de standaardvorm zonder -e of -st, etc; wegens eerdere selectie daarop
        if prev.func == 'ADJ':
            if isCNOM(prev.dep) and cur.dep == 'acl':
                # roodgloeiende
                return koppel(prev, cur)
            elif prev.dep == 'advmod' and cur.dep == 'acl':
                # de rood gloeiende draad
                return koppel(prev, cur)
            else:
                # anders niet koppelen.
                return
        if prev.dep == cur.dep:
            if isCNOM(cur.dep):
                # zelfde functie in de zin en vervult de rol van ow/lv/mwvw
                return koppel(prev, cur)
            elif cur.dep == 'nmod':
                # 'Ik heb een student kamer gekocht.
                return koppel(prev, cur)
    if isCijfer(cur):
        if prev.woord == 'jaren' and nxt[0].func == 'N' and (nxt[0].dep == 'appos' or isCNOM(nxt[0].dep)):
            # jaren-80-muziek (witte boekje); groene boekje 'jaren 80-muziek' niet ondersteund.
            koppelstreep(prev, cur)
            koppelstreep(cur, nxt[0])
            return
    else:
        # woorden niet samenvoegen
        return

def fixPOS(w):
    if not 'wt' in w.wobj:
        return
    oldfunc = w.func
    if not w.func in w.wobj['wt'] or w.wobj['wt'][w.func]:
        # wiktionary vindt dat de classificatie mogelijk is, of het woord is niet in het lijstje relevante woordtypes
        pass
    elif w.wobj['wt']['N']:
        # heuristiek: als een WW, BW of ADJ verkeerd geclassificeerd is, en het mag een N zijn,
        # dan er vanuit gaan dat het een N mag zijn, en niet kijken of het iets anders mag zijn.
        w.func = 'N'
    elif w.wobj['wt']['ADJ']:
        # heuristiek: idem, maar dan voor een ADJ
        w.func = 'ADJ'
    elif w.wobj['wt']['WW']:
        # zowel N als ADJ kunnen niet volgens wiktionary; als WW wel kan, maken we dat ervan
        # dit is de minst waarschijnlijke, omdat spacy woorden vaker niet-WWs als WW klassificeert, dan WWs als iets anders.
        w.func = 'WW'
    elif w.wobj['wt']['BW']:
        # bijwoorden zijn relatief zeldzaam; dit is dus de minst waarschijnlijke override
        w.func = 'BW'
    # else doe niks; wiktionary klassificeert het als niet N/ADJ/WW/BW

    if w.func != oldfunc:
        print("!!!!!!!!!! Woordfunctie overschreven voor '{}' van {} naar {}.".format(w.orig, oldfunc, w.func))

def fixText(txt, dic = 's', debug = 0):
    text = ''
    doc = inter.nlp[dic](txt)
    zinnen = doc.sents
    for zin in zinnen:
        words = inter.leeszin(zin, lookup, 's', debug)
        for w in words:
            # check of wiktionary vindt dat een woord mogelijk is in de classificatie.
            fixPOS(w)
        for i, w in enumerate(words):
            if i == 0:
                continue
            a = words[i-1]
            b = w
            c = words[i+1:]
            checkCompound(a, b, c)
        zin = ''
        for w in words:
            if w.func == None:
                continue
            zin += w.orig
        yield zin

def fixFile(filename, debug):
    with open(filename, 'r') as r:
        outf = (filename+' ')[:filename.rfind('.')] + '.out'
        with open(outf, 'w') as w:
            print("\nwriting to {}".format(outf))
            line = r.readline()
            while line != '':
                for z in fixText(line, 's', debug):
                    print(z, end='', sep='')
                    w.write(z)
                    w.flush()
                line = r.readline()

def main(filename, debug):
    zin = "Dit is een voorbeeldzin waarin alles goed gespeld is, waarmee het spacy-algoritme wordt gedemonstreerd."
    zin = "Wat een mooie dag is het vandaag. Hoe gaat het?\nMet mij goed namelijk."
    if filename:
        try:
            fixFile(filename, debug)
        except KeyboardInterrupt:
            print('')
        zin = ''

    while zin != '':
        #doc = next(inter.nlp['s'](zin).sents)
        #words = inter.leeszin(doc)
        zin = input() # input("-> ")
        #print(zin, "\n==>\n", end='', sep='', flush=True)
        for z in fixText(zin, 's', debug):
            if debug:
                print(z, end='', sep='')
                if not filename:
                    print('')
            pass
        #print('')

def dewikify(text):
    text = re.sub(r"{\|(?!\|})[\s\S]+\n\|}", "", text) # verwijder alle tabellen.
    text = re.sub(r"<!--[\s\S]*-->", "", text) # verwijder alle comments
    text = re.sub(r"(={1,6})\s+(.*)\s+\1", r"\2", text) # verwijder titelopmaak
    text = re.sub(r"'{2,3}", "", text) # verwijder bold/italic text
    text = re.sub(r"\[\[(?![Ff]ile:|[Ii]mage|[Bb]estand|[Cc]ategor(ie|y))([^\|\]]*\|)?([^\]]+)\]\]", r"\3", text) # verwijder wikilinks, inclusief in afbeelding-captions
    text = re.sub(r"\[\[([Ff]ile:|[Ii]mage|[Bb]estand|[Cc]ategor(ie|y))[^\]]+\]\]", "", text) # verwijder afbeeldingen/categorieën, nadat alle interne [[]] uit de [[File:...|caption [[link]] delen]] zijn verwijderd
    text = re.sub(r"\[([a-z]+:(\/\/)?)[^ ]+ ([^\]]+)\]", r"\3", text) # verwijder externe links
    text = re.sub(r"<(math|code|nowiki|source|ref|gallery)>(?!<\/\1>)(.+)<\/\1>", "", text) # verwijder niet-tekstuele tags incl. inhoud
    text = re.sub(r"<[^>]+\/>", "", text) # verwijder alle self-closing tags
    text = re.sub(r"\n-{4,}\n", "\n", text) # verwijder <hr/>
    rgx = r"\{\{\{((?!(\{|\}){2})(.|\n|\r))+\}\}\}|\{\{((?!(\{|\}){2})(.|\n|\r))+\}\}"
    while re.search(rgx, text): # blijf de 'innermost' template verwijderen zolang er templates zijn
        text = re.sub(rgx, "", text)
    text = re.sub(r"\n{3,}", "\n\n", text) # maximaal 2 enters achter elkaar
    return text.strip()

def getWiki(filename, debug):
    if not filename or not filename.startswith('wikipedia/') or filename.endswith('.wiki'):
        return False
    article = filename[len('wikipedia/'):]
    pagina = article
    repeat = 1
    if article.lower()[0:len('special:random')] == 'special:random':
        repeat = debug or 1
        debug = 0
    for i in range(repeat):
        r = requests.get('https://nl.wikipedia.org/w/index.php?title={}&action=raw'.format(pagina))
        article = re.findall(r"title=([^&]+)", r.url)[0] # handel redirects af, zoals o.a. Special:Random
        article = re.sub(r"\/|\\", "~", article) # zorg dat er geen slashes in bestanden staan
        ofile = 'wikipedia/'+article
        if os.path.exists(ofile+'.txt'):
            continue
        with open(ofile+'.wiki', 'w') as w:
            w.write(r.text)
        with open(ofile+'.txt', 'w') as w:
            w.write(dewikify(r.text))
            filename = 'wikipedia/'+article+'.txt'
        main(filename, debug)
    return True

def getFok(filename, debug):
    if not filename or not filename.startswith('fok/') or filename.endswith('.txt'):
        return False
    postid = filename[len('fok/'):]
    repeat = 1
    if postid == '*':
        repeat = debug or 1
        debug = 0
    for i in range(repeat):
        if postid == '*':
            postid = random.randint(1, 2500000)
        url = "http://forum.fok.nl/topic/{}"
        r = requests.get(url.format(postid))
        soup = BeautifulSoup(r.text, 'html.parser')
        todelete = ".quoteTitel, .contents img, .quote b:first-child"
        delete = soup.select(todelete)
        while len(delete):
            for d in delete:
                d.decompose()
            delete = soup.select(todelete)
        thread = soup.find_all('div', {'class':'postmain_right'})
        posts = []
        for post in thread:
            text = html2text(str(post))
            posts.append(text)
        filename = 'fok/'+str(postid)+'.txt'
        with open(filename, 'w') as w:
            w.write("\n\n".join(posts))
        main(filename, debug)
    return True

filename, debug = None, 0
if len(sys.argv) > 2:
    filename = sys.argv[1]
    debug = int(sys.argv[2])
elif len(sys.argv) > 1:
    if sys.argv[1] == '1' or sys.argv[1] == '0':
        debug = int(sys.argv[1])
    else:
        filename = sys.argv[1]

if not getWiki(filename, debug) and not getFok(filename, debug):
    main(filename, debug)

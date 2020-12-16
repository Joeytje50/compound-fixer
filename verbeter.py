import re
import interpreteer as inter
import wiktionary as wikt
# voor klinkerbotsingen:
from unidecode import unidecode
import sys

# TODO: spacy confidence ophalen (onmogelijk?)
# TODO: wiktionary als 2e bron oppakken
# TODO: 

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
    # TODO
    return False

######### Samenvoegingsfuncties #########

def plakvast(a, b):
    # behoud eigenschappen van het tweede woord; samenstellingen volgen grammatica
    # van het tweede woord (geslacht, samenvoeging, etc).
    # print('vastgeplakt:', a.orig, b.orig)
    b.orig = a.orig.rstrip() + b.orig.lstrip()
    b.comp = a.comp + a.orig.rstrip()
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
        # TODO: Niet triviaal. Gemeenteraad is zonder -n-
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
        # TODO: linkerdeel opsplitsen in subwoorden om zo wel iets te kunnen doen.
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
    elif prev.dep in ['amod', 'nmod'] and prev.func == 'ADJ' and prev.functype == 'prenom' and \
        (isCNOM(cur.dep) or cur.dep in ['amod', 'nmod']) and cur.func == nxt[0].func == 'N' and cur.functype == nxt[0].functype == 'soort' and \
        (nxt[0].dep in ['ROOT', 'xcomp', 'compound:prt'] or isCNOM(nxt[0].dep)):
            # woorden zoals laagsteprijsgarantie, langeafstandsloper, etc.
            koppel(prev, cur, nxt[0])
    elif prev.func == 'N' and prev.dep == 'appos' and cur.dep == 'compound:prt':
        # Spacy vindt dat dit een compound-part is
        koppelstreep(prev, cur)
    elif prev.func == 'ADJ' and ('met-e' in prev.tag or 'sup' in prev.tag) and not isPrefix(prev):
        # bvnw vervoegd met -e(r) of -st(e) worden niet samengesteld; voorbeelden:
        # De groter wordende man, het grootste gewicht, de vreemde markt, de roodst gloeiende lamp.
        # bvnw in standaardvorm moeten wel samengevoegd; voorbeelden:
        # De grootwordende man, het grootgewicht, de vreemdmarkt, de roodgloeiende.
        return
    elif prev.func == 'ADJ' and cur.func == 'N' and prev.dep == cur.dep and isCNOM(cur.dep):
        # TODO: de BHV-zin in de testzinnen wordt nu als 'met-e' gemarkeerd en valt hier dus buiten.
        koppel(prev, cur)
    elif prev.func == cur.func == 'N' and prev.dep == cur.dep and isCNOM(prev.dep):
        # twee ZNWs achter elkaar met dezelfde functie als ow/lv/mwvw in de zin
        koppel(prev, cur)
    elif prev.func == cur.func and cur.func in ['N', 'ADJ'] and prev.dep in ['nmod', 'amod'] and cur.dep in ['nmod', 'amod']:
        # twee ZNWs of BVNWs achter elkaar met een 'modifyer'-functie op het volgende woord.
        koppel(prev, cur)
    elif prev.dep in ['nmod', 'amod'] and prev.func in ['N', 'ADJ'] and (isCNOM(cur.dep) or cur.dep == 'appos') and cur.func in ['N', 'ADJ']:
        # tv-programma
        koppel(prev, cur)
    #elif prev.dep in ['nmod', 'amod'] and cur.func == 'SPEC' and cur.functype == 'deeleigen' and cur.dep in ['flat', 'appos']:
        # een nmod/amod vóór een deeleigen wil eigenlijk eraan vast zitten.
        # TODO: gaat fout in geval van AnneFrank Huis
    #    koppel(prev, cur)
    elif prev.dep == cur.dep and isCNOM(cur.dep):
        # zelfde functie in de zin en vervult de rol van ow/lv/mwvw
        koppel(prev, cur)
    elif prev.func == 'TW' and cur.func == 'TW':
        # honderddrie, duizendtwee, honderdduizend, 300 000
        if not grootGetal(prev) and not grootGetal(cur) and not prev.woord.endswith('duizend'):
            # behoud nodige spaties bij grote getallen:
            # vijf_miljoen_en_drie; vijf_miljoen_vierenveertig, drieduizend_zes;
            koppel(prev, cur)
    elif prev.func == 'TW' and cur.woord == 'en' and nxt[0].func == 'TW' and not grootGetal(prev):
        # drieëntwintig, eenenveertig
        koppel(prev, cur, nxt[0])
    elif prev.dep == 'compound:prt' and prev.func == 'BW' and cur.func == 'WW':
        # weg gesleurd, door gehaald, bij gevoegd, etc.
        plakvast(prev, cur)
    elif prev.dep in ['amod', 'nmod'] and prev.func == 'N' and (isCNOM(cur.dep) or (cur.dep == 'ROOT' and cur.func == 'N')):
        # bijv maximumgewicht, oud-coach, reclamebord. Als prev ADJ is niet koppelen (bijvoorbeeld 'een rood huis')
        # soms wordt een znw als ww herkend, zoals 'dit is een lading honden poep'. De syntactische analyse is dan nauwkeuriger.
        koppel(prev, cur)
    elif isCNOM(prev.dep) and cur.dep == 'appos':
        # 'De buidel rat is dood'
        koppel(prev, cur)
    elif isCNOM(prev.dep) and cur.dep == 'nmod':
        # 'Ik heb een student kamer gekocht.
        koppel(prev, cur)
    elif prev.func == 'ADJ' and cur.func == 'ADJ':
        # prev is in de standaardvorm zonder -e of -st, etc; wegens eerdere selectie daarop
        if isCNOM(prev.dep) and cur.dep == 'acl':
            # roodgloeiende
            koppel(prev, cur)
        elif prev.func == cur.func == 'ADJ' and prev.dep == 'advmod' and cur.dep in ['acl', 'amod']:
            # de rood gloeiende draad
            koppel(prev, cur)
        # anders niet koppelen.
    elif prev.func == 'ADJ' and prev.functype == 'prenom' and prev.dep in ['amod', 'nmod'] and isCNOM(cur.dep) and isPrefix(prev):
        # 'De _oud voetballer_ is blij.', maar moet prefix zijn, anders 'We hebben een avond vullendprogramma gemaakt'.
        koppel(prev, cur)
    elif prev.func == 'ADJ' and prev.functype == 'prenom' and prev.dep in ['amod', 'nmod'] and cur.dep in ['amod', 'nmod']:
        # EHBO diploma in voorbeeldzinnen
        koppel(prev, cur)
    elif isPrefix(prev) and (cur.func == 'N' or cur.func == 'ADJ' or (prev.functype == cur.functype == 'deeleigen')):
        # pseudo-intelligent, ex-coach
        koppel(prev, cur)
    elif prev.func == 'N' and prev.dep == 'obl' and (cur.dep == 'amod' or isCNOM(cur.dep)):
        # avondvullend programma
        koppel(prev, cur)
    #elif prev.func == 'ADJ' and prev.dep == 'advmod' and cur.dep == 'amod':
        # hoogstvervelend, uiterst vervelend
    #    koppel(prev, cur)
    elif prev.func == 'N' and isSuffix(cur):
        koppel(prev, cur)
    elif prev.woord == 'jaren' and isCijfer(cur) and nxt[0].func == 'N' and (nxt[0].dep == 'appos' or isCNOM(nxt[0].dep)):
        # jaren-80-muziek (witte boekje); groene boekje 'jaren 80-muziek' niet ondersteund.
        koppelstreep(prev, cur)
        koppelstreep(cur, nxt[0])
    #elif prev.func == 'TW' and prev.dep == 'nummod' and (isCNOM(cur.dep) or cur.dep in ['nmod', 'amod']):
    # "Dit kan met twee mensen." gaat hier fout.
    #    koppelstreep(prev, cur)
    elif prev.func == 'TW' and isCijfer(prev) and (cur.func == 'ADJ' or ((cur.dep == 'nmod' or cur.dep == 'fixed') and isCNOM(nxt[0].dep))):
        # jaren 80-muziek (groene boekje). 16-jarige;
        # 100-dollarbiljetten, 24-uursservice
        koppelstreep(prev, cur)
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
        # heuristiek: als een WW of ADJ verkeerd geclassificeerd is, en het mag een N zijn,
        # dan er vanuit gaan dat het een N mag zijn, en niet kijken of het een ADJ mag zijn.
        w.func = 'N'
    elif w.wobj['wt']['ADJ']:
        # heuristiek: idem, maar dan voor een ADJ
        w.func = 'ADJ'
    elif w.wobj['wt']['WW']:
        # zowel N als ADJ kunnen niet volgens wiktionary; als WW wel kan, maken we dat ervan
        # dit is de minst waarschijnlijke, omdat spacy woorden vaker niet-WWs als WW klassificeert, dan WWs als iets anders.
        w.func = 'WW'
    # else doe niks; wiktionary klassificeert het als niet N/ADJ/WW

    #if w.func != oldfunc:
    #    print("!!!!!!!!!! Woordfunctie overschreven voor '{}' van {} naar {}.".format(w.orig, oldfunc, w.func))

def fixText(txt, dic = 's', debug = 0):
    text = ''
    doc = inter.nlp[dic](txt)
    zinnen = doc.sents
    for zin in zinnen:
        words = inter.leeszin(zin, 's', debug)
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

def fixFile(filename):
    with open(filename, 'r') as f:
        line = f.readline()
        while line != '':
            for z in fixText(line, 's', debug):
                print(z, end='', sep='')
            line = f.readline()

zin = "Dit is een voorbeeldzin waarin alles goed gespeld is, waarmee het spacy-algoritme wordt gedemonstreerd."
zin = "Wat een mooie dag is het vandaag. Hoe gaat het?\nMet mij goed namelijk."

filename, debug = None, 0
if len(sys.argv) > 1:
    filename = sys.argv[1]
if len(sys.argv) > 2:
    debug = int(sys.argv[2])

if filename:
    print('Fixed file', filename)
    fixFile(filename)
    zin = ''

while zin != '':
    #doc = next(inter.nlp['s'](zin).sents)
    #words = inter.leeszin(doc)
    zin = input() # input("-> ")
    print(zin, "\n==>\n", end='', sep='', flush=True)
    for z in fixText(zin, 's', debug):
        print(z, end='', sep='')
    print('')

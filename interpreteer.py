import spacy
import hunspell
import wiktionary as wkt
from sys import stderr

# https://spacy.io/api/dependencyparser
nlp = {
        's': spacy.load('nl_core_news_sm'),
        #'m': spacy.load('nl_core_news_md'),
        #'l': spacy.load('nl_core_news_lg')
    }
hsp = hunspell.HunSpell("/usr/share/hunspell/nl_NL.dic", "/usr/share/hunspell/nl_NL.aff")

def infoheader():
    print('`woord`'.ljust(19, ' '),
            '`func`  ',
            '`functype`\t',
            '`dep`\t\t',
            '`base`\t\t',
            '`warr`', file=stderr)

def ellips(arr, lim=3):
    if len(arr) > lim:
        return arr[0:lim] + ['...']
    else:
        return arr

class Woord:
    def __init__(self, lookup, w, orig, base, tag, ok, dep):
        self.woord = w
        self.orig = orig
        self.base = base
        self.tag = self.getTag(tag)
        self.correct = ok
        self.dep = dep
        self.comp = ''
        if w == None:
            self.wobj = {'wikt': False}
        elif w in lookup:
            self.wobj = lookup[w]
        else:
            self.wikt()
            lookup[w] = self.wobj

    def printinfo(self):
        warr = {}
        if self.wobj['wikt']:
            if self.func == 'N':
                warr['gender'] = self.wobj['gender']
                try:
                    warr['meer'] = self.wobj['meer']
                except:
                    print(self.wobj)
            if self.func == 'ADJ' and 'bvnw' in self.wobj:
                warr['bvnw'] = self.wobj['bvnw']
            if 'rel' in self.wobj:
                warr['rel'] = self.wobj['rel']
            if 'drv' in self.wobj:
                warr['drv'] = ellips(self.wobj['drv'])
            if 'verw' in self.wobj:
                warr['verw'] = ellips(self.wobj['verw'])
            if 'num' in self.wobj:
                warr['num'] = self.wobj['num']
            if 'afkorting' in self.wobj:
                warr['afkorting'] = self.wobj['afkorting']
            if self.wobj['compound'] != None:
                warr['compound'] = self.wobj['compound']
        else:
            warr['wikt'] = False

        print('✓ ' if self.correct else '✗ ',
                self.woord.rjust(15, ' ')+':',
                self.func.ljust(8, ' '),
                str(self.functype).ljust(7, ' ')+'\t',
                self.dep.ljust(15, ' '),
                self.base.ljust(15, ' '),
                warr, '\n'+'\t'*9,
                self.tag,
                #self.wobj,
                file=stderr
            )
        #print(self.tag)

    def wikt(self):
        if self.func == 'LET':
            self.wobj = {'wikt': False}
            return # geen leestekens opzoeken
        wd = wkt.wordData(self.base)
        if not wd:
            # probeer het woord zelf ipv de base; 'voetballer' wordt als base bijvoorbeeld 'voetball',
            # terwijl 'voetballer' wel gewoon bestaat.
            wd = wkt.wordData(self.orig.strip())
            if not wd:
                self.wobj = {'wikt': False}
                return # geen wiktionary-pagina voor dit woord
        w = wkt.wordToObj(wd[0], self.woord, self.base, wd[1])
        self.wobj = w

    def getTag(self, tag):
        if tag == None:
            self.func = self.functype = None
            return [None]
        tags = tag.split('|')
        self.func = tags[0] # woordtype
        if len(tags) > 1:
            self.functype = tags[1] # specifiek woordtype (_persoonlijk_ voornaamwoord, etc)
        else:
            self.functype = False # geen extra info
        return tags


def leeszin(zin, lookup, dic = 's', debug=True):
    if debug:
        infoheader()
    words = []
    for w in zin:
        tags = w.tag_.split('|')
        W = Woord(lookup, w.norm_, w.text_with_ws, w.lemma_, w.tag_, hsp.spell(w.norm_), w.dep_)
        words.append(W)
        if debug:
            W.printinfo()
    words.append(Woord(*(None,) * 7))
    return words

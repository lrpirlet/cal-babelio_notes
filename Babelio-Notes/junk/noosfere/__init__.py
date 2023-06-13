#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
#
# Note: If this work (done to learn both python and the Hyper Text Markup Language) finds its way to the public domain, so be it.
# I have no problem with, and reserve the right to ignore, any error, choice and poor optimization.
# I use it, it is MY problem... You use it, it is YOUR problem.
# For example, my mother language is French and my variable's names are MY choice for MY easy use...
# Anyway, I'll comment (or not) in English or in French or in both depending when I write it (no comment please :-) )
#
# noosfere is a database of books, volumes, covers, authors, translators, cover designers, critics, critic's author, movies adaptation...
# noosfere is NOT commercial, it is the DB of an association of authors, readers, editors... see about.txt
# last but not least noosfere is in French ONLY: noosfere defines itself as "nooSFere : encyclopédie francophone de Science-Fiction."
#
# A volume has in common with a book the author and the title but not the cover, not the editor, not the isbn, not.."
# I want the information about a volume... I want a coherent information.
#
# In order to collect the information about a volume one must use either the ISBN, the author and the title or at least the title
#
# If the ISBN exists a search in noosfere may point (or not) to a series of volumes (yet only one book :-) )
#
# if the author is the best known identifier a search in noosfere points to an author's list of books (or a list of authors :-( )
# out of this list, a match to the title will point to a series of volumes
#
# if the title is the only reference, a search in noosfere will output a list of books sorted by best match along with a score
# again a book will point to a series of volume... NOT IMPLEMENTED, except for a few book this ends up with too much irrelevant data
#
# out of the volume list one must choose the best candidate to get a coherent set of volumes attributes (cover, isbn, editor, critics, serie, serie #, etc...
#
#
# the nice think about noosfere is the power of the search (each word may be "ANDed, exact or fuzzy match, etc...)
# the result gives a LOT of information about the book, author, translator...
# and the nice think about calibre is the possibility to insert working url in the comments and in the catalog
#

__license__   = 'GPL v3'
__copyright__ = '2021, Louis Richard Pirlet'
__docformat__ = 'restructuredtext en'           # whatever that means???

# those are python code that are directly available in calibre closed environment (test import... using calibre-debug)
import urllib                                   # to access the web
from bs4 import BeautifulSoup as BS             # to dismantle and manipulate HTTP (HyperText Markup Language)
#import sys                                      # so I can access sys (mainly during development, probably useless now)
import time                                     # guess that formats data and time in a common understanding
from queue import Empty, Queue                  # to submit jobs to another process (worker use it to pass results to calibre
from difflib import SequenceMatcher as SM
''' difflib has SequenceMatcher to compare 2 sentences
s1 = ' It was a dark and stormy night. I was all alone sitting on a red chair. I was not completely alone as I had three cats.'
s2 = ' It was a murky and stormy night. I was all alone sitting on a crimson chair. I was not completely alone as I had three felines.'
result = SM(None, s1, s2).ratio()
result is 0.9112903225806451... anything above .6 may be considered similar
'''

# the following make some calibre code available to my code
from calibre.ebooks.metadata.sources.base import (Source, Option)
from calibre.ebooks.metadata import check_isbn
from calibre.utils.icu import lower
from calibre.utils.localization import get_udc

def urlopen_with_retry(log, dbg_lvl, br, url, rkt, who):
    # this is an attempt to keep going when the connection to noosfere fails for no (understandable) reason
    #
    debug=dbg_lvl & 4
    if debug:
        log.info(who, "In urlopen_with_retry(log, dbg_lvl, br, url, rkt, who)")

    tries, delay, backoff=4, 3, 2
    while tries > 1:
        try:
            sr = br.open(url,data=rkt,timeout=30)
            log.info(who,"(ret_soup) sr.getcode()  : ", sr.getcode())
            if debug:
                log.info(who,"url_vrai      : ", sr.geturl())
                log.info(who,"sr.info()     : ", sr.info())
                log.info(who,"ha ouais, vraiment? charset=iso-8859-1... ca va mieux avec from_encoding...")
            return (sr, sr.geturl())
        except urllib.error.URLError as e:
            if "500" in str(e):
                log.info("\n\n\n"+who,"HTTP Error 500 is Internal Server Error, sorry\n\n\n")
                raise Exception('(ret_soup) Failed while acessing url : ',url)
            else:
                log.info(who,"(urlopen_with_retry)", str(e),", will retry in", delay, "seconds...")
                time.sleep(delay)
                delay *= backoff
                tries -= 1
                if tries == 1 :
                    log.info(who, "exception occured...")
                    log.info(who, "code : ",e.code,"reason : ",e.reason)
                    raise Exception('(ret_soup) Failed while acessing url : ',url)

def ret_soup(log, dbg_lvl, br, url, rkt=None, who=''):
    '''
    Function to return (soup,sr.geturl()) with
    soup the HTML coded information and
    sr.geturl() the url from where soup was extracted.
    '''
    debug=dbg_lvl & 4
    if debug:
        log.info(who, "In ret_soup(log, dbg_lvl, br, url, rkt=none, who='[__init__]')")
        log.info(who, "br  : ", br)
        log.info(who, "url : ", url)
        log.info(who, "rkt : ", rkt)

  # Note: le SEUL moment ou on doit passer d'un encodage des characteres a un autre est quand on reçoit des donneées
  # d'un site web... tout, absolument tout, est encodé en uft_8 dans le plugin... J'ai vraiment peiné a trouver l'encodage
  # des charracteres qui venaient de noosfere... Meme le decodage automatique se plantait...
  # J'ai du isoler la création de la soup du decodage dans la fonction ret_soup().
  # variable "from_encoding" isolée pour trouver quel est l'encodage d'origine...
  #
  # variable "from_encoding" isolated to find out what is the site character encoding... The announced charset is WRONG
  # Even auto decode did not always work... I knew that my setup was wrong but it took me a while...
  # Maybe I should have tried earlier the working solution as the emitting node is MS
  # (Thanks MS!!! and I mean it as I am running W10.. :-) but hell, proprietary standard is not standard)...
  # It decode correctly to utf_8 with windows-1252 forced as from_encoding
    from_encoding="windows-1252"


    log.info(who, "Accessing url : ", url)
    if rkt :
        log.info(who, "search parameters : ",rkt)
        rkt=urllib.parse.urlencode(rkt).encode('ascii')
        if debug: log.info(who, "formated parameters : ", rkt)

    resp = urlopen_with_retry(log, dbg_lvl, br, url, rkt, who)
    if debug: log.info(who,"...et from_encoding, c'est : ", from_encoding)

    sr, url_ret = resp[0], resp[1]

    soup = BS(sr, "html5lib", from_encoding=from_encoding)              #"windows-1252")
    if debug:
#        log.info(who,"soup.prettify() :\n",soup.prettify())               # très utile parfois, mais que c'est long...
        log.info(who,"(ret_soup) return (soup,sr.geturl()) from ret_soup\n")
    return (soup, url_ret)

def verify_isbn(log, dbg_lvl, isbn_str, who=''):
    '''
    isbn_str est brute d'extraction... la fonction renvoie un isbn correct ou "invalide"
    Notez qu'on doit supprimer les characteres de separation et les characteres restants apres extraction
    et que l'on traite un mot de 10 ou 13 characteres.

    isbn_str is strait from extraction... function returns an ISBN correct, or not
    Characters irrelevant to ISBN and separators inside ISBN must be removed,
    the resulting word must be either 10 or 13 characters long.
    '''
    debug=dbg_lvl & 4
    if debug:
        log.info(who,"\nIn verify_isbn(log, dbg_lvl, isbn_str)")
        log.info(who,"isbn_str         : ",isbn_str)

    for k in ['(',')','-',' ']:
        if k in isbn_str:
            isbn_str=isbn_str.replace(k,"")
    if debug:
        log.info(who,"isbn_str cleaned : ",isbn_str)
        log.info(who,"return check_isbn(isbn_str) from verify_isbn\n")
    return check_isbn(isbn_str)         # calibre does the check for me after cleaning...

def ret_clean_text(log, dbg_lvl, text, swap=False, who=''):
    '''
    for noosfere search to work smoothly, authors and title needs to be cleaned
    we need to remove non significant characters and remove useless space character
    '''
    debug=dbg_lvl & 4
    if debug:
        log.info(who,"\nIn ret_clean_txt(self, log, text, swap =",swap,")")
        log.info(who,"text         : ", text)

  # Calibre per default presents the author as "Firstname Lastname", cleaned to be become "firstname lastname"
  # Noosfere present the author as "LASTNAME Firstname", let's get "Firstname LASTNAME" cleaned to "firstname lastname"
    for k in [',','.','-',"'",'"','(',')']:             # yes I found a name with '(' and ')' in it...
        if k in text:
            text = text.replace(k," ")
    text=" ".join(text.split())

    if swap:
        if debug:
            log.info("swap name and surname")
        nom=prenom=""
        for i in range(len(text.split())):
            if (len(text.split()[i])==1) or (not text.split()[i].isupper()):
                prenom += " "+text.split()[i]
            else:
                nom += " "+text.split()[i]
        text=prenom+" "+nom
        if debug: log.info("text         : ", text)

    if debug:
        log.info(who,"cleaned text : ", text)
        log.info(who,"return text from ret_clean_txt")

    return lower(get_udc().decode(text))

class noosfere(Source):
  # see https://manual.calibre-ebook.com/fr/plugins.html#calibre.ebooks.metadata.sources.base.Source
  # and https://manual.calibre-ebook.com/fr/_modules/calibre/ebooks/metadata/sources/base.html#Source

    name                    = 'noosfere DB'
    description             = _('Source extention: downloads and sets metadata from noosfere.org for selected volumes')
    author                  = 'Louis Richard Pirlet'
    version                 = (1, 2, 0)
    minimum_calibre_version = (5, 11, 0)

    ID_NAME = 'nsfr_id'
    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'identifier:isbn', 'identifier:nsfr_id', 'languages',
                                'comments', 'publisher', 'pubdate', 'series', 'tags'])
    has_html_comments = True
    supports_gzip_transfer_encoding = True

  # Since the noosfere is written in French for French talking poeple, I
  # took the liberty to write the following information in French. I will
  # comment with a translation in the english language.

                                  # config help message: noosfere is a database that presents information
                                  # about French books, tagged as science-fiction. Those informations span
                                  # from author to films made of the books, including translators,
                                  # illustrators, critics... and of course there work. The book that were
                                  # published several time are exposed as a "volume". Each of those volumes
                                  # share the authors and the book content, they MAY share, or not, the
                                  # cover, the editor, the editor's collection and the associated order
                                  # number, the resume, the critics,etc.... The choice of the volume is done
                                  # by the program. One may somewhat influence the choice through the dialog
                                  # box `priorité de tri´. On the other hand, there is no official way to
                                  # programmaticaly update a custom column. So There is a tick box that will
                                  # push the information along with the publisher. Please read the doc to
                                  # understand how to put it back later in the right place with a right format.

    config_help_message = '<p>'+_(" noosfere est une base de donnée qui propose des informations"
                                  " à propos des ouvrages, de genre science fiction, disponibles en langue française.<br>"
                                  " Ces informations vont de l'auteur aux films produits sur base de l'ouvrage en"
                                  " passant par les auteurs, les traducteurs, les illustrateurs, les critiques..."
                                  " et bien sur, leurs œuvres.<br>Les livres qui ont été publiés plusieurs fois"
                                  " sont repris chacun sous un volume dont est exposé l'ISBN, la date de dépôt légal"
                                  " (repris sous la date de publication, souvent méconnue), la couverture, l'éditeur,"
                                  " la collection de l'éditeur et son numéro d'ordre.<br><br>Le choix, programmé, du volume"
                                  " est quelque peu paramétrable par la boite de dialogue `priorité de tri´.<br><br>"
                                  " D'autre part, il n'existe pas de moyens officiels de remplir une colonne définie"
                                  " par l'utilisateur. Pour rester dans les clous, je propose de remplir le champs"
                                  " de l'éditeur avec, conjointement à celui-ci, la collection et son numéro d'ordre.<br>"
                                  " Une petite procédure, décrite dans la doc devrait remettre tout en ordre."
                                  )

  # priority handling, a choice box that propose to set the priority over
  # the oldest
  # the latest
  # note that the selected volume will have the most represented editor
  # (if editor x reedited 4 time the book, and editor Y only once,
  # editor x will certainly be selected)
  # see algorithm explanation in worker.py 'ret_top_vol_indx(self, url, book_title)'

    PRIORITY_HANDLING={
                       'oldest':_("un plus ancien"),
                       'latest':_("un plus récent")
                        }

    options = (
            Option(
                   'fat_publisher',
                   'bool',
                   True,
                   _("Ajoute collection et son numéro d'ordre au champ éditeur"),       # add the editor's collection and the associated order number to the publisher field
                   _("Cochez cette case pour ajouter la collection et son numéro d'ordre au champs de l'éditeur.<br>"
                     "Voir LIS-MOI editeur_collection_seriel-code.txt")                 # check this box to enable... see README publisher_collection_seriel-code.txt
                   ),
            Option(
                   'debug_level',
                   'number',
                   7,
                   _("Verbosité du journal, de 0 à 7"),                                                    # verbosity of the log
                   _("Le niveau de verbosité:<br>"                                                         # the level of verbosity.
                     " O un minimum de rapport,<br>"                                                       # value 0 will output the minimum,
                     " 1 rapport étendu de __init__,<br>"                                                  # 1 debug messages of __init__
                     " 2 rapport étendu de worker,<br>"                                                    # 2 debug messages of worker
                     " 4 rapport étendu des annexes...<br>"                                                # 4 debug level of accessory code...
                     " La somme 3, 5 ou 7 peut être introduite, ainsi 7 donne un maximum de rapport.<br>"  # 3, 5 or 7 is the sum of the value defined above.
                     " Note: mettre la verbosité = 7 pour rapport d'erreur")                               # use 7 to log an issue
                                                         # In fact it is a bitwise flag spread over the last 3 bits of debug_level
                   ),
            Option(
                   'Priority',
                   'choices',
                   'oldest',
                   _('priorité de choix:'),
                   _("Priorité de choix du volume."),    # how to push the priority over the choice of the volume
                   choices=PRIORITY_HANDLING
                   ),
            Option(
                   'ISBN_wanted',
                   'bool',
                   True,
                   _("Privilégie un volume avec un ISBN présent"),       # Boost the priority if ISB present for the volume
                   _("Cochez cette case pour sélectionner un volume avec ISBN si il existe.")
                   ),
            Option(
                   'Balanced_wanted',
                   'bool',
                   True,
                   _("choix du volume pondéré"),          #
                   _("la priorite est donnée au volume avec:<br>"
                     "résumé présent, 1pt<br>"                   # résumé présent:                       r   1pt
                     "critique présente, 1pt<br>"                # critique présente:                    c   1pt         # semble pas trop correct car CS n'existe pas même si, quand
                     "critique de la série, 1pt<br>"             # critique de la série                  cs  1pt         # une critique existe, elle est parfois reprise pour tous les volumes
                     "sommaire des nouvelles présentes, 1pt<br>" # sommaire des nouvelles présentes:     s   1pt
                     "information vérifiée, 1pt<br>"             # information vérifiée                  v   1pt
                     "titre identique, 1pt<br>"                  # titre identique                       t   1pt
                     "et/ou couverture présente 1pt")            # image présente                        p   1pt

                   ),
            Option(
                   'requested_editor',
                   'string',
                   "x",
                   _("Impose un éditeur, 3 possibilités"),                                        # impose a publisher, 3 possibilities
                   _("Non défini (boite vide): l'éditeur ne fait pas partie du choix.<br>"            # Undefined (empty box): publisher is not part of the choice
                     " Défini inexistant: le volume aura l'éditeur le plus représenté.<br>"            # Defined (x) but inexistant): volume will have most present publisher
                     " Défini avec un MATCH PARFAIT: le volume sera choisi avec cet éditeur.")     # Defined with a PERFECT MATCH volume will be choosen with that publisher.
                   ),
            Option(
                   'Prixobtenus',
                   'bool',
                   False,
                   _("Ajoute 'Prix obtenus' et 'Prix obtenus par des textes au sommaire"),        # add some field to the comment field
                   _("Cochez cette case pour ajouter ces infos, si elles existent dans noosfere.") # check this box to enable...
                   ),
            Option(
                   'Citédanslespagesthématiquessuivantes',
                   'bool',
                   False,
                   _("Ajoute Cité dans les pages thématiques suivantes"),                          # add some field to the comment field
                   _("Cochez cette case pour ajouter ces infos, si elles existent dans noosfere.") # check this box to enable...
                   ),
            Option(
                   'Citédansleslistesthématiquesdesoeuvressuivantes',
                   'bool',
                   False,
                   _("Ajoute Cité dans les listes thématiques des oeuvres suivantes"),             # add some field to the comment field
                   _("Cochez cette case pour ajouter ces infos, si elles existent dans noosfere.") # check this box to enable...
                   ),
            Option(
                   'CitédanslesConseilsdelecture',
                   'bool',
                   False,
                   _("Ajoute Cité dans les Conseils de lecture"),                                  # add some field to the comment field
                   _("Cochez cette case pour ajouter ces infos, si elles existent dans noosfere.") # check this box to enable...
                   ),
            Option(
                   'Adaptations',
                   'bool',
                   False,
                   _("Ajoute Adaptations (cinéma, télévision, BD, théâtre, radio, jeu vidéo...)"), # add some field to the comment field
                   _("Cochez cette case pour ajouter ces infos, si elles existent dans noosfere.") # check this box to enable...
                   ),
            )

  # this defines a method to access both the code and the data in the object
    @property
    def extended_publisher(self):
        x = getattr(self, 'ext_pub', None)
        if x is not None:
            return x
        ext_pub = self.prefs.get('fat_publisher', False)
        return ext_pub

    @property
    def dbg_lvl(self):
        x = getattr(self, 'dl', None)
        if x is not None:
            return x
        dl = self.prefs.get('debug_level', False)
        return dl

    @property
    def set_priority_handling(self):
        x = getattr(self, 'prio_handling', None)
        if x is not None:
            return x
        prio_handling = self.prefs['Priority']
        if prio_handling not in self.PRIORITY_HANDLING:
            prio_handling = sorted(self.PRIORITY_HANDLING.items(),reverse=True)[0]    # sort the dict to make a list and select first item (that should be the default)
        return prio_handling

    @property
    def with_isbn(self):
        x = getattr(self, 'wisbn', None)
        if x is not None:
            return x
        wisbn = self.prefs.get('ISBN_wanted', False)
        return wisbn

    @property
    def balanced(self):
        x = getattr(self, 'wbal', None)
        if x is not None:
            return x
        wbal = self.prefs.get('Balanced_wanted', False)
        return wbal

    @property
    def must_be_editor(self):
        x = getattr(self, 'te', None)
        if x is not None:
            return x
        te = self.prefs.get('requested_editor', None)
        return te

    @property
    def get_Prixobtenus(self):
        x = getattr(self, 'get_po', None)
        if x is not None:
            return x
        get_po = self.prefs.get('Prixobtenus', False)
        return get_po

    @property
    def get_Citédanslespagesthématiquessuivantes(self):
        x = getattr(self, 'get_cdpt', None)
        if x is not None:
            return x
        get_cdpt = self.prefs.get('Citédanslespagesthématiquessuivantes', False)
        return get_cdpt

    @property
    def get_Citédansleslistesthématiquesdesoeuvressuivantes(self):
        x = getattr(self, 'get_cdlt', None)
        if x is not None:
            return x
        get_cdlt = self.prefs.get('Citédansleslistesthématiquesdesoeuvressuivantes', False)
        return get_cdlt

    @property
    def get_CitédanslesConseilsdelecture(self):
        x = getattr(self, 'get_cdcl', None)
        if x is not None:
            return x
        get_cdcl = self.prefs.get('CitédanslesConseilsdelecture', False)
        return get_cdcl

    @property
    def get_Adaptations(self):
        x = getattr(self, 'get_a', None)
        if x is not None:
            return x
        get_a = self.prefs.get('Adaptations', False)
        return get_a

    def get_book_url(self, identifiers):
        '''
        get_book_url : used by calibre to convert the identifier to a URL...
        return an url if nsfr_id exists and is valid
        '''
        nsfr = identifiers.get('nsfr_id', None)
        if "vl$" in nsfr:
            nsfr_id = nsfr.split("$")[-1]
        if nsfr_id:
            return (self.ID_NAME, nsfr_id, "https://www.noosfere.org/livres/niourf.asp?numlivre=" + nsfr_id)

    def id_from_url(self, url):
        '''
        id_from_url : takes an URL and extracts the identifier details...
        '''
        idt=""
        if "https://www.noosfere.org/livres/niourf.asp?numlivre=" in url.lower():
            idt = url.lower().replace("https://www.noosfere.org/livres/niourf.asp?numlivre=","").strip()
        if idt:
            return (self.ID_NAME, "vl$" + idt)
        else:
            return None

    def get_cached_cover_url(self, identifiers):
        '''
        Copied from other working metadata source (thanks to David Forrester and the Kobo Books Metadata source)

        I guess this routine returns an url that was discovered somewhere else and put into cache
        probably using cache_identifier_to_cover_url in the worker.py
        as ISBN is missing sometime in noosfere
        as noosfere does not provide any proprietary id
        I will use nsfr_id, a combination of bk_<significant part of book_url>_vl_<significant part of vol_url>
        this should allow to go directly to the book page (that could be the vol page if there is only one vol for the book)
        '''
        url = None
        nsfr_id = identifiers.get('nsfr_id', None)
        if nsfr_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                nsfr_id = self.cached_isbn_to_identifier(isbn)
        if nsfr_id is not None:
            url = self.cached_identifier_to_cover_url(nsfr_id)
        return url

    def ret_author_index(self, log, br, authors):
        '''
        Trouve la référence de l'auteur dans la soupe de noosfere
        retourne author_index, un dictionnaire avec key=AUTEUR, val=href
        L'idée est de renvoyer UNE seule référence... trouver l'auteur est primordial si isbn is indisponible

        Find author references in the soup produced by noosfere, return author_index a dictionary with key=author, val=href
        the idea is to find ONE single reference... to get the author is important if isbn is unavailable
        '''
        debug=self.dbg_lvl & 1
        log.info("\nIn ret_author_index(soup)")
        if debug:
            log.info("authors    : ", authors)
        all_author_index={}
        author_index=[]

      # try to get a short list of authors using "MOTS-CLEFS" match
        for j in range(len(authors)):
            rkt = {"Mots":authors[j],"auteurs":"auteurs","ModeMoteur":"MOTS-CLEFS","ModeRecherche":"AND","recherche":"1","Envoyer":"Envoyer"}
            url = "https://www.noosfere.org/livres/noosearch.asp"
            soup = ret_soup(log, self.dbg_lvl, br, url, rkt=rkt )[0]
            tmp_ai=soup.select('a[href*="auteur.asp"]')
            if len(tmp_ai):
                for i in range(len(tmp_ai)):
                    url_author, author, perta=tmp_ai[i]["href"], tmp_ai[i].text, tmp_ai[i].find_previous('tr').select_one('td').text
                    ratio = SM(None, ret_clean_text(log, self.dbg_lvl, author,swap=True), authors[j]).ratio()
                    if debug:
                        log.info("pertinence : ", perta, end=" ; ")
                        log.info("SM.ratio : {:.3f}".format(ratio), end=" ; ")
                        log.info("url_author : ", url_author, end=" ; ")
                        log.info("authors[j] : ", authors[j], end=" ; ")
                        log.info("author : ", ret_clean_text(log, self.dbg_lvl, author))
                    if ratio >= .6 :
                        all_author_index[url_author]=[ratio, author]

            if not len(all_author_index):                          # failed the short list, let's go for the long list using "LITTERAL" match
                if debug: log.info("exact match failed, trying fuzzy match")
              # return self.ret_author_index(self, log, br, authors, ModeMoteur="LITTERAL")
              # ça marche pas... ret_author_index() got multiple values for argument 'ModeMoteur'
              # this is NOT a function but a class method
              # it is possible to move the common part of this code below, but my mind refuses to understand the change
              # when debugging... so duplicate the code (maybe an optimiseur later will make it... m'en fout)
                for j in range(len(authors)):
                    rkt = {"Mots":authors[j],"auteurs":"auteurs","ModeMoteur":"LITTERAL","ModeRecherche":"AND","recherche":"1","Envoyer":"Envoyer"}
                    url = "https://www.noosfere.org/livres/noosearch.asp"
                    soup = ret_soup(log, self.dbg_lvl, br, url, rkt=rkt )[0]
                    tmp_ai=soup.select('a[href*="auteur.asp"]')
                    if len(tmp_ai):
                        for i in range(len(tmp_ai)):
                            url_author, author, perta=tmp_ai[i]["href"], tmp_ai[i].text, tmp_ai[i].find_previous('tr').select_one('td').text
                            ratio = SM(None, ret_clean_text(log, self.dbg_lvl, author,swap=True), authors[j]).ratio()
                            if debug:
                                log.info("pertinence : ", perta, end=" ; ")
                                log.info("SM.ratio : {:.3f}".format(ratio), end=" ; ")
                                log.info("url_author : ", url_author, end=" ; ")
                                log.info("authors[j] : ", authors[j], end=" ; ")
                                log.info("author : ", ret_clean_text(log, self.dbg_lvl, author))
                            if ratio >= .6 :
                                all_author_index[url_author]=[ratio, author]

        sorted_author_index=dict(sorted(all_author_index.items(), key=lambda x: x[1][0],reverse=True))

        if debug: log.info("sorted_author_index :\n",sorted_author_index)

      # With python 3.6 onward, the standard dict type maintains insertion order by default.
      # Python 3.7 elevates this implementation detail to a language specification,
      # noosfere sort the highest pertinence first (the most probable author comes out first)
      # so, I have no need to sort on pertinence field (would be different for calibre below Version 5)
      #
      # we only consider those with the highest pertinence, we limit to when the pertinence drops to less than half of the maximum
        count=0
        for key,ref in sorted_author_index.items():
            count+=1
            url_author, ratio, name_author = key, ref[0], ref[1]
            author_index.append(url_author)
            if debug:
                log.info("ratio : ", ratio, end=" ; ")
                log.info("author     : ", name_author, end=" ; ")
                log.info("url_author : ", url_author, end=" ; ")
                log.info("count : ",count)
#                log.info("author_index : ",author_index)       # may be long
            if count == 8 : break

        if debug: log.info('return from ret_author_index')
        return author_index

    def ret_book_per_author_index(self, log, br, author_index, title, book_index):
        '''
        Find the books references of a known author from the returned soup for noosfere
        returns a dict "book_per_author_index{}" with key as title and val as the link to the book
        Idea is to send back a few references that hopefully contains the title expected

        Trouver la référence des livres d'un auteur connu dans la soupe produite par noosfere
        retourne "book_per_author_index{}", un dictionnaire avec key=titre, val=href
        L'idée est de renvoyer une série de référencé, dont on extrait les livres proches du titre de calibre

        now that we have a list of authors, let's get all the books associated with them
        The "book_per_author_index" dictionnary will contain all book's references...
        If a book has a common url it will be overwritten by the following author, ensuring a list of unique books
        '''
        debug=self.dbg_lvl & 1
        log.info("\nIn ret_book_per_author_index(self, log, br, author_index, title, book_index)")
        if debug:
            log.info("author_index : ",author_index)
            log.info("title        : ",title)
            log.info("book_index   : ",book_index)

        book_per_author_index={}

        for i in range(len(author_index)):
            rqt= author_index[i]+"&Niveau=livres"
            url="https://www.noosfere.org"+rqt
            soup = ret_soup(log, self.dbg_lvl, br, url)[0]
            tmp_bpai=soup.select('a[href*="ditionsLivre.asp"]')
            for i in range(len(tmp_bpai)):
                book_title=tmp_bpai[i].text.lower()
                book_url=(tmp_bpai[i]["href"].replace('./','/livres/').split('&'))[0]
                ratio = SM(None, title, ret_clean_text(log, self.dbg_lvl, book_title)).ratio()
                if debug:
                    log.info("SM.ratio : {:.3f}".format(ratio),end=" ; ")
                    log.info("book_url : ",book_url,end=" ; ")
                    log.info('tmp_bpai[i]["href"] : ',tmp_bpai[i]["href"],end=" ; ")
                    log.info("book_title : ",book_title)
                if ratio > .6 :
                    book_per_author_index[ratio]=[book_url, "", book_title]
                if ratio == 1:
                    book_per_author_index={}
                    book_per_author_index[ratio]=[book_url, "", book_title]
                    break
                  # we have a perfect match no need to go further in the author books
                  # and I know it could cause problem iff several authors produce an identical title

            sorted_book_index=dict(sorted(book_per_author_index.items(),reverse=True))
            if debug: log.info("sorted bySM.ratio")
            for key,ref in sorted_book_index.items():
                if debug:
                    log.info("SM.ratio : {:.3f}".format(key),end=" ; ")
                    log.info("book_url : ",ref[0],end=" ; ")
                    log.info("book_title : ",ref[2])
                book_index[ref[0]] = ref[2]
            log.info('book_index[book_url] = book_title : ',book_index)

            if ratio == 1:
                log.info("Perfect match, we got it and we can stop looking further")
                break
              # we have a perfect match no need to examine other authors

        if debug: log.info('return book_index from ret_book_per_author_index\n')
        return book_index

    def ISBN_ret_book_index(self, log, br, isbn, book_index):
        '''
        Trouver la référence d'un livre (titre ou ISBN) dans la soupe produite par noosfere
        retourne book_index{}, un dictionnaire avec key=book_url, val=title
        L'idée est de trouver UNE seule référence...
        Attention: on retourne une référence qui peut contenir PLUSIEURs volumes
        C'est a dire: différents éditeurs, différentes re-éditions et/ou, même, un titre différent... YESss)

        Find the book's reference (either title or ISBN) in the returned soup from noosfere
        returns book_index{}, a dictionary with key=book_url, val=title
        The idea is to find ONE unique reference...
        Caution: the reference may contains several volumes,
        each with potentially a different editor, a different edition date,... and even a different title
        '''
        debug=self.dbg_lvl & 1
        log.info("\nIn ISBN_ret_book_index(self, log, br, isbn, book_index)")

        # if isbn valid then we want to select exact match (correspondance exacte = MOTS-CLEFS)
        rkt={"Mots": isbn,"livres":"livres","ModeMoteur":"MOTS-CLEFS","ModeRecherche":"AND","recherche":"1","Envoyer":"Envoyer"}
        url = "https://www.noosfere.org/livres/noosearch.asp"
        soup = ret_soup(log, self.dbg_lvl, br, url, rkt=rkt )[0]
        tmp_rbi=soup.select('a[href*="ditionsLivre.asp"]')
        if len(tmp_rbi):
            for i in range(len(tmp_rbi)):
                if debug:
                    log.info("tmp_rbi["+str(i)+"].text, tmp_rbi["+str(i)+"]['href'] : ",tmp_rbi[i].text,tmp_rbi[i]["href"])
                book_index[tmp_rbi[i]["href"]]=tmp_rbi[i].text

        if debug:
            log.info("book_index : ",book_index)
            log.info("return book_index from ISBN_ret_book_index\n")
        return book_index

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        '''
        this is the entry point...
        Note this method will retry without identifiers automatically... read can be resubmitted from inside it
        if no match is found with identifiers.
        '''

        log.info('self.extended_publisher                                     : ', self.extended_publisher)
        log.info('self.dgb_lvl                                                : ', self.dbg_lvl)
        log.info('self.set_priority_handling                                  : ', self.set_priority_handling)
        log.info('self.with_isbn                                              : ', self.with_isbn)
        log.info('self.balanced                                               : ', self.balanced)
        log.info('self.must_be_editor                                         : ', self.must_be_editor)
        log.info('self.get_Prixobtenus                                        : ', self.get_Prixobtenus)
        log.info('self.get_Citédanslespagesthématiquessuivantes               : ', self.get_Citédanslespagesthématiquessuivantes)
        log.info('self.get_Citédansleslistesthématiquesdesoeuvressuivantes    : ', self.get_Citédansleslistesthématiquesdesoeuvressuivantes)
        log.info('self.get_CitédanslesConseilsdelecture                       : ', self.get_CitédanslesConseilsdelecture)
        log.info('self.get_Adaptations                                        : ', self.get_Adaptations)

        debug=self.dbg_lvl & 1
        log.info('\nEntering identify(self, log, result_queue, abort, title=None, authors=None,identifiers={}, timeout=30)')
        if debug:
            log.info('log          : ', log)
            log.info('result_queue : ', result_queue)
            log.info('abort        : ', abort)
            log.info('title        : ', title)
            log.info('authors      : ', authors, type(authors))
            log.info('identifiers  : ', identifiers, type(identifiers))
            log.info('\n')

        br = self.browser

        isbn = identifiers.get('isbn', None)
        if isbn: isbn = verify_isbn(log, self.dbg_lvl, isbn)
        log.info('ISBN value is : ', isbn)

      # the nsfr_id is designed to be the significant part of the URL:
      # that is the number after the "=" in the URL containing "niourf.asp?numlivre"
      # one can force the access to a particular volume by setting the value of nsfr_id to vl$<number>
      # could be an entry point if I can make sure that noosfere DB is alone and in interactive mode...
      # example: for "Boule de foudre", author LIU Cixin...
      # URL is: https://www.noosfere.org/livres/niou...vre=2146606157 and
      # set nsfr_id to vl$2146606157 to directly access this volume, bypassing search of "best volume".
        nsfr_id = identifiers.get('nsfr_id', None)
        log.info('nsfr_id value is : ', nsfr_id)

        log.info('"Clean" both the authors list and the title... ')
        if authors:
            for i in range(len(authors)):
                if ',' in authors[i]:               # if comma, assume last-name, first-name... swap it
                    spl_authors=authors[i].split(',')
                    if len(spl_authors)==2: authors[i]=" ".join([spl_authors[1],spl_authors[0]])
                authors[i] = ret_clean_text(log, self.dbg_lvl, authors[i])
        if title:
            title = ret_clean_text(log, self.dbg_lvl, title)

        log.info('getting one or more book url')
        book_index={}        # book_index={} is a dict: {key:ref} with: book_url, book_title = key, ref
        if nsfr_id:
            log.info('trying noosfere id, ', nsfr_id )
            nsfr = nsfr_id.split("$")
            if "bk" in nsfr[0] :
                url = "/livres/EditionsLivre.asp?numitem="+nsfr[1]
                if "vl" in nsfr[2] :
                    url = "/livres/niourf.asp?numlivre="+nsfr[3]
                book_index[url]=title
            elif "vl" in nsfr[0] :
                url = "/livres/niourf.asp?numlivre="+nsfr[1]
                book_index[url]=title
            else:
                log.info('noosfere id not valid...')

        if not book_index:
            log.info('trying ISBN', isbn)
            if isbn:
                book_index = self.ISBN_ret_book_index(log, br, isbn, book_index)
                if not len(book_index):
                    log.error("This ISBN was not found: ", isbn, "trying with title", title,"and author", authors)
                    return self.identify(log, result_queue, abort, title=title, authors=authors, timeout=timeout)
            elif title and authors:
                log.info('trying using authors and title')
                author_index=self.ret_author_index(log, br, authors)
                if len(author_index):
                    book_index = self.ret_book_per_author_index(log, br, author_index, title, book_index)
                if not len(author_index):
                    log.info("Désolé, aucun auteur trouvé avec : ",authors)
                    return

        if not book_index:
            log.error("No book found in noosfere... ")
            return

        if abort.is_set():
            log.info('abort was set... aborting... ')
            return

        tmp_list,i=[],0
        for key,ref in book_index.items():
            book_url, book_title = key, ref
            if debug:log.info("sending to worker", i,"book_url, book_title : ", book_url,", ", book_title)
            i+=1
            tmp_list.append((book_url, book_title))

        log.info('\nCreating each worker... ')
        from calibre_plugins.noosfere.worker import Worker
        workers = [Worker(log, data[0], data[1], isbn, result_queue, br, i, self, self.dbg_lvl) for i, data in enumerate(tmp_list)]

        for w in workers:
            w.start()
            # Don't send all requests at the same time
            time.sleep(0.2)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    log.info('abort was set while in loop... aborting... ')
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        if debug: log.info("return None from identify")
        return None


    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        '''
        will download cover from Noosfere provided it was found (and then cached)... If not, it will
        run the metadata download and try to cache the cover URL...
        '''
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors, identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return

        br = self.browser
        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(cached_url, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)

####################### test section #######################

if __name__ == '__main__':
  # Run these tests from the directory containing all files needed for the plugin (the files that go into the zip file)
  # that is: __init__.py, plugin-import-name-noosfere.txt and optional .py such as worker.py, ui.py
  # issue in sequence:
  # calibre-customize -b .
  # calibre-debug -e __init__.py
  # attention: on peut voir un message prévenant d'une erreur... en fait ce message est activé par la longueur du log... (parfois fort grand)
  # Careful, a message may pop up about an error... however this message pops up function of the length of the log... (sometime quite big)
  # anyway, verify... I have been caught at least once

    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test, series_test)
    test_identify_plugin(noosfere.name,
        [

            ( # A book with ISBN specified not in noosfere
                {'identifiers':{'isbn': '9782265070769'}, 'title':'Le chenal noir', 'authors':['G.-J. Arnaud']},
                [title_test("Le Chenal noir", exact=True), authors_test(['G.-J. Arnaud']), series_test('La Compagnie des glaces - Nouvelle époque',2)]
            ),

            ( # A book with ISBN specified
                {'identifiers':{'isbn': '2-266-03441-3'}, 'title':'Futurs sans escale', 'authors':['ANTHOLOGIE']},
                [title_test("Futurs sans escale", exact=True), authors_test(['ANTHOLOGIE']), series_test('Isaac Asimov présente',1)]
            ),

            ( # A book with ISBN specified
                {'identifiers':{'isbn': '2-265-04038-X'}, 'title':'Onze bonzes de bronze', 'authors':['Max ANTHONY']},
                [title_test("Onze bonzes de bronze", exact=True), authors_test(['Max ANTHONY']), series_test('Ned Lucas',1)]
            ),

            ( # A book with nsfr_id:bk$5308$vl$-323559
                {'identifiers':{'nsfr_id':'bk$5308$vl$-323559'}, 'title':"Le Printemps d'Helliconia", 'authors':['B.W. Aldiss']},
                [title_test("Le Printemps d'Helliconia", exact=True), authors_test(['Brian Aldiss']), series_test('Helliconia', 1.0)]
            ),

            ( # A book with a wrong ISBN and title not quite right, will find one correct and 3 incorrect, correct is hightest priority...
                {'identifiers':{'isbn': '227721409x'}, 'title':"La Patrouille des temps", 'authors':['Poul Anderson']},
                [title_test("La Patrouille du temps", exact=True), authors_test(['Poul Anderson']), series_test('La Patrouille du Temps', 1.0)]
            ),

##            ( # A book with no ISBN specified ... will fail over serie (serie is missing...)
##                {'identifiers':{}, 'title':"La Guerre contre le Rull", 'authors':['A.E. van Vogt']},
##                [title_test("La Guerre contre le Rull", exact=True), authors_test(['Alfred Elton VAN VOGT']), series_test('',0)]
##            ),

##            ( # A book with a HTTP Error 500
##                {'identifiers':{'isbn': '2-290-04457-1'}, 'title':"Le Monde de l'exil", 'authors':['David BRIN']},
##                [title_test("Le Monde de l'exil", exact=True), authors_test(['David Brin']), series_test('', 0)]
##            ),

        ])

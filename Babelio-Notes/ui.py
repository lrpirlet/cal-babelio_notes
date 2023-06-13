#!/usr/bin/env python3
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

# I want to combine ui and worker, as worker will NOT be spawed, ever.

__license__   = 'GPL v3'
__copyright__ = 'Louis Richard Pirlet based on Christophe work'
__docformat__ = 'restructuredtext en'

from calibre import prints
from calibre.constants import DEBUG

from calibre.gui2.actions import InterfaceAction        # The class that all interface action plugins must inherit from
from calibre.ebooks.metadata.book.base import Metadata

import urllib                                   # to access the web
from bs4 import BeautifulSoup as BS             # to dismantle and manipulate HTTP (HyperText Markup Language) a text formated utf-8

import time, datetime
from urllib.parse import quote

from lxml.html import fromstring, tostring
from calibre import browser

from calibre import as_unicode
from calibre.utils.icu import lower
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.localization import get_udc

from calibre.ebooks.metadata.sources.search_engines import rate_limit



TIME_INTERVAL = 1.2      # this is the minimum interval between 2 access to the web (with decorator on ret_soup())

class Un_par_un(object):
    '''
    This is a class decorator, cause I am too lazy to rewrite that plugin... :),
    beside I want to learn creating one. Well, granted, dedicated to ret_soup()

    Purpose: execute the decorated function with a minimum of x seconds
    between each execution, and collect all access time information...

    rate_limit() from calibre.ebooks.metadata.sources.search_engines provides the delay
    using a locked file containing the access time... maintenance of this resource
    is hidden in a context manager implementation.

    @contextmanager
    def rate_limit(name='test', time_between_visits=2, max_wait_seconds=5 * 60, sleep_time=0.2):

    I assume that calibre will wait long enough for babelio plugin (I pushed to 45 sec after first match)
    '''
    def __init__(self,fnctn):
        self.function = fnctn
        self._memory = []

    def __call__(self, *args, **kwargs):
        # note : name='Babelio_db' so we interleave with babelio_db would this plugin be used at the same time
        with rate_limit(name='Babelio_db', time_between_visits=TIME_INTERVAL):
          # call decorated function: "ret_soup" whose result is (soup,url)
            result = self.function(*args, **kwargs)
            self._memory.append((result[1], time.asctime()))
            return result

    def get_memory(self):
        mmry = self._memory
        self._memory = []
        return mmry

@Un_par_un
def ret_soup(br, url, rkt=None):
    '''
    Function to return the soup for beautifullsoup to work on. with:
    br the mechanize browser, url the request address, rkt the
    arguments for a POST request, if rkt is None, the request is GET...
    Un_par_un introduce a wait time to avoid DoS attack detection,
    soup is the response from the URL, formatted utf-8 (no decode needed).
    url_ret is the URL address of soup as reported by br.
    return (soup, url_ret)
    '''
    if DEBUG:
        prints("DEBUG In ret_soup(log, dbg_lvl, br, url, rkt=none, who=''\n")
        prints("DEBUG URL request time : ", datetime.datetime.now().strftime("%H:%M:%S"))
    start = time.time()
    if DEBUG:
        prints("DEBUG br                : ", br)
        prints("DEBUG url               : ", url)
        prints("DEBUG rkt               : ", rkt)

    prints("Accessing url     : ", url)
    if rkt :
        prints("search parameters : ",rkt)
        rkt=urllib.parse.urlencode(rkt).encode('ascii')
        if DEBUG: prints("DEBUG formated parameters : ", rkt)

    try:
        sr = br.open(url,data=rkt,timeout=30)
        prints("(ret_soup) sr.getcode()  : ", sr.getcode())
        if DEBUG:
            prints("DEBUG url_vrai      : ", sr.geturl())
            prints("DEBUG sr.info()     : ", sr.info())
        url_ret = sr.geturl()
    except urllib.error.URLError as e:
        prints("exception occured...")
        prints("code : ",e.code,"reason : ",e.reason)
        raise Exception('(urlopen_with_retry) Failed while acessing url : ',url)
    soup = BS(sr, "html5lib")

    # if DEBUG: prints("DEBUG soup.prettify() :\n",soup.prettify())               # hide_it # très utile parfois, mais que c'est long...
    return (soup, url_ret)

def ret_clean_text(text):
    '''
    For the site search to work smoothly, authors and title needs to be cleaned.
    we need to remove non significant characters and remove useless space character...
    '''
    if DEBUG:
        prints("DEBUG: In ret_clean_txt(text)\n")
        prints("DEBUG: text         : ", text)

    txt = lower(get_udc().decode(text))

    for k in [',','.',':','-',"'",'"','(',')','<','>','/']:             # yes I found a name with '(' and ')' in it...
        if k in txt:
            txt = txt.replace(k," ")
    clntxt=" ".join(txt.split())

    if DEBUG:
        prints("DEBUG: cleaned text : ", clntxt)
        prints("DEBUG: return text from ret_clean_txt")

    return clntxt


#################################################################

class InterfaceBabelioNotes(InterfaceAction):

    name = 'Babelio Notes'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    action_spec = ('Babelio Notes', None,
            'Recherche note moyenne et votes sur le site de Babelio', ())
    action_type = 'current'

    def genesis(self):
        # This method is called once per plugin, do initial setup here

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.
        #
        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        icon = get_icons('images/babelio.png')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        # Assign our menu to this action and an icon
        self.qaction.triggered.connect(self.update_babelio)

    def update_babelio(self):
        '''
        Set the metadata in the files in the selected book's record to
        match the current metadata in the database.
        '''

        from calibre.gui2 import error_dialog, info_dialog

        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Vous devez sélectionner un ou plusieurs livres', show=True)
        # Map the rows to book ids
        book_ids = self.gui.library_view.get_selected_ids()

        #dbA = self.gui.current_db
        db = self.gui.current_db.new_api

        for book_id in book_ids:
            # Get the current metadata for this book from the db
            mi = db.get_metadata(book_id, get_cover=True, cover_as_data=True)

            notes = mi.get ("#ratingbab")
            votes = mi.get ("#nbvotbab")
            trouvebab = mi.get ("#trouvebab")
            title = mi.title
            authors = mi.authors
            ids = mi.get_identifiers()
            if DEBUG:
                prints("+-"*40)
                prints("DEBUG: ids : {}".format(ids))

            babelio_worker = DownloadBabelioWorker(title, authors, ids)
            # babelio_worker = DownloadBabelioWorker(title,authors)
            new_notes = babelio_worker.notes
            new_votes = babelio_worker.votes
            trouvebaby = 'Y'
            trouvebabn = 'N'

            # ne mettre à jour que si le nombre de votes trouvés est supérieur à celui déjà présent
            if new_votes:
                db.new_api.set_field('#trouvebab', {book_id: trouvebaby})
                votes_float = float(new_votes)
                if votes:
                    if votes_float > votes:
                        db.new_api.set_field('#ratingbab', {book_id: new_notes})
                        db.new_api.set_field('#nbvotbab', {book_id: new_votes})
                    else:
                        if DEBUG: prints('DEBUG: pas de nouveaux votes sur babelio ')
                else:
                    db.new_api.set_field('#ratingbab', {book_id: new_notes})
                    db.new_api.set_field('#nbvotbab', {book_id: new_votes})
            else:
                db.new_api.set_field('#trouvebab', {book_id: trouvebabn})

            self.gui.iactions['Edit Metadata'].refresh_books_after_metadata_edit({book_id})

        info_dialog(self.gui, 'Babelio Notes',
                'Recherche note et votes sur le site Babelio pour %d livre(s)'%len(book_ids),
                show=True)


        #######################################################################################

class DownloadBabelioWorker(Source):

    def __init__(self, title, authors, ids, timeout=20):
        self.timeout = timeout
        self.notes = None
        self.votes = None
        self.title = title
        self.authors = authors
        self.isbn = ids["isbn"] if "babelio_id" in ids else ""
        self.bbl_id = ids["babelio_id"] if "babelio_id" in ids else ""
         # l'idée c'est que si on a babelio_id alors on connais le lvre ET son url
        self.run()

    def run(self):

        matches = []
        br = browser()
        query = ""

        prints("self.title   : {}".format(self.title))
        prints("self.authors : {}".format(self.authors))
        prints("self.bbl_id  : {}".format(self.bbl_id))
        prints("self.isbn    : {}".format(self.isbn))

        nknwn = ['Inconnu(e)','Unknown','Inconnu','Sconosciuto','Necunoscut(ă)']   #français, anglais, français(Canada), italien, roman
        for i in range(len(nknwn)):
            if self.authors and nknwn[i] in self.authors[0]:
                self.authors = None
                if DEBUG: prints("DEBUG: authors Unknown processed : ", self.authors)
                break

        if self.bbl_id and "/" in self.bbl_id and self.bbl_id.split("/")[-1].isnumeric():
            matches = ["https://www.babelio.com/livres/" + self.bbl_id]
            if DEBUG:
                prints("DEBUG: bbl_id matches : ", matches)
                prints("DEBUG: babelio identifier trouvé... pas de recherche sur babelio... on saute directement au livre\n")

        if not matches:          # on saute au dessus de tout le reste et on trouve les valeurs rating
            query= "https://www.babelio.com/resrecherche.php?Recherche=%s&item_recherche=isbn"%self.isbn
            if DEBUG:
                prints("DEBUG: ISBN identifier trouvé, on cherche cet ISBN sur babelio : ", query)
            soup = ret_soup(br, query)[0]
            matches = self.parse_search_results(title, authors, soup, br)

        if not matches:          # on saute au dessus de tout le reste et on trouve les valeurs rating
            intab = "àâäéèêëîïôöùûüÿçćåáü"
            outab = "aaaeeeeiioouuuyccaau"

            title = self.title
            title = title.lower()
            trantab = title.maketrans(intab, outab)
            title = title.translate(trantab)
            title = title.replace('œ','oe')
            print(('title %s' %title))

            authors = []
            for author in self.authors:
                author = author.lower()
                trantab = author.maketrans(intab, outab)
                author = author.translate(trantab)
                author = author.replace('œ','oe')
                authors.append(author)
                print(('author %s' %author))
            print(('authors %s' %authors))

            if not query:
                query = self.create_query(title=title, authors=authors)
            # execption levée dans quelques cas http error 403 : Forbidden
            try:
                response = br.open_novisit(query, timeout=self.timeout)
            except:
                return None
            try:
                raw = response.read().strip()
                raw = raw.decode('iso-8859-1', errors='replace')
                #print('raw %s' %raw)
                root = fromstring(clean_ascii_chars(raw))
            except:
                return None
            try:
                self._parse_search_results(root, matches)
            except:
                print('erreur parse')
                return None
                raise
            print('avant notice titre + auteur')

        if len(matches) == 0:
            print('liste vide pour recherche titre + auteur => recherche à parir du titre')
            # recherche à partir du titre seul
            query = self.create_query(title=title)
            print(('query %s' %query))
            try:
                response = br.open_novisit(query, timeout=self.timeout)
            except:
                return None
            try:
                raw = response.read().strip()
                raw = raw.decode('iso-8859-1', errors='replace')
                root = fromstring(clean_ascii_chars(raw))
            except:
                return None
            try:
                print(('authors pour titre %s' %authors))
                first_author = authors[0]
                print ('first_author %s' %first_author)
                self._parse_search_results_titre(root, matches, first_author)
            except:
                print('erreur parse titre')
                return None
                raise

            print('avant notice titre seul')

        # si notices trouvées avec titre + auteur ou titre seul
        if len(matches) > 0:                                 # ok laisse ainsi maintenant... MAIS len doit etre 1 et suelement 1 simon on melange des livres
            save_vote = 0
            for notice in matches:
                print(('notice %s' %notice))
                response = br.open_novisit(notice, timeout=self.timeout)
                if DEBUG:
                    prints("DEBUG response.getcode() : ", response.getcode())
                    prints("DEBUG response.info()    : ", response.info())
                    prints("DEBUG response.geturl()  : ", response.geturl())

                raw = response.read().strip()
                raw = raw.decode('iso-8859-1', errors='replace')
                root = fromstring(clean_ascii_chars(raw))

                vote = root.xpath('//span[@itemprop="aggregateRating"]//span[@itemprop="ratingCount"]')
                #ne conserver que les votes les plus élevés
                if vote:
                    votes_notice = vote[0].text_content().strip()
                    print(('votes_notice %s' %votes_notice))
                    votes_float = float(votes_notice)
                    if votes_float > save_vote:
                        self.votes = votes_notice
                        save_vote = votes_float
                        print(('self.votes %s' %self.votes))
                        note = root.xpath('//span[@itemprop="aggregateRating"]/span[@itemprop="ratingValue"]')
                        if note:
                            self.notes = note[0].text_content().strip()
                        print(('self.notes %s' %self.notes))
                else:
                    print('votes non trouvés')


    def create_query(self, title=None, authors=None):
        '''
        create_query build and returns an URL with purpose of researching babelio
        with a book title and first author (author may be empty)
        '''

        BASE_URL = 'http://www.babelio.com/resrecherche.php?Recherche='
        BASE_URL_MID = '+'
        BASE_URL_LAST = '&page=1&item_recherche=livres&tri=auteur'

        q = ''
        au = ''

        if title:
            #title = get_udc().decode(title)
            title_tokens = list(self.get_title_tokens(title,
                                strip_joiners=False, strip_subtitle=True))
            if title_tokens:
                print(('title_tokens %s' %title_tokens))
                try:
                    tokens = [quote(t.encode('iso-8859-1') if isinstance(t, str) else t) for t in title_tokens]
                    q='+'.join(tokens)
                except:
                    return None

        if authors:
            #authors = [get_udc().decode(a) for a in authors]
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                print(('author_tokens %s' %author_tokens))
                try:
                    tokens = [quote(t.encode('iso-8859-1') if isinstance(t, str) else t) for t in author_tokens]
                    au='+'.join(tokens)
                except:
                    return None

        if not q:
            return None
        return '%s%s%s%s%s'%(BASE_URL,au,BASE_URL_MID,q,BASE_URL_LAST)

    def parse_search_results(orig_title, orig_authors, soup, br):
        '''
        this method returns "matches".
        note: if several matches, the first presented in babelio will be the first in the
        matches list; it will be submited as the first worker... (highest priority)
        !! CAUTION !! if the number of book discovered is greater than 12, only the 12 most
        significant will be returned
        '''
        prints('In parse_search_results(self, log, orig_title, orig_authors, soup, br)')

        if DEBUG:
            prints("DEBUG orig_title    : ", orig_title)
            prints("DEBUG orig_authors  : ", orig_authors)

        BASE_URL = 'https://www.babelio.com'

        unsrt_match, matches = [], []
        count=0
        while count < 5 :                                                       # loop over 6 first pages of search result (max 6 request @ 1.6 sec)
            try:
                x=soup.select_one('div.mes_livres').select_one('tbody').select('tr')
            except:
                break
            if len(x):                                                          # loop over all html addresses tied with titre_v2 (all book ref)
                for i in range(len(x)):                                         # !!CAUTION!! each page may have up to 10 books
                    y = x[i].select_one('td.titre_livre > a.titre_v2')
                    sous_url = y["href"].strip()
                    titre = y.text.strip()
                    ttl=ret_clean_text(log, self.dbg_lvl, titre)
                    orig_ttl=ret_clean_text(log, self.dbg_lvl, orig_title)
                    y = x[i].select_one('td.auteur > a.auteur_v2')
                    auteur=y.text.strip()
                    aut=ret_clean_text(log, self.dbg_lvl, auteur)
                    maxi=0
                    if orig_authors:
                        for i in range(len(orig_authors)):
                            orig_authors[i] = ret_clean_text(log, self.dbg_lvl, orig_authors[i])
                            maxi = max(maxi, (SM(None,aut,orig_authors[i]).ratio()))        # compute and find max ratio comparing auteur presented by babelio to each item of requested authors
                    else:
                        orig_authors=[]
                    unsrt_match.append((sous_url,(SM(None,ttl, orig_ttl).ratio()+maxi)))    # compute ratio comparing titre presented by babelio to requested title
                    # unsrt_match.append((sous_url,(SM(None,ttl, orig_ttl).ratio()+maxi),titre,orig_title,auteur,orig_authors))   # may be long
            if not soup.select_one('.icon-next'):                               #
                break                                                           # exit loop if no more next page
            count = count + 1                                                   #
            nxtpg = BASE_URL + soup.select_one('.icon-next')["href"]    # get next page adress
            if DEBUG:
                prints("DEBUG next page : ",nxtpg)                            #
            soup=ret_soup(log, self.dbg_lvl, br, nxtpg)[0]               # get new soup content and loop again, request MUST take at least 1 second
            time.sleep(0.5)                                                     # but wait a while so as not to hit www.babelio.com too hard

        srt_match = sorted(unsrt_match, key= lambda x: x[1], reverse=True)      # find best matches over the orig_title and orig_authors

        prints('nombre de références trouvées dans babelio', len(srt_match))
        # if DEBUG:                                                                          # hide_it # may be long
        #     for i in range(len(srt_match)): log.info('srt_match[i] : ', srt_match[i])      # hide_it # may be long

        srt_match = srt_match[:12]                                              # limit to 12 requests (max 12 requests @ #workers sec)
        for i in range(len(srt_match)):
            matches.append(BASE_URL + srt_match[i][0])

        if not matches:
            if DEBUG:
                prints("DEBUG matches at return time : ", matches)
            return None
        else:
            prints("nombre de matches : ", len(matches))
            if DEBUG:
                prints("DEBUG matches at return time : ")
                for i in range(len(matches)):
                    prints("      ", matches[i])

        return matches

    def _parse_search_results(self, root, matches):
        '''
        _parse_search_results scans the results of the search and
        add all books to the list named matches
        '''

        BASE_URL0 = 'http://www.babelio.com'
        print('parse')
        results = root.xpath('//*[@class="mes_livres"]/table/tbody/tr/td[1]')
        print(('results %s' %results))
        if not results:
            print('not results')
            return
        for result in results:
           print('in results')
           result_url=result.xpath('a/@href')
           print(('result_url %s' %result_url))
           matches.append( '%s%s'%(BASE_URL0,result_url[0]))
           print(('matches : %r' %matches))
        print('fin parse')

    def _parse_search_results_titre(self, root, matches, first_author):

        BASE_URL0 = 'http://www.babelio.com'
        print('parse titre')
        print ('first_author %s' %first_author)
        br = browser()

        ind_page = 1
        while ind_page < 4:
            if len(matches) > 0:
                break
            else:
                auteurs = root.xpath('//*[@class="mes_livres"]/table/tbody/tr/td[3]')
                print(('auteurs %s' %auteurs))
                if not auteurs:
                    print('not auteurs titre')
                    return

                intab = "àâäéèêëîïôöùûüÿçćåáü"
                outab = "aaaeeeeiioouuuyccaau"

                i = 0
                indice = -1
                for auteur in auteurs:
                   print('in auteurs')
                   nom_auteur=auteur.xpath('a/text()')
                   aut=nom_auteur[0].strip().lower()
                   trantab = aut.maketrans(intab, outab)
                   aut = aut.translate(trantab)
                   aut = aut.replace('œ','oe')
                   print(('nom_auteur %s' %aut))
                   if aut == first_author:
                     print('auteur trouvé')
                     indice=i
                     print('indice %s' %indice)
                     break
                   i=i+1

                results = root.xpath('//*[@class="mes_livres"]/table/tbody/tr/td[1]')
                i = 0
                for result in results:
                   print('in results titre')
                   result_url=result.xpath('a/@href')
                   print(('result_url titre %s' %result_url))
                   print('indice %s' %indice)
                   if i == indice:
                      matches.append( '%s%s'%(BASE_URL0,result_url[0]))
                      print(('matches titre : %r' %matches))
                      break
                   i=i+1

            ind_page = ind_page + 1
            print(('ind_page %s' %ind_page))
            if len(matches) == 0:
                #page_next = root.xpath('//*[@id="page_corps"]/div/div[4]/div[2]/a[8]/@href')
                page_next = root.xpath('//div[@class="pagination row"]/a[@class="fleche icon-next"]/@href')
                print(('page_next %s' %page_next))
                if page_next:
                    page = BASE_URL0 + page_next[0]
                    print(('page %s' %page))
                    response = br.open_novisit(page)
                    raw = response.read().strip()
                    raw = raw.decode('iso-8859-1', errors='replace')
                    root = fromstring(clean_ascii_chars(raw))
                else:
                    return

        print('fin parse titre seul')


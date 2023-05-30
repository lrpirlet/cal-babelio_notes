#!/usr/bin/env python3
#vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                       print_function)

__license__   = 'GPL v3'
__copyright__ = 'Louis Richard Pirlet based on Christophe work'
__docformat__ = 'restructuredtext en'

import time, re
from urllib.parse import quote

from lxml.html import fromstring, tostring
from calibre import browser

from calibre import as_unicode
from calibre.utils.icu import lower
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.localization import get_udc

from calibre import prints
from calibre.constants import DEBUG

class DownloadBabelioWorker(Source):

    def __init__(self, title, authors, bbl_id, timeout=20):
        self.timeout = timeout
        self.notes = None
        self.votes = None
        self.title = title
        self.authors = authors
        self.bbl_id = bbl_id            # l'idée c'est que si on a babelio_id alors on connais le lvre ET son url
        self.run()

    def run(self):

        matches = []
        br = browser()

        print("self.title   : {}".format(self.title))
        print("self.authors : {}".format(self.authors))
        print("self.bbl_id  : {}".format(self.bbl_id))

        if self.bbl_id and "/" in self.bbl_id and self.bbl_id.split("/")[-1].isnumeric():
            matches = ["https://www.babelio.com/livres/" + self.bbl_id]
            if DEBUG: prints("DEBUG: bbl_id matches : ", matches)

        if len(matches) == 0:          # on saute au dessus de tout le reste et on trouve les valeurs rating
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


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
from calibre import browser                     # broser is mechanize

from calibre import as_unicode
from calibre.utils.icu import lower
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.localization import get_udc

from calibre.ebooks.metadata.sources.search_engines import rate_limit
from calibre.gui2 import warning_dialog, error_dialog, question_dialog, info_dialog, show_restart_warning

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
        self.qaction.triggered.connect(self.update_babelio_notes)

    def update_babelio_notes(self):
        '''
        Set the metadata in the files in the selected book's record to
        match the current metadata in the database.
        '''
      # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        row_count = len(rows)
        if not rows or row_count == 0:
            return error_dialog(self.gui, 'Vous devez sélectionner un ou plusieurs livres', show=True)

      # Map the rows to book ids
        book_ids = self.gui.library_view.get_selected_ids()

        for book_id in book_ids:
            self.update_one_line(book_id, row_count)

        info_dialog(self.gui, 'Babelio Notes',
                'Recherche note et votes sur le site Babelio pour %d livre(s)'%len(book_ids),
                show=True)

    def update_one_line(self, book_id, row_count):
        '''
        update one line in the selection
        '''
        db = self.gui.current_db.new_api

      # Get the current metadata for this book from the db
        mi = db.get_metadata(book_id, get_cover=True, cover_as_data=True)
        votes = mi.get ("#nbvotbab")
        title = mi.title
        authors = mi.authors
        ids = mi.get_identifiers()
        if DEBUG:
            prints("\nDEBUG "+(4*"+- Babelio Notes +-"))
            prints("DEBUG: ids : {}".format(ids))

        cur_notes, cur_votes = self.get_rating(ids)

      # Babelio a été accédé avec succès si cur_votes ou si cur_notes est plus grand que 0
        if cur_votes:
            db.new_api.set_field('#trouvebab', {book_id: 'Y'})
        else:
            db.new_api.set_field('#trouvebab', {book_id: 'N'})
            if row_count == 1:
                error_dialog(self.gui, "Babelio Notes",
                         "<p> Si pas banni de Babelio :( ,</p>"
                         "<p> Babelio_id est très probablement absent ou invalide.</p>"
                         "<p> Veuillez le charger manuellement ou bien avec le plugin Babelio_db</p>", show=True)
            else:
                # log.info("Accès à babelio!")  TODO
                # flag that line
                pass
            if DEBUG:
                prints("DEBUG cur_votes = {} ...".format(cur_votes))
                prints("DEBUG Si pas banni de Babelio :( ,")
                prints("DEBUG Babelio_id est très probablement absent ou invalide.")
                prints("DEBUG Veuillez le charger manuellement ou bien avec le plugin Babelio_db")

      # ne mettre à jour que si le nombre de votes trouvés est supérieur à celui déjà présent
        if votes:
            if cur_votes > votes:
                db.new_api.set_field('#ratingbab', {book_id: cur_notes})
                db.new_api.set_field('#nbvotbab', {book_id: cur_votes})
            else:
                if DEBUG: prints('DEBUG: pas de nouveaux votes sur babelio ')
        else:
            db.new_api.set_field('#ratingbab', {book_id: cur_notes})
            db.new_api.set_field('#nbvotbab', {book_id: cur_votes})

        self.gui.iactions['Edit Metadata'].refresh_books_after_metadata_edit({book_id})

    def get_rating(self, ids):
        '''
        go to the book URL on babelio if babelio_db exist
        return notes as float and votes as int
        '''
        if DEBUG: prints("In get_rating")
        notes, votes = 0, 0
        br = browser()
        soup = None
        bbl_id = ids["babelio_id"] if "babelio_id" in ids else ""

        if DEBUG:
            prints("DEBUG ids    : {}".format(ids))
            prints("DEBUG bbl_id : {}".format(bbl_id))

        if bbl_id and "/" in bbl_id and bbl_id.split("/")[-1].isnumeric():
            bk_url = "https://www.babelio.com/livres/" + bbl_id
            if DEBUG:
                prints("DEBUG: url deduced from babelio_id : ", bk_url)
        else:
            return notes, votes

        soup = ret_soup(br, bk_url)[0]
        if not soup:
            return notes, votes
        if DEBUG:
            # prints("DEBUG soup prettyfied :\n", soup.prettify())      # only for deep debug, too big
            pass

        try:
            notes, votes = self.parse_rating(soup)
        except:
            return notes, votes

        return notes, votes

    def parse_rating(self, soup):
        '''
        find and isolate rating an count of rating in the soup
        returns rating as float and rating_cnt as int
        '''
        if DEBUG:
            prints("DEBUG in parse_rating(self, soup)")

      # if soup.select_one('span[itemprop="aggregateRating"]') fails, an exception will be raised
        rating_soup = soup.select_one('span[itemprop="aggregateRating"]').select_one('span[itemprop="ratingValue"]')
        bbl_rating = float(rating_soup.text.strip())
        rating_cnt_soup = soup.select_one('span[itemprop="aggregateRating"]').select_one('span[itemprop="ratingCount"]')
        bbl_rating_cnt = int(rating_cnt_soup.text.strip())

        return bbl_rating, bbl_rating_cnt

    def apply_settings(self):
        from calibre_plugins.babelio_notes.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        if DEBUG: prints("in apply_settings")
        if DEBUG: prints("prefs['ON_BABELIO'] : ", prefs["ON_BABELIO"])
        if DEBUG: prints("prefs['NOTE_MOYENNE'] : ", prefs['NOTE_MOYENNE'])
        if DEBUG: prints("prefs['NBR_VOTES'] : ", prefs['NBR_VOTES'])
        prefs
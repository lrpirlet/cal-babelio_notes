#!/usr/bin/env python3
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

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

from calibre_plugins.babelio_notes.config import prefs
from calibre_plugins.babelio_notes.utility import ret_soup, create_menu_action_unique

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

        # load the prefs so that they are available
        # this does NOT create the .json file
        # this does not create the column
        self.on_babelio_name = prefs["ON_BABELIO"]
        self.note_moyenne_name = prefs["NOTE_MOYENNE"]
        self.nbr_votes_name = prefs["NBR_VOTES"]

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        # Assign our menu to this action and an icon
        self.qaction.triggered.connect(self.update_babelio_notes)

    def test_for_column_names(self):
        '''
        this will verify the presence of the columns name when at least one line is selected
        return True if column names present
        '''
        if DEBUG:
            prints("in test_for_column")
            prints('prefs["ON_BABELIO"]   : {}'.format(self.on_babelio_name))
            prints('prefs["NOTE_MOYENNE"] : {}'.format(self.note_moyenne_name))
            prints('prefs["NBR_VOTES"]    : {}'.format(self.nbr_votes_name))

        custom_columns = self.gui.library_view.model().custom_columns
        all_custom_col = []
        for key, column in custom_columns.items(): all_custom_col.append(key)
        if DEBUG: prints("all_custom_col :", all_custom_col)
        if (self.on_babelio_name and self.note_moyenne_name and self.nbr_votes_name) not in all_custom_col:
            if DEBUG:
                prints("Okay, Houston...we've had a problem here (Apollo 13)")
            info_dialog(self.gui, 'Colonne inexistante',
                "<p> L'une ou l'autre colonne n'existe(nt) pas... Veuillez y remédier.</p>"
                "<p> On peut utiliser <strong>Babelio Notes</strong>, pour <strong>personnaliser l'extension</strong>.</p>",
                show=True)
            return False
        return True

    def update_babelio_notes(self):
        '''
        For each of the selected lines do get rating & rating count from babelio,
        then set the metadata.
        limit the number of lines to 50 or 1 minute work (each access to babelio is 1.2 sec)
        '''
      # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        row_count = len(rows)
        if not rows or row_count == 0:
            return error_dialog(self.gui, 'Vous devez sélectionner un ou plusieurs livres', show=True)
        if row_count > 50:
            return error_dialog(self.gui, 'Selectionner un max de 50 lines par itération', show=True)

      # Map the rows to book ids
        book_ids = self.gui.library_view.get_selected_ids()

      # some lines are selected, so check for presence of needed column
        if not self.test_for_column_names():
            return

        for book_id in book_ids:
            self.update_one_line(book_id, row_count)

        if DEBUG:
            for i in (ret_soup.get_memory()):
                prints("{} accès à {}".format(i[1], i[0]))

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
        votes = mi.get (self.nbr_votes_name)
        title = mi.title
        authors = mi.authors
        ids = mi.get_identifiers()
        if DEBUG:
            prints("\nDEBUG "+(4*"+- Babelio Notes +-"))
            prints("DEBUG: ids : {}".format(ids))

        cur_notes, cur_votes = self.get_rating(ids)

      # Babelio a été accédé avec succès si cur_votes ou si cur_notes est plus grand que 0
        if cur_votes:
            db.new_api.set_field(self.on_babelio_name, {book_id: 'Y'})
        else:
            db.new_api.set_field(self.on_babelio_name, {book_id: 'N'})
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
                db.new_api.set_field(self.note_moyenne_name, {book_id: cur_notes})
                db.new_api.set_field(self.nbr_votes_name, {book_id: cur_votes})
            else:
                if DEBUG: prints('DEBUG: pas de nouveaux votes sur babelio ')
        else:
            if cur_notes:
                db.new_api.set_field(self.note_moyenne_name, {book_id: cur_notes})
            if cur_votes:
                db.new_api.set_field(self.nbr_votes_name, {book_id: cur_votes})

        self.gui.iactions['Edit Metadata'].refresh_books_after_metadata_edit({book_id})

    def get_rating(self, ids):
        '''
        go to the book URL on babelio according to babelio_id in ids
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
        # if DEBUG:
        #     prints("DEBUG soup prettyfied :\n", soup.prettify())      # only for deep debug, too big

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
        '''
        this apply the settings fron the configuration
        '''
        from calibre_plugins.babelio_notes.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        if DEBUG: prints("in apply_settings")
        if DEBUG: prints("prefs['ON_BABELIO'] : ", prefs["ON_BABELIO"])
        if DEBUG: prints("prefs['NOTE_MOYENNE'] : ", prefs['NOTE_MOYENNE'])
        if DEBUG: prints("prefs['NBR_VOTES'] : ", prefs['NBR_VOTES'])
        prefs
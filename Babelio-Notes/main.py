#!/usr/bin/env python3
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = 'Louis Richard Pirlet based on Christophe work'
__docformat__ = 'restructuredtext en'

from calibre import prints, browser              # browser is mechanize
from calibre.constants import DEBUG
from calibre.gui2 import open_url, error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction # The class that all interface action plugins must inherit from
from calibre_plugins.babelio_notes.config import prefs
from calibre_plugins.babelio_notes.utility import ret_soup, create_menu_action_unique

from qt.core import (QMenu, QMessageBox, QToolButton, QUrl, QEventLoop, QTimer)

from bs4 import BeautifulSoup as BS              # to dismantle and manipulate HTTP (HyperText Markup Language)
import tempfile, os, contextlib

class InterfaceBabelioNotes(InterfaceAction):

    name = 'Babelio Notes'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    action_spec = ('Babelio Notes', None,
            'Recherche note moyenne et votes sur le site de Babelio', ())
    action_type = 'current'

  # remove help file that may have been updated anyway
    with contextlib.suppress(FileNotFoundError): os.remove(os.path.join(tempfile.gettempdir(), "babelio_notes_doc.html"))

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

      # get_icons and get_resources are partially defined function (zip location is defined)
      # those are known when genesis is called by calibre
        icon = get_icons('images/babelio.png')

      # load the prefs so that they are available this does NOT create the .json file nor create the columns haeder
        self.on_babelio_name = prefs["ON_BABELIO"]
        self.note_moyenne_name = prefs["NOTE_MOYENNE"]
        self.nbr_votes_name = prefs["NBR_VOTES"]

      # here we create a menu attached to this icon
        self.build_menus()
      # Assign our menu to this icon associated with an action
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.update_babelio_notes)

    def build_menus(self):
        self.menu = QMenu(self.gui)
        self.menu.clear()

        create_menu_action_unique(self, self.menu, _("Met à jour les Notes"), 'images/mises-a-jour.png',
                                  triggered=self.update_babelio_notes)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _("Personnalise l'extension")+'...', 'images/config.png',
                                  triggered=self.set_configuration)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _('Aide'), 'images/documentation.png',
                                  triggered=self.show_help)
        create_menu_action_unique(self, self.menu, _('A propos'), 'images/about.png',
                                  triggered=self.about)

        self.gui.keyboard.finalize()
      # Assign our menu to this action and an icon, also add dropdown menu
        self.qaction.setMenu(self.menu)

    def test_for_column_names(self):
        '''
        this will verify the presence of the columns name when at least one line is selected
        return True if column names present
        '''
        if DEBUG:
            prints("DEBUG Babelio_Notes in test_for_column")
            prints('DEBUG Babelio_Notes prefs["ON_BABELIO"]   : {}'.format(self.on_babelio_name))
            prints('DEBUG Babelio_Notes prefs["NOTE_MOYENNE"] : {}'.format(self.note_moyenne_name))
            prints('DEBUG Babelio_Notes prefs["NBR_VOTES"]    : {}'.format(self.nbr_votes_name))

        custom_columns = self.gui.library_view.model().custom_columns
        all_custom_col = []
        for key, column in custom_columns.items(): all_custom_col.append(key)
        if DEBUG: prints("DEBUG Babelio_Notes all_custom_col :", all_custom_col)
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
            return error_dialog(self.gui, "C'est trop peu",
                                'Vous devez sélectionner un ou plusieurs livres', show=True)
        if row_count > 50:
            return error_dialog(self.gui, "C'est beaucoup trop",
                                'Vous pouvez selectionner un max de 50 livres.', show=True)

      # initialize a list and a count of all those that could not be updated
      # make sure it is visible within the whole class
        self.set_N, self.count_N = set(), 0
      # then unmark the marked
        self.gui.current_db.set_marked_ids(self.set_N)

      # Map the rows to book ids
        book_ids = self.gui.library_view.get_selected_ids()

      # some lines are selected, so we can check for presence of needed column
        if not self.test_for_column_names():
            return
      # logtxt will contains all info about porcessed lines... init here after setup ok
        self.logtxt = ""

        for book_id in book_ids:
            self.update_one_line(book_id, row_count)

        self.logtxt += ("\n\n distribution dans le temps des accès à babelio.com")
        if DEBUG:
            prints("DEBUG Babelio_Notes")
        for i in (ret_soup.get_memory()):
            if DEBUG:
                prints("{} accès à {}".format(i[1], i[0]))
            self.logtxt += ("\n{} accès à {}".format(i[1], i[0]))

        if row_count > 1 and self.count_N > 1:
            info_dialog(self.gui, 'Babelio Notes',
                "\nRecherche des Notes et des Votes sur le site Babelio pour {} livres dont {} lignes sont marquées comme non mises à jour\n"
                "\nSi pas banni de Babelio :(, les Babelio_id marqués sont très probablement absents ou invalides."
                "\nVeuillez les charger ou manuellement ou avec le plugin Babelio_db".format(row_count, self.count_N),
                det_msg=self.logtxt, show=True)
        elif row_count > 1 and self.count_N == 1:
            info_dialog(self.gui, 'Babelio Notes',
                "\nRecherche des Notes et des Votes sur le site Babelio pour {} livres dont {} ligne est marquée comme non mise à jour\n"
                "\nSi pas banni de Babelio :(, le Babelio_id marqué est très probablement absent ou invalide."
                "\nVeuillez le charger ou manuellement ou avec le plugin Babelio_db".format(row_count, self.count_N),
                det_msg=self.logtxt, show=True)
        elif row_count == 1 and self.count_N == 1:
            info_dialog(self.gui, 'Babelio Notes',
                "\nRecherche des Notes et des Votes sur le site Babelio pour {} livre dont {} ligne est marquée comme non mise à jour\n"
                "\nSi pas banni de Babelio :(, le Babelio_id marqué est très probablement absent ou invalide."
                "\nVeuillez le charger ou manuellement ou avec le plugin Babelio_db".format(row_count, self.count_N),
                det_msg=self.logtxt, show=True)
        else:
            info_dialog(self.gui, 'Babelio Notes',
                "\nRecherche des Notes et des Votes sur le site Babelio pour {}"
                " livre dont {} ligne est marquée comme non mise à jour\n".format(row_count, self.count_N),
                det_msg=self.logtxt, show=True)

      # new_api does not know anything about marked books, so we use the full db object
        if len(self.set_N):
            self.gui.current_db.set_marked_ids(self.set_N)
      # do search for marked...                       # well, i'm not too sure what to do here... let's keep old behavior
            # self.gui.search.setEditText('marked:true')
            # self.gui.search.do_search()

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
            prints("\n*-*-*- DEBUG Babelio_Notes in update_one_line -*-*-*")
        self.logtxt += ("\n\nTitre : {}\nAuteur(s) {}: ".format(title,authors))

        cur_notes, cur_votes = self.get_rating(ids)

      # Babelio a été accédé avec succès si cur_votes ou si cur_notes est plus grand que 0
        if cur_votes is not None:
            db.new_api.set_field(self.on_babelio_name, {book_id: 'Y'})
        else:
            db.new_api.set_field(self.on_babelio_name, {book_id: 'N'})
            self.set_N.add(book_id)
            self.count_N += 1

            if DEBUG:
                prints("DEBUG Babelio_Notes cur_votes = {} ...".format(cur_votes))
                prints("DEBUG Babelio_Notes Si pas banni de Babelio :( ,")
                prints("DEBUG Babelio_Notes Babelio_id est très probablement absent ou invalide.")
                prints("DEBUG Babelio_Notes Veuillez le charger ou manuellement ou avec le plugin Babelio_db")

      # ne mettre à jour que si le nombre de votes trouvés est supérieur à celui déjà présent
        if votes:
            if cur_votes > votes:
                db.new_api.set_field(self.note_moyenne_name, {book_id: cur_notes})
                db.new_api.set_field(self.nbr_votes_name, {book_id: cur_votes})
                self.logtxt += (", le nombre de notes sur babelio était {}".format(votes))
            else:
                if DEBUG: prints('DEBUG Babelio_Notes pas de nouveaux votes sur babelio ')
                self.logtxt += (", pas de notes suppémentaire sur babelio")
        else:       # ne mettre à jour que si cur_notes is not None et > zéro (évite update a zero quand banni...)
            if cur_notes:
                db.new_api.set_field(self.note_moyenne_name, {book_id: cur_notes})
            if cur_votes:
                db.new_api.set_field(self.nbr_votes_name, {book_id: cur_votes})

        self.gui.iactions['Edit Metadata'].refresh_books_after_metadata_edit({book_id})

    def get_rating(self, ids):
        '''
        go to the book URL on babelio according to babelio_id in ids
        return notes as float and votes as int or None, None if not from babelio.com
        '''
        br = browser()
        soup = None
        bbl_id = ids["babelio_id"] if "babelio_id" in ids else ""

        if DEBUG:
            prints("DEBUG Babelio_Notes ids    : {}".format(ids))
            prints("DEBUG Babelio_Notes bbl_id : {}".format(bbl_id))

        if bbl_id and "/" in bbl_id and bbl_id.split("/")[-1].isnumeric():
            bk_url = "https://www.babelio.com/livres/" + bbl_id
            if DEBUG:
                prints("DEBUG Babelio_Notes url deduced from babelio_id : ", bk_url)
            self.logtxt += ("\nAccès à {}".format(bk_url))
        else:
            if not bbl_id:
                self.logtxt += ("\nPas de babelio_id... donc pas d'accès à babelio.com")
            else:
                self.logtxt += ("\nInvalide babelio_id... donc pas d'accès à babelio.com")
            return None, None

        soup = ret_soup(br, bk_url)[0]
        if not soup:
            self.logtxt("\nOups, babelio.com n'a pas répondu.. réseau? banissement??")
            return None, None
        # if DEBUG:
        #     prints("DEBUG Babelio_Notes soup prettyfied :\n", soup.prettify())      # only for deep debug, too big

      # try here and assume there was no notes and/or no votes to find... set it to 0
        try:
            notes, votes = self.parse_rating(soup)
        except:
            self.logtxt += ("\nbabelio.com semble ne pas avoir des votes et/ou des notes")
            return 0, 0

        return notes, votes

    def parse_rating(self, soup):
        '''
        find and isolate rating an count of rating in the soup
        returns rating as float and rating_cnt as int
        will fails if float() or int() is applied to empty string
        Will probably fails if babelio returns corrupted content
        '''

      # if soup.select_one('span[itemprop="aggregateRating"]') fails, an exception will be raised
        rating_soup = soup.select_one('span[itemprop="aggregateRating"]').select_one('span[itemprop="ratingValue"]')
        bbl_rating = float(rating_soup.text.strip())
        rating_cnt_soup = soup.select_one('span[itemprop="aggregateRating"]').select_one('span[itemprop="ratingCount"]')
        bbl_rating_cnt = int(rating_cnt_soup.text.strip())

        self.logtxt += ("\n moyenne des notes : {}, nombre de notes : {}".format(bbl_rating, bbl_rating_cnt))
        return bbl_rating, bbl_rating_cnt

    def set_configuration(self):
        '''
        will present the configuration widget... should handle custom columns needed for
        self.collection_name (#collection) and self.coll_srl_name (#coll_srl).
        '''
        self.interface_action_base_plugin.do_user_config(self.gui)

    def show_help(self):
        '''
        Extract on demand the help file resource to a temp file
        '''
        def get_help_file_resource():
            file_path = os.path.join(tempfile.gettempdir(), "babelio_notes_doc.html")
            file_data = self.load_resources('doc/' + "babelio_notes_doc.html")['doc/' + "babelio_notes_doc.html"]
            if DEBUG:
                prints('DEBUG Babelio_Notes show_help - file_path:', file_path)
            with open(file_path,'wb') as fhtm:
                fhtm.write(file_data)
            return file_path
        url = 'file:///' + get_help_file_resource()
        url = QUrl(url)
        open_url(url)

    def about(self):
        text = ("Le plugin noosfere_util""\n========================"
                "\n  La présence sur babelio, ou non, se nomme : {},"
                "\n  La moyenne des notes se nomme : {},"
                "\n  le nombre de notes se nomme : {}."
                "\n======================== \n".format(self.on_babelio_name, self.note_moyenne_name, self.nbr_votes_name)).encode('utf-8')
        text += get_resources("doc/about.txt")
        QMessageBox.about(self.gui, 'A propos de Babelio Notes', text.decode('utf-8'))

    def apply_settings(self):
        '''
        this apply the settings fron the configuration
        '''
        from calibre_plugins.babelio_notes.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        if DEBUG:
            prints("DEBUG Babelio_Notes in apply_settings")
            prints("DEBUG Babelio_Notes prefs['ON_BABELIO'] : ", prefs["ON_BABELIO"])
            prints("DEBUG Babelio_Notes prefs['NOTE_MOYENNE'] : ", prefs['NOTE_MOYENNE'])
            prints("DEBUG Babelio_Notes prefs['NBR_VOTES'] : ", prefs['NBR_VOTES'])
        prefs
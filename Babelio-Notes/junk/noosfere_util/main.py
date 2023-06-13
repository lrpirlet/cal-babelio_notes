#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2021, Louis Richard Pirlet'

from pickle import FALSE
from typing import Collection
from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import open_url, error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction, menu_action_unique_name
from calibre.utils.date import UNDEFINED_DATE
from calibre_plugins.noosfere_util.config import prefs

from qt.core import (QMenu, QMessageBox, QToolButton, QUrl, QEventLoop, QTimer)

# from PyQt5.QtWidgets import QToolButton, QMenu, QMessageBox
# from PyQt5.QtCore import QUrl

# from time import sleep        # for debug purpose
import tempfile, glob, os, contextlib

def create_menu_action_unique(ia, parent_menu, menu_text, image=None, tooltip=None,
                       shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                       unique_name=None, favourites_menu_unique_name=None):
    '''
    Create a menu action with the specified criteria and action, using the new
    InterfaceAction.create_menu_action() function which ensures that regardless of
    whether a shortcut is specified it will appear in Preferences->Keyboard
    '''

    # extracted from common_utils.py, found in many plugins ... header as follow:
    #
    # __license__   = 'GPL v3'
    # __copyright__ = '2011, Grant Drake <grant.drake@gmail.com>
    # __docformat__ = 'restructuredtext en'
    #
    # change to notice is the use of get_icons instead of get_icon in:
    #    ac.setIcon(get_icons(image))
    # ok, to be honest I could make this one work... I had lots of
    # difficulties with the many common_utils.py files that have the same name
    # but different content...
    # P.S. I like blue icons :-)...

    orig_shortcut = shortcut
    kb = ia.gui.keyboard
    if unique_name is None:
        unique_name = menu_text
    if not shortcut is False:
        full_unique_name = menu_action_unique_name(ia, unique_name)
        if full_unique_name in kb.shortcuts:
            shortcut = False
        else:
            if shortcut is not None and not shortcut is False:
                if len(shortcut) == 0:
                    shortcut = None
                else:
                    shortcut = _(shortcut)

    if shortcut_name is None:
        shortcut_name = menu_text.replace('&','')

    ac = ia.create_menu_action(parent_menu, unique_name, menu_text, icon=None, shortcut=shortcut,
        description=tooltip, triggered=triggered, shortcut_name=shortcut_name)
    if shortcut is False and not orig_shortcut is False:
        if ac.calibre_shortcut_unique_name in ia.gui.keyboard.shortcuts:
            kb.replace_action(ac.calibre_shortcut_unique_name, ac)
    if image:
        ac.setIcon(get_icons(image))
    if is_checked is not None:
        ac.setCheckable(True)
        if is_checked:
            ac.setChecked(True)
    return ac

class InterfacePlugin(InterfaceAction):

    name = 'noosfere util'

    action_spec = ("noosfere util", None,
            "lance les utilités pour noosfere DB", None)
    popup_type = QToolButton.InstantPopup
    action_add_menu = True
    action_type = 'current'
    current_instance = None

    do_shutdown = False                 # assume main calibre does NOT shutdown

  # remove previous log files for web_main process in the temp dir
    with contextlib.suppress(FileNotFoundError): os.remove(os.path.join(tempfile.gettempdir(), 'nsfr_utl-web_main.log'))
  # remove help file that may have been updated anyway
    with contextlib.suppress(FileNotFoundError): os.remove(os.path.join(tempfile.gettempdir(), "nfsr_utl_doc.html"))
  # remove all trace of an old synchronization file between calibre and the outside process running QWebEngineView
    for i in glob.glob( os.path.join(tempfile.gettempdir(),"nsfr_utl_sync-cal-qweb*")):
            with contextlib.suppress(FileNotFoundError): os.remove(i)
  # remove all trace of a main calibre shutdown file to warn the outside process running QWebEngineView
    for i in glob.glob( os.path.join(tempfile.gettempdir(),"nsfr_utl_terminate-cal-qweb*")):
            with contextlib.suppress(FileNotFoundError): os.remove(i)

    def genesis(self):
      # get_icons and get_resources are partially defined function (zip location is defined)
      # those are known when genesis is called by calibre
        icon = get_icons('blue_icon/top_icon.png')
      # qaction is created and made available by calibre for noosfere_util
        self.qaction.setIcon(icon)
      # load the prefs so that they are available
        self.collection_name = prefs["COLLECTION_NAME"]
        self.coll_srl_name = prefs["COLL_SRL_NAME"]
      # here we create a menu in calibre
        self.build_menus()
      # here we process shutdown_started signal
        self.gui.shutdown_started.connect(self.handle_shutdown)


    def build_menus(self):
        self.menu = QMenu(self.gui)
        self.menu.clear()
        create_menu_action_unique(self, self.menu, _('Efface les métadonnées en surplus'), 'blue_icon/wipe_it.png',
                                  triggered=self.wipe_selected_metadata)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _('Navigateur Web pour le choix du volume'), 'blue_icon/choice.png',
                                  triggered=self.run_web_main)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _("Distribue l'information éditeur"), 'blue_icon/eclate.png',
                                  triggered=self.unscramble_publisher)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _("Personnalise l'extension")+'...', 'blue_icon/config.png',
                                  triggered=self.set_configuration)
        self.menu.addSeparator()

        create_menu_action_unique(self, self.menu, _('Help'), 'blue_icon/documentation.png',
                                  triggered=self.show_help)
        create_menu_action_unique(self, self.menu, _('About'), 'blue_icon/about.png',
                                  triggered=self.about)

      # The following is hidden cause it only allows a developper to navigate the metadata db
      # there is really no other uses for 'testtesttest'
        # self.menu.addSeparator()
        # create_menu_action_unique(self, self.menu, _('testtesttest'), 'blue_icon/top_icon.png',
        #                           triggered=self.testtesttest)

        self.gui.keyboard.finalize()

      # Assign our menu to this action and an icon, also add dropdown menu
        self.qaction.setMenu(self.menu)

    def handle_shutdown(self):
        '''
        It is possible to kill (main) calibre while the (noosfere_util) web_browser detached process
        is still running. If a book is selected, then probability to hang (main) calibre is very high,
        preventing restarting calibre. A process named "The main calibre program" is still running...
        The workaroundis to kill this process or to reboot...

        To avoid this situation, A signal named "shutdown_started" was implemented so that something
        like 2 seconds are available to the (noosfere_util) web_browser detached process cleanly.

        The handle_shutdown(), triggered by the signal, do create a temp file that tells
        the web_browser detached process, to terminate, simulating the user aborting...
        At the same time, the handle_shutdown() will simulate the answer from the web_browser detached
        process to speed-up the reaction...

        Some temporary files will be left behind that will be killed at next invocation of noosfere_util.
        '''
        if DEBUG : prints("in handle_shutdown()")
        self.do_shutdown = True
        if DEBUG : prints("self.do_shutdown = True")
        terminate_tpf=tempfile.NamedTemporaryFile(prefix="nsfr_utl_terminate-cal-qweb", delete=False)
        terminate_tpf.close
        if DEBUG : prints("tmp file nsfr_utl_terminate-cal-qweb created")

    def run_web_main(self):
        '''
        For the selected books:
        wipe metadata, launch a web-browser to select the desired volumes,
        set the nsfr_id, remove the ISBN (?fire a metadata download?)
        '''
        if DEBUG: prints("in run_web_main")

      # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Pas de métadonnées affectées',
                             'Aucun livre sélectionné', show=True)

      # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        if DEBUG : prints("ids : ", ids)

      # do the job for one book
      # nsfr_id_recu is true if metadata was updated, false if web_returned no nsfr_id
        nbr_ok = 0
        set_ok = set()
        for book_id in ids:
          # if main calibre does shutdown, stop processing any more book_id
            if not self.do_shutdown:
                answer = self.run_one_web_main(book_id)
                nsfr_id_recu, more = answer[0], answer[1]
            else:
                more = False        # if NOT more, nsfr_id_recu is False
            if not more:
                break
          # mark books that have NOT been bypassed... so we can fetch metadata on selected
            if nsfr_id_recu:
                nbr_ok += 1
                set_ok.add(book_id)
                prints("set_ok", set_ok)

      # tell user about what has been done...sorry, NOT if main calibre is closed...
        if not self.do_shutdown:
            if DEBUG: prints('nfsr_id is recorded, metadata is prepared for {} book(s) out of {}'.format(nbr_ok, len(ids)))
            info_dialog(self.gui, 'nsfr_id: enregistré',
                'Les métadonnées ont été préparées pour {} livre(s) sur {}'.format(nbr_ok, len(ids)),
                show=True)
          # new_api does not know anything about marked books, so we use the full db object
            if len(set_ok):
                self.gui.current_db.set_marked_ids(set_ok)
                self.gui.search.setEditText('marked:true')
                self.gui.search.do_search()

    def run_one_web_main(self, book_id):
        '''
        For the books_id:
        wipe metadata, launch a web-browser to select the desired volumes,
        set the nsfr_id, remove the ISBN (?fire a metadata download?)
        '''
        if DEBUG: prints("in run_one_web_main")

      # check for presence of needed column
        if not self.test_for_column():
            return

      # make current the book processed so that main calibre displays "Book details"
        self.gui.library_view.select_rows([book_id])

        db = self.gui.current_db.new_api
        mi = db.get_metadata(book_id, get_cover=False, cover_as_data=False)
        isbn, auteurs, titre="","",""

        if DEBUG: prints("book_id          : ", book_id)
        if DEBUG and mi.title: prints("title       *    : ", mi.title)
        if DEBUG and mi.authors: prints("authors     *    : ", mi.authors)
        if DEBUG and "isbn" in mi.get_identifiers(): prints("isbn             : ", mi.get_identifiers()["isbn"])

      # set url, isbn, auteurs and titre
        url = "https://www.noosfere.org/livres/noosearch.asp"     # jump directly to noosfere advanced search page
        if "isbn" in mi.get_identifiers(): isbn = mi.get_identifiers()["isbn"]
        auteurs = " & ".join(mi.authors)
        titre = mi.title
        data = [url, isbn, auteurs, titre]
        if DEBUG:
            prints(" url is a string : ", isinstance(url, str))
            prints(" isbn is a string : ", isinstance(isbn, str))
            prints(" auteurs is a string : ", isinstance(auteurs, str))
            prints(" titre is a string : ", isinstance(titre, str))

      # unless shutdown_started signal asserted
        if not self.do_shutdown:
          # Launch a separate process to view the URL in WebEngine
            self.gui.job_manager.launch_gui_app('webengine-dialog', kwargs={'module':'calibre_plugins.noosfere_util.web_main', 'data':data})
            if DEBUG: prints("webengine-dialog process submitted")          # WARNING: "webengine-dialog" is a defined function in calibre\src\calibre\utils\ipc\worker.py ...DO NOT CHANGE...
      # wait for web_main.py to settle and create a temp file to synchronize QWebEngineView with calibre...
      # watch out, self.do_shutdown is set by a signal, any time...
        while not (self.do_shutdown or glob.glob(os.path.join(tempfile.gettempdir(),"nsfr_utl_sync-cal-qweb*"))):
            loop = QEventLoop()
            QTimer.singleShot(200, loop.quit)
            loop.exec_()
      # wait till file is removed but loop fast enough for a user to feel the operation instantaneous...
      # watch out, self.do_shutdown is set by a signal, any time...
        while (not self.do_shutdown) and (glob.glob(os.path.join(tempfile.gettempdir(),"nsfr_utl_sync-cal-qweb*"))):
            loop = QEventLoop()
            QTimer.singleShot(200, loop.quit)
            loop.exec_()
      # unless shutdown_started signal asserted
        if not self.do_shutdown:
          # sync file is gone, meaning QWebEngineView process is closed so, we can collect the result, bypass if shutdown_started
            with open(os.path.join(tempfile.gettempdir(),"nsfr_utl_report_returned_id"), "r", encoding="utf_8") as tpf:
                returned_id = tpf.read()
            if DEBUG: prints("returned_id", returned_id)

        if self.do_shutdown:
            return(False,False)                             # shutdown_started, do not try to change db
        elif returned_id.replace("vl$","").replace("-","").isnumeric():
            nsfr_id = returned_id
          # set the nsfr_id, reset most metadata...
            for key in mi.custom_field_keys():
                display_name, val, oldval, fm = mi.format_field_extended(key)
                if self.coll_srl_name == key : cstm_coll_srl_fm=fm
                if self.collection_name == key : cstm_collection_fm=fm
            mi.publisher=""
            mi.series=""
            mi.language=""
            mi.pubdate=UNDEFINED_DATE
            mi.set_identifier('nsfr_id', nsfr_id)
            mi.set_identifier('isbn', "")
            if cstm_coll_srl_fm:
                cstm_coll_srl_fm["#value#"] = ""
                mi.set_user_metadata(self.coll_srl_name, cstm_coll_srl_fm)
            if cstm_collection_fm:
                cstm_collection_fm["#value#"] = ""
                mi.set_user_metadata(self.collection_name, cstm_collection_fm)
          # commit the change, force reset of the above fields, leave the others alone
            db.set_metadata(book_id, mi, force_changes=True)
            return (True, True)                                 # nsfr_id received, more book
        elif "unset" in returned_id:
            if DEBUG: prints('unset, no change will take place...')
            return (False, True)                                # nsfr_id NOT received, more book
        elif "aborted" in returned_id:
            if DEBUG: prints('aborted, no change will take place...')
            return (False, True)                                # nsfr_id NOT received, more book
        elif "killed" in returned_id:
            if DEBUG: prints('killed, no change will take place...')
            return (False, False)                               # nsfr_id NOT received, NO more book
        else:
            if DEBUG: prints("should not ends here... returned_id : ", returned_id)
            return (False, False)                               # STOP everything program error

    def wipe_selected_metadata(self):
        '''
        For all selected book
        Deletes publisher, tags, series, rating, self.coll_srl_name (#coll_srl),
        self.collection_name (#collection), and any ID except ISBN. All other fields are supposed
        to be overwritten when new metadata is downloaded from noosfere.
        Later, ISBN will be wiped just before nsfr_id (and maybe ISBN) is written.
        '''
        if DEBUG: prints("in wipe_selected_metadata")

      # check for presence of needed column
        if not self.test_for_column():
            return

        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Pas de métadonnées affectées',
                             'Aucun livre sélectionné', show=True)

        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        if DEBUG : prints("ids : ", ids)
        db = self.gui.current_db.new_api

        for book_id in ids:
            # Get the current metadata for this book from the db (not any info about cover)
            mi = db.get_metadata(book_id, get_cover=False, cover_as_data=False)
            # find custom field of interest
            for key in mi.custom_field_keys():
                display_name, val, oldval, fm = mi.format_field_extended(key)
                if self.coll_srl_name == key :
                    cstm_coll_srl_fm=fm
                if self.collection_name == key :
                    cstm_collection_fm=fm

            # reset the metadata fields that need to be: publisher, self.collection_name (#collection),
            # self.coll_srl_name (#coll_srl), series, language, pubdate, identifier
            # leaving those we want to keep (isbn, authors, title) and those we know will be replaced or
            # augmented (comments, rating, tag, whatever custom columns...)
            mi.publisher=""
            mi.series=""
            mi.language=""
            mi.pubdate=UNDEFINED_DATE
            mi.set_identifier('nsfr_id', "")
            if cstm_coll_srl_fm:
                cstm_coll_srl_fm["#value#"] = ""
                mi.set_user_metadata(self.coll_srl_name, cstm_coll_srl_fm)
            if cstm_collection_fm:
                cstm_collection_fm["#value#"] = ""
                mi.set_user_metadata(self.collection_name, cstm_collection_fm)
            # commit changes
            db.set_metadata(book_id, mi, force_changes=True)

        if DEBUG: prints('Updated the metadata in the files of {} book(s)'.format(len(ids)))

        info_dialog(self.gui, 'Métadonnées changées',
                'Les métadonnées ont été effacées pour {} livre(s)'.format(len(ids)),
                show=True)

      # select all and only those that have been cleaned... for a possible futher action
      # such as metadata download from calibre or choice of the volume from noosfere_util
        self.gui.current_db.set_marked_ids(ids)
        self.gui.search.setEditText('marked:true')
        self.gui.search.do_search()


    def unscramble_publisher(self):
        if DEBUG: prints("in unscramble_publisher")
      # check for presence of needed column
        if not self.test_for_column():
            return
      # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Pas de métadonnées affectées',
                             'Aucun livre sélectionné', show=True)

        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        if DEBUG: prints("ids : ", ids)
        db = self.gui.current_db.new_api
        for book_id in ids:
          # Get the current metadata of interest for this book from the db
            mi = db.get_metadata(book_id, get_cover=False, cover_as_data=False)
            scrbl_dt = mi.publisher
            if scrbl_dt:
                val_collection, val_coll_srl = None, None
                if "€" in scrbl_dt: scrbl_dt, val_coll_srl = scrbl_dt.split("€")
                if "§" in scrbl_dt: scrbl_dt, val_collection = scrbl_dt.split("§")
                if DEBUG:
                    prints("val_collection : ", val_collection) if val_collection else prints("val_collection not in publisher")
                    prints("val_coll_srl   : ", val_coll_srl) if val_coll_srl else prints("val_coll_srl not in publisher")
                    prints("éditeur (scrbl_dt)   : ", scrbl_dt)
              # Set the current metadata of interest for this book in the db
                if val_collection: db.set_field(self.collection_name, {book_id: val_collection})
                if val_coll_srl: db.set_field(self.coll_srl_name, {book_id: val_coll_srl})
                db.set_field("publisher", {book_id: scrbl_dt})
                self.gui.iactions['Edit Metadata'].refresh_gui([book_id])

        info_dialog(self.gui, 'Information distribuée',
                "L'information a été distribuée pour {} livre(s)".format(len(ids)),
                show=True)

    def test_for_column(self):
        if DEBUG:
            prints("in test_for_column")
            prints("recorded self.collection_name", self.collection_name)
            prints("recorded self.coll_srl_name", self.coll_srl_name)

        custom_columns = self.gui.library_view.model().custom_columns
        all_custom_col = []
        for key, column in custom_columns.items(): all_custom_col.append(key)
        if DEBUG: prints("all_custom_col :", all_custom_col)
        if (self.collection_name and self.coll_srl_name) not in all_custom_col:
            if DEBUG: prints("Okay, Houston...we've had a problem here (Apollo 13)")
            info_dialog(self.gui, 'Colonne inexistante',
                "<p> L'une ou l'autre colonne ou même les deux n'existe(nt) pas... Veuillez y remédier.</p>"
                "<p> On peut utiliser <strong>noosfere_util</strong>, pour <strong>personnaliser l'extension</strong>.</p>",
                show=True)
            return False
        return True

    def testtesttest(self): # so I can play with the metadata db...
        if DEBUG: prints("in testtesttest")

      # check for presence of needed column
        if not self.test_for_column():
            return

        if DEBUG: prints("in testtesttest; self.collection_name", self.collection_name)
        if DEBUG: prints("in testtesttest; self.coll_srl_name", self.coll_srl_name)

        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        # if DEBUG: prints("rows type : ", type(rows), "rows", rows) rows are selected rows in calibre
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Pas de métadonnées affectées',
                             'Aucun livre sélectionné', show=True)

        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        if DEBUG: prints("ids : ", ids)
        db = self.gui.current_db.new_api

        for book_id in ids:
            # Get the current metadata for this book from the db
            mi = db.get_metadata(book_id, get_cover=True, cover_as_data=True)
            fmts = db.formats(book_id)
            if DEBUG: prints("fmts = db.formats(book_id)", fmts)
            if DEBUG: prints(20*"*.")
            if DEBUG: prints("book_id             : ", book_id)
            if DEBUG: prints("mi.title       *    : ", mi.title)
            if DEBUG: prints("mi.authors     *    : ", mi.authors)
            if DEBUG: prints("mi.publisher   --   : ", mi.publisher)
            if DEBUG: prints("mi.pubdate          : ", mi.pubdate)
            if DEBUG: prints("mi.uuid             : ", mi.uuid)
            if DEBUG: prints("mi.languages        : ", mi.languages)
            if DEBUG: prints("mi.tags        --   : ", mi.tags)
            if DEBUG: prints("mi.series      --   : ", mi.series)
            if DEBUG: prints("mi.rating      --   : ", mi.rating)
            if DEBUG: prints("mi.application_id   : ", mi.application_id)
            if DEBUG: prints("mi.id               : ", mi.id)
            if DEBUG: prints("mi.user_categories  : ", mi.user_categories)
            if DEBUG: prints("mi.identifiers      : ", mi.identifiers)

            for key in mi.custom_field_keys():
                if DEBUG: prints("custom_field_keys   : ", key)
                display_name, val, oldval, fm = mi.format_field_extended(key)
                if self.coll_srl_name == key :
                    cstm_coll_srl_fm=fm
                    if DEBUG: prints("self.coll_srl_name = {}\n cstm_coll_srl_fm = {}".format(key,fm))
                if self.collection_name == key :
                    cstm_collection_fm=fm
                    if DEBUG: prints("self.collection_name = {}\n cstm_collection_fm = {}".format(key,fm))
            if DEBUG: prints(20*"#²")

            for key in mi.custom_field_keys():
                # if DEBUG: prints("custom_field_keys   : ", key)
                display_name, val, oldval, fm = mi.format_field_extended(key)
                # if DEBUG: prints("display_name={}, val={}, oldval={}, ff={}".format(display_name, val, oldval, fm))
                if fm and fm['datatype'] != 'composite':
                    if DEBUG: prints("custom_field_keys not composite : ", key)
                    if DEBUG: prints("display_name={}\n val={}\n oldval={}\n ff={}".format(display_name, val, oldval, fm))
                    for sub_key in fm:
                        if DEBUG: prints("fm keys : ", sub_key, end="      | " )
                        if DEBUG: prints("fm[{}] : ".format(sub_key), fm[sub_key])
                    if DEBUG: prints(20*"..")


            if DEBUG: prints(20*"+-")
            if DEBUG: prints("value for self.coll_srl_name    : ", db.field_for(self.coll_srl_name, book_id))
            if DEBUG: prints("valueself.collection_name  : ", db.field_for(self.collection_name, book_id))

            mi.publisher=""
            mi.series=""
            mi.language=""
            mi.set_identifier('nsfr_id', "")

            if cstm_coll_srl_fm:
                cstm_coll_srl_fm["#value#"] = ""
                mi.set_user_metadata(self.coll_srl_name, cstm_coll_srl_fm)
            if cstm_collection_fm:
                cstm_collection_fm["#value#"] = ""
                mi.set_user_metadata(self.collection_name, cstm_collection_fm)

            # db.set_metadata(book_id, mi, force_changes=True) # BUT I will NOT change anything...


        info_dialog(self.gui, 'exposed data',
                'Exposed the metadata of {} book(s)'.format(len(ids)),
                show=True)

    def set_configuration(self):
        '''
        will present the configuration widget... should handle custom columns needed for
        self.collection_name (#collection) and self.coll_srl_name (#coll_srl).
        '''
        if DEBUG: prints("in set_configuration")

        self.interface_action_base_plugin.do_user_config(self.gui)

    def show_help(self):
         # Extract on demand the help file resource to a temp file
        def get_help_file_resource():
          # keep "nfsr_utl_doc.html" as the last item in the list, this is the help entry point
          # we need both files for the help
            file_path = os.path.join(tempfile.gettempdir(), "noosfere_util_web_075.png")
            file_data = self.load_resources('doc/' + "noosfere_util_web_075.png")['doc/' + "noosfere_util_web_075.png"]
            if DEBUG: prints('show_help picture - file_path:', file_path)
            with open(file_path,'wb') as fpng:
                fpng.write(file_data)

            file_path = os.path.join(tempfile.gettempdir(), "nfsr_utl_doc.html")
            file_data = self.load_resources('doc/' + "nfsr_utl_doc.html")['doc/' + "nfsr_utl_doc.html"]
            if DEBUG: prints('show_help - file_path:', file_path)
            with open(file_path,'wb') as fhtm:
                fhtm.write(file_data)
            return file_path
        url = 'file:///' + get_help_file_resource()
        url = QUrl(url)
        open_url(url)

    def about(self):
        text = get_resources("doc/about.txt")
        text += ("\nLe nom de la collection par l'éditeur est : {},"
                "\nLe numéro d'ordre dans la collection par l'éditeur "
                "est : {}".format(self.collection_name,self.coll_srl_name)).encode('utf-8')
        QMessageBox.about(self.gui, 'About the noosfere_util',
                text.decode('utf-8'))

    def apply_settings(self):
        from calibre_plugins.noosfere_util.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        if DEBUG: prints("in apply_settings")
        if DEBUG: prints("prefs['COLLECTION_NAME'] : ", prefs['COLLECTION_NAME'])
        if DEBUG: prints("prefs['COLL_SRL_NAME'] : ", prefs['COLL_SRL_NAME'])
        prefs

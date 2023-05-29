#!/usr/bin/env python3
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = 'Louis Richard Pirlet based on Christophe work'
__docformat__ = 'restructuredtext en'

from calibre import prints
from calibre.constants import DEBUG
# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
#from calibre_plugins.traducteur_test.main import TraducteurDialog
from calibre.ebooks.metadata.book.base import Metadata
#from PyQt5.Qt import QDialog, QVBoxLayout, QPushButton, QMessageBox, QLabel
from calibre_plugins.babelio_notes.worker import DownloadBabelioWorker


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
                prints("DEBUG: ids : {}".format(ids))
                prints(ids.get("babelio_id", ""))

            if "babelio_id" in ids:
                bbl_id = ids["babelio_id"]
            else:
                bbl_id = ""
            babelio_worker = DownloadBabelioWorker(title,authors,bbl_id)
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
#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2021, Louis Richard Pirlet'

from qt.core import (QWidget, QLabel, QComboBox, QHBoxLayout, QVBoxLayout, QFont, Qt)
# from PyQt5.QtWidgets import (QWidget, QLabel, QComboBox, QHBoxLayout, QVBoxLayout)
# from PyQt5.QtGui import QFont
# from PyQt5.QtCore import Qt

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog, info_dialog, question_dialog, show_restart_warning
from calibre.gui2.ui import get_gui
from calibre.gui2.preferences.create_custom_column import CreateNewCustomColumn
from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/babelio_notes')

# Set defaults
prefs.defaults["ON_BABELIO"] = "#trouvebab"
prefs.defaults["NOTE_MOYENNE"] = "#ratingbab"
prefs.defaults["NBR_VOTES"] = "#nbvotbab"

class ConfigWidget(QWidget):

    def __init__(self, plugin_action):
        QWidget.__init__(self)
        self.plugin_action = plugin_action

        self.on_babelio = prefs.defaults["ON_BABELIO"]
        self.note_moyenne = prefs.defaults["NOTE_MOYENNE"]
        self.nbr_votes = prefs.defaults["NBR_VOTES"]

        self.current_on_babelio = prefs["ON_BABELIO"]
        self.current_note_moyenne = prefs["NOTE_MOYENNE"]
        self.current_nbr_votes = prefs["NBR_VOTES"]

        if DEBUG:
            prints("In ConfigWidget")
            prints("self.current_on_babelio : ", self.current_on_babelio)
            prints("self.current_note_moyenne : ", self.current_note_moyenne)
            prints("self.current_nbr_votes : ", self.current_nbr_votes)

  # define here a creator = CreateNewCustomColumn(gui) so that it remain common during the whole configuration
  # The parameter 'gui' passed when creating a class instance is the main calibre gui (calibre.gui2.ui.get_gui())

        self.gui = get_gui()
        self.creator = CreateNewCustomColumn(self.gui)

  # create the combo box
        self.create_combo_box_list("enumeration")
        self.create_combo_box_list("float")
        self.create_combo_box_list("int")
        self.setGeometry(100, 100, 300, 200)
        self.pick_columns_name()
        self.show()

    def create_combo_box_list(self, column_type):
        """
        creates a list for the comboboxes to use, list is ordered
        column_type is "enumeration" for pertinent_on_babelio_list
        column_type is "float" for pertinent_note_moyenne_list
        column_type is "int" for pertinent_nbr_votes_list
        """
        if DEBUG: prints("\nIn create_combo_box_list(self, column_type); column_type : ", column_type)
        if column_type == "enumeration" :
            self.pertinent_on_babelio_list = self.get_custom_columns("enumeration")
            self.pertinent_on_babelio_list.extend(["", "Ajouter et sélectionner une colonne"])
            if DEBUG: prints("self.pertinent_on_babelio_list: ", self.pertinent_on_babelio_list)
        elif column_type == "float":
            self.pertinent_note_moyenne_list = self.get_custom_columns("float")
            self.pertinent_note_moyenne_list.extend(["", "Ajouter et sélectionner une colonne"])
            if DEBUG: prints("self.pertinent_note_moyenne_list: ", self.pertinent_note_moyenne_list)
        elif column_type == "int":
            self.pertinent_nbr_votes_list = self.get_custom_columns("int")
            self.pertinent_nbr_votes_list.extend(["", "Ajouter et sélectionner une colonne"])
            if DEBUG: prints("self.pertinent_nbr_votes_list: ", self.pertinent_nbr_votes_list)

    def get_custom_columns(self, column_type):
        """
        return a list of column suitable for column_type
          (either "comment": column not shown in the Tag browser,
          or "text": column shown in the Tag browser)
        """
        if DEBUG: prints("\nIn get_custom_columns(self, column_type : {})".format(column_type))
        custom_columns = self.creator.current_columns()
        possible_columns = []
        for key, column in custom_columns.items():
            typ = column['datatype']
            if typ in column_type and not column['is_multiple']:
                possible_columns.append(key)
        if DEBUG: prints("In get_custom_columns; possible_columns :", possible_columns)
        return sorted(possible_columns)

    def pick_columns_name(self):
        """
        Create the widgets so users can select or create a column from the combo boxes
        """
        if DEBUG: prints("\nIn pick_columns_name")

        info_label = QLabel("Sélectionne les colonnes pour distribuer l'information Babelio Notes")
        info_label.setFont(QFont('Arial', 12))
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setToolTip("En sélectionnant la création de colonne on redémarre calibre. Ensuite, après le redémarrage, on pourra sélectionner une colonne valide.")

        label_on_babelio = QLabel("Présence, ou non, de babelio_id associé à l'ouvrage")
        label_on_babelio.setToolTip('La colonne présentée est celle actuellement sélectionnée. Si vide ou impropre, choisir "Ajouter et sélectionner une colonne"')
        self.name_on_babelio = QComboBox(self)
        self.name_on_babelio.addItems(self.pertinent_on_babelio_list)
        self.name_on_babelio.setCurrentIndex(self.name_on_babelio.findText(self.current_on_babelio,Qt.MatchFixedString))
        self.name_on_babelio.textActivated.connect(self.select_for_on_babelio)

        label_note_moyenne = QLabel("Moyenne des notes attribuées à l'ouvrage")
        label_note_moyenne.setToolTip('La colonne présentée est celle actuellement sélectionnée.Si vide ou impropre, choisir "Ajouter et sélectionner une colonne"')
        self.name_note_moyenne = QComboBox(self)
        self.name_note_moyenne.addItems(self.pertinent_note_moyenne_list)
        self.name_note_moyenne.setCurrentIndex(self.name_note_moyenne.findText(self.current_note_moyenne,Qt.MatchFixedString))
        self.name_note_moyenne.textActivated.connect(self.select_for_note_moyenne)

        label_nbr_votes = QLabel("Nombre de notes attribuées à l'ouvrage")
        label_nbr_votes.setToolTip('La colonne présentée est celle actuellement sélectionnée. Si vide ou impropre, choisir "Ajouter et sélectionner une colonne"')
        self.name_nbr_votes = QComboBox(self)
        self.name_nbr_votes.addItems(self.pertinent_nbr_votes_list)
        self.name_nbr_votes.setCurrentIndex(self.name_nbr_votes.findText(self.current_nbr_votes,Qt.MatchFixedString))
        self.name_nbr_votes.textActivated.connect(self.select_for_nbr_votes)
      # First line
        h_box1 = QHBoxLayout()
        h_box1.addWidget(label_on_babelio)
        h_box1.addWidget(self.name_on_babelio)
      # Second line
        h_box2 = QHBoxLayout()
        h_box2.addWidget(label_note_moyenne)
        h_box2.addWidget(self.name_note_moyenne)
      # third line
        h_box3 = QHBoxLayout()
        h_box3.addWidget(label_nbr_votes)
        h_box3.addWidget(self.name_nbr_votes)
      # Add widgets and layouts to QVBoxLayout
        v_box = QVBoxLayout()
        v_box.addWidget(info_label)
        v_box.addLayout(h_box1)
        v_box.addLayout(h_box2)
        v_box.addLayout(h_box3)
      # v_box.addWidget(self.display_total_label)
        self.setLayout(v_box)

    def select_for_on_babelio(self, name):
        if DEBUG: prints("\nIn select_for_on_babelio(self, name : {}".format(name))
        if name == "Ajouter et sélectionner une colonne":
            self.create_custom_column(lookup_name = "#trouvebab")
        else:
            self.on_babelio = name
            self.name_on_babelio.setCurrentIndex(self.name_on_babelio.findText(name,Qt.MatchFixedString))
        if DEBUG: prints("self.on_babelio : ", self.on_babelio)

    def select_for_note_moyenne(self, name):
        if DEBUG: prints("\nIn select_for_note_moyenne(self, name : {}".format(name))
        if name == "Ajouter et sélectionner une colonne":
            self.create_custom_column(lookup_name = "#ratingbab")
        else:
            self.note_moyenne = name
            self.name_note_moyenne.setCurrentIndex(self.name_note_moyenne.findText(name,Qt.MatchFixedString))
        if DEBUG: prints("self.note_moyenne : ", self.note_moyenne)

    def select_for_nbr_votes(self, name):
        if DEBUG: prints("\nIn select_for_nbr_votes(self, name : {}".format(name))
        if name == "Ajouter et sélectionner une colonne":
            self.create_custom_column(lookup_name = "#nbvotbab")
        else:
            self.nbr_votes = name
            self.name_nbr_votes.setCurrentIndex(self.name_nbr_votes.findText(name,Qt.MatchFixedString))
        if DEBUG: prints("self.nbr_votes : ", self.nbr_votes)

    def create_custom_column(self, lookup_name=None):
        if DEBUG: prints("\nIn create_custom_column - lookup_name:", lookup_name)
        if lookup_name == "#trouvebab" :
            display_params = {"description": "La présence, ou non, de babelio_id et donc de l'ouvrage à babelio.com", 'enum_values': ['Y', 'N'], 'enum_colors': [], 'use_decorations': False}
            datatype = "enumeration"
            column_heading  = "Babelio (Y/N)"

        elif lookup_name == "#ratingbab" :
            display_params =   {"description": "La moyenne de toutes les notes attribueés", 'number_format': None, 'decimals': 2}
            datatype = "float"
            column_heading  = "Note moyenne"

        elif lookup_name == "#nbvotbab" :
            display_params =   {'description': "Le nombre de notes attribuées", 'number_format': None}
            datatype = "int"
            column_heading  = "Nombre de votes"

# on devrait utiiser show_restart_warning()???

        if self.creator.must_restart():
            restart = question_dialog(self.gui, 'Désolé, calibre doit redémarrer pour procéder',
                "<p>Aucune modification ne peut plus être actée...<p>"
                "<p>Faut-il redémarrer maintenant, avant de créer une autre colonne ? <p>",
                show_copy_button=False)
            if restart :
                self.save_settings
                self.gui.quit(restart=True)
            else:
                return

        result = self.creator.create_column(lookup_name, column_heading, datatype, False, display=display_params, generate_unused_lookup_name=True, freeze_lookup_name=False)
        if DEBUG: prints("result : ", result)
        if result[0] == CreateNewCustomColumn.Result.COLUMN_ADDED:
            if lookup_name == "#trouvebab" :
                self.name_on_babelio.removeItem(self.name_on_babelio.findText("Ajouter et sélectionner une colonne", Qt.MatchFixedString))
                self.name_on_babelio.addItem(result[1])
                self.name_on_babelio.setCurrentIndex(self.name_on_babelio.findText(result[1], Qt.MatchFixedString))
                self.on_babelio = result[1]
            elif lookup_name == "#ratingbab" :
                self.name_note_moyenne.removeItem(self.name_note_moyenne.findText("Ajouter et sélectionner une colonne", Qt.MatchFixedString))
                self.name_note_moyenne.addItem(result[1])
                self.name_note_moyenne.setCurrentIndex(self.name_note_moyenne.findText(result[1], Qt.MatchFixedString))
                self.note_moyenne = result[1]
            elif lookup_name == "#nbvotbab" :
                self.name_nbr_votes.removeItem(self.name_nbr_votes.findText("Ajouter et sélectionner une colonne", Qt.MatchFixedString))
                self.name_nbr_votes.addItem(result[1])
                self.name_nbr_votes.setCurrentIndex(self.name_nbr_votes.findText(result[1], Qt.MatchFixedString))
                self.nbr_votes = result[1]
        return

    def save_settings(self):
        if DEBUG: prints("in save_settings")
        if DEBUG: prints("self.on_babelio : ", self.on_babelio)
        if DEBUG: prints("self.note_moyenne : ", self.note_moyenne)
        if DEBUG: prints("self.nbr_votes : ", self.nbr_votes)

        prefs["ON_BABELIO"] = self.on_babelio
        prefs["NOTE_MOYENNE"] = self.note_moyenne
        prefs["NBR_VOTES"] = self.nbr_votes

        allow_restart = question_dialog(self.gui, 'calibre devrait redémarrer',
                "<p>Pour être pris en considération, ce choix de colonne(s) impose un redémarrage...<p>"
                "<p>La dénomination de la présence, ou non, de babelio_id sera : <strong>{}</strong><p>"
                "<p>La dénomination de la moyenne de toutes les notes attribueés sera : <strong>{}</strong><p>"
                "<p>La dénomination du nombre de notes attribuée sera : <strong>{}</strong><p>"
                "<p>On redémarre maintenant?<p>".format(self.on_babelio,self.note_moyenne,self.nbr_votes),
                show_copy_button=False)
        if allow_restart :
                 self.gui.quit(restart=True)



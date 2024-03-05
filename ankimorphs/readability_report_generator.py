from functools import partial
from pathlib import Path
from typing import Optional, TextIO

from anki.collection import Collection
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import (  # pylint:disable=no-name-in-module
    QAbstractItemView,
    QHeaderView,
    Qt,
    QTableWidget,
    QTableWidgetItem,
)

from . import spacy_wrapper
from .ankimorphs_config import AnkiMorphsConfig
from .ankimorphs_db import AnkiMorphsDB
from .exceptions import CancelledOperationException, EmptyFileSelectionException
from .generator_dialog import GeneratorDialog
from .morpheme import Morpheme, MorphOccurrence
from .morphemizer import Morphemizer, SpacyMorphemizer
from .table_utils import QTableWidgetIntegerItem, QTableWidgetPercentItem
from .ui.readability_report_generator_ui import Ui_ReadabilityReportGeneratorWindow


class ReadabilityReportGeneratorDialog(GeneratorDialog):
    # ReadabilityReportGeneratorDialog inherits from GeneratorDialog, so if you cannot find
    # a self.[...] function or property, look there.

    def __init__(self) -> None:
        super().__init__(child=self.__class__.__name__)
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)
        self.file_name_column = 0
        self._total_morphs = 1
        self._known_column = 2
        self._learning_column = 3
        self._unknowns_column = 4
        self._number_of_columns = 5
        self._setup_table(self.ui.numericalTableWidget)
        self._setup_table(self.ui.percentTableWidget)
        self._setup_buttons()
        self.show()

    def _setup_table(self, table: QTableWidget) -> None:
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)

        table.setAlternatingRowColors(True)
        table.setColumnCount(self._number_of_columns)

        table.setColumnWidth(self.file_name_column, 200)
        table.setColumnWidth(self._total_morphs, 120)
        table.setColumnWidth(self._known_column, 80)
        table.setColumnWidth(self._learning_column, 90)
        table.setColumnWidth(self._unknowns_column, 100)

        table_vertical_headers: Optional[QHeaderView] = table.verticalHeader()
        assert table_vertical_headers is not None
        table_vertical_headers.hide()

        table_horizontal_headers: Optional[QHeaderView] = table.horizontalHeader()
        assert table_horizontal_headers is not None
        table_horizontal_headers.setSectionsMovable(True)

        # disables manual editing of the table
        self.ui.numericalTableWidget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

    def _setup_buttons(self) -> None:
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)
        self.ui.inputPushButton.clicked.connect(self._on_input_button_clicked)
        self.ui.generateReportPushButton.clicked.connect(self._generate_report)

    def _generate_report(self) -> None:
        assert mw is not None
        mw.progress.start(label="Generating readability report")
        operation = QueryOp(
            parent=mw,
            op=self._background_generate_report,
            success=self._on_success,
        )
        operation.failure(self._on_failure)
        operation.with_progress().run_in_background()

    def _background_generate_report(  # pylint:disable=too-many-locals
        self, col: Collection
    ) -> None:
        del col  # unused
        assert mw is not None
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)

        if self.ui.inputDirLineEdit.text() == "":
            raise EmptyFileSelectionException

        input_files: list[Path] = self._gather_input_files()
        nlp = None  # spacy.Language
        morphemizer: Morphemizer = self._morphemizers[self.ui.comboBox.currentIndex()]
        assert morphemizer is not None

        if isinstance(morphemizer, SpacyMorphemizer):
            selected: str = self.ui.comboBox.itemText(self.ui.comboBox.currentIndex())
            spacy_model = selected.removeprefix("spaCy: ")
            nlp = spacy_wrapper.get_nlp(spacy_model)

        # sorting has to be disabled before populating because bugs can occur
        self.ui.numericalTableWidget.setSortingEnabled(False)
        self.ui.percentTableWidget.setSortingEnabled(False)

        # clear previous results
        self.ui.numericalTableWidget.clearContents()
        self.ui.percentTableWidget.clearContents()

        files_morph_dicts: dict[Path, dict[str, MorphOccurrence]] = {}

        for input_file in input_files:
            if mw.progress.want_cancel():  # user clicked 'x' button
                raise CancelledOperationException

            mw.taskman.run_on_main(
                partial(
                    mw.progress.update,
                    label=f"Reading file:<br>{input_file.relative_to(self._input_dir_root)}",
                )
            )

            with open(input_file, encoding="utf-8") as file:
                file_morphs: dict[str, MorphOccurrence] = self._create_file_morphs_dict(
                    file, morphemizer, nlp
                )
                files_morph_dicts[input_file] = file_morphs

        mw.taskman.run_on_main(
            partial(
                mw.progress.update,
                label="Generating Report...",
            )
        )

        am_config = AnkiMorphsConfig()
        am_db = AnkiMorphsDB()

        self.ui.numericalTableWidget.setRowCount(len(input_files))
        self.ui.percentTableWidget.setRowCount(len(input_files))

        for _row, _input_file in enumerate(input_files):
            file_morphs = files_morph_dicts[_input_file]

            known_morphs, learning_morphs, unknown_morphs = self._get_morph_statuses(
                am_config, am_db, file_morphs
            )

            self._populate_numerical_table(
                _input_file,
                _row,
                known_morphs,
                learning_morphs,
                unknown_morphs,
            )
            self._populate_percentage_table(
                _input_file,
                _row,
                known_morphs,
                learning_morphs,
                unknown_morphs,
            )

        self.ui.numericalTableWidget.setSortingEnabled(True)
        self.ui.percentTableWidget.setSortingEnabled(True)

        am_db.con.close()

    def _create_file_morphs_dict(self, file: TextIO, morphemizer, nlp) -> dict[str, MorphOccurrence]:  # type: ignore[no-untyped-def]
        # nlp: spacy.Language

        file_morphs: dict[str, MorphOccurrence] = {}
        for line in file:
            morphs: list[Morpheme] = self._get_morphs_from_line(morphemizer, nlp, line)
            for morph in morphs:
                key = morph.lemma + morph.inflection
                if key in file_morphs:
                    file_morphs[key].occurrence += 1
                else:
                    file_morphs[key] = MorphOccurrence(morph)
        return file_morphs

    @staticmethod
    def _get_morph_statuses(
        am_config: AnkiMorphsConfig,
        am_db: AnkiMorphsDB,
        file_morphs: dict[str, MorphOccurrence],
    ) -> tuple[int, int, int]:
        known_morphs: int = 0
        learning_morphs: int = 0
        unknown_morphs: int = 0

        for morph_occurrence_object in file_morphs.values():
            morph = morph_occurrence_object.morph
            occurrence = morph_occurrence_object.occurrence

            highest_learning_interval: Optional[int] = (
                am_db.get_highest_learning_interval(morph.lemma, morph.inflection)
            )

            if highest_learning_interval is None:
                unknown_morphs += occurrence
                continue

            if highest_learning_interval == 0:
                unknown_morphs += occurrence
            elif highest_learning_interval < am_config.recalc_interval_for_known:
                learning_morphs += occurrence
            else:
                known_morphs += occurrence

        return known_morphs, learning_morphs, unknown_morphs

    def _populate_numerical_table(
        self,
        _input_file: Path,
        _row: int,
        known_morphs: int,
        learning_morphs: int,
        unknown_morphs: int,
    ) -> None:
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)

        relative_path = _input_file.relative_to(self._input_dir_root)

        total_morphs: int = known_morphs + learning_morphs + unknown_morphs

        file_name_item = QTableWidgetItem(str(relative_path))
        total_morphs_item = QTableWidgetIntegerItem(total_morphs)
        known_item = QTableWidgetIntegerItem(known_morphs)
        learning_item = QTableWidgetIntegerItem(learning_morphs)
        unknowns_item = QTableWidgetIntegerItem(unknown_morphs)

        total_morphs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        known_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        learning_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        unknowns_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ui.numericalTableWidget.setItem(
            _row, self.file_name_column, file_name_item
        )
        self.ui.numericalTableWidget.setItem(
            _row, self._total_morphs, total_morphs_item
        )
        self.ui.numericalTableWidget.setItem(_row, self._known_column, known_item)
        self.ui.numericalTableWidget.setItem(_row, self._learning_column, learning_item)
        self.ui.numericalTableWidget.setItem(_row, self._unknowns_column, unknowns_item)

    def _populate_percentage_table(
        self,
        _input_file: Path,
        _row: int,
        known_morphs: int,
        learning_morphs: int,
        unknown_morphs: int,
    ) -> None:
        assert isinstance(self.ui, Ui_ReadabilityReportGeneratorWindow)

        total_morphs: int = known_morphs + learning_morphs + unknown_morphs
        known_morphs_percent: float = 0
        learning_morphs_percent: float = 0
        unknown_morphs_percent: float = 0

        if total_morphs != 0:
            known_morphs_percent = (known_morphs / total_morphs) * 100
            learning_morphs_percent = (learning_morphs / total_morphs) * 100
            unknown_morphs_percent = (unknown_morphs / total_morphs) * 100

        relative_path = _input_file.relative_to(self._input_dir_root)

        file_name_item = QTableWidgetItem(str(relative_path))
        total_morphs_item = QTableWidgetIntegerItem(total_morphs)
        known_item = QTableWidgetPercentItem(round(known_morphs_percent, 1))
        learning_item = QTableWidgetPercentItem(round(learning_morphs_percent, 1))
        unknowns_item = QTableWidgetPercentItem(round(unknown_morphs_percent, 1))

        total_morphs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        known_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        learning_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        unknowns_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ui.percentTableWidget.setItem(_row, self.file_name_column, file_name_item)
        self.ui.percentTableWidget.setItem(_row, self._total_morphs, total_morphs_item)
        self.ui.percentTableWidget.setItem(_row, self._known_column, known_item)
        self.ui.percentTableWidget.setItem(_row, self._learning_column, learning_item)
        self.ui.percentTableWidget.setItem(_row, self._unknowns_column, unknowns_item)

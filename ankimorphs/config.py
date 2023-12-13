from typing import Any, Optional, Union

from anki.notes import Note
from aqt import mw
from aqt.qt import (  # pylint:disable=no-name-in-module
    QKeySequence,
    QMessageBox,
    QPushButton,
    Qt,
)
from aqt.utils import tooltip

from . import ankimorphs_globals

# Unfortunately, 'TypeAlias' is introduced in python 3.10 so for now
# we can only create implicit type aliases.
FilterTypeAlias = dict[str, Union[str, bool, int, dict[str, str], None]]


class AnkiMorphsConfigFilter:  # pylint:disable=too-many-instance-attributes
    def __init__(self, _filter: FilterTypeAlias):
        try:
            self.has_error: bool = False

            self.note_type: str = _get_filter_str(_filter, "note_type")
            self.note_type_id: Optional[int] = _get_filter_optional_int(
                _filter, "note_type_id"
            )
            self.tags: dict[str, str] = _get_filter_str_from_json(_filter, "tags")
            self.field: str = _get_filter_str(_filter, "field")
            self.field_index: Optional[int] = _get_filter_optional_int(
                _filter, "field_index"
            )
            self.morphemizer_description: str = _get_filter_str(
                _filter, "morphemizer_description"
            )
            self.morphemizer_name: str = _get_filter_str(_filter, "morphemizer_name")
            self.morph_priority: str = _get_filter_str(_filter, "morph_priority")
            self.morph_priority_index: Optional[int] = _get_filter_optional_int(
                _filter, "morph_priority_index"
            )
            self.read: bool = _get_filter_bool(_filter, "read")
            self.modify: bool = _get_filter_bool(_filter, "modify")
            self.unknowns_field: str = _get_filter_str(_filter, "unknowns_field")
            self.unknowns_field_index: Optional[int] = _get_filter_optional_int(
                _filter, "unknowns_field_index"
            )
            self.unknowns_count_field: str = _get_filter_str(
                _filter, "unknowns_count_field"
            )
            self.unknowns_count_field_index: Optional[int] = _get_filter_optional_int(
                _filter, "unknowns_count_field_index"
            )
            self.highlighted_field: str = _get_filter_str(_filter, "highlighted_field")
            self.highlighted_field_index: Optional[int] = _get_filter_optional_int(
                _filter, "highlighted_field_index"
            )
            self.difficulty_field: str = _get_filter_str(_filter, "difficulty_field")
            self.difficulty_field_index: Optional[int] = _get_filter_optional_int(
                _filter, "difficulty_field_index"
            )
        except (KeyError, AssertionError):
            self.has_error = True
            if not ankimorphs_globals.ankimorphs_broken:
                show_critical_config_error()
                ankimorphs_globals.ankimorphs_broken = True
            else:
                # ignore duplicate errors
                pass


class AnkiMorphsConfig:  # pylint:disable=too-many-instance-attributes
    def __init__(self, is_default: bool = False) -> None:
        try:
            self.shortcut_recalc: QKeySequence = _get_key_sequence_config(
                "shortcut_recalc", is_default
            )
            self.shortcut_settings: QKeySequence = _get_key_sequence_config(
                "shortcut_settings", is_default
            )
            self.shortcut_browse_ready_same_unknown: QKeySequence = (
                _get_key_sequence_config(
                    "shortcut_browse_ready_same_unknown", is_default
                )
            )
            self.shortcut_browse_all_same_unknown: QKeySequence = (
                _get_key_sequence_config("shortcut_browse_all_same_unknown", is_default)
            )
            self.shortcut_set_known_and_skip: QKeySequence = _get_key_sequence_config(
                "shortcut_set_known_and_skip", is_default
            )
            self.shortcut_learn_now: QKeySequence = _get_key_sequence_config(
                "shortcut_learn_now", is_default
            )
            self.shortcut_view_morphemes: QKeySequence = _get_key_sequence_config(
                "shortcut_view_morphemes", is_default
            )
            self.skip_only_known_morphs_cards: bool = _get_bool_config(
                "skip_only_known_morphs_cards", is_default
            )
            self.skip_unknown_morph_seen_today_cards: bool = _get_bool_config(
                "skip_unknown_morph_seen_today_cards", is_default
            )
            self.skip_show_num_of_skipped_cards: bool = _get_bool_config(
                "skip_show_num_of_skipped_cards", is_default
            )
            self.recalc_interval_for_known: int = _get_int_config(
                "recalc_interval_for_known", is_default
            )
            self.parse_ignore_bracket_contents: bool = _get_bool_config(
                "parse_ignore_bracket_contents", is_default
            )
            self.parse_ignore_round_bracket_contents: bool = _get_bool_config(
                "parse_ignore_round_bracket_contents", is_default
            )
            self.parse_ignore_slim_round_bracket_contents: bool = _get_bool_config(
                "parse_ignore_slim_round_bracket_contents", is_default
            )
            self.parse_ignore_names_morphemizer: bool = _get_bool_config(
                "parse_ignore_names_morphemizer", is_default
            )
            self.parse_ignore_names_textfile: bool = _get_bool_config(
                "parse_ignore_names_textfile", is_default
            )
            self.parse_ignore_suspended_cards_content: bool = _get_bool_config(
                "parse_ignore_suspended_cards_content", is_default
            )
            self.recalc_on_sync: bool = _get_bool_config("recalc_on_sync", is_default)
            self.recalc_suspend_known_new_cards: bool = _get_bool_config(
                "recalc_suspend_known_new_cards", is_default
            )
            self.tag_ready: str = _get_string_config("tag_ready", is_default)
            self.tag_not_ready: str = _get_string_config("tag_not_ready", is_default)
            self.tag_known_automatically: str = _get_string_config(
                "tag_known_automatically", is_default
            )
            self.tag_known_manually: str = _get_string_config(
                "tag_known_manually", is_default
            )
            self.tag_learn_card_now: str = _get_string_config(
                "tag_learn_card_now", is_default
            )
            self.filters: list[AnkiMorphsConfigFilter] = _get_filters_config(is_default)
        except (KeyError, AssertionError):
            if not ankimorphs_globals.ankimorphs_broken:
                show_critical_config_error()
                ankimorphs_globals.ankimorphs_broken = True
            else:
                # ignore duplicate errors
                pass


def _get_config(
    key: str,
) -> Union[str, int, bool, list[FilterTypeAlias], None]:
    config = get_configs()
    assert config is not None
    item = config[key]
    assert isinstance(item, (str, bool, int, list))
    return item


def get_configs() -> Optional[dict[str, Any]]:
    assert mw is not None
    return mw.addonManager.getConfig(__name__)


def get_default_config(key: str) -> Any:
    config = get_all_default_configs()
    assert config is not None
    return config[key]


def get_all_default_configs() -> Optional[dict[str, Any]]:
    assert mw is not None
    addon = mw.addonManager.addonFromModule(__name__)  # necessary to prevent anki bug
    return mw.addonManager.addonConfigDefaults(addon)


def update_configs(new_configs: dict[str, object]) -> None:
    assert mw is not None
    config = mw.addonManager.getConfig(__name__)
    assert config is not None
    for key, value in new_configs.items():
        config[key] = value
    mw.addonManager.writeConfig(__name__, config)


def _reset_all_configs() -> None:
    default_configs = get_all_default_configs()
    assert default_configs is not None
    update_configs(default_configs)


def get_read_enabled_filters() -> list[AnkiMorphsConfigFilter]:
    config_filters = _get_filters_config()
    assert isinstance(config_filters, list)
    read_filters = []
    for config_filter in config_filters:
        if config_filter.read:
            read_filters.append(config_filter)
    return read_filters


def get_modify_enabled_filters() -> list[AnkiMorphsConfigFilter]:
    config_filters = _get_filters_config()
    assert isinstance(config_filters, list)
    modify_filters = []
    for config_filter in config_filters:
        if config_filter.modify:
            modify_filters.append(config_filter)
    return modify_filters


def get_matching_modify_filter(note: Note) -> Optional[AnkiMorphsConfigFilter]:
    modify_filters: list[AnkiMorphsConfigFilter] = get_modify_enabled_filters()
    for am_filter in modify_filters:
        if am_filter.note_type_id == note.mid:
            return am_filter
    return None


def get_matching_read_filter(note: Note) -> Optional[AnkiMorphsConfigFilter]:
    read_filters: list[AnkiMorphsConfigFilter] = get_read_enabled_filters()
    for am_filter in read_filters:
        if am_filter.note_type_id == note.mid:
            return am_filter
    return None


def _get_filters_config(is_default: bool = False) -> list[AnkiMorphsConfigFilter]:
    if is_default:
        filters_config = get_default_config("filters")
    else:
        filters_config = _get_config("filters")
    assert isinstance(filters_config, list)

    filters = []
    for _filter in filters_config:
        am_filter = AnkiMorphsConfigFilter(_filter)
        if not am_filter.has_error:
            filters.append(am_filter)
    return filters


def _get_key_sequence_config(key: str, is_default: bool = False) -> QKeySequence:
    if is_default:
        config_item = get_default_config(key)
    else:
        config_item = _get_config(key)
    assert isinstance(config_item, str)
    return QKeySequence(config_item)


def _get_int_config(key: str, is_default: bool = False) -> int:
    if is_default:
        config_item = get_default_config(key)
    else:
        config_item = _get_config(key)
    assert isinstance(config_item, int)
    return config_item


def _get_string_config(key: str, is_default: bool = False) -> str:
    if is_default:
        config_item = get_default_config(key)
    else:
        config_item = _get_config(key)
    assert isinstance(config_item, str)
    return config_item


def _get_bool_config(key: str, is_default: bool = False) -> bool:
    if is_default:
        config_item = get_default_config(key)
    else:
        config_item = _get_config(key)
    assert isinstance(config_item, bool)
    return config_item


def _get_filter_str(_filter: FilterTypeAlias, key: str) -> str:
    filter_item = _filter[key]
    assert isinstance(filter_item, str)
    return filter_item


def _get_filter_bool(_filter: FilterTypeAlias, key: str) -> bool:
    filter_item = _filter[key]
    assert isinstance(filter_item, bool)
    return filter_item


def _get_filter_str_from_json(_filter: FilterTypeAlias, key: str) -> dict[str, str]:
    filter_item_dict = _filter[key]
    assert isinstance(filter_item_dict, dict)
    return filter_item_dict


def _get_filter_optional_int(_filter: FilterTypeAlias, key: str) -> Optional[int]:
    filter_item = _filter[key]
    assert isinstance(filter_item, int) or filter_item is None
    return filter_item


def show_critical_config_error() -> None:
    critical_box = QMessageBox(mw)
    critical_box.setWindowTitle("AnkiMorphs Error")
    critical_box.setIcon(QMessageBox.Icon.Critical)
    ok_button: QPushButton = QPushButton("Restore All Defaults")
    critical_box.addButton(ok_button, QMessageBox.ButtonRole.YesRole)
    body: str = (
        "**The default AnkiMorphs configs have been changed!**"
        "<br/><br/>"
        "Backwards compatibility has been broken, "
        "read the <a href='https://github.com/mortii/anki-morphs/releases'>changelog</a> for more info."
        "<br/><br/>"
        "Please do the following:\n"
        "1. Click the 'Restore All Defaults' button below\n"
        "2. Redo your AnkiMorphs settings\n\n"
    )
    critical_box.setTextFormat(Qt.TextFormat.MarkdownText)
    critical_box.setText(body)
    critical_box.exec()

    if critical_box.clickedButton() == ok_button:
        _reset_all_configs()
        tooltip("Please restart Anki", period=5000, parent=mw)

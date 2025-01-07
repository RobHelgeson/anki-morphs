from __future__ import annotations

import re

import anki
from anki.template import TemplateRenderContext

from . import (
    ankimorphs_config,
    ankimorphs_globals,
    text_highlighting,
    text_preprocessing,
    debug_utils,
)
from .ankimorphs_config import AnkiMorphsConfig, AnkiMorphsConfigFilter
from .ankimorphs_db import AnkiMorphsDB
from .morpheme import Morpheme
from .morphemizers import morphemizer as morphemizer_module
from .morphemizers import spacy_wrapper
from .morphemizers.morphemizer import Morphemizer, SpacyMorphemizer


def highlight_morphs_jit(
    field_text: str,
    field_name: str,
    filter_name: str,
    context: TemplateRenderContext,
) -> str:
    """Use morph learning progress to decorate the morphemes in the supplied text.
    Adds css classes to the output that can be styled in the card."""

    # Perf: Bail early if the user attempts to use this template filter on the already
    # formatted data.
    if (
        filter_name
        not in [
            "am-highlight",
            "am-highlight-furigana",
            "am-highlight-kanji",
            "am-highlight-kana",
        ]
        or field_name == ankimorphs_globals.EXTRA_FIELD_HIGHLIGHTED
    ):
        return field_text

    am_config_filter: AnkiMorphsConfigFilter | None = (
        ankimorphs_config.get_matching_filter(context.note())
    )

    if am_config_filter is None:
        return field_text

    morphemizer: Morphemizer | None = morphemizer_module.get_morphemizer_by_description(
        am_config_filter.morphemizer_description
    )

    if not morphemizer:
        return field_text

    am_config = AnkiMorphsConfig()

    card_morphs: list[Morpheme] = _get_morph_meta_for_text(
        morphemizer, field_text, am_config
    )

    if not card_morphs:
        return field_text

    debug_utils.dev_print(f"filter name: {filter_name}")

    styles = _get_styles(filter_name)

    highlighted_jit_text = (
        f"<span class='{filter_name}'>"
        + styles
        + " "
        + text_highlighting.get_highlighted_text(
            am_config=am_config,
            morphemes=card_morphs,
            text=_dehtml(field_text),
            use_html_rubies=filter_name != "am-highlight",
        )
        + "</span>"
    )

    debug_utils.dev_print(f"highlighted_jit_text: {highlighted_jit_text}")

    return highlighted_jit_text


def _get_morph_meta_for_text(
    morphemizer: Morphemizer,
    field_text: str,
    am_config: AnkiMorphsConfig,
) -> list[Morpheme]:
    """Take in a string and gather the morphemes from it."""

    # If we were piped in after the `furigana` built-in filter, or if there is html in the source
    # data, we need to do some cleansing.
    clean_text = _dehtml(field_text, am_config, True)

    if isinstance(morphemizer, SpacyMorphemizer):
        nlp = spacy_wrapper.get_nlp(
            morphemizer.get_description().removeprefix("spaCy: ")
        )

        morphs = text_preprocessing.get_processed_spacy_morphs(
            am_config, next(nlp.pipe([clean_text]))
        )
    else:
        morphs = text_preprocessing.get_processed_morphemizer_morphs(
            morphemizer, clean_text, am_config
        )

    morphs = list(set(morphs))

    if not morphs:
        return []

    with AnkiMorphsDB() as am_db:
        for morph in morphs:
            if am_config.evaluate_morph_inflection:
                morph.highest_inflection_learning_interval = (
                    am_db.get_highest_inflection_learning_interval(morph) or 0
                )
            else:
                morph.highest_lemma_learning_interval = (
                    am_db.get_highest_lemma_learning_interval(morph) or 0
                )

    return morphs


def _dehtml(
    text: str,
    am_config: AnkiMorphsConfig | None = None,
    clean_html: bool = False,
) -> str:
    """Prepare a string to be passed to a morphemizer. Specially process <ruby><rt> tags to extract
    ruby to reconstruct base/ruby ruby shorthand. Remove all html from the input string.
    """

    # Capture html ruby ruby. The built in furigana filter will turn X[yz] into
    # <ruby><rb>X</rb><rt>yz</rt></ruby>, and if we blindly strip out all html we will loose
    # information on the ruby. Find <rt> tags and capture all text between them in a capture
    # group called ruby, allow for any attributes or other decorations on the <rt> tag by
    # non-eagerly capturing all chars up to '>', so that the whole element can just be dropped.
    # non-eagerly capture one or more characters into the capture group named ruby.
    # Samples:
    # <ruby><rb>X</rb><rt>yz</rt></ruby> = ` X[yz]`
    # <ruby>X<rt>yz</rt></ruby> = ` X[yz]`
    # <ruby>X<rt class='foo'>234</rt>sdf</ruby> = ` X[234]sdf`
    # <ruby>X<rt >>234</rt>sdf</ruby> = ` X[>234]sdf`
    # <ruby>X<rt></rt></ruby> = Will not match
    ruby_longhand = r"(?:<ruby[^<]*>)(?:<rb[^>]*>|.{0})(?P<base>.*?)(?:</rb>|.{0})<rt[^>]*>(?P<ruby>.+?)</rt>(?P<after>.*?)(?:</ruby>)"

    # Emit the captured ruby into square brackets, thus reconstructing the ruby shorthand "X[yz]".
    # Pad with a leading space so that we can retain the base/ruby relationship
    ruby_shorthand = r" \g<base>[\g<ruby>]\g<after>"

    text = re.sub(ruby_longhand, ruby_shorthand, text, flags=re.IGNORECASE).strip()

    if clean_html:
        text = anki.utils.strip_html(text)

    return text_preprocessing.get_processed_text(am_config, text) if am_config else text


def _get_styles(filter_name: str) -> str:
    """Get local styles for this run, based on the filter name."""

    if filter_name == "am-highlight-kana":
        return """<style>
.am-highlight-kana {
    & ruby {
        display: inline-block;
        visibility: hidden;

        & rt {
            font-size: inherit;
            margin-top: -1em;
            visibility: visible;
        }
    }
}
</style>"""

    if filter_name == "am-highlight-kanji":
        return """<style>
.am-highlight-kanji {
    & ruby rt {
        display: none;
    }
}
</style>"""

    return ""

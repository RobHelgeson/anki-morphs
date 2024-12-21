from __future__ import annotations

from collections import deque

from . import text_preprocessing
from .ankimorphs_config import AnkiMorphsConfig
from .morpheme import Morpheme


class Range:
    """Base class for Ranges."""

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end


class RubyRange(Range):
    """Represents a ruby and its range in parent string."""

    def __init__(self, start: int, end: int, base: str, ruby: str):
        super().__init__(start, end)
        self.base = base
        self.ruby = ruby

    def prefix_len(self) -> int:
        return len("<ruby>")

    def open(self) -> str:
        return "<ruby>"

    def close(self) -> str:
        return "</ruby>"

    def rt(self) -> str:
        return f"<rt>{self.ruby}</rt>"

    def rt_offset(self) -> int:
        return len(self.base) - 1

    def inject(self, target: str) -> str:
        return target[: self.start] + str(self) + target[self.end :]

    def __str__(self) -> str:
        return f"<ruby>{self.base}<rt>{self.ruby}</rt></ruby>"

    def __repr__(self) -> str:
        return f"Range: {self.start}-{self.end}. Value: {self.base}[{self.ruby}]."


class StatusRange(Range):
    """Represents a morph's status and range in parent string."""

    def __init__(self, start: int, end: int, status: str):
        super().__init__(start, end)
        self.status = status

    def open_len(self) -> int:
        """Len of the open tag, useful for setting string splice offsets."""
        return len(self.open())

    def open(self) -> str:
        return f'<span morph-status="{self.status}">'

    def close(self) -> str:
        return "</span>"

    def inject(self, target: str) -> str:
        """Put this morph into the given string."""

        return (
            target[: self.start]
            + self.open()
            + target[self.start : self.end]
            + self.close()
            + target[self.end :]
        )

    def __repr__(self) -> str:
        return f"Range: {self.start}-{self.end}. Status: {self.status}."


class TextHighlighter:
    """Represents an expression to highlight. Tracks 2 sets of data, one for rubies the other
    for morph status. all the magic happens in _process() where we merge them together on top
    of the base string."""

    def __init__(self, expression: str, morphs_and_statuses: list[MorphAndStatus]):
        self._highlighted: str | None = None
        self.expression: str = expression
        self.rubies: deque[RubyRange] = deque()
        self.statuses: deque[StatusRange] = deque()

        self._tag_rubies()
        self._tag_morphemes(self.expression.lower(), morphs_and_statuses)

    def _tag_rubies(self) -> None:
        """Populate internal deque of found ruby locations."""

        end = 0

        while True:
            match = text_preprocessing.ruby_regex.search(self.expression, pos=end)

            if not match:
                break

            end = match.start() + len(match.group(1))

            self.rubies.append(
                RubyRange(match.start(), end, match.group(1), match.group(2))
            )
            self.expression = (
                self.expression[: match.start()]
                + match.group(1)
                + self.expression[match.end() :]
            )

    def _tag_morphemes(
        self, expression: str, morphs_and_statuses: list[MorphAndStatus]
    ) -> None:
        """Populate internal deque of found morph locations."""

        for morph_and_status in sorted(
            morphs_and_statuses, key=lambda meta: len(meta.morph), reverse=True
        ):
            while True:
                start = expression.find(morph_and_status.morph)

                if start == -1:
                    break

                end = start + len(morph_and_status.morph)

                self.statuses.append(StatusRange(start, end, morph_and_status.status))
                expression = (
                    expression[:start] + (" " * (end - start)) + expression[end:]
                )

        self.statuses = deque(sorted(self.statuses, key=lambda range: range.start))

    def highlighted(self) -> str:
        """Get the highlighted string. Pull from cache if present."""

        if not self._highlighted:
            self._highlighted = self.expression or ""

            if self._highlighted and (self.rubies or self.statuses):
                self._process()

        return self._highlighted

    def _process(self) -> None:  # pylint:disable=too-many-branches, too-many-statements
        """Process the text in self._highlighted, now that all the metadata has been gathered."""

        ruby: RubyRange | None = None
        stat: StatusRange | None = None

        while self._highlighted is not None:
            if ruby is None and self.rubies:
                ruby = self.rubies.pop()

            if stat is None and self.statuses:
                stat = self.statuses.pop()

            if ruby is None and stat is None:
                break

            # If there are only statuses.
            if ruby is None:
                # print("There are only statuses.")
                # Ignore is here because (surprisingly) mypy can not tell the
                # only path that leads here requires stat to be non-None.
                self._highlighted = stat.inject(self._highlighted)  # type: ignore[union-attr]
                stat = None
                continue

            # If there are only rubies.
            if stat is None:
                # print("There are only rubies.")
                self._highlighted = ruby.inject(self._highlighted)
                ruby = None
                continue

            # If there is no overlap between ruby and status, process the latest one.
            if ruby.end <= stat.start or ruby.start >= stat.end:
                # print("There is no overlap between ruby and status.")
                if ruby.start > stat.start:
                    self._highlighted = ruby.inject(self._highlighted)
                    ruby = None
                else:
                    self._highlighted = stat.inject(self._highlighted)
                    stat = None
                continue

            # If the status is the same as the ruby
            if ruby.start == stat.start and ruby.end == stat.end:
                # print("The status is the same as the ruby.")
                self._highlighted = (
                    self._highlighted[: stat.start]
                    + stat.open()
                    + str(ruby)
                    + stat.close()
                    + self._highlighted[stat.end :]
                )
                ruby = None
                stat = None
                continue

            # If the ruby is completely inside the status
            if ruby.start >= stat.start and ruby.end <= stat.end:
                # print("The ruby is completely inside the status.")
                self._highlighted = (
                    self._highlighted[: stat.start]
                    + stat.open()
                    + self._highlighted[
                        stat.start : stat.start + ruby.start - stat.start
                    ]
                    + str(ruby)
                    + self._highlighted[ruby.end : stat.end]
                    + stat.close()
                    + self._highlighted[stat.end :]
                )
                ruby = None

                # Pull and process rubies until the next ruby is outside of this status.
                while self.rubies:
                    if self.rubies[-1].end <= stat.start:
                        break

                    ruby = self.rubies.pop()
                    ruby.start += stat.open_len()
                    ruby.end += stat.open_len()
                    self._highlighted = ruby.inject(self._highlighted)

                stat = None
                ruby = None
                continue

            # If the status is completely inside the ruby
            if ruby.start <= stat.start and ruby.end >= stat.end:
                # print("The status is completely inside the ruby.")
                self._highlighted = ruby.inject(self._highlighted)
                stat.start += ruby.prefix_len()
                stat.end += ruby.prefix_len()
                self._highlighted = stat.inject(self._highlighted)
                stat = None

                # Pull and process statuses until the next status is outside of this ruby.
                while self.statuses:
                    if self.statuses[-1].end <= ruby.start:
                        break

                    stat = self.statuses.pop()
                    stat.start += ruby.prefix_len()
                    stat.end += ruby.prefix_len()
                    self._highlighted = stat.inject(self._highlighted)

                ruby = None
                stat = None
                continue

            # If the ruby starts then status starts, ruby ends, status ends
            if ruby.start < stat.start and ruby.end < stat.end:
                # print("The ruby starts then status starts, ruby ends, status ends.")
                self._highlighted = (
                    self._highlighted[: ruby.start]
                    + ruby.open()
                    + self._highlighted[ruby.start : stat.start]
                    + stat.open()
                    + self._highlighted[
                        stat.start : stat.start
                        + (stat.end - stat.start)
                        - (stat.end - ruby.end)
                    ]
                    + stat.close()
                    + ruby.rt()
                    + ruby.close()
                    + stat.open()
                    + self._highlighted[ruby.end : stat.end]
                    + stat.close()
                    + self._highlighted[stat.end :]
                )
                stat = None

                # Pull and process statuses until the next status is outside of this ruby.
                while self.statuses:
                    if self.statuses[-1].end <= ruby.start:
                        break

                    stat = self.statuses.pop()
                    stat.start += ruby.prefix_len()
                    stat.end += ruby.prefix_len()
                    self._highlighted = stat.inject(self._highlighted)

                ruby = None
                stat = None
                continue

            # If the status starts then ruby starts, status ends, ruby ends
            if ruby.start > stat.start and ruby.end > stat.end:
                # print("The status starts then ruby starts, status ends, ruby ends.")
                self._highlighted = (
                    self._highlighted[: stat.start]
                    + stat.open()
                    + self._highlighted[stat.start : ruby.start]
                    + stat.close()
                    + ruby.open()
                    + stat.open()
                    + self._highlighted[ruby.start : ruby.start + ruby.rt_offset()]
                    + stat.close()
                    + self._highlighted[stat.end : ruby.end]
                    + ruby.rt()
                    + ruby.close()
                    + self._highlighted[ruby.end :]
                )

                ruby = None
                stat = None
                continue

            # print("Made it past all possible cases. This should not be possible.")

            # Just in case, to prevent infinite loop, we're disposing of the current pieces
            ruby = None
            stat = None


class MorphAndStatus:
    """A class to track morpheme data relevant to highlighting."""

    def __init__(
        self,
        morpheme: Morpheme,
        evaluate_morph_inflection: bool,
        interval_for_known_morphs: int,
    ):
        self.morph = morpheme.inflection.lower()
        self.status = MorphAndStatus.get_status_for_morph(
            morpheme,
            evaluate_morph_inflection,
            interval_for_known_morphs,
        )

    @staticmethod
    def get_status_for_morph(
        morpheme: Morpheme,
        evaluate_morph_inflection: bool,
        interval_for_known_morphs: int,
    ) -> str:
        """Get the morpheme's status. Use the relevant interval based on the user's config."""

        if evaluate_morph_inflection:
            learning_interval = getattr(
                morpheme, "highest_inflection_learning_interval", 0
            )
        else:
            learning_interval = getattr(morpheme, "highest_lemma_learning_interval", 0)

        if learning_interval == 0:
            return "unknown"

        if learning_interval < interval_for_known_morphs:
            return "learning"

        return "known"


def get_highlighted_text(
    am_config: AnkiMorphsConfig,
    morphemes: list[Morpheme],
    text: str,
) -> str:
    """Highlight a text string based on found morphemes. Supports rubies.
    See test cases for exhaustive examples."""

    morphs_and_statuses = [
        MorphAndStatus(
            morpheme,
            am_config.evaluate_morph_inflection,
            am_config.interval_for_known_morphs,
        )
        for morpheme in morphemes
    ]

    return TextHighlighter(text, morphs_and_statuses).highlighted()

"""Server-side rendering for AMP HTML in Python."""

import contextlib
import json
import re
import types
from collections import OrderedDict
from enum import Enum
from html.parser import HTMLParser
from typing import NamedTuple


class TransformationError(Exception):
    """An originalor to throw when attributes can't be converted to CSS."""


# The namedtuples will still be accessed using index notation for performance.
class Translation(NamedTuple):
    """A CSS translation from an AMP attribute."""

    selector: str
    statements: OrderedDict


class Sizes(NamedTuple):
    """Parsed sizes attribute."""

    default: str
    other: list


class Media(NamedTuple):
    """A media query and value pair."""

    query: str
    value: str


class Sizer(NamedTuple):
    """Sizer element attributes."""

    attrs: list
    maybe_img_attrs: list | None


class Translator:
    """A tool to convert special attributes to CSS."""

    @classmethod
    def parse_sizes(cls, value: str) -> Sizes:
        """Parse the value of a special attribute."""
        # Normalize whitespace
        size_values = re.split(r"\s*,\s*", value.strip())

        try:
            default = size_values.pop()
        except IndexError:
            return Sizes(default="", other=[])

        other = []

        for size_value in size_values:
            size_parts = re.split(r"\)\s+", size_value)
            if len(size_parts) != 2:
                raise ValueError("Invalid sizes definition")

            query = f"{size_parts[0]})"
            query = query.replace(r"\s+", "")
            value = size_parts[1]

            media = Media(query=query, value=value)
            other.append(media)

        return Sizes(default=default, other=other)


class MediaTranslator(Translator):
    """A tool to convert `media=...` attributes to CSS."""

    @classmethod
    def translate(cls, value: str, element_id: str) -> Translation | None:
        """Convert a `media=...` attribute to CSS."""
        # Normalize whitespace
        media = re.sub(r"\s+", " ", value).strip()

        if not media:
            return None

        if media[0] == "(":
            media = f"all and {media}"

        media = media[4:] if media.startswith("not ") else f"not {media}"

        selector = f"#{element_id}"

        return Translation(
            selector=selector,
            statements=OrderedDict(
                [
                    (media, "display:none"),
                ],
            ),
        )


class SizesTranslator(Translator):
    """A tool to convert `sizes=...` attributes to CSS."""

    @classmethod
    def translate(cls, value: str, element_id: str) -> Translation:
        """Convert a `sizes=...` attribute to CSS."""
        sizes = cls.parse_sizes(value)
        selector = f"#{element_id}"
        statements = [(None, f"width:{sizes[0]}")]
        other_sizes = sizes[1]

        # The user agent will pick a width from the sizes attribute, using the
        # first item with a <media-condition> (the part in parentheses) that
        # evaluates to true. This means, we have to reverse the order the media
        # queries in CSS to emulate this behavior (the last definition has
        # precedence).
        other_sizes.reverse()
        statements.extend((size[0], f"width:{size[1]}") for size in other_sizes)

        return Translation(selector=selector, statements=OrderedDict(statements))


class HeightsTranslator(Translator):
    """A tool to convert `heights=...` attributes to CSS."""

    @classmethod
    def translate(cls, value: str, element_id: str) -> Translation:
        """Convert a `heights=...` attribute to CSS."""
        sizes = cls.parse_sizes(value)
        selector = f"#{element_id}>:first-child"
        statements = [(None, f"padding-top:{sizes[0]}")]
        other_sizes = sizes[1]

        # The user agent will pick a value from the heights attribute, using
        # the first item with a <media-condition> (the part in parentheses)
        # that evaluates to true. This means, we have to reverse the order the
        # media queries in CSS to emulate this behavior (the last definition
        # has precedence).
        other_sizes.reverse()
        statements.extend((size[0], f"padding-top:{size[1]}") for size in other_sizes)

        return Translation(selector=selector, statements=OrderedDict(statements))


TRANSLATIONS = types.MappingProxyType(
    {
        "media": MediaTranslator,
        "sizes": SizesTranslator,
        "heights": HeightsTranslator,
    },
)


class Layout(Enum):
    """Possible layout options for an AMP html element."""

    NODISPLAY = "nodisplay"  # noqa: WPS115 (allow caps for Enums)
    FIXED = "fixed"  # noqa: WPS115
    FIXED_HEIGHT = "fixed-height"  # noqa: WPS115
    RESPONSIVE = "responsive"  # noqa: WPS115
    CONTAINER = "container"  # noqa: WPS115
    FILL = "fill"  # noqa: WPS115
    FLEX_ITEM = "flex-item"  # noqa: WPS115
    INTRINSIC = "intrinsic"  # noqa: WPS115

    def get_class(self) -> str:
        """Return the CSS class appropriate for this layout."""
        return f"i-amphtml-layout-{self.value}"

    def is_size_defined(self) -> bool:
        """Return whether this layout has its size defined."""
        return self in SIZE_DEFINED_LAYOUTS


# Store constants for performance
LAYOUT_NODISPLAY = Layout.NODISPLAY
LAYOUT_FIXED = Layout.FIXED
LAYOUT_FIXED_HEIGHT = Layout.FIXED_HEIGHT
LAYOUT_RESPONSIVE = Layout.RESPONSIVE
LAYOUT_CONTAINER = Layout.CONTAINER
LAYOUT_FILL = Layout.FILL
LAYOUT_FLEX_ITEM = Layout.FLEX_ITEM
LAYOUT_INTRINSIC = Layout.INTRINSIC

SIZE_DEFINED_LAYOUTS = (
    LAYOUT_FIXED,
    LAYOUT_FIXED_HEIGHT,
    LAYOUT_RESPONSIVE,
    LAYOUT_FILL,
    LAYOUT_FLEX_ITEM,
    LAYOUT_INTRINSIC,
)


class CSSLengthUnit(Enum):
    """Possible unit strings for a CSS length value."""

    PX = "px"  # noqa: WPS115 (allow caps for Enums)
    EM = "em"  # noqa: WPS115
    REM = "rem"  # noqa: WPS115
    VH = "vh"  # noqa: WPS115
    VW = "vw"  # noqa: WPS115
    VMIN = "vmin"  # noqa: WPS115
    VMAX = "vmax"  # noqa: WPS115


# Store constant for performance
UNIT_PX = CSSLengthUnit.PX


class CSSLength(NamedTuple):
    """A CSS length with numeral and unit."""

    numeral: float
    unit: CSSLengthUnit


CSS_LENGTH_AUTO = "auto"
CSS_LENGTH_ONE_PX = CSSLength(numeral=1, unit=UNIT_PX)


class AMPNode:
    """Store an AMP-specific HTML element."""

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Set up default attributes of an AMP-specific HTML element."""
        self.tag = tag

        self.element_id = None

        self._classes = []
        self._style = ""
        self._is_hidden = False

        self._other_attrs = {}
        self._is_transformed = False

        self.sizer = None
        self.maybe_img_attrs = None

        self.strip_translated_attrs = True

        for attr in attrs:
            if attr[0] == "id":
                self.element_id = attr[1]
            elif attr[0] == "class":
                self._classes = attr[1].split(" ") if attr[1] else []
            elif attr[0] == "style":
                self._style = attr[1] or ""
            elif attr[0] == "hidden":
                self._is_hidden = True
            else:
                # Should be only one value per key
                self._other_attrs[attr[0]] = attr[1]

    def transform(self, next_auto_id: str) -> tuple[list[Translation], bool] | None:
        """Apply the transformation.

        Returns styles that need to be appended to the beginning of the amp-
        custom style section.
        """
        # Create img if necessary
        if self.tag == "amp-img" and "data-hero" in self._other_attrs:
            self._other_attrs["i-amphtml-ssr"] = None
            img_attrs = [
                ("class", "i-amphtml-fill-content i-amphtml-replaced-content"),
                ("decoding", "async"),
            ]

            attrs_to_copy = (
                "alt",
                "attribution",
                "object-fit",
                "object-position",
                "reforiginalerpolicy",
                "src",
                "srcset",
                "sizes",
                "title",
            )
            attrs_to_copy = (attr for attr in attrs_to_copy if attr in self._other_attrs)
            img_attrs.extend((attr, self._other_attrs[attr]) for attr in attrs_to_copy)

            self.maybe_img_attrs = img_attrs

        # Translate special attributes to amp-custom CSS
        css_data = None
        did_strip_sizes = False

        translations = [attr for attr in self._other_attrs if attr in TRANSLATIONS]
        if translations:
            potential_id = self.element_id or next_auto_id

            css_data_items = []
            for attr_to_translate in translations:
                if attr_to_translate == "sizes" and "disable-inline-width" in self._other_attrs:
                    # Sizes is meant to be passed to the img tag for source
                    # selection, but the user didn’t intend for it to have any
                    # side effects. Don’t add any.

                    # https://amp.dev/documentation/guides-and-tutorials/learn/amp-html-layout/?format=websites
                    continue

                attribute_value = self._other_attrs[attr_to_translate]
                translator = TRANSLATIONS[attr_to_translate]

                try:
                    translation = translator.translate(attribute_value, potential_id)
                except ValueError as original:
                    raise TransformationError(
                        f"Invalid value for `{attr_to_translate}` attribute",
                    ) from original
                else:
                    if translation:
                        css_data_items.append(translation)
                        if attr_to_translate == "sizes":
                            # Need to know so we can apply "responsive" layout
                            did_strip_sizes = True

            if css_data_items:
                used_auto_id = False
                if not self.element_id:
                    used_auto_id = True
                    self.element_id = potential_id

                css_data = css_data_items, used_auto_id

            if self.strip_translated_attrs:
                for attr_to_translate in translations:
                    if not (attr_to_translate == "sizes" and not did_strip_sizes):
                        del self._other_attrs[attr_to_translate]

        # Apply the transformation
        layout_value = self._other_attrs.get("layout")

        width = self._parse_length(self._other_attrs.get("width"))
        if not isinstance(width, CSSLength) and layout_value in {None, "fixed"}:
            with contextlib.suppress(KeyError):
                width = {
                    "amp-analytics": CSS_LENGTH_ONE_PX,
                    "amp-audio": CSS_LENGTH_AUTO,
                    "amp-pixel": CSS_LENGTH_ONE_PX,
                    "amp-social-share": CSSLength(numeral=60, unit=UNIT_PX),
                }[self.tag]

        height = self._parse_length(self._other_attrs.get("height"))
        if not isinstance(height, CSSLength) and layout_value in {None, "fixed", "fixed-height"}:
            social_share_height_px = 44
            with contextlib.suppress(KeyError):
                height = {
                    "amp-analytics": CSS_LENGTH_ONE_PX,
                    "amp-audio": CSS_LENGTH_AUTO,
                    "amp-pixel": CSS_LENGTH_ONE_PX,
                    "amp-social-share": CSSLength(numeral=social_share_height_px, unit=UNIT_PX),
                }[self.tag]

        if not layout_value:
            width_is_set = isinstance(width, CSSLength)
            height_is_set = isinstance(height, CSSLength)

            if not width_is_set and not height_is_set:
                layout_value = "container"
            elif height_is_set and not width_is_set:
                layout_value = "fixed_height"
            elif height_is_set and width_is_set and did_strip_sizes:
                layout_value = "responsive"

                # Apply this directly, because otherwise the runtime won't see
                # the `sizes` attribute, and will think the element should be
                # "fixed".
                self._other_attrs["layout"] = layout_value
            else:
                layout_value = "fixed"

        try:
            layout = Layout(layout_value)
        except ValueError as original:
            raise TransformationError("Transformation not supported") from original

        self._classes.append(layout.get_class())
        if layout.is_size_defined():
            self._classes.append("i-amphtml-layout-size-defined")

        if layout == LAYOUT_NODISPLAY:
            self._is_hidden = True

        elif layout == LAYOUT_FIXED:
            if not isinstance(width, CSSLength) or not isinstance(height, CSSLength):
                raise TransformationError("Length and width required for fixed layout")

            self._style = "width:{}{};height:{}{};{}".format(
                str(width[0]).rstrip("0").rstrip("."),
                width[1].value,
                str(height[0]).rstrip("0").rstrip("."),
                height[1].value,
                self._style,
            )

        elif layout == LAYOUT_FIXED_HEIGHT:
            if not isinstance(height, CSSLength):
                raise TransformationError("Length and width required for fixed layout")

            self._style = "height:{}{};{}".format(
                str(height[0]).rstrip("0").rstrip("."),
                height[1].value,
                self._style,
            )

        elif layout == LAYOUT_FLEX_ITEM:
            if isinstance(height, CSSLength):
                self._style = "height:{}{};{}".format(
                    str(height[0]).rstrip("0").rstrip("."),
                    height[1].value,
                    self._style,
                )

            if isinstance(width, CSSLength):
                self._style = "width:{}{};{}".format(
                    str(width[0]).rstrip("0").rstrip("."),
                    width[1].value,
                    self._style,
                )

        self._other_attrs["i-amphtml-layout"] = layout.value

        # Create sizer if necessary
        create_sizer = (
            isinstance(width, CSSLength)
            and isinstance(height, CSSLength)
            and width.numeral != 0
            and width.unit == height.unit
        )
        if create_sizer and isinstance(width, CSSLength) and isinstance(height, CSSLength):
            if layout == LAYOUT_RESPONSIVE:
                padding = (height.numeral / width.numeral) * 100
                style = f"display:block;padding-top:{padding:.4f}%;"
                self.sizer = Sizer(attrs=[("style", style)], maybe_img_attrs=None)

            elif layout == LAYOUT_INTRINSIC:
                svg_string = (
                    '<svg height="{}" width="{}" xmlns="http://www.w3.org/2000/svg"'
                    ' version="1.1"/>'
                )
                svg_string = svg_string.format(height.numeral, width.numeral)

                img_attrs = [
                    ("alt", ""),
                    ("aria-hidden", "true"),
                    ("class", "i-amphtml-intrinsic-sizer"),
                    ("role", "presentation"),
                    ("src", f"data:image/svg+xml;charset=utf-8,{svg_string}"),
                ]

                self.sizer = Sizer(
                    attrs=[("class", "i-amphtml-sizer")],
                    maybe_img_attrs=img_attrs,
                )

        return css_data

    def get_attrs(self) -> list[tuple[str, str | None]]:
        """Return an list of attribute tuples that represents current state.

        This returns different values before and after a call to `transform()`.
        """
        attrs = list(self._other_attrs.items())

        if self.element_id:
            attrs.insert(0, ("id", self.element_id))

        if self._classes:
            attrs.insert(0, ("class", " ".join(self._classes)))

        if self._style:
            attrs.insert(0, ("style", self._style))

        if self._is_hidden:
            attrs.append(("hidden", "hidden"))

        return attrs

    def _parse_length(self, length: str | None) -> CSSLength | str | None:
        """Parse a valid length value.

        Returns a CSSLength, or an alternative constant (CSS_LENGTH_AUTO), or
        None; All are valid results.

        Throws a TransformationError if a valid result can't be parsed.

        This utility function is stateless.
        """
        if not length:
            return None

        if length == "auto":
            return CSS_LENGTH_AUTO

        try:
            match = re.findall(r"(\d+(?:\.\d+)?)(.*)", length)[0]
            numeral = float(match[0])
        except (IndexError, ValueError) as original:
            raise TransformationError("Invalid size value") from original

        unit_value = match[1] or "px"
        try:
            unit = CSSLengthUnit(unit_value)
        except ValueError as original:
            raise TransformationError("Invalid size value") from original

        return CSSLength(numeral=numeral, unit=unit)


RENDER_DELAYING_EXTENSIONS = (
    "amp-dynamic-css-classes",
    # 'amp-experiment',  # we handle this by looking for the tag instead
    "amp-story",
)

ID_PREFIX = "i-amp-"


class AMPRenderer(HTMLParser):
    """A parser to ingest AMP HTML and perform various transformations."""

    def __init__(
        self,
        runtime_styles: str | None,
        runtime_version: str | None,
    ) -> None:
        """Initialize AMPRenderer with runtime styles & version.

        Parameters
        ----------
        runtime_styles : str | None
            The current contents of https://cdn.ampproject.org/v0.css
        runtime_version : str | None
            The version number for the runtime styles as a string
            with leading zeros, e.g. '012007302351001'

        """
        super().__init__()

        self.runtime_styles = runtime_styles
        self.runtime_version = runtime_version

        self._is_test_mode = False
        if not self.runtime_styles or not self.runtime_version:
            self._is_test_mode = True

        self.trim_attrs = False
        self.strip_comments = False

        # Always keep charrefs intact; This class is meant to reproduce HTML.
        self.convert_charrefs = False

    def reset(self) -> None:
        """Reset the state of the renderer so that it can be run again."""
        super().reset()

        self._remove_boilerplate = True

        self._boilerplate = ""
        self._is_in_boilerplate = False
        self._boilerplate_index = None

        self._noscript_boilerplate = ""
        self._is_in_noscript = False
        self._noscript_boilerplate_index = None

        self._is_expecting_experiment_script = False
        self._is_expecting_experiment_data = False
        self._is_expecting_experiment_end = False
        self._current_experiment_data = ""

        self._is_render_paused = False
        self._is_render_cancelled = False

        self._result = []
        self._found_custom_element = False
        self._next_auto_id_num = 0
        self._translated_css_data = []

        self._translated_styles_index = None

        with contextlib.suppress(AttributeError):
            del self.no_boilerplate

    def handle_decl(self, decl: str) -> None:
        """Process a declaration string."""
        self._result.append(f"<!{decl.lower()}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Process a start tag."""
        tag = tag.lower()

        if self._is_expecting_experiment_data:
            # Expecting some JSON, found a start tag == NO EXPERIMENT
            self._apply_experiment_data()

        if self._is_expecting_experiment_script:
            self._is_expecting_experiment_script = False

            if tag == "script":
                for attr in attrs:
                    if attr[0] == "type" and attr[1] == "application/json":
                        # Expecting script & found it; Next, we expect some
                        # JSON data.
                        self._is_expecting_experiment_data = True

        if self._is_expecting_experiment_end:
            # Expecting </amp-experiment>, found a start tag == NO EXPERIMENT
            self._is_expecting_experiment_end = False

        if tag == "noscript":
            self._is_in_noscript = True

        if tag == "style" and "amp-boilerplate" in {attribute[0] for attribute in attrs}:
            self._is_in_boilerplate = True

            # Add appropriate boilerplate placeholder
            if self._is_in_noscript and self._noscript_boilerplate_index is None:
                self._noscript_boilerplate_index = len(self._result)
            elif self._boilerplate_index is None:
                self._boilerplate_index = len(self._result)

            return

        safe_attrs = attrs

        if tag == "html":
            if "i-amphtml-layout" in {attribute[0] for attribute in attrs}:
                # A simple check to see if it’s transformed already
                self._is_render_cancelled = True
            else:
                html_attrs = [("i-amphtml-layout", None), ("i-amphtml-no-boilerplate", None)]
                if not self._is_test_mode:
                    html_attrs.append(("transformed", "self;v=1"))

                safe_attrs.extend(html_attrs)

        if tag in {"template", "script"}:
            # Don't render amp-* elements inside of `template` or `script`
            self._is_render_paused = True

            if tag == "script":
                for attr in attrs:
                    if attr[0] == "custom-element" and attr[1] in RENDER_DELAYING_EXTENSIONS:
                        # Don’t remove boilerplate if one of the render-
                        # delaying extensions is included.
                        self._remove_boilerplate = False

        sizer = None
        maybe_img_attrs = None
        is_amp_element = (
            not self._is_render_cancelled
            and not self._is_render_paused
            and tag.startswith("amp-")
            and "data-norender" not in {attribute[0] for attribute in attrs}
        )

        if tag == "amp-audio":
            # Don’t remove boilerplate if `amp-audio` is included
            self._remove_boilerplate = False

        elif is_amp_element:
            if tag == "amp-experiment":
                # Start the finite automata to see if we need to keep the
                # boilerplate.
                self._is_expecting_experiment_script = True

            amp_element = AMPNode(tag, attrs)

            try:
                transformation = amp_element.transform(self._get_next_auto_id())
            except TransformationError:
                self._remove_boilerplate = False
            else:
                if transformation:
                    translations, used_auto_id = transformation
                    self._translated_css_data.extend(translations)

                    if used_auto_id:
                        # We had to generate an ID for this element
                        self._increment_auto_id_num()

            safe_attrs = amp_element.get_attrs()
            sizer = amp_element.sizer
            maybe_img_attrs = amp_element.maybe_img_attrs

        # Turn attribute data in to strings
        attr_strings = []
        for attr in safe_attrs:
            attr_name = attr[0].lower()
            if attr[1] is None:
                attr_strings.append(f" {attr_name}")
            else:
                value = str(attr[1])
                if self.trim_attrs:
                    value = value.strip()
                value = value.replace('"', "&quot;")
                attr_strings.append(f' {attr_name}="{value}"')

        if self._is_test_mode:
            # Sort alphabetically for diffing
            attr_strings.sort()

        attr_string = "".join(attr_strings)

        self._result.append(f"<{tag}{attr_string}>")

        # Add sizer if necessary
        if sizer:
            sizer_attr_strings = []
            for attr in sizer[0]:
                attr_name = attr[0].lower()
                if attr[1] is None:
                    sizer_attr_strings.append(f" {attr_name}")
                else:
                    value = str(attr[1])
                    value = value.replace('"', "&quot;")
                    sizer_attr_strings.append(f' {attr_name}="{value}"')
            sizer_attr_string = "".join(sizer_attr_strings)

            self._result.append(f"<i-amphtml-sizer{sizer_attr_string}>")

            if sizer[1] is not None:
                img_attr_strings = []
                for attr in sizer[1]:
                    attr_name = attr[0].lower()
                    if attr[1] is None:
                        img_attr_strings.append(f" {attr_name}")
                    else:
                        value = str(attr[1])
                        value = value.replace('"', "&quot;")
                        img_attr_strings.append(f' {attr_name}="{value}"')
                img_attr_string = "".join(img_attr_strings)

                self._result.append(f"<img{img_attr_string}>")

            self._result.append("</i-amphtml-sizer>")

        # Add img if necessary
        if maybe_img_attrs:
            img_attr_strings = []
            for attr in maybe_img_attrs:
                attr_name = attr[0].lower()
                if attr[1] is None:
                    img_attr_strings.append(f" {attr_name}")
                else:
                    value = str(attr[1])
                    value = value.replace('"', "&quot;")
                    img_attr_strings.append(f' {attr_name}="{value}"')
            img_attr_string = "".join(img_attr_strings)

            self._result.append(f"<img{img_attr_string}>")

        # Add runtime styles if necessary
        if tag == "head" and not self._is_render_cancelled:
            if self._is_test_mode:
                # AMP Optimizer uses a stub like this, and then replaces it
                # later. Use a stub so we can test against their expected
                # output.
                style = "<style amp-runtime></style>"
            else:
                style = (
                    "<style amp-runtime"
                    f' i-amphtml-version="{self.runtime_version}">{self.runtime_styles}</style>'
                )
            self._result.append(style)

        if tag == "style":
            # Insert a placeholder into <style amp-custom> so we can add in
            # the transformed styles later.
            has_custom_element = (
                "amp-custom" in {attribute[0] for attribute in attrs}
                and self._translated_styles_index is None
            )
            if has_custom_element:
                self._found_custom_element = True
                self._translated_styles_index = len(self._result)

    def handle_endtag(self, tag: str) -> None:
        """Process a closing tag."""
        tag = tag.lower()

        if self._is_expecting_experiment_data:
            # Finish ingesting JSON data
            json_data_string = self._apply_experiment_data()

            if tag == "script":
                try:
                    # If valid JSON...
                    json_data = json.loads(json_data_string)
                except ValueError:
                    pass
                else:
                    # If data wasn’t empty...
                    if json_data:
                        self._is_expecting_experiment_end = True

        elif self._is_expecting_experiment_script:
            self._is_expecting_experiment_script = False

        elif self._is_expecting_experiment_end:
            # If successful experiment and only one child of node, then there
            # is an experiment active and the boilerplate can't be removed.
            self._is_expecting_experiment_end = False

            if tag == "amp-experiment":
                self._remove_boilerplate = False

        if tag == "noscript":
            self._is_in_noscript = False

        if tag == "style" and self._is_in_boilerplate:
            self._is_in_boilerplate = False
            return

        is_missing_custom_element = (
            tag == "head"
            and not self._found_custom_element
            and self._translated_styles_index is None
        )
        if is_missing_custom_element:
            # If there was no custom element found in the head, add the
            # placeholder at the end in case we have custom styles to add
            # later. `self._found_custom_element` will remain False, and we’ll
            # inspect that later to decide whether the <script> element itself
            # needs to be added.
            self._translated_styles_index = len(self._result)

        if tag in {"template", "script"}:
            self._is_render_paused = False

        self._result.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:  # noqa: WPS110 (match HTMLParser signature)
        """Process HTML data."""
        self._add_data(data)

    def handle_entityref(self, name: str) -> None:
        """Process an HTML entity."""
        self._add_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        """Process a numbered HTML entity."""
        self._add_data(f"&#{name};")

    def handle_comment(self, data: str) -> None:  # noqa: WPS110 (match HTMLParser signature)
        """Process an HTML comment."""
        if not self.strip_comments:
            self._result.append(f"<!--{data}-->")

    def render(self, amp_html: str) -> str:
        """Run the server-side-rendering routine."""
        self.reset()

        self._auto_id_nums_to_ignore = []

        conflict_ids = re.findall(f"id=['\"]?{ID_PREFIX}([0-9]+)['\"]?", amp_html)
        for conflict_id in conflict_ids:
            self._auto_id_nums_to_ignore.append(int(conflict_id))

        self.feed(amp_html)
        self.close()

        # Combine translated styles by media query and value when possible
        media_batches = OrderedDict()

        for selector, statements in self._translated_css_data:
            media_batch_key = tuple(statements.keys())
            batch = media_batches.get(media_batch_key) or OrderedDict()

            for query, statement_value in statements.items():
                value_dict = batch.get(query) or OrderedDict()

                selector_list = value_dict.get(statement_value) or []
                selector_list.append(selector)
                value_dict[statement_value] = selector_list

                batch[query] = value_dict

            media_batches[media_batch_key] = batch

        css_parts = []
        for batch in media_batches.values():
            for query, values in batch.items():
                parts = []

                for key, value in values.items():
                    css_selector = ",".join(value)
                    parts.append(f"{css_selector}{{{key}}}")

                css = "".join(parts)
                if query:
                    css = f"@media {query}{{{css}}}"

                css_parts.append(css)

        style_string = "".join(css_parts)

        if style_string and not self._found_custom_element:
            # Insert the amp-custom tag if necessary
            style_string = f"<style amp-custom>{style_string}</style>"

        if self._translated_styles_index is not None:
            self._result.insert(self._translated_styles_index, style_string)

            if (
                self._boilerplate_index is not None
                and self._translated_styles_index <= self._boilerplate_index
            ):
                self._boilerplate_index += 1

            if (
                self._noscript_boilerplate_index is not None
                and self._translated_styles_index <= self._noscript_boilerplate_index
            ):
                self._noscript_boilerplate_index += 1

        self.no_boilerplate = True
        if self._is_render_cancelled or not self._remove_boilerplate:
            self.no_boilerplate = False

            # Restore the boilerplate
            if self._boilerplate_index is not None:
                boilerplate = f"<style amp-boilerplate>{self._boilerplate}</style>"
                self._result.insert(self._boilerplate_index, boilerplate)

                if (
                    self._noscript_boilerplate_index is not None
                    and self._boilerplate_index <= self._noscript_boilerplate_index
                ):
                    self._noscript_boilerplate_index += 1

            if self._noscript_boilerplate_index is not None:
                noscript_boilerplate = (
                    f"<style amp-boilerplate>{self._noscript_boilerplate}</style>"
                )
                self._result.insert(self._noscript_boilerplate_index, noscript_boilerplate)

        result = "".join(self._result)

        if self._is_render_cancelled or not self._remove_boilerplate:
            result = result.replace(" i-amphtml-no-boilerplate", "")

        # Remove empty noscript tags; This happens when removing boilerplate
        return result.replace("<noscript></noscript>", "")

    def _add_data(self, html_data: str) -> None:
        if self._is_in_boilerplate:
            if self._is_in_noscript:
                self._noscript_boilerplate += html_data
                return

            self._boilerplate += html_data
            return

        if self._is_expecting_experiment_data:
            self._current_experiment_data += html_data
            return

        self._result.append(html_data)

    def _get_next_auto_id(self) -> str:
        return ID_PREFIX + str(self._next_auto_id_num)

    def _increment_auto_id_num(self) -> None:
        self._next_auto_id_num += 1
        while self._next_auto_id_num in self._auto_id_nums_to_ignore:
            self._next_auto_id_num += 1

    def _apply_experiment_data(self) -> str:
        self._result.append(self._current_experiment_data)

        experiment_data = self._current_experiment_data

        self._current_experiment_data = ""
        self._is_expecting_experiment_data = False

        return experiment_data

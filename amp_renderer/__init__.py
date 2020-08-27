# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals

# Standard Library
import json
import re
import sys
from builtins import bytes  # noqa
from builtins import str  # noqa
from collections import OrderedDict, namedtuple
from enum import Enum

if sys.version_info[0] < 3:
    # Third Party
    from HTMLParser import HTMLParser

else:
    # Standard Library
    from html.parser import HTMLParser


class AMPNode:
    class TransformationError(Exception):
        pass

    class Translator:
        Translation = namedtuple('Translation', 'selector statements')

        @classmethod
        def parse_sizes(cls, value):
            # Normalize whitespace
            size_values = re.split(r'\s*,\s*', value.strip())

            try:
                default = size_values.pop()
            except IndexError:
                return ''

            Sizes = namedtuple('Size', 'default other')  # noqa
            sizes = Sizes(default=default, other=[])

            Media = namedtuple('Media', 'query value')  # noqa
            for size_value in size_values:
                size_parts = re.split(r'\)\s+', size_value)
                if len(size_parts) != 2:
                    raise ValueError('Invalid sizes definition')

                query = '{})'.format(size_parts[0])
                query = query.replace(r'\s+', '')
                value = size_parts[1]

                media = Media(query=query, value=value)
                sizes.other.append(media)

            return sizes

    class MediaTranslator(Translator):
        @classmethod
        def translate(cls, value, element_id):
            # Normalize whitespace
            media = re.sub(r'\s+', ' ', value).strip()

            if not media:
                return None

            if media[0] == '(':
                media = 'all and {}'.format(media)

            if media.startswith('not '):
                media = media[4:]
            else:
                media = 'not {}'.format(media)

            selector = '#{}'.format(element_id)

            return cls.Translation(
                selector=selector,
                statements=OrderedDict([
                    (media, 'display:none'),
                ]))

    class SizesTranslator(Translator):
        @classmethod
        def translate(cls, value, element_id):
            sizes = cls.parse_sizes(value)

            selector = '#{}'.format(element_id)

            statements = [(None, 'width:{}'.format(sizes.default))]

            other_sizes = sizes.other

            """The user agent will pick a width from the sizes attribute,
            using the first item with a <media-condition> (the part in
            parentheses) that evaluates to true. This means, we have to
            reverse the order the media queries in CSS to emulate this
            behavior (the last definition has precedence)."""
            other_sizes.reverse()

            for size in other_sizes:
                statements.append((size.query, 'width:{}'.format(size.value)))

            return cls.Translation(
                selector=selector,
                statements=OrderedDict(statements))

    class HeightsTranslator(Translator):
        @classmethod
        def translate(cls, value, element_id):
            sizes = cls.parse_sizes(value)

            selector = '#{}>:first-child'.format(element_id)

            statements = [(None, 'padding-top:{}'.format(sizes.default))]

            other_sizes = sizes.other

            """The user agent will pick a value from the heights attribute,
            using the first item with a <media-condition> (the part in
            parentheses) that evaluates to true. This means, we have to
            reverse the order the media queries in CSS to emulate this
            behavior (the last definition has precedence)."""
            other_sizes.reverse()
            for size in other_sizes:
                statements.append((size.query, 'padding-top:{}'.format(size.value)))

            return cls.Translation(
                selector=selector,
                statements=OrderedDict(statements))

    TRANSLATIONS = {
        'media': MediaTranslator,
        'sizes': SizesTranslator,
        'heights': HeightsTranslator,
    }

    class Layout(Enum):
        NODISPLAY = 'nodisplay'
        FIXED = 'fixed'
        FIXED_HEIGHT = 'fixed-height'
        RESPONSIVE = 'responsive'
        CONTAINER = 'container'
        FILL = 'fill'
        FLEX_ITEM = 'flex-item'
        INTRINSIC = 'intrinsic'

        def get_class(self):
            return 'i-amphtml-layout-{}'.format(self.value)

        def is_size_defined(self):
            return self in [
                self.FIXED,
                self.FIXED_HEIGHT,
                self.RESPONSIVE,
                self.FILL,
                self.FLEX_ITEM,
                self.INTRINSIC,
            ]

    class CSSLengthUnit(Enum):
        PX = 'px'
        EM = 'em'
        REM = 'rem'
        VH = 'vh'
        VW = 'vw'
        VMIN = 'vmin'
        VMAX = 'vmax'

    CSSLength = namedtuple('CSSLength', 'numeral unit')
    CSS_LENGTH_AUTO = 'auto'
    CSS_LENGTH_ONE_PX = CSSLength(numeral=1, unit=CSSLengthUnit.PX)

    def __init__(self, tag, attrs):
        self.tag = tag

        self.id = None

        self._classes = []
        self._style = ''
        self._is_hidden = False

        self._other_attrs = {}
        self._is_transformed = False

        self.sizer = None
        self.maybe_img_attrs = None

        self.should_strip_translated_attrs = True

        for attr in attrs:
            if attr[0] == 'id':
                self.id = attr[1]
            elif attr[0] == 'class':
                self._classes = attr[1].split(' ')
            elif attr[0] == 'style':
                self._style = attr[1]
            elif attr[0] == 'hidden':
                self._is_hidden = True
            else:
                # Should be only one value per key
                self._other_attrs[attr[0]] = attr[1]

    def _parse_length(self, length):
        """Parse a valid length value.

        Returns a CSSLength, or an alternative constant (CSS_LENGTH_AUTO),
        or None; All are valid results.

        Throws a TransformationError if a valid result can't be parsed.

        This utility function is stateless.
        """
        if not length:
            return None

        if length == 'auto':
            return self.CSS_LENGTH_AUTO

        try:
            match = re.findall(r'(\d+(?:\.\d+)?)(.*)', length)[0]
            numeral = float(match[0])
        except (IndexError, ValueError):
            raise self.TransformationError('Invalid size value')

        unit_value = match[1] or 'px'
        try:
            unit = self.CSSLengthUnit(unit_value)
        except ValueError:
            raise self.TransformationError('Invalid size value')

        return self.CSSLength(numeral=numeral, unit=unit)

    def transform(self, next_auto_id):
        """Apply the transformation.

        Returns styles that need to be appended to the beginning of the
        amp-custom style section.
        """
        # Create img if necessary
        if self.tag == 'amp-img' and 'data-hero' in self._other_attrs:
            self._other_attrs['i-amphtml-ssr'] = None
            img_attrs = [
                ('class', 'i-amphtml-fill-content i-amphtml-replaced-content'),
                ('decoding', 'async'),
            ]

            attrs_to_copy = [
                'alt',
                'attribution',
                'object-fit',
                'object-position',
                'referrerpolicy',
                'src',
                'srcset',
                'sizes',
                'title',
            ]
            for name in [k for k in attrs_to_copy if k in self._other_attrs]:
                img_attrs.append((name, self._other_attrs[name]))

            self.maybe_img_attrs = img_attrs

        # Translate special attributes to amp-custom CSS
        css_data = None
        did_strip_sizes = False

        translations = [k for k in self._other_attrs if k in self.TRANSLATIONS]
        if translations:
            potential_id = self.id or next_auto_id

            css_data_items = []
            for t in translations:
                if t == 'sizes' and 'disable-inline-width' in self._other_attrs:
                    """Sizes is meant to be passed to the img tag for source
                    selection, but the user didn’t intend for it to have any
                    side effects. Don’t add any.

                    https://amp.dev/documentation/guides-and-tutorials/learn/amp-html-layout/?format=websites  # noqa
                    """
                    continue

                attribute_value = self._other_attrs[t]
                Translator = self.TRANSLATIONS[t]  # noqa

                try:
                    translation = Translator.translate(attribute_value, potential_id)
                except ValueError:
                    raise self.TransformationError('Invalid value for `{}` attribute'.format(t))
                else:
                    if translation:
                        css_data_items.append(translation)
                        if t == 'sizes':
                            # Need to know so we can apply "responsive" layout
                            did_strip_sizes = True

            if css_data_items:
                used_auto_id = False
                if not self.id:
                    used_auto_id = True
                    self.id = potential_id

                css_data = css_data_items, used_auto_id

            if self.should_strip_translated_attrs:
                for t in translations:
                    del self._other_attrs[t]

        # Apply the transformation
        layout_value = self._other_attrs.get('layout')

        width = self._parse_length(self._other_attrs.get('width'))
        if not isinstance(width, self.CSSLength) and layout_value in [None, 'fixed']:
            try:
                width = {
                    'amp-analytics': self.CSS_LENGTH_ONE_PX,
                    'amp-audio': self.CSS_LENGTH_AUTO,
                    'amp-pixel': self.CSS_LENGTH_ONE_PX,
                    'amp-social-share': self.CSSLength(numeral=60, unit=self.CSSLengthUnit.PX),
                }[self.tag]
            except KeyError:
                pass

        height = self._parse_length(self._other_attrs.get('height'))
        if not isinstance(height, self.CSSLength) and layout_value in [None, 'fixed', 'fixed-height']:
            try:
                height = {
                    'amp-analytics': self.CSS_LENGTH_ONE_PX,
                    'amp-audio': self.CSS_LENGTH_AUTO,
                    'amp-pixel': self.CSS_LENGTH_ONE_PX,
                    'amp-social-share': self.CSSLength(numeral=44, unit=self.CSSLengthUnit.PX),
                }[self.tag]
            except KeyError:
                pass

        if not layout_value:
            width_is_set = isinstance(width, self.CSSLength)
            height_is_set = isinstance(height, self.CSSLength)

            if not any([width_is_set, height_is_set]):
                layout_value = 'container'
            elif height_is_set and not width_is_set:
                layout_value = 'fixed_height'
            elif height_is_set and width_is_set and did_strip_sizes:
                layout_value = 'responsive'
            else:
                layout_value = 'fixed'

        try:
            layout = self.Layout(layout_value)
        except ValueError:
            raise self.TransformationError('Transformation not supported')

        self._classes.append(layout.get_class())
        if layout.is_size_defined():
            self._classes.append('i-amphtml-layout-size-defined')

        if layout == self.Layout.NODISPLAY:
            self._is_hidden = True

        elif layout == self.Layout.FIXED:
            if not all(isinstance(length, self.CSSLength) for length in [width, height]):
                raise self.TransformationError('Length and width required for fixed layout')

            self._style = 'width:{wn}{wu};height:{hn}{hu};{existing_style}'.format(
                wn=str(width.numeral).rstrip('0').rstrip('.'),
                wu=width.unit.value,
                hn=str(height.numeral).rstrip('0').rstrip('.'),
                hu=height.unit.value,
                existing_style=self._style)

        elif layout == self.Layout.FIXED_HEIGHT:
            if not isinstance(height, self.CSSLength):
                raise self.TransformationError('Length and width required for fixed layout')

            self._style = 'height:{numeral}{unit};{existing_style}'.format(
                numeral=str(height.numeral).rstrip('0').rstrip('.'),
                unit=height.unit.value,
                existing_style=self._style)

        elif layout == self.Layout.FLEX_ITEM:
            if isinstance(height, self.CSSLength):
                self._style = 'height:{numeral}{unit};{existing_style}'.format(
                    numeral=str(height.numeral).rstrip('0').rstrip('.'),
                    unit=height.unit.value,
                    existing_style=self._style)

            if isinstance(width, self.CSSLength):
                self._style = 'width:{numeral}{unit};{existing_style}'.format(
                    numeral=str(width.numeral).rstrip('0').rstrip('.'),
                    unit=width.unit.value,
                    existing_style=self._style)

        self._other_attrs['i-amphtml-layout'] = layout.value

        # Create sizer if necessary
        if all(isinstance(length, self.CSSLength) for length in [width, height]):
            if all([width.numeral != 0, width.unit == height.unit]):
                Sizer = namedtuple('Sizer', 'attrs maybe_img_attrs')

                if layout == self.Layout.RESPONSIVE:
                    padding = (height.numeral / width.numeral) * 100
                    style = 'display:block;padding-top:{:.4f}%;'.format(padding)
                    self.sizer = Sizer(attrs=[('style', style)], maybe_img_attrs=None)

                elif layout == self.Layout.INTRINSIC:
                    svg_string = '<svg height="{h}" width="{w}" xmlns="http://www.w3.org/2000/svg" version="1.1"/>'
                    svg_string = svg_string.format(height.numeral, width.numeral)

                    img_attrs = [
                        ('alt', ''),
                        ('aria-hidden', 'true'),
                        ('class', 'i-amphtml-intrinsic-sizer'),
                        ('role', 'presentation'),
                        ('src', 'data:image/svg+xml;charset=utf-8,{}'.format(svg_string)),
                    ]

                    self.sizer = Sizer(attrs=[('class', 'i-amphtml-sizer')], maybe_img_attrs=img_attrs)

        return css_data

    def get_attrs(self):
        """Return an list of attribute tuples that represents current state.

        This returns different values before and after a call to `transform()`.
        """
        attrs = list(self._other_attrs.items())

        if self.id:
            attrs.insert(0, ('id', self.id))

        if self._classes:
            attrs.insert(0, ('class', ' '.join(self._classes)))

        if self._style:
            attrs.insert(0, ('style', self._style))

        if self._is_hidden:
            attrs.append(('hidden', 'hidden'))

        return attrs


class AMPRenderer(HTMLParser, object):
    """A parser to ingest AMP HTML and perform various transformations."""

    # These are added in where found, and removed during cleanup.
    TRANSLATED_STYLES_PLACEHOLDER = '/* style-amp-custom-translated */'
    BOILERPLATE_PLACEHOLDER = '/* style-amp-boilerplate */'
    NOSCRIPT_BOILERPLATE_PLACEHOLDER = '/* style-amp-boilerplate-noscript */'

    RENDER_DELAYING_EXTENSIONS = [
        'amp-dynamic-css-classes',
        # 'amp-experiment',  # we handle this by looking for the tag instead
        'amp-story',
    ]

    ID_PREFIX = 'i-amp-'

    def __init__(self, runtime_styles, runtime_version, *args, **kwargs):
        """Initialize AMPRenderer with runtime styles & version.

        Parameters:
            runtime_styles (string): The current contents of
                                     https://cdn.ampproject.org/v0.css

            runtime_version (string): The version number for the runtime
                                      styles as a string with leading zeros,
                                      e.g. '012007302351001'

        """
        super(AMPRenderer, self).__init__(*args, **kwargs)

        self.runtime_styles = runtime_styles
        self.runtime_version = runtime_version

        self._is_test_mode = False
        if not self.runtime_styles or not self.runtime_version:
            self._is_test_mode = True

        self.should_trim_attrs = False
        self.should_strip_comments = False

        # Always keep charrefs intact; This class is meant to reproduce HTML.
        self.convert_charrefs = False

    def reset(self):
        super(AMPRenderer, self).reset()

        self._should_remove_boilerplate = True

        self._boilerplate = ''
        self._is_in_boilerplate = False

        self._noscript_boilerplate = ''
        self._is_in_noscript = False

        self._is_expecting_experiment_script = False
        self._is_expecting_experiment_data = False
        self._is_expecting_experiment_end = False
        self._current_experiment_data = ''

        self._is_render_paused = False
        self._is_render_cancelled = False

        self._result = ''
        self._found_custom_element = False
        self._next_auto_id_num = 0
        self._translated_css_data = []

        try:
            del self.no_boilerplate
        except AttributeError:
            pass

    def _get_next_auto_id(self):
        return '{}{}'.format(self.ID_PREFIX, self._next_auto_id_num)

    def _increment_auto_id_num(self):
        self._next_auto_id_num += 1
        while self._next_auto_id_num in self._auto_id_nums_to_ignore:
            self._next_auto_id_num += 1

    def _apply_experiment_data(self):
        self._result = '{}{}'.format(self._result, self._current_experiment_data)

        experiment_data = self._current_experiment_data

        self._current_experiment_data = ''
        self._is_expecting_experiment_data = False

        return experiment_data

    def handle_decl(self, decl):
        self._result = '{}<!{}>'.format(self._result, decl.lower())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if self._is_expecting_experiment_data:
            # Expecting some JSON, found a start tag == NO EXPERIMENT
            self._apply_experiment_data()

        if self._is_expecting_experiment_script:
            self._is_expecting_experiment_script = False

            if tag == 'script':
                for attr in attrs:
                    if attr[0] == 'type' and attr[1] == 'application/json':
                        """Expecting script & found it; Next, we expect some
                        JSON data"""
                        self._is_expecting_experiment_data = True

        if self._is_expecting_experiment_end:
            # Expecting </amp-experiment>, found a start tag == NO EXPERIMENT
            self._is_expecting_experiment_end = False

        if tag == 'noscript':
            self._is_in_noscript = True

        if tag == 'style':
            if 'amp-boilerplate' in (attr[0] for attr in attrs):
                self._is_in_boilerplate = True

                # Add appropriate boilerplate placeholder
                if self._is_in_noscript and self.NOSCRIPT_BOILERPLATE_PLACEHOLDER not in self._result:
                    self._result = '{}{}'.format(self._result, self.NOSCRIPT_BOILERPLATE_PLACEHOLDER)
                elif self.BOILERPLATE_PLACEHOLDER not in self._result:
                    self._result = '{}{}'.format(self._result, self.BOILERPLATE_PLACEHOLDER)

                return

        safe_attrs = attrs

        if tag == 'html':
            if 'i-amphtml-layout' in (attr[0] for attr in attrs):
                # A simple check to see if it’s transformed already
                self._is_render_cancelled = True
            else:
                html_attrs = [('i-amphtml-layout', None), ('i-amphtml-no-boilerplate', None)]
                if not self._is_test_mode:
                    html_attrs.append(('transformed', 'self;v=1'))

                safe_attrs.extend(html_attrs)

        if tag in ['template', 'script']:
            # Don't render amp-* elements inside of `template` or `script`
            self._is_render_paused = True

            if tag == 'script':
                for attr in attrs:
                    if attr[0] == 'custom-element' and attr[1] in self.RENDER_DELAYING_EXTENSIONS:
                        """Don’t remove boilerplate if one of the render-
                        delaying extensions is included"""
                        self._should_remove_boilerplate = False

        sizer = None
        maybe_img_attrs = None
        if tag == 'amp-audio':
            # Don’t remove boilerplate if `amp-audio` is included
            self._should_remove_boilerplate = False

        elif not self._is_render_cancelled and not self._is_render_paused and tag.startswith('amp-'):
            if tag == 'amp-experiment':
                """Start the finite automata to see if we need to keep the
                boilerplate"""
                self._is_expecting_experiment_script = True

            amp_element = AMPNode(tag, attrs)

            try:
                transformation = amp_element.transform(self._get_next_auto_id())
            except AMPNode.TransformationError:
                self._should_remove_boilerplate = False
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
            if attr[1] is not None:
                value = str(attr[1])
                if self.should_trim_attrs:
                    value = value.strip()
                value = value.replace('"', '&quot;')
                attr_strings.append(' {}="{}"'.format(attr[0].lower(), value))
            else:
                attr_strings.append(' {}'.format(attr[0].lower()))

        if self._is_test_mode:
            # Sort alphabetically for diffing
            attr_strings.sort()

        attr_string = ''.join(attr_strings)

        self._result = '{}<{}{}>'.format(self._result, tag, attr_string)

        # Add sizer if necessary
        if sizer:
            sizer_attr_strings = []
            for attr in sizer.attrs:
                if attr[1] is not None:
                    value = str(attr[1])
                    value = value.replace('"', '&quot;')
                    sizer_attr_strings.append(' {}="{}"'.format(attr[0].lower(), value))
                else:
                    sizer_attr_strings.append(' {}'.format(attr[0].lower()))
            sizer_attr_string = ''.join(sizer_attr_strings)

            self._result = '{}<i-amphtml-sizer{}>'.format(self._result, sizer_attr_string)

            if sizer.maybe_img_attrs is not None:
                img_attr_strings = []
                for attr in sizer.attrs:
                    if attr[1] is not None:
                        value = str(attr[1])
                        value = value.replace('"', '&quot;')
                        img_attr_strings.append(' {}="{}"'.format(attr[0].lower(), value))
                    else:
                        img_attr_strings.append(' {}'.format(attr[0].lower()))
                img_attr_string = ''.join(img_attr_strings)

                self._result = '{}<img{}>'.format(self._result, img_attr_string)

            self._result = '{}</i-amphtml-sizer>'.format(self._result)

        # Add img if necessary
        if maybe_img_attrs:
            img_attr_strings = []
            for attr in maybe_img_attrs:
                if attr[1] is not None:
                    value = str(attr[1])
                    value = value.replace('"', '&quot;')
                    img_attr_strings.append(' {}="{}"'.format(attr[0].lower(), value))
                else:
                    img_attr_strings.append(' {}'.format(attr[0].lower()))
            img_attr_string = ''.join(img_attr_strings)

            self._result = '{}<img{}>'.format(self._result, img_attr_string)

        # Add runtime styles if necessary
        if tag == 'head' and not self._is_render_cancelled:
            if self._is_test_mode:
                """AMP Optimizer uses a stub like this, and then replaces it
                later. Use a stub so we can test against their expected
                output."""
                style = '<style amp-runtime></style>'
            else:
                style = '<style amp-runtime i-amphtml-version="{}">{}</style>'.format(
                    self.runtime_version,
                    self.runtime_styles)
            self._result = '{}{}'.format(self._result, style)

        if tag == 'style':
            """Insert a placeholder into <style amp-custom> so we can add in
            the transformed styles later."""
            if 'amp-custom' in (attr[0] for attr in attrs) and self.TRANSLATED_STYLES_PLACEHOLDER not in self._result:
                self._found_custom_element = True
                self._result = '{}{}'.format(self._result, self.TRANSLATED_STYLES_PLACEHOLDER)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if self._is_expecting_experiment_data:
            # Finish ingesting JSON data
            data = self._apply_experiment_data()

            if tag == 'script':
                try:
                    # If valid JSON...
                    json_data = json.loads(data)
                except ValueError:
                    pass
                else:
                    # If data wasn’t empty...
                    if json_data:
                        self._is_expecting_experiment_end = True

        elif self._is_expecting_experiment_script:
            self._is_expecting_experiment_script = False

        elif self._is_expecting_experiment_end:
            """If successful experiment and only one child of node, then
            there is an experiment active and the boilerplate can't be
            removed."""
            self._is_expecting_experiment_end = False

            if tag == 'amp-experiment':
                self._should_remove_boilerplate = False

        if tag == 'noscript':
            self._is_in_noscript = False

        if tag == 'style' and self._is_in_boilerplate:
            self._is_in_boilerplate = False
            return

        if tag == 'head' and not self._found_custom_element and self.TRANSLATED_STYLES_PLACEHOLDER not in self._result:
            """If there was no custom element found in the head, add the
            placeholder at the end in case we have custom styles to add later.

            self._found_custom_element will remain False, and we’ll inspect
            that later to decide whether the <script> element itself needs to
            be added."""
            self._result = '{}{}'.format(self._result, self.TRANSLATED_STYLES_PLACEHOLDER)

        if tag in ['template', 'script']:
            self._is_render_paused = False

        self._result = '{}</{}>'.format(self._result, tag)

    def _add_data(self, data):
        if self._is_in_boilerplate:
            if self._is_in_noscript:
                self._noscript_boilerplate = '{}{}'.format(self._noscript_boilerplate, data)
                return

            self._boilerplate = '{}{}'.format(self._boilerplate, data)
            return

        if self._is_expecting_experiment_data:
            self._current_experiment_data = '{}{}'.format(self._current_experiment_data, data)
            return

        self._result = '{}{}'.format(self._result, data)

    def handle_data(self, data):
        self._add_data(data)

    def handle_entityref(self, name):
        self._add_data('&{};'.format(name))

    def handle_charref(self, name):
        self._add_data('&#{};'.format(name))

    def handle_comment(self, data):
        if not self.should_strip_comments:
            self._result = '{}<!--{}-->'.format(self._result, data)

    def render(self, data):
        self.reset()

        self._auto_id_nums_to_ignore = []

        conflict_ids = re.findall(r"""id=['"]?{}([0-9]+)['"]?""".format(self.ID_PREFIX), data)
        for conflict_id in conflict_ids:
            self._auto_id_nums_to_ignore.append(int(conflict_id))

        self.feed(data)
        self.close()

        # Combine translated styles by media query and value when possible
        media_batches = OrderedDict()

        for css_data in self._translated_css_data:
            selector = css_data.selector
            statements = css_data.statements

            media_batch_key = tuple(statements.keys())
            batch = media_batches.get(media_batch_key) or OrderedDict()

            for query in statements:
                value_dict = batch.get(query) or OrderedDict()

                value_key = statements[query]
                selector_list = value_dict.get(value_key) or []
                selector_list.append(selector)
                value_dict[value_key] = selector_list

                batch[query] = value_dict

            media_batches[media_batch_key] = batch

        css_parts = []
        for key in media_batches:
            batch = media_batches[key]

            for query in batch:
                parts = []

                for value in batch[query]:
                    selector = ','.join(batch[query][value])
                    parts.append('{s}{{{v}}}'.format(s=selector, v=value))

                css = ''.join(parts)
                if query:
                    css = '@media {q}{{{css}}}'.format(q=query, css=css)

                css_parts.append(css)

        style_string = ''.join(css_parts)

        if style_string and not self._found_custom_element:
            # Insert the amp-custom tag if necessary
            style_string = '<style amp-custom>{}</style>'.format(style_string)

        self._result = self._result.replace(self.TRANSLATED_STYLES_PLACEHOLDER, style_string)

        boilerplate = ''
        noscript_boilerplate = ''

        self.no_boilerplate = True
        if self._is_render_cancelled or not self._should_remove_boilerplate:
            self.no_boilerplate = False

            # Restore the boilerplate
            boilerplate = '<style amp-boilerplate>{}</style>'.format(self._boilerplate)
            noscript_boilerplate = '<style amp-boilerplate>{}</style>'.format(self._noscript_boilerplate)
            self._result = self._result.replace(' i-amphtml-no-boilerplate', '')

        self._result = self._result.replace(self.BOILERPLATE_PLACEHOLDER, boilerplate)
        self._result = self._result.replace(self.NOSCRIPT_BOILERPLATE_PLACEHOLDER, noscript_boilerplate)

        # Remove empty noscript tags; This happens when removing boilerplate
        self._result = self._result.replace('<noscript></noscript>', '')

        return self._result

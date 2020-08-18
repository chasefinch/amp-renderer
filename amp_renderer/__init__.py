# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals

# Standard Library
import re
from HTMLParser import HTMLParser
from builtins import bytes  # noqa
from builtins import str  # noqa
from collections import namedtuple
from enum import Enum


class AMPRenderer(HTMLParser, object):
    """A parser to ingest AMP HTML and perform various transformations.

    This parser will:
        (1) Server-side-render supported AMP HTML elements
        (2) Insert `img` tags for images with the data-hero attribute
        (3) Remove empty `class` and `style` tags for AMP HTML elements
        (4) Convert tag names and attribute names to lowercase
        (5) Convert numerical attribute values to strings
        (6) Use double quotes ("") for attributes, and escape double quotes
            inside attribute values

    It can also strip comments and trim HTML attributes, if those flags are
    enabled.
    """

    TRANSLATED_STYLES_PLACEHOLDER = '/* style-amp-custom-translated */'
    BOILERPLATE_PLACEHOLDER = '/* style-amp-boilerplate */'
    NOSCRIPT_BOILERPLATE_PLACEHOLDER = '/* style-amp-boilerplate-noscript */'

    _next_auto_id_num = 1

    class AMPNode:
        ID_PREFIX = 'i-amp-'

        class TransformationError(Exception):
            pass

        class Translator:
            class TranslationError(Exception):
                pass

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
                    size_parts = re.split(r'\s+', size_value)
                    if len(size_parts) <= 1:
                        raise cls.TranslationError('Invalid sizes definition')

                    size_value = size_parts.pop()
                    media = Media(query=' '.join(size_parts), value=size_value)

                    sizes.other.append(media)

                return sizes

        class MediaTranslator(Translator):
            @classmethod
            def make_translated_css(cls, value, element_id):
                # Normalize whitespace
                media = re.sub(r'\s+', ' ', value).strip()

                if not media:
                    return ''

                if media[0] == '(':
                    media = 'all and {}'.format(media)

                if media.startswith('not '):
                    media = media[4:]
                else:
                    media = 'not {}'.format(media)

                selector = '#{}'.format(element_id)
                return '@media {media}{{{selector}{{display:none}}}}'.format(media=media, selector=selector)

        class SizesTranslator(Translator):
            @classmethod
            def make_translated_css(cls, value, element_id):
                sizes = cls.parse_sizes(value)

                selector = '#{}'.format(element_id)

                default_size_statement = '{selector}{{width:{value}}}'.format(selector=selector, value=sizes.default)
                statements = [default_size_statement]

                other_sizes = sizes.other

                """The user agent will pick a width from the sizes attribute,
                using the first item with a <media-condition> (the part in
                parentheses) that evaluates to true. This means, we have to
                reverse the order the media queries in CSS to emulate this
                behavior (the last definition has precedence)."""
                other_sizes.reverse()
                for size in other_sizes:
                    statement = '@media {media}{{{selector}{{width:{value}}}}}'.format(
                        media=size.query,
                        selector=selector,
                        value=size.value)
                    statements.append(statement)

                return ''.join(statements)

        class HeightsTranslator(Translator):
            @classmethod
            def make_translated_css(cls, value, element_id):
                sizes = cls.parse_sizes(value)

                selector = '#{}>:first-child'.format(element_id)

                default_size_statement = '{selector}{{padding-top:{value}}}'.format(
                    selector=selector,
                    value=sizes.default)
                statements = [default_size_statement]

                other_sizes = sizes.other

                """The user agent will pick a value from the heights attribute,
                using the first item with a <media-condition> (the part in
                parentheses) that evaluates to true. This means, we have to
                reverse the order the media queries in CSS to emulate this
                behavior (the last definition has precedence)."""
                other_sizes.reverse()
                for size in other_sizes:
                    statement = '@media {media}{{{selector}{{padding-top:{value}}}}}'.format(
                        media=size.query,
                        selector=selector,
                        value=size.value)
                    statements.append(statement)

                return ''.join(statements)

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

        def transform(self, next_auto_id_num):
            """Apply the transformation.

            Returns styles that need to be appended to the beginning of the
            amp-custom style section.
            """
            translation = None

            translations = [k for k in self._other_attrs if k in self.TRANSLATIONS]
            if translations:
                used_auto_id = False
                if not self.id:
                    self.id = '{}{}'.format(self.ID_PREFIX, next_auto_id_num)
                    used_auto_id = True

                css_parts = []
                for t in translations:
                    attribute_value = self._other_attrs[t]
                    Translator = self.TRANSLATIONS[t]  # noqa
                    try:
                        css_part = Translator.make_translated_css(attribute_value, self.id)
                    except Translator.TranslationError:
                        raise self.TransformationError('Error translating "{}" attribute to css')
                    css_parts.append(css_part)
                css = ''.join(css_parts)

                translation = css, used_auto_id

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
                self._style = 'width:{wn}{wu};height:{hn}{hu}{existing_style}'.format(
                    wn=width.numeral,
                    wu=width.unit.value,
                    hn=height.numeral,
                    hu=height.unit.value,
                    existing_style=self._style)

            elif layout == self.Layout.FIXED_HEIGHT:
                self._style = 'height:{numeral}{unit}{existing_style}'.format(
                    numeral=height.numeral,
                    unit=height.unit.value,
                    existing_style=self._style)

            elif layout == self.Layout.FLEX_ITEM:
                if isinstance(height, self.CSSLength):
                    self._style = 'height:{numeral}{unit}{existing_style}'.format(
                        numeral=height.numeral,
                        unit=height.unit.value,
                        existing_style=self._style)

                if isinstance(width, self.CSSLength):
                    self._style = 'width:{numeral}{unit}{existing_style}'.format(
                        numeral=width.numeral,
                        unit=width.unit.value,
                        existing_style=self._style)

            self._other_attrs['i-amphtml-layout'] = layout.value

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

            return translation

        def get_attrs(self):
            attrs = self._other_attrs.items()

            if self.id:
                attrs.insert(0, ('id', self.id))

            if self._classes:
                attrs.insert(0, ('class', ' '.join(self._classes)))

            if self._style:
                attrs.insert(0, ('style', self._style))

            if self._is_hidden:
                attrs.append(('hidden', None))

            return attrs

    def __init__(self, runtime_styles, runtime_version, *args, **kwargs):
        super(AMPRenderer, self).__init__(*args, **kwargs)

        self.runtime_styles = runtime_styles
        self.runtime_version = runtime_version

        # Always keep charrefs intact; This class is meant to reproduce HTML.
        self.convert_charrefs = False

    def reset(self):
        super(AMPRenderer, self).reset()

        self._should_remove_boilerplate = True

        self._boilerplate = ''
        self._is_in_boilerplate = False

        self._noscript_boilerplate = ''
        self._is_in_noscript = False

        self._is_render_paused = False

        self.should_trim_attrs = False
        self.should_strip_comments = False

        self.result = ''

    def handle_decl(self, decl):
        self.result = '{}<!{}>'.format(self.result, decl.lower())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'noscript':
            self._is_in_noscript = True

        if tag == 'style':
            if 'amp-boilerplate' in [attr[0] for attr in attrs]:
                self._is_in_boilerplate = True

                if self._is_in_noscript and self.NOSCRIPT_BOILERPLATE_PLACEHOLDER not in self.result:
                    self.result = '{}{}'.format(self.result, self.NOSCRIPT_BOILERPLATE_PLACEHOLDER)
                elif self.BOILERPLATE_PLACEHOLDER not in self.result:
                    self.result = '{}{}'.format(self.result, self.BOILERPLATE_PLACEHOLDER)

                return

        if tag in ['template', 'script']:
            self._is_render_paused = True

        sizer = None
        maybe_img_attrs = None
        if not self._is_render_paused and tag.startswith('amp-'):
            amp_element = self.AMPNode(tag, attrs)

            try:
                transformation = amp_element.transform(self._next_auto_id_num)
            except self.AMPNode.TransformationError:
                self._should_remove_boilerplate = False
            else:
                if transformation:
                    css, used_auto_id = transformation
                    placeholder = self.TRANSLATED_STYLES_PLACEHOLDER
                    self.result = self.result.replace(placeholder, '{}{}'.format(css, placeholder))

                    if used_auto_id:
                        self._next_auto_id_num += 1

            safe_attrs = amp_element.get_attrs()
            sizer = amp_element.sizer
            maybe_img_attrs = amp_element.maybe_img_attrs

        else:
            safe_attrs = attrs

        if tag == 'html':
            for attr in [('i-amphtml-layout', None),
                         ('i-amphtml-no-boilerplate', None),
                         ('transformed', 'self;v=1')]:
                safe_attrs.append(attr)

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

        attr_string = ''.join(attr_strings)

        self.result = '{}<{}{}>'.format(self.result, tag, attr_string)

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

            self.result = '{}<i-amphtml-sizer{}>'.format(self.result, sizer_attr_string)

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

                self.result = '{}<img{}>'.format(self.result, img_attr_string)

            self.result = '{}</i-amphtml-sizer>'.format(self.result)

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

            self.result = '{}<img{}>'.format(self.result, img_attr_string)

        if tag == 'head':
            style = '<style amp-runtime i-amphtml-version="{}">{}</style>'.format(
                self.runtime_version,
                self.runtime_styles)
            self.result = '{}{}'.format(self.result, style)

        if tag == 'style':
            if 'amp-custom' in [attr[0] for attr in attrs] and self.TRANSLATED_STYLES_PLACEHOLDER not in self.result:
                self.result = '{}{}'.format(self.result, self.TRANSLATED_STYLES_PLACEHOLDER)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'noscript':
            self._is_in_noscript = False

        if tag == 'style' and self._is_in_boilerplate:
            self._is_in_boilerplate = False
            return

        if tag in ['template', 'script']:
            self._is_render_paused = False

        self.result = '{}</{}>'.format(self.result, tag)

    def _add_data(self, data):
        if self._is_in_boilerplate:
            if self._is_in_noscript:
                self._noscript_boilerplate = '{}{}'.format(self._noscript_boilerplate, data)
                return

            self._boilerplate = '{}{}'.format(self._boilerplate, data)
            return

        self.result = '{}{}'.format(self.result, data)

    def handle_data(self, data):
        self._add_data(data)

    def handle_entityref(self, name):
        self._add_data('&{};'.format(name))

    def handle_charref(self, name):
        self._add_data('&#{};'.format(name))

    def handle_comment(self, data):
        if not self.should_strip_comments:
            self.result = '{}<!--{}-->'.format(self.result, data)

    def feed(self, data):
        super(AMPRenderer, self).feed(data)

        self.result = self.result.replace(self.TRANSLATED_STYLES_PLACEHOLDER, '')

        boilerplate = ''
        noscript_boilerplate = ''
        if not self._should_remove_boilerplate:
            boilerplate = self._boilerplate
            noscript_boilerplate = self._noscript_boilerplate
            self.result = self.result.replace(' i-amphtml-no-boilerplate', '')

        self.result = self.result.replace(self.BOILERPLATE_PLACEHOLDER, boilerplate)
        self.result = self.result.replace(self.NOSCRIPT_BOILERPLATE_PLACEHOLDER, noscript_boilerplate)

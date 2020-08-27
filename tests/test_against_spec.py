# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals

# Standard Library
import codecs
import os
import re
import sys
from builtins import bytes  # noqa
from builtins import str  # noqa

# Third Party
import pytest

# AMP Renderer
from amp_renderer import AMPRenderer

if sys.version_info[0] < 3:
    # Third Party
    from HTMLParser import HTMLParser

else:
    # Standard Library
    from html.parser import HTMLParser


class OutputNormalizer(HTMLParser, object):
    """Alphabetize attributes, convert tags to lowercase, etc."""

    def __init__(self, *args, **kwargs):
        super(OutputNormalizer, self).__init__(*args, **kwargs)

        # Always keep charrefs intact; This class is meant to reproduce HTML.
        self.convert_charrefs = False

    def reset(self):
        super(OutputNormalizer, self).reset()

        self._result = ''

    def handle_decl(self, decl):
        self._result = '{}<!{}>'.format(self._result, decl.lower())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        attr_strings = []
        for attr in attrs:
            if attr[1] is not None:
                value = str(attr[1])
                value = value.replace('"', '&quot;')
                attr_strings.append(' {}="{}"'.format(attr[0].lower(), value))
            else:
                attr_strings.append(' {}'.format(attr[0].lower()))

        # Sort alphabetically for diffing
        attr_strings.sort()

        attr_string = ''.join(attr_strings)

        self._result = '{}<{}{}>'.format(self._result, tag, attr_string)

    def handle_endtag(self, tag):
        tag = tag.lower()

        self._result = '{}</{}>'.format(self._result, tag)

    def _add_data(self, data):
        self._result = '{}{}'.format(self._result, data)

    def handle_data(self, data):
        self._add_data(data)

    def handle_entityref(self, name):
        self._add_data('&{};'.format(name))

    def handle_charref(self, name):
        self._add_data('&#{};'.format(name))

    def handle_comment(self, data):
        self._result = '{}<!--{}-->'.format(self._result, data)

    def render(self, data):
        self.reset()
        self.feed(data)
        self.close()

        return self._result


class TestSpec:
    TESTS = [
        'adds_i_amphtml_layout_attribute',
        'boilerplate_not_removed_when_amp_experiment_present',
        'boilerplate_not_removed_when_amp-story_present',
        'boilerplate_not_removed_when_amp_experiment_present',
        'boilerplate_removed_when_amp_experiment_present_but_empty',
        'boilerplate_removed_when_amp_experiment_present_but_invalid_json',
        'boilerplate_removed_when_amp_experiment_present_but_no_tag',
        'boilerplate_then_noscript_removed',
        'converts_heights_attribute_to_css',
        'converts_media_attribute_to_css',
        'converts_sizes_attribute_to_css',
        'does_not_appy_transformations_if_already_present',
        'does_not_break_noscript_tags',
        'does_not_change_content_in_templates',
        'does_not_transform_amp_audio',
        'does_not_transform_invalid_measurements',
        'empty_custom_styles',
        'noscript_then_boilerplate_removed',
        'removes_amp_boilerplate',
        'transforms_layout_container',
        'transforms_layout_fill',
        'transforms_layout_fixed',
        'transforms_layout_fixed_height',
        'transforms_layout_flex_item_with_height',
        'transforms_layout_flex_item_with_width',
        'transforms_layout_flex_item_with_width_and_height',
        'transforms_layout_nodisplay',
        'transforms_layout_responsive',
    ]

    def _format(self, html_value):
        """Remove spaces between tags, and collapse whitespace.

        Far from safe, but fine for tests.
        """
        # remove space between tags
        # https://docs.djangoproject.com/en/3.0/_modules/django/utils/html/
        html_value = re.sub(r'>\s+<', '><', str(html_value))

        # Collapse all whitespace to a single space
        html_value = re.sub(r'\s+', ' ', str(html_value))

        # Add spacing for json
        html_value = re.sub('>{', '> {', str(html_value))
        html_value = re.sub('}</', '} </', str(html_value))
        html_value = re.sub('}{', '} {', str(html_value))
        html_value = re.sub('{}', '{ }', str(html_value))

        return html_value.strip()

    def _run_test(self, spec):
        local_path = os.path.dirname(__file__)
        input_path = '{}/spec/{}/input.html'.format(local_path, spec)
        output_path = '{}/spec/{}/expected_output.html'.format(local_path, spec)

        with codecs.open(input_path, 'r', encoding='utf-8') as html_file:
            html = html_file.read()

        with codecs.open(output_path, 'r', encoding='utf-8') as html_file:
            expected_output = html_file.read()

        normalizer = OutputNormalizer()
        expected = normalizer.render(expected_output)

        # Boot renderer in test mode to match the AMP Optimizer spec
        renderer = AMPRenderer(runtime_version=None, runtime_styles=None)
        result = renderer.render(html)

        assert self._format(result) == self._format(expected)

    @pytest.mark.parametrize('spec', TESTS)
    def test_files(self, spec):
        self._run_test(spec)

# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals

# Standard Library
from builtins import bytes  # noqa
from builtins import str  # noqa

# AMP Renderer
from amp_renderer import AMPNode


class TestLayout:
    Layout = AMPNode.Layout

    def test_get_class(self):
        for layout in list(self.Layout):
            assert layout.get_class() == 'i-amphtml-layout-{}'.format(layout.value)

    def test_is_size_defined(self):
        size_defined_layouts = [
            self.Layout.FIXED,
            self.Layout.FIXED_HEIGHT,
            self.Layout.RESPONSIVE,
            self.Layout.FILL,
            self.Layout.FLEX_ITEM,
            self.Layout.INTRINSIC,
        ]
        for layout in list(self.Layout):
            assert layout.is_size_defined() == (layout in size_defined_layouts)


class TestNode:
    ID = 'testID'
    STYLE = 'test:style;'
    CLASSES = ['class1', 'class2']
    DUMMY = 'dummy'

    def _get_attr_value_or_fail(self, attrs, name):
        matches = [x[1] for x in attrs if x[0] == name]
        assert len(matches) == 1
        return matches[0]

    def test_1(self):
        tag = 'amp-test'
        attrs = [
            ('hidden', None),
            ('id', self.ID),
            ('style', self.STYLE),
            ('class', ' '.join(self.CLASSES)),
            ('data-dummy', self.DUMMY),
        ]

        node = AMPNode(tag, attrs)

        assert node.id == self.ID
        assert node.tag == tag

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform(1)
        assert transformations is None

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 6

        class_name = self._get_attr_value_or_fail(transformed_attrs, 'class')
        assert set(class_name.split(' ')) == set(self.CLASSES + ['i-amphtml-layout-container'])

        layout = self._get_attr_value_or_fail(transformed_attrs, 'i-amphtml-layout')
        assert layout == AMPNode.Layout.CONTAINER.value

    def test_2(self):
        tag = 'amp-test'
        attrs = [
            ('style', self.STYLE),
            ('class', ' '.join(self.CLASSES)),
            ('layout', 'fixed'),
            ('width', '113'),
            ('height', '140px'),
            ('data-dummy', self.DUMMY),
        ]

        node = AMPNode(tag, attrs)

        assert node.tag == tag
        assert node.id is None

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform(1)
        assert transformations is None
        assert node.id is None

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 7

        class_name = self._get_attr_value_or_fail(transformed_attrs, 'class')
        assert set(class_name.split(' ')) == set(self.CLASSES + [
            'i-amphtml-layout-fixed',
            'i-amphtml-layout-size-defined',
        ])

        layout = self._get_attr_value_or_fail(transformed_attrs, 'i-amphtml-layout')
        assert layout == AMPNode.Layout.FIXED.value

    def test_3(self):
        tag = 'amp-test'
        attrs = [
            ('style', self.STYLE),
            ('class', ' '.join(self.CLASSES)),
            ('layout', 'responsive'),
            ('width', '113'),
            ('height', 'auto'),
            ('media', '(max-width 1024px)'),
            ('sizes', '(max-width 533px) 133px, 100vw'),
            ('data-dummy', self.DUMMY),
        ]

        node = AMPNode(tag, attrs)

        assert node.tag == tag

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform(1)
        assert node.id == 'i-amp-1'

        assert transformations[0] in [
            ('@media not all and (max-width 1024px){#i-amp-1{display:none}}'
             '#i-amp-1{width:100vw}@media (max-width 533px){#i-amp-1{width:133px}}'),
            ('#i-amp-1{width:100vw}@media (max-width 533px){#i-amp-1{width:133px}}'
             '@media not all and (max-width 1024px){#i-amp-1{display:none}}'),
        ]

        assert transformations[1]

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 8

        class_name = self._get_attr_value_or_fail(transformed_attrs, 'class')
        assert set(class_name.split(' ')) == set(self.CLASSES + [
            'i-amphtml-layout-responsive',
            'i-amphtml-layout-size-defined',
        ])

        layout = self._get_attr_value_or_fail(transformed_attrs, 'i-amphtml-layout')
        assert layout == AMPNode.Layout.RESPONSIVE.value

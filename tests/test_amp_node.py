"""Tests for AMPNode and related functionality."""

# AMP Renderer
from amp_renderer import AMPNode, Layout


class TestLayout:
    """Test the layout classes."""

    def test_get_class(self):
        """Test the get_class method."""
        for layout in list(Layout):
            assert layout.get_class() == "i-amphtml-layout-{}".format(layout.value)

    def test_is_size_defined(self):
        """Test the is_size_defined method."""
        size_defined_layouts = [
            Layout.FIXED,
            Layout.FIXED_HEIGHT,
            Layout.RESPONSIVE,
            Layout.FILL,
            Layout.FLEX_ITEM,
            Layout.INTRINSIC,
        ]
        for layout in list(Layout):
            assert layout.is_size_defined() == (layout in size_defined_layouts)


class TestNode:
    """Test the AMPNode class."""

    element_id = "testID"
    style = "test:style;"
    classes = ("class1", "class2")
    dummy = "dummy"

    def test_1(self):
        """Test #1."""
        tag = "amp-test"
        attrs = [
            ("hidden", "hidden"),
            ("id", self.element_id),
            ("style", self.style),
            ("class", " ".join(self.classes)),
            ("data-dummy", self.dummy),
        ]

        node = AMPNode(tag, attrs)

        assert node.element_id == self.element_id
        assert node.tag == tag

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform(1)
        assert transformations is None

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 6

        class_name = self._get_attr_value_or_fail(transformed_attrs, "class")
        assert set(class_name.split(" ")) == set(self.classes + ("i-amphtml-layout-container",))

        layout = self._get_attr_value_or_fail(transformed_attrs, "i-amphtml-layout")
        assert layout == Layout.CONTAINER.value

    def test_2(self):
        """Test #2."""
        tag = "amp-test"
        attrs = [
            ("style", self.style),
            ("class", " ".join(self.classes)),
            ("layout", "fixed"),
            ("width", "113"),
            ("height", "140px"),
            ("data-dummy", self.dummy),
        ]

        node = AMPNode(tag, attrs)

        assert node.tag == tag
        assert node.element_id is None

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform(1)
        assert transformations is None
        assert node.element_id is None

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 7

        class_name = self._get_attr_value_or_fail(transformed_attrs, "class")
        assert set(class_name.split(" ")) == set(
            self.classes
            + (
                "i-amphtml-layout-fixed",
                "i-amphtml-layout-size-defined",
            ),
        )

        layout = self._get_attr_value_or_fail(transformed_attrs, "i-amphtml-layout")
        assert layout == Layout.FIXED.value

    def test_3(self):
        """Test #3."""
        tag = "amp-test"
        attrs = [
            ("style", self.style),
            ("class", " ".join(self.classes)),
            ("layout", "responsive"),
            ("width", "113"),
            ("height", "auto"),
            ("media", "(max-width:1024px)"),
            ("srcset", "https://example.com/1x 133w, https://example.com/2x 266w"),
            ("sizes", "(max-width:533px) 133px, 100vw"),
            ("data-dummy", self.dummy),
        ]

        node = AMPNode(tag, attrs)

        assert node.tag == tag

        assert set(node.get_attrs()) == set(attrs)

        transformations = node.transform("i-amp-1")
        assert node.element_id == "i-amp-1"
        assert transformations[1]

        transformed_attrs = node.get_attrs()
        assert len(transformed_attrs) == 9

        class_name = self._get_attr_value_or_fail(transformed_attrs, "class")
        assert set(class_name.split(" ")) == set(
            self.classes
            + (
                "i-amphtml-layout-responsive",
                "i-amphtml-layout-size-defined",
            ),
        )

        layout = self._get_attr_value_or_fail(transformed_attrs, "i-amphtml-layout")
        assert layout == Layout.RESPONSIVE.value

    def _get_attr_value_or_fail(self, attrs, name):
        matches = [attr[1] for attr in attrs if attr[0] == name]
        assert len(matches) == 1
        return matches[0]

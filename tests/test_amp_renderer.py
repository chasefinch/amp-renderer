"""Tests for AMPRenderer and related functionality."""

# AMP Renderer
from amp_renderer import AMPRenderer

RUNTIME_VERSION = "01234"
RUNTIME_STYLES = "body{background-color:pink;}"


class RendererFactory:
    """Set up a renderer on demand to be tested."""

    @classmethod
    def make(cls, should_trim_attrs=False, should_strip_comments=False):
        """Generate and return a new AMPRenderer."""
        renderer = AMPRenderer(runtime_version=RUNTIME_VERSION, runtime_styles=RUNTIME_STYLES)

        renderer.should_trim_attrs = should_trim_attrs
        renderer.should_strip_comments = should_strip_comments

        return renderer


# content of test_class.py
class TestRenderer:
    """Test the AMP renderer class."""

    def test_basic(self):
        """Test the baseline HTML structure."""
        basic_html = """
            <!doctype html>
            <html ⚡️>
            <head>

            </head>
            <body>
                <div
                    id="testDiv"
                    class="testClass"
                ></div>
            </body>
            </html>
        """

        expected_result = f"""
            <!doctype html>
            <html ⚡️ i-amphtml-layout i-amphtml-no-boilerplate transformed="self;v=1">
            <head><style amp-runtime i-amphtml-version="{RUNTIME_VERSION}">{RUNTIME_STYLES}</style>

            </head>
            <body>
                <div id="testDiv" class="testClass"></div>
            </body>
            </html>
        """

        renderer = RendererFactory.make()
        result = renderer.render(basic_html)

        assert result == expected_result
        assert renderer.no_boilerplate

    def test_trim_attributes(self):
        """Test trimming whitespace from HTML attributes."""
        html = """
            <div
                data-test-attribute=" Lovely!  "
                [text]="
                    myFavorites.color
                "
            >
                Blue
            </div>
        """

        expected_result = """
            <div data-test-attribute="Lovely!" [text]="myFavorites.color">
                Blue
            </div>
        """

        renderer = RendererFactory.make(should_trim_attrs=True)
        result = renderer.render(html)

        assert result == expected_result
        assert renderer.no_boilerplate

    def test_strip_comments(self):
        """Test stripping HTML comments."""
        html = "<div><!-- This isn’t important. -->Hello there!</div>"
        expected_result = "<div>Hello there!</div>"

        renderer = RendererFactory.make(should_strip_comments=True)
        result = renderer.render(html)

        assert result == expected_result
        assert renderer.no_boilerplate

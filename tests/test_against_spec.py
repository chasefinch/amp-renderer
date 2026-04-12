"""Test against the spec files from AMP Optimizer."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from amp_renderer import AMPRenderer


class OutputNormalizer(HTMLParser):
    """Alphabetize attributes, convert tags to lowercase, etc."""

    def __init__(self) -> None:
        """Set up an Output Normalizer."""
        super().__init__()

        # Always keep charrefs intact; This class is meant to reproduce HTML.
        self.convert_charrefs = False

    def reset(self) -> None:
        """Restore the HTML parser to ready state."""
        super().reset()

        self._result = ""

    def handle_decl(self, decl: str) -> None:
        """Handle an HTML declaration."""
        self._result = f"{self._result}<!{decl.lower()}>"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Process an opening tag."""
        tag = tag.lower()

        attr_strings = []
        for attr in attrs:
            if attr[1] is None:
                attr_strings.append(f" {attr[0].lower()}")
            else:
                value = str(attr[1])
                value = value.replace('"', "&quot;")
                attr_strings.append(f' {attr[0].lower()}="{value}"')

        # Sort alphabetically for diffing
        attr_strings.sort()

        attr_string = "".join(attr_strings)

        self._result = f"{self._result}<{tag}{attr_string}>"

    def handle_endtag(self, tag: str) -> None:
        """Process a closing tag."""
        tag = tag.lower()

        self._result = f"{self._result}</{tag}>"

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
        self._result = f"{self._result}<!--{data}-->"

    def render(self, amp_html: str) -> str:
        """Run the normalization routine."""
        self.reset()
        self.feed(amp_html)
        self.close()

        return self._result

    def _add_data(self, html_data: str) -> None:
        """Append some more data to the result."""
        self._result = f"{self._result}{html_data}"


class TestSpec:
    """Test the AMP Renderer against the AMP Optimizer spec files."""

    tests = (
        "adds_i_amphtml_layout_attribute",
        "boilerplate_not_removed_when_amp_experiment_present",
        "boilerplate_not_removed_when_amp-story_present",
        "boilerplate_not_removed_when_amp_experiment_present",
        "boilerplate_removed_when_amp_experiment_present_but_empty",
        "boilerplate_removed_when_amp_experiment_present_but_invalid_json",
        "boilerplate_removed_when_amp_experiment_present_but_no_tag",
        "boilerplate_then_noscript_removed",
        "converts_heights_attribute_to_css",
        "converts_media_attribute_to_css",
        "converts_sizes_attribute_to_css",
        "does_not_appy_transformations_if_already_present",
        "does_not_break_noscript_tags",
        "does_not_change_content_in_templates",
        "does_not_transform_amp_audio",
        "does_not_transform_invalid_measurements",
        "empty_custom_styles",
        "noscript_then_boilerplate_removed",
        "removes_amp_boilerplate",
        "transforms_layout_container",
        "transforms_layout_fill",
        "transforms_layout_fixed",
        "transforms_layout_fixed_height",
        "transforms_layout_flex_item_with_height",
        "transforms_layout_flex_item_with_width",
        "transforms_layout_flex_item_with_width_and_height",
        "transforms_layout_nodisplay",
        "transforms_layout_responsive",
    )

    @pytest.mark.parametrize("spec", tests)
    def test_files(self, spec: str) -> None:
        """Run the test for all spec files."""
        self._run_test(spec)

    def _format(self, html_value: str) -> str:
        """Remove spaces between tags, and collapse whitespace.

        Far from safe, but fine for tests.
        """
        # remove space between tags
        # https://docs.djangoproject.com/en/3.0/_modules/django/utils/html/
        html_value = re.sub(r">\s+<", "><", str(html_value))

        # Collapse all whitespace to a single space
        html_value = re.sub(r"\s+", " ", str(html_value))

        # Add spacing for json
        html_value = re.sub(">{", "> {", str(html_value))
        html_value = re.sub("}</", "} </", str(html_value))
        html_value = re.sub("}{", "} {", str(html_value))
        html_value = re.sub("{}", "{ }", str(html_value))

        return html_value.strip()

    def _run_test(self, spec: str) -> None:
        local_path = Path(__file__).parent
        input_path = local_path / "spec" / spec / "input.html"
        output_path = local_path / "spec" / spec / "expected_output.html"

        html = input_path.read_text(encoding="utf-8")
        expected_output = output_path.read_text(encoding="utf-8")

        normalizer = OutputNormalizer()
        expected = normalizer.render(expected_output)

        # Boot renderer in test mode to match the AMP Optimizer spec
        renderer = AMPRenderer(runtime_version=None, runtime_styles=None)
        result = renderer.render(html)

        assert self._format(result) == self._format(expected)

# AMP Renderer

![Python 2.7 & 3.5+](https://img.shields.io/badge/python-2.7%20%7C%203.5%2B-blue) [![Build Status](https://travis-ci.com/chasefinch/amp-renderer.svg?branch=master)](https://travis-ci.com/chasefinch/amp-renderer) ![Coverage](https://img.shields.io/badge/coverage-89%25-green)

Unofficial Python port of [server-side rendering](https://amp.dev/documentation/guides-and-tutorials/optimize-and-measure/amp-optimizer-guide/explainer/?format=websites) from [AMP Optimizer](https://github.com/ampproject/amp-toolbox/tree/main/packages/optimizer). Tested in Python 3.5 and above, but also supports Python 2.7.

AMP Renderer performs the following optimizations:
1. Inject the specific layout markup into each AMP element
2. Insert the AMP runtime styles into the document
3. Remove the AMP boilerplate styles, if possible
4. Mark the document as “transformed” with the appropriate tags on the `html` element
5. Insert `img` tags for images with the data-hero attribute

It also makes these formatting updates:
1. Remove empty `class` and `style` tags for AMP HTML elements
2. Convert tag names and attribute names to lowercase
3. Convert numerical attribute values to strings
4. Use double quotes ("") for attributes, and escape double quotes inside attribute values
5. Remove whitespace between html attributes
6. If desired, removes comments (disabled by default)
7. If desired, trims whitespace around HTML attribute values (disabled by default, and not always a good idea)

AMPRenderer can be used on a block of arbitrary HTML, but when used on a full document, it will insert the AMP runtime styles and, if possible, remove the AMP boilerplate styles.

Boilerplate styles can be removed except in these cases:
- An AMP element uses an unsupported value for the `layout` attribute
- `amp-audio` is used
- There is at least one `amp-experiment` active
- Transformation fails for one or more elements due to an invalid attribute value for `media`, `sizes`, or `heights`
- Any render-delaying extension is used. Currently this means:
  - `amp-dynamic-css-classes`
  - `amp-story`

If boilerplate styles can’t be removed, the attribute `no_boilerplate` will be set to `True` after calling `render`; otherwise it will be `False`. Until `render` runs, the `no_boilerplate` attribute isn’t set at all.

## Usage

If using Django, you can use the [Django AMP Renderer middleware](https://github.com/chasefinch/django-amp-renderer).

Otherwise, install via PyPI:
	
	pip install amp-renderer

Minimal usage:

	from amp_renderer import AMPRenderer

	...

	RUNTIME_VERSION = "012345678" /* Current AMP runtime version number */
	RUNTIME_STYLES = "..." /* Current contents of https://cdn.ampproject.org/v0.css */

	renderer = AMPRenderer(
		runtime_version=RUNTIME_VERSION,
		runtime_styles=RUNTIME_STYLES)

	original_html = """
	    <!doctype html>
	    <html ⚡>
	      ...
	    </html>
	"""

	result = renderer.render(original_html)

	print(result)


Remove comments and/or trim attributes:

	renderer.should_strip_comments = True
	renderer.should_trim_attributes = True
	result = renderer.render(original_html)

	print(result)


The AMPRenderer class inherits from [HTMLParser](https://docs.python.org/3/library/html.parser.html), and can be similarly extended.

## Testing, etc.

Sort imports (Requires Python >= 3.6):

	make normal

Lint (Requires Python >= 3.6):

	make lint

Test:

	make test

## Discussion

There are still some aspects of the official AMP Optimizer implementation that haven’t been addressed yet. PRs welcome.

### General
- [x] ~Tested against AMP Optimizer’s ServerSideRendering spec~
- [ ] Automatic runtime version management

### Dynamic attributes
- [x] ~Support `sizes`, `media`, and `heights` via CSS injection~
- [ ] Warn or fail if CSS injection puts the `amp-custom` element over the byte limit
- [ ] Group CSS injections for `media` attributes by shared media queries to reduce necessary bytes

### Hero Images
- [x] ~Inject `img` tag for `amp-img`s with the `data-hero` attribute~
- [ ] Enforce 2-image limit on `data-hero`
- [ ] Autodetect hero images
- [ ] Support hero image functionality for `amp-iframe`, `amp-video`, and `amp-video-iframe`

### Performance

The Python AMP Renderer does not insert `preload` links into the `head` of the DOM object for hero images; This can be done by hand for more control over the critical path.

Since AMPRenderer adds the `amp-runtime` styles to the document, you can also use the [AMP Module Build](https://amp.dev/documentation/guides-and-tutorials/optimize-and-measure/amp-optimizer-guide/explainer/?format=websites#amp-module-build-(coming-soon)) by hand. To take advantage of this, rewrite the import scripts such that imports like this:

	<script async src="https://cdn.ampproject.org/v0.js"></script>

...become 2-part imports based on [Javascript Modules](https://v8.dev/features/modules#browser), like this:

	<script type="module" async src="https://cdn.ampproject.org/v0.mjs"></script>
	<script nomodule async src="https://cdn.ampproject.org/v0.js"></script> 

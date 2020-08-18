# AMP Renderer

Unofficial Python port of [server-side rendering](https://amp.dev/documentation/guides-and-tutorials/optimize-and-measure/amp-optimizer-guide/explainer/?format=websites) from [AMP Optimizer](https://github.com/ampproject/amp-toolbox/tree/main/packages/optimizer).

Python AMP Renderer can be used on a block of arbitrary HTML, but when used on a full document, it inserts the AMP runtime styles and, if possible, removes the AMP boilerplate styles.

Boilerplate styles are removed except in the following cases:
- An AMP element uses an unsupported layout
- `amp-audio` is used
- There is at least one `amp-experiment` tag in the document
- Any render-delaying extension is used. Currently this means:
  - `amp-dynamic-css-classes`
  - `amp-experiment`
  - `amp-story`

## Usage

Install via:
	
	pip install git+https://github.com/chasefinch/amp-renderer

Minimal usage:

	from amp_renderer import AMPRenderer

	...

	original_html = """
	    <!doctype html>
	    <html ⚡>
	      ...
	    </html>
	"""

	renderer = AMPRenderer()
	renderer.feed(original_html)

	print(renderer.result)

Remove comments and/or trim attributes:

	from amp_renderer import AMPRenderer

	...

	original_html = """
	    <!doctype html>
	    <html ⚡>
	      ...
	    </html>
	"""

	renderer = AMPRenderer()

	renderer.should_strip_comments = True
	renderer.should_trim_attributes = True

	renderer.feed(original_html)

	print(renderer.result)


The AMPRenderer class inherits from [HTMLParser](https://docs.python.org/3/library/html.parser.html), and can be similarly extended.

## Discussion

There are still some aspects of the official AMP Optimizer implementation that haven’t been addressed yet. PRs welcome.

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

Since AMPRenderer adds the `amp-runtime` styles to the document, you can also use the [AMP Module Build](https://amp.dev/documentation/guides-and-tutorials/optimize-and-measure/amp-optimizer-guide/explainer/?format=websites#amp-module-build-(coming-soon)) by hand. To take advantage of this, transform the import scripts such that imports like this:

	<script async src="https://www.ampproject.org/v0.js"></script>

become a 2-part import based on [Javascript Modules](https://v8.dev/features/modules#browser), like this:

	<script type="module" async src="https://www.ampproject.org/v0.mjs"></script>
	<script nomodule async src="https://www.ampproject.org/v0.js"></script> 
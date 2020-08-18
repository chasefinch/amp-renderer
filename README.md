# AMP Renderer

Unofficial Python port of [server-side rendering](https://amp.dev/documentation/guides-and-tutorials/optimize-and-measure/amp-optimizer-guide/) from [AMP Optimizer](https://github.com/ampproject/amp-toolbox/tree/main/packages/optimizer).

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

Python AMP Renderer can be used on a block of arbitrary HTML, but when used on a full HTML document, it inserts the amp-runtime styles and, if possible, removes the AMP boilerplate styles.

The AMPRenderer class inherits from [HTMLParser](https://docs.python.org/3/library/html.parser.html), and can be similarly extended.

## Caveats

There are still some aspects of the official AMP Optimizer implementation that haven’t been addressed yet. PRs are welcome.

- [x] ~Support `sizes`, `media`, and `heights` via CSS injection~
- [ ] Warn or fail if CSS injection puts the `amp-custom` element over the byte limit
- [ ] Group CSS injections for `media` attributes by shared media queries to reduce necessary bytes
- [ ] Support `amp-audio`
- [x] ~Inject `img` tag for hero images with the `data-hero` attribute~
- [ ] Enforce 2-img limit on `data-hero`
- [ ] Autodetect hero images

Also note that the Python AMP Renderer does not insert `preload` links into the `head` of the DOM object for hero images; This can be done by hand for more control over the critical path.
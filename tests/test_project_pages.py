"""The public project page is static, navigable, and backed by repository files."""
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.assets, self.images = set(), [], [], []
        self.lang = None
        self.scripts = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.lang = attrs.get('lang')
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.assets.append(attrs['href'])
        if tag == 'img':
            self.assets.append(attrs['src'])
            self.images.append(attrs)
        if tag == 'script':
            self.scripts += 1


def test_public_page_contract():
    source = ROOT / 'docs/index.html'
    assert source.is_file()
    text = source.read_text()
    page = Page()
    page.feed(text)
    assert page.lang == 'en'
    assert {'install', 'operate', 'atem', 'architecture', 'help'} <= page.ids
    assert 'physical validation' in text.lower()
    assert 'GPL' in text
    assert page.scripts == 0
    assert all(image.get('alt') and image.get('width') and image.get('height') for image in page.images)
    for target in page.links:
        if target.startswith('#'):
            assert target[1:] in page.ids, target
        elif '/blob/main/' in target:
            assert (ROOT / target.split('/blob/main/', 1)[1]).is_file(), target
    for asset in page.assets:
        assert not asset.startswith(('https:', 'http:'))
        assert (source.parent / asset).is_file(), asset
    assert not re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text), 'No device addresses on the public page'
    assert 'copyright' not in text.lower()
    image = page.images[0]
    data = (source.parent / image['src']).read_bytes()
    marker = data.index(b'\x9d\x01\x2a') + 3  # WebP VP8 keyframe dimensions
    import struct
    width, height = struct.unpack('<HH', data[marker:marker + 4])
    assert (int(image['width']), int(image['height'])) == (width & 0x3fff, height & 0x3fff)
    assert 'Resumen en español' in (ROOT / 'README.md').read_text()


def test_task_routes_checkpoints_and_limits():
    text = (ROOT / 'docs/index.html').read_text()
    page = Page()
    page.feed(text)
    assert {'start', 'checkpoints', 'faq'} <= page.ids
    assert 'Choose your next step' in text
    assert 'What this project does not do' in text
    assert text.count('<details>') >= 3
    assert 'Expected result' in text
    readme = (ROOT / 'README.md').read_text()
    assert '## Start here' in readme
    assert '## What this project does not do' in readme


def test_public_entry_points_use_neutral_venue_language():
    for relative in ('docs/index.html', 'README.md', 'docs/PAGES.md'):
        text = (ROOT / relative).read_text().lower()
        assert 'for_kingdom_halls' not in text, relative
        assert not re.search(r'\b(?:halls?|congregation|congregación)\b', text), relative


def test_demo_is_manual_local_and_transcribed():
    text = (ROOT / 'docs/index.html').read_text()
    page = Page()
    page.feed(text)
    assert 'demo-transcript' in page.ids
    assert 'UI state walkthrough' in text
    videos = re.findall(r'<video\b([^>]*)>', text)
    assert len(videos) == 1
    attrs = videos[0]
    assert 'controls' in attrs and 'preload="none"' in attrs
    assert 'autoplay' not in attrs and 'loop' not in attrs
    assert 'width="1280"' in attrs and 'height="820"' in attrs
    assert 'aria-describedby="demo-transcript"' in attrs
    assert 'poster="site/demo-poster.webp"' in attrs
    assert 'src="site/ui-walkthrough.mp4"' in text
    assert 'No physical camera test' in text
    for label in ('Choose Platform', 'Choose Comments', 'Simulated disconnect', 'Simulated recovery'):
        assert label in text
    video = ROOT / 'docs/site/ui-walkthrough.mp4'
    assert video.is_file()
    assert b'ftyp' == video.read_bytes()[4:8]
    assert video.stat().st_size < 200_000
    assert (ROOT / 'docs/site/demo-poster.webp').is_file()


def test_operator_entry_points_do_not_promise_unwired_safety_buttons():
    for relative in ('docs/index.html', 'README.md'):
        text = (ROOT / relative).read_text()
        assert 'not a verified' in text, relative
        assert 'STOP ALL' in text, relative
        assert 'Learn STOP, STOP ALL' not in text, relative
        assert 'Learn [STOP, STOP ALL' not in text, relative

#!/usr/bin/env python3
"""Check generated Pages links, local assets, anchors, and curated search content."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs and not (tag == 'link' and attrs.get('rel') == 'canonical'):
                self.links.append(attrs[key])

def main():
    p = argparse.ArgumentParser(); p.add_argument('site', nargs='?', default='site'); args = p.parse_args()
    root = Path(args.site).resolve(); errors = []; pages = {}
    for path in root.rglob('*.html'):
        obj = Page(); obj.feed(path.read_text()); pages[path] = obj
    for path, page in pages.items():
        for value in page.links:
            url = urlsplit(value)
            if url.scheme or url.netloc or value.startswith('data:'): continue
            if url.path.startswith('/'):
                # The 404 page uses project-root URLs because its depth is unknown.
                prefix = '/VMWeave-GPU/'
                if not url.path.startswith(prefix):
                    errors.append(f'{path.relative_to(root)}: URL escapes project prefix {value}'); continue
                target = (root / unquote(url.path[len(prefix):])).resolve()
            else:
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if target.is_dir(): target = target / 'index.html'
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f'{path.relative_to(root)}: missing {value}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f'{path.relative_to(root)}: missing anchor {value}')
    search = json.loads((root / 'search/search_index.json').read_text())
    docs = search.get('docs', [])
    if any(not stage.strip() for stage in search.get('config', {}).get('pipeline', [])):
        errors.append('Invalid blank search pipeline stage')
    if not any('오버헤드' in row.get('title', '') for row in docs): errors.append('Missing Korean search entries')
    if any('문서 위치 안내' in row.get('title', '') for row in docs): errors.append('Compatibility pages leaked into search')
    if errors: raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(pages)} HTML pages, local links/assets/anchors, {len(docs)} search entries')

if __name__ == '__main__': main()

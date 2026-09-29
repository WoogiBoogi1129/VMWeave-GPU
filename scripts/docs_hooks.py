"""Resolve repository links without copying code or evidence into the Pages site."""
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
REPO = 'https://github.com/WoogiBoogi1129/VMWeave-GPU'
EVIDENCE_REF = '62951a74fa63d31a7c7b5cdbe0b676a9c3cdac66'
FROZEN_BUNDLES = {
    '2026-09-22', '2026-09-22-pytorch', '2026-09-24-showcase',
    '2026-09-28-campaign', '2026-09-28-stage1', '2026-09-28-stage1-terminal',
    '2026-09-28-stage2', '2026-09-28-stage2-static',
    '2026-09-29-stage3', '2026-09-29-overhead',
}
LINK = re.compile(r'(!?\[[^\]]*\]\()([^\s)]+)(\))')


def on_page_markdown(markdown, *, page, config, files):
    def rewrite(match):
        url = urlsplit(match[2])
        if url.scheme or url.netloc or not url.path or url.path.startswith('/'):
            return match[0]
        target = (Path(page.file.abs_src_path).parent / unquote(url.path)).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError(f'{page.file.src_uri}: link escapes repository: {match[2]}')
        if not target.exists():
            raise ValueError(f'{page.file.src_uri}: missing link target: {match[2]}')
        if target.is_relative_to(DOCS):
            return match[0]
        rel = target.relative_to(ROOT).as_posix()
        parts = rel.split('/')
        frozen = parts[:3] == ['experiments', 'evidence', 'results'] and len(parts) > 3 and parts[3] in FROZEN_BUNDLES
        ref = EVIDENCE_REF if frozen else 'main'
        kind = 'tree' if target.is_dir() else 'blob'
        suffix = ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')
        resolved = f'{REPO}/{kind}/{ref}/{quote(rel)}{suffix}'
        return match[1] + resolved + match[3]
    # Keep code examples literal.
    parts = re.split(r'(^```[^\n]*\n.*?^```\s*$)', markdown, flags=re.M | re.S)
    return ''.join(part if part.startswith('```') else LINK.sub(rewrite, part) for part in parts)

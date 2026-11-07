"""Explicit inventory of bundled presentation assets; no arbitrary file routes."""
import mimetypes


def shared_assets(root):
    files = [root/'markdown.js',root/'markdown.css']
    files += [p for p in (root/'vendor').rglob('*') if p.suffix in ('.js','.css','.woff2')]
    return {'/'+p.relative_to(root).as_posix():(p.relative_to(root).as_posix(),
        'text/javascript; charset=utf-8' if p.suffix=='.js' else mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        for p in files if p.is_file()}

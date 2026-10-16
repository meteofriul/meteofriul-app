"""Read TurismoFVG's advertised sitemap as a fast detail-URL index.

The sitemap can lag the calendar; callers must reconcile it with dated search.
"""
from urllib.parse import urlsplit
from xml.etree import ElementTree
import requests

from .http_client import get_with_single_transient_retry


SITEMAP_URL = 'https://www.turismofvg.it/sitemapcms'
XML_NAMESPACE = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def read_xml(url, *, get=requests.get):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'www.turismofvg.it'
            or parsed.path != '/sitemapcms'):
        raise ValueError('unsafe TurismoFVG sitemap URL')
    response = get_with_single_transient_retry(
        get, url, timeout=(4, 30),
        headers={'User-Agent': 'Meteo-Friul-Pilot-Catalog/1.0'},
    )
    actual = urlsplit(response.url)
    if (actual.scheme != parsed.scheme or actual.hostname != parsed.hostname
            or actual.path != parsed.path or actual.query != parsed.query):
        raise ValueError('unexpected TurismoFVG sitemap redirect')
    if len(response.content) > 10 * 1024 * 1024:
        raise ValueError('TurismoFVG sitemap too large')
    return ElementTree.fromstring(response.content)


def discover_detail_urls(*, get=requests.get):
    root = read_xml(SITEMAP_URL, get=get)
    if root.tag != XML_NAMESPACE + 'sitemapindex':
        raise ValueError('unrecognized TurismoFVG sitemap index')
    children = [item.findtext(XML_NAMESPACE + 'loc') for item in
                root.findall(XML_NAMESPACE + 'sitemap')]
    if (not children or any(not child for child in children)
            or len(children) > 8 or len(set(children)) != len(children)):
        raise ValueError('invalid TurismoFVG sitemap children')
    details = {}
    for child in children:
        urlset = read_xml(child, get=get)
        if urlset.tag != XML_NAMESPACE + 'urlset':
            raise ValueError('unrecognized TurismoFVG sitemap child')
        for item in urlset.findall(XML_NAMESPACE + 'url'):
            url = item.findtext(XML_NAMESPACE + 'loc') or ''
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'www.turismofvg.it'
                    or not parsed.path.startswith('/eventi/') or parsed.query
                    or parsed.fragment):
                continue
            details[url] = {'url': url, 'lastmod': item.findtext(XML_NAMESPACE + 'lastmod')}
    if not details:
        raise ValueError('TurismoFVG sitemap has no Italian event details')
    return {'status': 'ok', 'sitemap_children': len(children),
            'detail_urls': list(details.values()), 'unique_urls': len(details)}


def compare_calendar_urls(sitemap, cards):
    indexed = {item['url'] for item in sitemap['detail_urls']}
    listed = {item['url'] for item in cards}
    return {'calendar_unique_urls': len(listed),
            'missing_from_sitemap': sorted(listed - indexed),
            'sitemap_only_urls': sorted(indexed - listed)}

"""Read-only source markup diagnostics; never publishes data."""
from html.parser import HTMLParser
import requests

URLS = {
    "Azalea": "https://www.azalea.it/",
    "CSS Udine": "https://www.cssudine.it/",
    "Teatro Verdi Pordenone": "https://teatroverdipordenone.it/la-stagione/",
    "Teatro Verdi Trieste": "https://www.teatroverdi-trieste.com/it/calendario-spettacoli/",
    "Pordenone Pensa": "https://www.pnpensa.it/",
}

class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self.links, self.current = [], [], None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.current = ""
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
    def handle_data(self, data):
        if self.current is not None:
            self.current += data
    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.blocks.append(self.current)
            self.current = None

if __name__ == "__main__":
    for name, url in URLS.items():
        try:
            r = requests.get(url, timeout=(4, 12))
            r.raise_for_status()
            p = Markup()
            p.feed(r.text)
            print(name, "structured:", [b[:350] for b in p.blocks])
            print("links:", list(dict.fromkeys(x for x in p.links if any(k in x for k in ("event", "spettacol", "giallo"))))[:12])
        except Exception as e:
            print(name, type(e).__name__)

"""Regression checks for the lxml parser defaults and the HTML audit consumer."""
import io
from pathlib import Path
import tempfile
import unittest

from lxml import etree, html


class LxmlSecurityTests(unittest.TestCase):
    def test_default_xml_parsers_do_not_expand_external_file_entities(self):
        with tempfile.TemporaryDirectory(prefix="meteo-lxml-security-") as directory:
            secret = Path(directory) / "canary.txt"
            secret.write_text("private-file-canary", encoding="utf-8")
            xml = (f'<!DOCTYPE root [<!ENTITY external SYSTEM "{secret.as_uri()}">]>'
                   '<root>&external;</root>').encode()
            for parser in ("iterparse", "ETCompatXMLParser"):
                with self.subTest(parser=parser):
                    try:
                        if parser == "iterparse":
                            elements = [element for _, element in etree.iterparse(io.BytesIO(xml))]
                            output = b"".join(etree.tostring(element) for element in elements)
                        else:
                            output = etree.tostring(etree.fromstring(xml, etree.ETCompatXMLParser()))
                    except etree.XMLSyntaxError:
                        continue
                    self.assertNotIn(b"private-file-canary", output)

    def test_html_audit_xpath_and_text_content_remain_available(self):
        tree = html.fromstring('<div><a class="card" href="/event">Evento <b>locale</b></a></div>')
        card = tree.xpath('//a[contains(@class,"card")]')[0]
        self.assertEqual(card.text_content(), "Evento locale")
        self.assertEqual(card.get("href"), "/event")

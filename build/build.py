#!/usr/bin/env python3
"""Assemble the LMNP simulator: inline fonts + logos (base64 data URIs) into
the template, then emit a standalone index.html and an artifact body file."""
import base64, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
REPO = ROOT.parent

def data_uri(name, mime):
    raw = (ASSETS / name).read_bytes()
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())

tokens = {
    "__POPPINS500__": data_uri("poppins-500.woff2", "font/woff2"),
    "__POPPINS600__": data_uri("poppins-600.woff2", "font/woff2"),
    "__POPPINS700__": data_uri("poppins-700.woff2", "font/woff2"),
    "__MONTVAR__":    data_uri("montserrat-var.woff2", "font/woff2"),
    "__LOGO_DARK__":  data_uri("logo-s2a.webp", "image/webp"),
    "__LOGO_LIGHT__": data_uri("logo-s2a-light.webp", "image/webp"),
    "__FAVICON__":    "data:image/svg+xml;base64," + base64.b64encode(
                        (ASSETS / "favicon.svg").read_bytes()).decode(),
}

inner = (ROOT / "template.html").read_text(encoding="utf-8")
for k, v in tokens.items():
    inner = inner.replace(k, v)

# Artifact body file (no <head>/<html> — wrapped at publish time)
(REPO / "dist").mkdir(exist_ok=True)
(REPO / "dist" / "app.html").write_text(inner, encoding="utf-8")

# Standalone document for direct use / GitHub Pages / bookmark
favicon = tokens["__FAVICON__"]
doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="theme-color" content="#0f1e2e"/>
<meta name="description" content="Simulateur LMNP S2A - Sud Alpes Audit : Micro-BIC vs Reel, cash-flow et impact a la revente."/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-title" content="Simulateur LMNP"/>
<title>Simulateur LMNP | S2A - Sud Alpes Audit</title>
<link rel="icon" href="{favicon}"/>
<link rel="apple-touch-icon" href="{favicon}"/>
<style>html,body{{margin:0;padding:0}}</style>
</head>
<body>
{inner}
</body>
</html>
"""
(REPO / "index.html").write_text(doc, encoding="utf-8")

print("Built: index.html (%d KB), dist/app.html (%d KB)" % (
    len((REPO / "index.html").read_text(encoding="utf-8")) // 1024,
    len(inner) // 1024))

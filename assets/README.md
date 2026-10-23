# Ikona Sellasist Connector

Plik `brand-inspired-icon.webp.b64` zawiera dokładne bajty ikony WebP zakodowane w Base64. Nie jest to oficjalne logo Sellasist.

Manifest `../manifest.json` zawiera już tę ikonę w polu `icon` jako `data:image/webp;base64,...` i nie wymaga pliku zewnętrznego.

Aby odtworzyć WebP lokalnie:

```bash
python -c "import base64,pathlib; p=pathlib.Path('assets/brand-inspired-icon.webp.b64'); p.with_suffix('').write_bytes(base64.b64decode(p.read_text().strip()))"
```

Alternatywnie `python tools/build_assets.py` odtwarza ikonę i generuje od nowa manifest.

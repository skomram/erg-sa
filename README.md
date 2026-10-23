# Sellasist Connector for Ergonode

Aplikacja typu **Ergonode Apps2** do integracji produktów, atrybutów i zdjęć z Sellasist. Kod źródłowy aplikacji uruchamiany na osobnym serwerze. **GitHub sam w sobie nie hostuje aplikacji** - wymagana jest publiczna usługa HTTPS.

## Status realizacji - ważne

| Zakres | Status |
|---|---|
| Manifest Ergonode Apps i ikona Base64 | Zaimplementowane, walidowane lokalnie |
| Handshake HS256, token X-APP-TOKEN | Zaimplementowane, testy lokalne |
| Konfiguracja wieloetapowa Apps | Zaimplementowane, testy lokalne |
| Słownik i mapowanie drag-and-drop | Zaimplementowane, testy lokalne |
| Synchronizacja delta/full/scheduler | Obsługa endpointów zaimplementowana; orkiestrację uruchamia Ergonode |
| Odczyt zdarzeń IMAGE/GALLERY | Zaimplementowane zgodnie z udokumentowanym payloadem |
| Mapowanie SKU -> Sellasist product ID | Import mapy przez chronione API administracyjne |
| Wysyłanie produktu przez PUT /products/{id} | Kod zaimplementowany; domyślnie blokowany do testu kontraktowego |
| Zastępowanie galerii | Kod przygotowany; format pola `images` do sprawdzenia z aktualnym OpenAPI Sellasist |
| Sellasist -> Ergonode | Odczyt produktu i import pól TEXT_AREA przez udokumentowaną mutację GraphQL, wymaga potwierdzenia ścieżek pól Sellasist |
| Synchronizacja wszystkich wariantów, kategorii i cen dwukierunkowo | Niezaimplementowana - bez zgadywania schematów i ryzykownych zapisów |
| Produkcja end-to-end | Niezweryfikowana - wymagane konto testowe Sellasist + instancja Ergonode |

To **nie jest deklaracja 100% kompletności**. Udostępnione interfejsy umożliwiają dalszą rozbudowę, ale uruchomienie zapisu do API produkcyjnego wymaga testu kontraktowego.

## Instalacja

1. Umieść pliki repozytorium na GitHubie (rozpakuj ZIP tak, aby `Dockerfile`, `manifest.json` i katalog `app/` były w katalogu głównym).
2. Wdróż aplikację na własnym serwerze Docker z publicznym HTTPS (reverse proxy do `127.0.0.1:8080`).
3. `cp .env.example .env`. Ustaw silny `ENCRYPTION_KEY`, `ADMIN_TOKEN`, `ERGONODE_ALLOWED_HOSTS` (host docelowej instancji Ergonode).
4. `docker compose up -d --build`.
5. Sprawdź `https://TWOJ-HOST/manifest.json`.
6. W Ergonode Apps wybierz **New app** i podaj ten adres URL do manifestu.
7. Wypełnij trzy etapy konfiguracji. Najpierw ustaw tryb `preview`, a `send_empty_gallery` pozostaw `false`.
8. Po instalacji sprawdź `GET /admin/installations` (z nagłówkiem `X-ADMIN-TOKEN`), aby poznać `app_installation_id`. Importuj powiązania SKU -> identyfikator Sellasist przed synchronizacją rzeczywistych produktów.
9. Przetestuj produkt z obrazem i galerią oraz porównaj payload ze schematem OpenAPI swojej wersji Sellasist.
10. Dopiero po testach zmień tryb na `live` i włącz `ENABLE_LIVE_WRITES=true`.

## Import identyfikatorów produktów

```bash
curl -X POST 'https://TWOJ-HOST/admin/links' \
  -H 'X-ADMIN-TOKEN: TWOJ_ADMIN_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"app_installation_id":"ID_INSTALACJI_Z_ERGONODE","products":[{"sku":"SKU1","sellasist_id":12345}]}'
```

Obsługa do 10 000 powiązań w żądaniu. Można wysłać wiele żądań. Podgląd utworzonego payloadu: `GET /admin/preview/{app_installation_id}/{sku}` z `X-ADMIN-TOKEN`.

## Import odwrotny do Ergonode

Usługa może importować tekstowe opisy pobrane z `GET /products/{id}` do atrybutów `TEXT_AREA` Ergonode przez udokumentowaną mutację `productAddAttributeValueTranslationsTextarea`.

```bash
curl -X POST 'https://TWOJ-HOST/admin/import/sellasist-textareas' \
  -H 'X-ADMIN-TOKEN: TWOJ_ADMIN_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"app_installation_id":"ID_INSTALACJI","sku":"SKU1","sellasist_product_id":12345,"fields":[{"sellasist_path":"product.description","ergonode_attribute_code":"description","language":"pl_PL"}]}'
```

**Uwaga:** `product.description` jest jedynie przykładową ścieżką. Musi odpowiadać rzeczywistej odpowiedzi `GET /products/{id}`. Domyślnie zwracany jest podgląd mutacji GraphQL bez zapisu. Włączenie wymaga `ENABLE_ERGONODE_IMPORTS=true` w kontenerze oraz potwierdzenia poprawności API URL w danych handshake.

## Ważne zasady

- Payloady zdarzeń i sekrety w bazie są szyfrowane.
- `product_deleted` nie usuwa automatycznie produktów Sellasist. W Ergonode zdarzenie może też oznaczać cofnięcie dostępu do segmentu.
- `synchronization_ended` nie wykonuje niejawnego czyszczenia danych.
- Przyrostowa synchronizacja przesyła tylko zmienione atrybuty. Aktualizacja galerii odbywa się tylko, gdy odpowiedni atrybut się zmienił.
- Pusta galeria nigdy nie usuwa zdjęć bez jawnej konfiguracji.
- Domyślne mapowanie docelowe obejmuje `name`, `description`, `ean`, `images`. Ich zgodność ze schematem PUT wymaga testu kontraktowego.
- Brak powiązania SKU do Sellasist ID jest błędem (422), a nie powodem automatycznego stworzenia niekompletnego produktu.
- `write_access=true` w manifeście jest konieczne do importu zwrotnego.
- `api_url` z handshake jest używany bez dopisywania nieudokumentowanej ścieżki.
- `api_key_header` jest konfigurowalny, ponieważ bez pobrania pliku `api.yaml` nie potwierdzono dokładnej nazwy nagłówka Sellasist.
- Ikona `assets/brand-inspired-icon.webp` jest **własnym znakiem inspirowanym barwami Sellasist**, nie oficjalnym oryginalnym logo. Przed dystrybucją publiczną zastąp zatwierdzonym zasobem marki i wygeneruj ponownie manifest przez `tools/build_assets.py`.

## Testy

```bash
pip install -r requirements-dev.txt
python tools/check_manifest.py
pytest -q
```

## Dokumentacja źródłowa

- https://docs.ergonode.com/apps2/detailed-reference/manifest
- https://docs.ergonode.com/apps2/detailed-reference/authentication
- https://docs.ergonode.com/apps2/detailed-reference/configuration
- https://docs.ergonode.com/apps2/detailed-reference/manifest/dictionaries
- https://docs.ergonode.com/apps2/detailed-reference/synchronization/synchronization-events
- https://docs.ergonode.com/apps2/detailed-reference/synchronization/synchronization-endpoints
- https://docs.ergonode.com/graphql/guides/batching-mutations
- https://api.sellasist.pl/
- https://api.sellasist.pl/changelog/

## Bezpieczeństwo

Nie zapisuj `.env` do GitHuba. Sekrety instalacji i konfiguracja są szyfrowane kluczem Fernet, dane trzymane w wolumenie Docker. Admin API wymaga `X-ADMIN-TOKEN`. Wystaw wyłącznie przez HTTPS i ogranicz dostęp do endpointów administracyjnych na poziomie reverse proxy. Do produkcji dodaj monitoring, backupy i osobną bazę/queue przy bardzo wysokim ruchu.

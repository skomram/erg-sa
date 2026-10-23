# Analiza Sellasist REST API dla integracji Ergonode Apps

Data analizy: 2026-10-23  
Wersja API wyświetlana w Swagger UI: 1.92.7.  
Status: analiza opublikowanych endpointów i historii zmian, bez wykonania żądań na koncie Sellasist i bez pobrania pełnego pliku OpenAPI YAML.

## Źródła

- REST API: https://api.sellasist.pl/
- Historia zmian API: https://api.sellasist.pl/changelog/
- Nowe parametry i model legacy: https://sellasist.pl/pomoc/parametry-produktow-konfiguracja-funkcjonalnosci-i-mapowanie
- Webhooki dla asortymentu: https://sellasist.pl/pomoc/jak-dodac-akcje-automatyczna-wywolanie-zdefiniowanego-adresu-url-webhook
- Obsługa zdjęć produktu: https://sellasist.pl/pomoc/jak-dodac-zdjecie-do-produktu
- Pola dodatkowe: https://sellasist.pl/pomoc/jak-utworzyc-dodatkowe-pola-na-karcie-produktu-w-sellasist
- Ergonode Apps: https://docs.ergonode.com/apps2/
- Synchronizacja Apps: https://docs.ergonode.com/apps2/detailed-reference/synchronization/synchronization-endpoints

**Oznaczenia**: [D] udokumentowana metoda/funkcja; [W] wniosek projektowy do implementacji; [T] niezbędny test kontraktowy; [N] niepotwierdzone w dostępnych materiałach.

## 1. Model połączenia i autoryzacja

- [D] Sellasist udostępnia REST API pod adresem konta z sufiksem `/api/v1`, np. `https://demo.sellasist.pl/api/v1`.
- [D] Klucz API generuje się w panelu `Integracje > Klucze API`.
- [N] Opublikowany widok Swaggera posługuje się nazwą `apiKey`, ale bez odczytania `components.securitySchemes` nie należy zakładać nazwy nagłówka `apiKey` ani sposobu przenoszenia tokenu. Tak samo nie należy używać niezweryfikowanego `Authorization: Bearer ...`.
- [T] Wykonać autoryzowany `GET /products?limit=1` na koncie testowym i potwierdzić sposób autoryzacji, obsługę błędnego klucza, wymagane nagłówki oraz rzeczywisty kształt odpowiedzi.
- [W] Konfiguracja musi zawierać host konta, tajny klucz przechowywany w szyfrowanym magazynie, identyfikator instalacji Apps, tryb podglądu i zakres uprawnień/operacji.
- [W] Ograniczyć hosty do dozwolonego formatu, nie logować kluczy i pełnych danych osobowych, nie obsługiwać przekierowań na niezaufane domeny.

## 2. Inwentaryzacja endpointów istotnych dla PIM

| Zasób | Operacje potwierdzone w dokumentacji | Zastosowanie |
|---|---|---|
| `/products`, `/products/{product_id}` | GET, POST (kolekcja), PUT (identyfikator) | Tworzenie i aktualizacja danych produktu |
| `/products_bulk` | GET, PUT | Masowy odczyt i aktualizacja produktów |
| `/products_logs` | GET | Dziennik zmian produktów |
| `/images`, `/images/{image_id}`, `/images/{product_id}` | POST, PUT, DELETE, GET według odpowiednich tras | Pliki i galerie produktów |
| `/categories`, `/categories/{category_id}` | GET, POST, PUT, DELETE | Drzewo kategorii |
| `/manufacturers`, `/manufacturers/{id}` | GET, POST, PUT | Producenci i marka |
| `/attributes`, `/attributes_groups`, `/attributes_properties` | GET, POST, PUT, DELETE | Starszy model atrybutów |
| `/qualities`, `/qualitiesgroups`, `/qualitiesproperties` | GET, POST, PUT, DELETE | Nowszy model parametrów |
| `/products_qualities/{product_id}` | POST, DELETE | Przypięcie/odpięcie parametrów produktu |
| `/products_fields`, `/products_fields/{field_id}` | GET, POST, PUT, DELETE | Dodatkowe pola kart produktów |
| `/products_variants`, `/products_variants/{product_variant_id}` | GET, POST, PUT | Warianty produktów |
| `/variants`, `/variants_groups`, `/variants_properties` | GET, POST (wybrane), GET szczegółów | Słowniki wariantowe |
| `/sets/{main_product_id}`, `/sets_bulk`, `/sets_items/{id}` | GET, POST, PUT, DELETE zależnie od zasobu | Zestawy produktów |
| `/storages`, `/products_stock` | GET i operacje zapisu | Magazyny i stany |
| `/products_offers` | GET, POST, PUT | Powiązania ofert marketplace |
| `/external_accounts`, `/shops` | GET | Konta sprzedażowe i sklepy |
| `/responsiblepersons`, `/responsibleproducers` | GET, POST, PUT | Dane GPSR |
| `/vat_countries`, `/vat_rates` | GET i operacje zapisu | Stawki VAT wielu krajów |
| `/orders`, `/orders_bulk`, `/orders_logs` | GET, POST, PUT zależnie od zasobu | Moduł zamówień, poza podstawowym zakresem PIM |
| `/returns`, `/returns_statuses`, `/returns_sources` | GET, POST, PUT, DELETE zależnie od zasobu | Zwroty, opcjonalnie |
| `/complaints` | GET, POST, PUT zależnie od zasobu | Reklamacje, opcjonalnie |

Uwaga: tabela jest skrótem zakresów zasobów. Ścisłe ścieżki metod i request body należy wygenerować z OpenAPI. W szczególności brak w opublikowanej liście `DELETE /products/{id}` - nie projektować twardego usuwania produktu jako domyślnej operacji.

## 3. Produkty i identyfikacja

- [D] `GET /products` wspiera `from_id` do pobierania produktów o ID większym od podanego (od 2024-06-03). Nie jest to filtr zmian istniejących produktów.
- [D] `GET /products` ma filtr `status` (od 2026-08-18), `category_id` obejmujący kategorię główną i podrzędne (od 2026-10-09), oraz filtrowanie po nazwie producenta.
- [D] Dokumentacja/changelog pokazują pola `title`, `ean`, `symbol`, `catalog_number`, `additional_eans`, `additional_fields`, `descriptions`, `manufacturer_id`, `archived`, `as_set`.
- [W] W Ergonode identyfikatorem zdarzenia produktu jest SKU (`resource_id.type=sku`). W Sellasist istnieje własne `product_id`; numer `symbol` nie może być automatycznie utożsamiany z SKU bez mapowania.
- [W] Klucze powiązania przechowywać jako `(installation_id, ergonode_sku, sellasist_product_id)` z dodatkowymi indeksami EAN/symbol; po zmianie kodu lub wykryciu duplikatu nie zakładać nowego produktu automatycznie.
- [W] Wszelkie pola mogą mieć osobny kierunek synchronizacji: Ergonode -> Sellasist, Sellasist -> Ergonode, tylko odczyt, wyłączone.
- [T] Zweryfikować rzeczywisty `product_data_update` i wymagane pola `POST /products` / `PUT /products/{id}` z surowym schematem OpenAPI. Nie używać zgadywanego `name` zamiast udokumentowanego `title`.

## 4. Zdjęcia i galerie

- [D] `GET /images/{product_id}` zwraca listę obrazów; od wersji 1.81.0 udostępnia `original_url`.
- [D] `POST /images`, `PUT /images/{image_id}`, `DELETE /images/{image_id}` służą zarządzaniu obrazami.
- [D] Od wersji 1.91.2 `PUT /products/{product_id}` obsługuje `images_replacement_flag` do zastąpienia całej galerii.
- [D] W panelu Sellasist pierwsze zdjęcie jest głównym; UI obsługuje kolejność i widoczność zdjęć według kanału/języka.
- [T] Sprawdzić request-body dla `CreateImageRequest`, `UpdateImageRequest`, `ImagesForProductSchema` i `product_data_update`, formę przekazywania URL lub pliku, format elementów tablicy i flagę zastąpienia.
- [T] Potwierdzić, czy operacja zastąpienia usuwa obrazy z biblioteki, czy tylko odłącza je od produktu, i jak ustawia zdjęcie główne/wersje językowe.
- [W] Model bezpieczny: pobranie aktualnej galerii -> wyliczenie różnicy -> podgląd -> zapis -> odczyt i kontrola -> dziennik. Nie kasować zdjęć, kiedy źródłowy URL nie działa lub brak mapowania produktu.
- [W] Przekazywać pełną, uporządkowaną listę zdjęć tylko po jawnej zgodzie na zastępowanie; pusta lista nigdy domyślnie nie czyści galerii.
- [W] Stosować identyfikatory/hash oryginalnych obrazów do wykrywania duplikatów i zmian; plik przetwarzać jako IMAGE/GALLERY Ergonode, z zachowaniem kolejności.

## 5. Dwa modele atrybutów i mapowanie

- [D] Sellasist ma starszą strukturę `Grupa -> Atrybut -> Wartość` oraz nowszą `Parametr -> Wartość`, z opcjonalnym grupowaniem.
- [D] W nowym modelu parametry i wartości można tworzyć/zmieniać przez `/qualities`, `/qualitiesgroups`, `/qualitiesproperties`; przypisanie do produktu jest obsługiwane przez `/products_qualities/{product_id}`.
- [W] Ekran mapowania musi rozróżniać pole systemowe, legacy attribute, quality/qualityproperty, dodatkowe pole, opis, wariant oraz zdjęcie/galerię.
- [W] Reguły transformacji: słownik wartości, mapowanie ID, łączenie wielu pól, prefiks/sufiks, jednostki, liczby dziesiętne, wartości puste, języki, wielowartościowość i rozdzielanie wartości.
- [T] Potwierdzić, które typy `Ergonode TEXT/TEXT_AREA/SELECT/MULTI_SELECT/DATE/NUMERIC/UNIT/PRICE/IMAGE/GALLERY/FILE/PRODUCT_RELATION` są zapisowalne do jakich typów pola Sellasist i czy `GET /products/{id}` zawiera całą konfigurację legacy attributes.

## 6. Kategorie, warianty i zestawy

- [D] Od wersji 1.90.9 `PUT /products` obsługuje `categories_replacement_mode`: `0` dopisuje kategorie, `1` usuwa poprzednie przypisania i zastępuje nowymi.
- [D] Istnieją zasoby produktów wariantowych oraz wariantowych słowników.
- [D] Zestawy są obsługiwane przez `/sets/{main_product_id}`, `/sets_bulk` i usuwanie pozycji `/sets_items/{id}`.
- [W] Synchronizacja zasobów powinna mieć kolejność: producent -> słowniki/parametry -> kategorie -> produkty bazowe -> warianty/zestawy/relacje -> obrazy i aktualizacje wtórne.
- [W] Dla pustych kategorii nie stosować automatycznie trybu zastąpienia; dla relacji nie usuwać stron niewidocznych z powodu segmentów/uprawnień Ergonode.
- [T] Zweryfikować kompletność danych wariantu i dostępne opcje usunięcia/dezaktywacji wariantu.

## 7. Ceny, magazyny, waluty

- [D] `/products_bulk` obsługuje masową aktualizację i odczyt wielu pól produktu.
- [D] `/products_stock` od czerwca 2026 wspiera masowy odczyt i zapis stanów.
- [D] W wersji 1.92.3 (2026-10-09) `pricesfieldsvalues` może zawierać `currency`, aby zapisać ręczną cenę określonej waluty bez zmiany `value` w walucie domyślnej; odpowiedź zawiera nowy obiekt `prices`.
- [D] `/products_bulk` od 1.92.4 obsługuje `additional_fields`, a błędne wartości mogą wrócić jako `warnings` bez przerwania zapisu pozostałych danych.
- [W] Ceny, promocje, VAT, waluty oraz magazyny synchronizować jako oddzielne strumienie z jawnie wybranym systemem nadrzędnym.
- [W] Rozdzielić stan magazynowy od dostępności handlowej; nie nadpisywać stanów Sellasist danymi PIM, chyba że operator wybierze taki tryb.
- [W] W odpowiedziach masowych kontrolować status pozycji, warnings i nie tylko HTTP 2xx.
- [T] Sprawdzić maksymalny rozmiar paczek, paginację i przepustowość konta. Opublikowane schematy zawierają błędy `400`, `413`, ale brak potwierdzonego limitu RPS.

## 8. Marketplace, GPSR, dokumenty i pola dodatkowe

- [D] `/products_offers` pozwala pobierać, tworzyć i przepinać powiązania ofert z produktami/wariantami; od 1.91.8 dokumentuje przepinanie masowe do 1000 ofert.
- [D] API udostępnia producentów, osoby i producentów odpowiedzialnych GPSR.
- [D] `/products_fields` udostępnia pola dodatkowe; panel Sellasist wskazuje, że dane takich pól są widoczne administratorowi, nie automatycznie w kanałach sprzedaży.
- [W] Dane ofert i identyfikatorów marketplace traktować jako obszar Sellasist, nie nadpisywać ich przez synchronizację katalogu PIM.
- [N] Osobna biblioteka dokumentów PIM (PDF, instrukcje, certyfikaty) nie jest w widocznej liście REST API takim samym zasobem jak `images`. Należy przetestować dozwolone pola plikowe i dodatkowe pola produktu przed zadeklarowaniem obsługi dokumentów.

## 9. Synchronizacja zwrotna Sellasist -> Ergonode

- [D] Sellasist posiada konfigurator automatyzacji, także dla asortymentu, z efektem `Wywołaj URL` oraz żądaniem GET/POST/HEAD i własnymi nagłówkami.
- [D] REST API udostępnia `/products_logs`; istnienie listy logów nie dowodzi jeszcze kompletności filtra zmian ani istnienia własnego webhooka API dla każdej operacji.
- [W] Po stronie Apps obsługiwać webhooki jako impulsy do pobrania stanu produktu przez Sellasist API, nie przyjmować treści webhooka jako bezpośredniego źródła prawdy.
- [W] Dodać harmonogram przyrostowego odpytywania i pełną kontrolę okresową. `from_id` wykrywa tylko ID wyższe od znacznika i NIE wykrywa aktualizacji już istniejących produktów.
- [W] Zapobiegać pętlom: pochodzenie zdarzenia, zapis hash ostatniej wersji, krótka blokada powrotna i priorytet danych dla każdego pola.
- [T] Sprawdzić w Sellasist zestaw warunków/efektów automatyzacji asortymentu, payload, sposób potwierdzania, retries i autoryzację webhooka.

## 10. Niezbędna odporność operacyjna

- Kolejka zadań, retry z wykładniczym opóźnieniem i jitter, osobna obsługa błędów 401, 404, 422, 413 i 5xx; ewentualne 429 po weryfikacji odpowiedzi.
- Idempotentne operacje i tabela powiązań SKU/ID/wersji/ostatniego zapisu.
- Checkpoint paginacji i wznowienie po awarii; nie uznawać partii za kompletną przy partial success.
- Diff przed zapisem, dry-run, audyt źródła i celu, przywracanie poprzednich galerii i mapowań.
- Ochrona przed SSRF przy pobieraniu URL zdjęć, kontrola przekierowań, typu MIME, maksymalnego rozmiaru pliku, niedostępnych i wygasłych URL.
- Kontrola danych wielojęzycznych, separatorów dziesiętnych, stref czasu, jednostek miary i wielowalutowości.
- Testy kontraktowe na API testowym Sellasist: schemat request/response, błąd autoryzacji, błędne ID, duplikaty SKU/EAN, zapisy pustych pól, zdjęcie główne, pełne zastąpienie, masowe warnings, retry, warianty, zestawy, słowniki.

## 11. Audyt projektu Sellasist Connector for Ergonode 0.1.0

Audyt dotyczy kodu z poprzedniego archiwum rozmowy, nie produkcyjnej instalacji.

| Obecnie | Problem / zalecenie |
|---|---|
| Klient HTTP: tylko `GET /products/{id}`, `PUT /products/{id}`, `GET /images/{id}` | Rozbudować o pozostałe potwierdzone zasoby |
| Nagłówek `apiKey` z wyborem trzech wartości | Zweryfikować definicję `securitySchemes` OpenAPI zamiast zgadywania |
| Docelowe pola `name`, `description`, `ean`, `images` | Powiązać z faktycznym `product_data_update`, m.in. `title`, `descriptions` |
| Galeria w formacie `url_strings` lub `objects_url` | Obie formy są hipotetyczne, sprawdzić `ImagesForProductSchema` |
| Włączanie zastąpienia galerii | Zachować jako funkcję wymagającą pełnego testu zapisu/odczytu |
| Atrybuty i kategorie tylko logowane | Brakuje rzeczywistej synchronizacji słowników/kategorii |
| Mapowanie SKU -> ID przez ręczny import | Dodać bezpieczne wyszukiwanie i dopasowanie oraz kontrolę konfliktów |
| `Sellasist -> Ergonode` tylko `TEXT_AREA` na wywołanie admina | Dodać kolejkę wejściową, webhooki i mapowania innych pól |
| Brak katalogu wariantów/zestawów/producentów | Rozbudować po przetestowaniu kontraktów |
| Testy klienta używają `httpx.MockTransport` | To testy własnego kodu, nie zgodności z działającym Sellasist |
| Brak przetwarzania bulk warnings | Dodać detekcję częściowego sukcesu przy HTTP 2xx |
| Brak porównywania galeria przed nadpisaniem | Dodać diff, zabezpieczenie kolejności i przywracanie |

## 12. Punkty blokujące deklarację 100% zgodności

1. Nie udało się pobrać pełnego źródłowego `api.yaml` z Swagger UI. Interfejs reklamuje wersję `1.92.7`, a etykieta pliku ma `api.yaml?v=1.90.7`; nazwa parametru wersji nie dowodzi, że treść YAML jest przestarzała.
2. Brak możliwości wykonania próbnych wywołań do rzeczywistego konta Sellasist. Nie należy prosić o klucz API w czacie ani umieszczać go na GitHubie.
3. Niezatwierdzone schematy `images`, `CreateImageRequest`, `UpdateImageRequest`, `product_data_update`, `products_bulk`, `qualities`, autoryzacja `apiKey` i paginacja.
4. Brak zmierzonego limitu zapytań API, rozmiaru batchy i zachowania przy częściowym sukcesie.
5. Nieprzetestowane skutki zastępowania galerii, kategorii i innych danych w istniejących kanałach sprzedaży.

## 13. Plan akceptacji następnej wersji

- P0 - autoryzacja i GET, GET/PUT produktu, poprawne mapowanie SKU/ID, zdjęcia z zastąpieniem i weryfikacją odczytu, dry-run, audyt i rollback.
- P1 - słowniki legacy i qualities, grupy, wartości, kategorie, producenci, bulk i warnings, warianty, zestawy, ceny i VAT, magazyny.
- P2 - webhooki asortymentowe, logi Sellasist, import zwrotny, dynamiczne mapowanie i reguły konfliktów.
- P3 - marketplace links, GPSR, pliki, rozbudowane pola dodatkowe, scenariusze wielokontowe i wysoką skalę.

**Stan końcowy:** dokumentacja potwierdza szeroką możliwość integracji. Dotychczasowy projekt 0.1.0 jest bazą demonstracyjną i nie może być oznaczony jako kompletne, kontraktowo zweryfikowane rozwiązanie do produkcji.

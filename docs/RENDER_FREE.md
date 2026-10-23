# Darmowe uruchomienie testowe na Render

**Cel:** uruchomienie publicznego serwera HTTPS aplikacji Sellasist Connector bez lokalnej instalacji i bez Codex.

## Uruchomienie krok po kroku

1. Otwórz: https://render.com/deploy?repo=https://github.com/skomram/erg-sa
2. Zaloguj się w Render (możesz użyć GitHub). Jeśli zobaczysz prośbę o uprawnienie do repozytorium, zatwierdź dostęp do `skomram/erg-sa`.
3. Render pobierze plik `render.yaml` z gałęzi `main` i przygotuje usługę Docker o nazwie zbliżonej do `sellasist-ergonode-test` w regionie Frankfurt na planie **Free**. Upewnij się, że na podsumowaniu nadal widnieje **Free**.
4. Przy tworzeniu usługi ustaw `ERGONODE_ALLOWED_HOSTS` - hostname z adresu API instancji Ergonode, bez `https://` ani ścieżek. Przykład: `pim.example.com`. Jeśli host API jest inny niż panel Ergonode, należy podać host API, którego używa Apps podczas handshake. Pozostałe sekrety `ENCRYPTION_KEY` i `ADMIN_TOKEN` Render wygeneruje automatycznie.
5. Zatwierdź wdrożenie Blueprint. Render zbuduje obraz z istniejącego `Dockerfile`. Po zakończeniu udostępni adres HTTPS w domenie `onrender.com`.
6. Otwórz otrzymany adres z końcówką `/healthz`. Oczekiwany wynik: `{"status":"ok"}`.
7. Otwórz ten sam adres z końcówką `/manifest.json`. Powinien zwrócić JSON z nazwą `Sellasist Connector`.
8. W Ergonode przejdź do **Apps -> New app**, wklej dokładnie adres z punktu 7, np. `https://NAZWA-TWOJEJ-USLUGI.onrender.com/manifest.json` i przeprowadź instalację oraz konfigurację.
9. Pozostaw `write_mode=preview`, `replace_images=false`, `send_empty_gallery=false`. Zapis do Sellasist i zwrotny import do Ergonode są dodatkowo wyłączone przez flagi środowiskowe.

## Ważne ograniczenie planu Free

Na Render Free serwis zasypia po 15 minutach bez ruchu i jego ponowne uruchomienie może trwać około minuty. **Lokalna baza SQLite znika przy uśpieniu, restarcie lub ponownym wdrożeniu.** Nasz projekt zapisuje w niej instalacje Ergonode, klucze współdzielone, konfiguracje i mapowania produktów. Po takim zdarzeniu utraci powiązanie z Ergonode i wymaga ponownej instalacji/configuracji.

Dlatego ten plan jest **wyłącznie do jednorazowej demonstracji endpointów / krótkiego testu handshake**, nie do ciągłej synchronizacji PIM. Nie włączaj synchronizacji danych produkcyjnych. Dla trwalszej pracy potrzebny jest serwer z trwałym wolumenem SQLite lub przeróbka aplikacji na bazę zewnętrzną, a dla niezawodnych webhooków także serwer bez usypiania.

## Gdy instalacja nie działa

- Nie wklejaj do Ergonode adresu `github.com` ani `raw.githubusercontent.com` - nie uruchamiają one endpointów aplikacji.
- Jeśli nie działa `/healthz`, sprawdź `Logs` i `Events` w Render, zwłaszcza obecność poprawnego `ENCRYPTION_KEY`.
- Jeśli nie działa handshake, sprawdź `ERGONODE_ALLOWED_HOSTS` oraz to, czy usługa nie jest akurat uśpiona.
- Jeśli Render prosi o kartę lub proponuje usługę płatną, upewnij się, że nie wybierasz planu Starter ani dysku trwałego.
- Nie umieszczaj klucza Sellasist w repozytorium GitHub, zgłoszeniu GitHub ani publicznym linku.

Źródła:
- https://render.com/docs/free
- https://render.com/docs/deploy-to-render
- https://render.com/docs/blueprint-spec
- https://docs.ergonode.com/apps2/quick-start

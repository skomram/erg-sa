# Instalacja Sellasist Connector w Ergonode Apps

## Stan projektu

- Repozytorium: https://github.com/skomram/erg-sa
- Manifest w repozytorium: https://github.com/skomram/erg-sa/blob/main/manifest.json
- Bezpośredni plik JSON: https://raw.githubusercontent.com/skomram/erg-sa/main/manifest.json
- Kod aplikacji: `app/`; obraz Docker: `Dockerfile`; przykładowa konfiguracja: `.env.example`.
- Projekt demonstracyjny: **nieprzetestowany z produkcyjnym kontem Sellasist**. Zapis danych domyślnie wyłączony.

## Dlaczego nie należy instalować przez raw.githubusercontent.com?

Ergonode Apps przyjmuje adres URL manifestu JSON, ale aplikacja musi również obsługiwać żądania HTTP (m.in. `POST /handshake`, `GET/POST /configuration`, `PUT /consume/{event}`) pod adresem swojej usługi.

W manifeście parametr `url` jest opcjonalny. Gdy go brakuje, **Ergonode przyjmuje host manifestu jako host aplikacji**. Wklejenie `https://raw.githubusercontent.com/skomram/erg-sa/main/manifest.json` spowoduje więc skierowanie handshake do serwera GitHuba, który nie obsługuje backendu tej aplikacji. Sam GitHub nie uruchamia usługi FastAPI.

## Jak uzyskać adres gotowy do rejestracji?

1. Uruchom aplikację na serwerze z publicznym HTTPS (np. własny VPS z Docker i reverse proxy). Nie wystarczy GitHub Pages.
2. Skonfiguruj plik `.env` poza repozytorium zgodnie z `.env.example`: `ENCRYPTION_KEY`, `ADMIN_TOKEN`, `ERGONODE_ALLOWED_HOSTS`. Nigdy nie publikuj kluczy na GitHubie.
3. Uruchom `docker compose up -d --build` i wystaw port backendu przez własną domenę z TLS.
4. Potwierdź w przeglądarce `https://TWOJ-HOST/healthz` i `https://TWOJ-HOST/manifest.json`.
5. W panelu Ergonode przejdź do **Apps -> New app** i wklej **`https://TWOJ-HOST/manifest.json`**, a nie surowy adres pliku na GitHubie.
6. W konfiguracji Apps ustaw połączenie Sellasist i pozostaw tryb `preview` oraz opcję czyszczenia galerii wyłączoną, dopóki kontrakty API Sellasist nie zostaną potwierdzone.

Dzięki udostępnianiu manifestu bezpośrednio przez uruchomioną aplikację nie trzeba na stałe ustawiać w manifeście `url`: host jest wtedy prawidłowo wyznaczany z URL manifestu.

## Weryfikacja lokalna

```bash
pip install -r requirements-dev.txt
python tools/check_manifest.py
python -m pytest -q
```

## Źródła

- https://docs.ergonode.com/apps2/quick-start
- https://docs.ergonode.com/apps2/detailed-reference/manifest
- https://docs.ergonode.com/apps2/detailed-reference/authentication
- https://docs.ergonode.com/apps2/detailed-reference/configuration
- https://docs.ergonode.com/apps2/detailed-reference/synchronization/synchronization-endpoints

"""Fetch sicuro di risorse da URL esterni per l'estrazione bando (#16).

Espone due funzioni principali:
- fetch_url_safely(url): scarica il contenuto validando schema/host a ogni
  hop di redirect (protezione SSRF), con limite di dimensione e timeout.
- extract_text_from_html(html): estrae il testo "pulito" (senza nav/footer/
  script) da una pagina HTML, per poi riusare extract_bando_data() esistente.

Nota di sicurezza: l'allow-list dello schema (solo https) da sola non basta
a prevenire SSRF, perché un URL può reindirizzare verso un host interno
(es. il metadata endpoint di un cloud provider, 169.254.169.254) pur
partendo da uno schema/host pubblico legittimo. Per questo motivo i redirect
NON sono delegati alla libreria `requests` (allow_redirects=True) ma seguiti
manualmente, uno alla volta, rivalidando schema e host a ogni hop.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

from modules.schema import MIN_TEXT_CHARS

ALLOWED_URL_SCHEMES = {"https"}
URL_FETCH_TIMEOUT_SECONDS = 15
URL_FETCH_MAX_BYTES = 10_000_000  # 10 MB, stesso limite dell'upload PDF
URL_FETCH_MAX_REDIRECTS = 3
URL_FETCH_CHUNK_SIZE = 65536
USER_AGENT = "BandiScannerBot/1.0 (+estrazione automatica bandi)"


class InvalidUrlException(Exception):
    """URL non valido o non consentito (schema, host privato, troppo grande,
    troppi redirect). Il messaggio è pensato per essere mostrato all'utente."""


def _is_public_hostname(hostname: str) -> bool:
    """True se l'hostname risolve solo a indirizzi IP pubblici.

    Rifiuta risoluzioni verso IP privati/loopback/link-local/riservati per
    prevenire SSRF verso servizi interni. Un hostname che risolve a più IP
    (round-robin DNS) è considerato pubblico solo se TUTTI gli IP lo sono.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def validate_bando_url(url: str) -> None:
    """Valida schema e host di un URL fornito dall'utente.

    Solleva InvalidUrlException con un messaggio adatto a essere mostrato
    all'utente se l'URL non è valido o non è consentito.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise InvalidUrlException("URL non valido.") from exc

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise InvalidUrlException("Sono supportati solo link che iniziano con https://.")
    if not parsed.hostname:
        raise InvalidUrlException("URL non valido: host mancante.")
    if not _is_public_hostname(parsed.hostname):
        raise InvalidUrlException("URL non consentito: punta a un host interno o non raggiungibile.")


def fetch_url_safely(url: str) -> tuple[bytes, str, str | None, str]:
    """Scarica una risorsa da URL, seguendo i redirect manualmente e
    rivalidando schema/host a ogni hop.

    Ritorna (contenuto, content_type, encoding, url_finale).
    Solleva InvalidUrlException (URL/redirect non validi, risorsa troppo
    grande, troppi redirect) o requests.RequestException (errori di rete).
    """
    current_url = url

    for _ in range(URL_FETCH_MAX_REDIRECTS + 1):
        validate_bando_url(current_url)

        resp = requests.get(
            current_url,
            timeout=URL_FETCH_TIMEOUT_SECONDS,
            stream=True,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
        )
        try:
            if resp.is_redirect or resp.is_permanent_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise InvalidUrlException("Il link reindirizza senza indicare una destinazione valida.")
                current_url = urljoin(current_url, location)
                continue

            content = bytearray()
            for chunk in resp.iter_content(chunk_size=URL_FETCH_CHUNK_SIZE):
                content.extend(chunk)
                if len(content) > URL_FETCH_MAX_BYTES:
                    raise InvalidUrlException(
                        f"Risorsa troppo grande (limite {URL_FETCH_MAX_BYTES // 1_000_000} MB)."
                    )

            content_type = resp.headers.get("content-type", "")
            encoding = resp.encoding
            return bytes(content), content_type, encoding, current_url
        finally:
            resp.close()

    raise InvalidUrlException("Troppi redirect (limite superato).")


def extract_text_from_html(html: str) -> str:
    """Estrae il testo principale da una pagina HTML, scartando
    navigazione/footer/script. Ritorna stringa vuota se l'estrazione fallisce
    (il chiamante decide come trattare il caso, in analogia a un PDF vuoto)."""
    text = trafilatura.extract(html, favor_recall=True) or ""
    return text if len(text.strip()) >= MIN_TEXT_CHARS else ""

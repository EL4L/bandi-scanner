"""Test per modules/url_extractor.py — fetch sicuro URL e estrazione HTML (#16)."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.url_extractor import (
    InvalidUrlException,
    URL_FETCH_MAX_BYTES,
    URL_FETCH_MAX_REDIRECTS,
    extract_text_from_html,
    fetch_url_safely,
    validate_bando_url,
)


def test_validate_bando_url_https_pubblico_ok():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_bando_url("https://www.example.com/bando.pdf")


def test_validate_bando_url_rifiuta_http():
    with pytest.raises(InvalidUrlException, match="https"):
        validate_bando_url("http://www.example.com")


def test_validate_bando_url_rifiuta_ftp():
    with pytest.raises(InvalidUrlException, match="https"):
        validate_bando_url("ftp://www.example.com")


def test_validate_bando_url_rifiuta_file_scheme():
    with pytest.raises(InvalidUrlException):
        validate_bando_url("file:///etc/passwd")


def test_validate_bando_url_rifiuta_host_mancante():
    with pytest.raises(InvalidUrlException, match="host mancante"):
        validate_bando_url("https:///percorso-senza-host")


def test_validate_bando_url_rifiuta_loopback():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        with pytest.raises(InvalidUrlException, match="non consentito"):
            validate_bando_url("https://localhost/")


def test_validate_bando_url_rifiuta_ip_privato_10():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://intranet.aziendale.local/")


def test_validate_bando_url_rifiuta_ip_privato_192():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.1", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://router.local/")


def test_validate_bando_url_rifiuta_link_local_metadata_cloud():
    """169.254.169.254 è il metadata endpoint standard su AWS/GCP/Azure —
    un bersaglio SSRF classico se non bloccato esplicitamente."""
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("169.254.169.254", 0))]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://metadata.internal/")


def test_validate_bando_url_rifiuta_se_dns_non_risolve():
    import socket as socket_module
    with patch("socket.getaddrinfo", side_effect=socket_module.gaierror("nome a dominio inesistente")):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://dominio-che-non-esiste-xyz123.test/")


def test_validate_bando_url_rifiuta_se_uno_dei_multi_ip_e_privato():
    """DNS round-robin: se anche solo uno degli IP risolti è privato, l'host
    non è considerato pubblico (difesa in profondità)."""
    with patch("socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("93.184.216.34", 0)),
        (2, 1, 6, "", ("10.0.0.1", 0)),
    ]):
        with pytest.raises(InvalidUrlException):
            validate_bando_url("https://misto.example.com/")


def _make_response(*, status_ok=True, is_redirect=False, location=None,
                    chunks=(b"contenuto",), headers=None):
    resp = MagicMock()
    resp.is_redirect = is_redirect
    resp.is_permanent_redirect = False
    resp.headers = headers or {}
    if is_redirect and location:
        resp.headers = {**resp.headers, "location": location}
    resp.iter_content = MagicMock(return_value=iter(chunks))
    resp.encoding = "utf-8"
    resp.close = MagicMock()
    return resp


def test_fetch_url_safely_scarica_contenuto_semplice():
    resp = _make_response(chunks=(b"hello ", b"world"), headers={"content-type": "text/html"})
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=resp) as mock_get:
            content, content_type, encoding, final_url = fetch_url_safely("https://www.example.com/bando")
    assert content == b"hello world"
    assert content_type == "text/html"
    assert final_url == "https://www.example.com/bando"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["allow_redirects"] is False


def test_fetch_url_safely_segue_un_redirect_e_rivalida():
    redirect_resp = _make_response(is_redirect=True, location="https://www.example.com/finale")
    final_resp = _make_response(chunks=(b"pagina finale",))
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", side_effect=[redirect_resp, final_resp]) as mock_get:
            content, _, _, final_url = fetch_url_safely("https://www.example.com/vecchio")
    assert content == b"pagina finale"
    assert final_url == "https://www.example.com/finale"
    assert mock_get.call_count == 2


def test_fetch_url_safely_rifiuta_redirect_verso_ip_privato():
    """Il caso critico SSRF: il primo hop è pubblico, il redirect punta a un
    host privato — deve essere rifiutato comunque, non solo il primo hop."""
    redirect_resp = _make_response(is_redirect=True, location="https://intranet.local/segreto")

    def fake_getaddrinfo(hostname, *_args, **_kwargs):
        if hostname == "intranet.local":
            return [(2, 1, 6, "", ("10.0.0.1", 0))]
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
        with patch("requests.get", return_value=redirect_resp):
            with pytest.raises(InvalidUrlException):
                fetch_url_safely("https://www.example.com/vecchio")


def test_fetch_url_safely_rifiuta_troppi_redirect():
    redirect_resp = _make_response(is_redirect=True, location="https://www.example.com/loop")
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=redirect_resp) as mock_get:
            with pytest.raises(InvalidUrlException, match="redirect"):
                fetch_url_safely("https://www.example.com/loop")
    assert mock_get.call_count == URL_FETCH_MAX_REDIRECTS + 1


def test_fetch_url_safely_rifiuta_risorsa_troppo_grande():
    chunk = b"x" * (URL_FETCH_MAX_BYTES // 4 + 1)
    resp = _make_response(chunks=(chunk, chunk, chunk, chunk, chunk))
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", return_value=resp):
            with pytest.raises(InvalidUrlException, match="grande"):
                fetch_url_safely("https://www.example.com/file-enorme")


def test_fetch_url_safely_propaga_errori_di_rete():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        with patch("requests.get", side_effect=requests.ConnectionError("timeout")):
            with pytest.raises(requests.RequestException):
                fetch_url_safely("https://www.example.com/irraggiungibile")


def test_extract_text_from_html_scarta_nav_e_footer():
    html = (
        "<html><body>"
        "<nav>Home Chi siamo Contatti</nav>"
        "<article><h1>Bando Innovazione</h1><p>"
        + ("Contenuto informativo del bando. " * 15)
        + "</p></article>"
        "<footer>Copyright 2026 Tutti i diritti riservati</footer>"
        "</body></html>"
    )
    text = extract_text_from_html(html)
    assert "Bando Innovazione" in text
    assert "Contenuto informativo" in text
    assert "Copyright" not in text
    assert "Chi siamo" not in text


def test_extract_text_from_html_ritorna_stringa_vuota_se_troppo_corto():
    html = "<html><body><p>Ciao</p></body></html>"
    assert extract_text_from_html(html) == ""


def test_extract_text_from_html_ritorna_stringa_vuota_se_pagina_vuota():
    assert extract_text_from_html("<html><body></body></html>") == ""

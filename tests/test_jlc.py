"""JLC istemcisi: sunucu bağlantıyı yanıtsız kapatınca tarama düşmemeli, yeniden denemeli."""
import http.client
import io
import json

import muadil.jlc as jlc


class Yanit(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_kopan_baglanti_yeniden_denenir(monkeypatch):
    cagri = []

    def sahte(r, timeout=0):
        cagri.append(1)
        if len(cagri) < 3:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return Yanit(json.dumps({"code": 200, "data": {"tamam": 1}}).encode())

    monkeypatch.setattr(jlc.urllib.request, "urlopen", sahte)
    monkeypatch.setattr(jlc.time, "sleep", lambda s: None)
    assert jlc.istek({}) == {"tamam": 1} and len(cagri) == 3

"""JLCPCB parça kataloğu istemcisi.

JLCPCB'nin kendi sitesinin kullandığı arama ucu: anahtarsız, canlı stok ve fiyat verir.
Tek sorguda en çok 100 sayfa x 1000 parça döner; büyük üst kategoriler alt kategorilere bölünür.
Kibar tarama: istekler arasında bekleme, hata olursa artan beklemeyle yeniden deneme.
"""
import gzip
import http.client
import json
import re
import time
import urllib.request
from pathlib import Path

ARAMA = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
AJAN = "muadil/0.1 (+https://github.com/melikeatilgan)"
SAYFA = 1000
SAYFA_SINIRI = 100
KATEGORILER = json.loads((Path(__file__).parent / "kategoriler.json").read_text(encoding="utf-8"))

# Ham kayıttan saklanan alanlar (gerisi sitenin iç bilgisi).
ALANLAR = ("componentCode", "componentModelEn", "componentBrandEn", "componentSpecificationEn",
           "firstSortName", "secondSortName", "componentLibraryType", "preferredComponentFlag",
           "stockCount", "componentPrices", "describe", "attributes", "dataManualUrl",
           "lcscGoodsUrl", "minImage", "minPurchaseNum", "rohsFlag")


def istek(govde: dict, deneme: int = 5) -> dict:
    veri = json.dumps(govde).encode()
    for i in range(deneme):
        try:
            r = urllib.request.Request(ARAMA, data=veri, headers={
                "Content-Type": "application/json", "User-Agent": AJAN, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(r, timeout=90) as y:
                ham = y.read()
                if y.headers.get("Content-Encoding") == "gzip":
                    ham = gzip.decompress(ham)
            d = json.loads(ham)
            if d.get("code") != 200:
                raise RuntimeError(f"JLC yanıt kodu {d.get('code')}: {d.get('message')}")
            return d["data"]
        # OSError: URLError, zaman aşımı ve sunucunun bağlantıyı yanıtsız kapatması (RemoteDisconnected) dahil
        except (OSError, http.client.HTTPException, RuntimeError, json.JSONDecodeError) as e:
            if i == deneme - 1:
                raise
            time.sleep(10 * 2 ** i)  # 10, 20, 40, 80 sn
            print(f"  yeniden deneme {i + 1}: {e}", flush=True)


def kirp(r: dict) -> dict:
    return {k: r.get(k) for k in ALANLAR}


def ara(anahtar: str, adet: int = 50) -> list[dict]:
    """Canlı arama: parça kodu, MPN ya da anahtar kelime."""
    d = istek({"keyword": anahtar, "currentPage": 1, "pageSize": adet})
    sayfa = d.get("componentPageInfo") or {}
    return [kirp(r) for r in sayfa.get("list") or []]


def sayi(ust: str, alt: str | None = None) -> int:
    govde = {"currentPage": 1, "pageSize": 1, "presaleType": "stock", "firstSortName": ust}
    if alt:
        govde["secondSortName"] = alt
    return (istek(govde).get("componentPageInfo") or {}).get("total", 0)


def sayfalar(ust: str, alt: str | None = None, bekle: float = 1.0):
    """Stoklu parçaları sayfa sayfa getirir."""
    for no in range(1, SAYFA_SINIRI + 1):
        govde = {"currentPage": no, "pageSize": SAYFA, "presaleType": "stock", "firstSortName": ust}
        if alt:
            govde["secondSortName"] = alt
        liste = (istek(govde).get("componentPageInfo") or {}).get("list") or []
        if not liste:
            return
        yield [kirp(r) for r in liste]
        if len(liste) < SAYFA:
            return
        time.sleep(bekle)


def dilim_adi(ust: str, alt: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9()_.,&-]+", "_", ust + ("__" + alt if alt else ""))[:120]


def tara(hedef: Path, bekle: float = 1.0, taze_saat: float = 12) -> dict:
    """Tüm stoklu kataloğu tarar; her (üst, alt) dilimini ayrı jsonl.gz dosyasına yazar.
    Son `taze_saat` içinde yazılmış dilimler atlanır (yarıda kalan tarama kaldığı yerden sürer)."""
    hedef.mkdir(parents=True, exist_ok=True)
    rapor = {}
    for ust, altlar in KATEGORILER.items():
        toplam = sayi(ust)
        dilimler = [(ust, None)] if toplam <= SAYFA * SAYFA_SINIRI else [(ust, a) for a in altlar]
        for u, a in dilimler:
            ad = dilim_adi(u, a)
            dosya = hedef / f"{ad}.jsonl.gz"
            if dosya.exists() and time.time() - dosya.stat().st_mtime < taze_saat * 3600:
                with gzip.open(dosya, "rt", encoding="utf-8") as f:
                    rapor[ad] = sum(1 for _ in f)
                continue
            n = 0
            with gzip.open(dosya.with_suffix(".yeni"), "wt", encoding="utf-8") as f:
                for liste in sayfalar(u, a, bekle):
                    for r in liste:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    n += len(liste)
            dosya.with_suffix(".yeni").replace(dosya)
            rapor[ad] = n
            print(f"{n:>7}  {ad}", flush=True)
        if len(dilimler) > 1:
            alinan = sum(rapor[dilim_adi(ust, a)] for _, a in dilimler)
            rapor[ust + " (eksik)"] = toplam - alinan
            print(f"  {ust}: toplam {toplam}, alt kategorilerden {alinan}", flush=True)
    return rapor


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["tara"]:
        kok = Path(__file__).resolve().parent.parent / "veri" / "ham" / "jlc"
        r = tara(kok)
        (kok / "rapor.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print("bitti:", sum(v for k, v in r.items() if not k.endswith("(eksik)")))
    else:
        for p in ara(" ".join(sys.argv[1:]) or "C6186")[:10]:
            print(p["componentCode"], p["componentModelEn"], p["componentBrandEn"], p["stockCount"])

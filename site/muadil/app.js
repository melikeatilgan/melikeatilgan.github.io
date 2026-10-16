// Muadil arayüzü: statik veri dosyalarını okur, sunucu gerektirmez.
import { h, sayi, dolar, hazirla, parca, bul } from "./veri.js";

const $ = (s) => document.querySelector(s);
const durum = $("#durum");
const sonuc = $("#sonuc");

const SINIFLAR = [
  ["dogrudan", "Doğrudan takılır", "iyi"],
  ["farkli", "Takılır, farkları var", "uyari"],
  ["kontrol", "Kontrol gerekli", ""],
  ["farkli_kilif", "Farklı kılıf", ""],
  ["uygun_degil", "Uygun değil", "kotu"],
];
const JLC_SINIF = { temel: ["JLC temel", "iyi"], tercihli: ["JLC tercihli", "vurgu"], genis: ["JLC genişletilmiş", ""] };
const AILE = {
  regulator: "LDO / doğrusal regülatör", transistor: "Transistör", diyot: "Diyot", opamp: "Op-amp / karşılaştırıcı",
  zamanlayici: "555 zamanlayıcı", lojik: "Lojik", direnc: "Chip direnç", mlcc: "Seramik kondansatör (MLCC)",
};
const PIN_DURUM = { tamam: "Uyumlu", uyari: "Not", hata: "Uyumsuz", belirsiz: "Belirsiz" };

let meta;
let nesil = 0; // her arama ve ayrıntı açma yeni nesil; geç gelen eski yanıt ekrana yazılmaz
async function baslat() {
  meta = await hazirla();
  const t = new Date(meta.tarama * 1000);
  $("#meta").textContent = `Veri: ${t.toLocaleDateString("tr-TR")} ${t.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })} ` +
    `tarihli JLCPCB taraması, ${sayi(meta.parca)} stoklu parça. Pin tablosu olan parça: ${sayi(meta.pin_tablolu ?? meta.pinli)}.`;
}

async function ara(q) {
  q = q.trim();
  if (!q) return;
  const n = ++nesil;
  history.replaceState(null, "", "?q=" + encodeURIComponent(q));
  $("#sorgu").value = q;
  durum.textContent = "Aranıyor...";
  sonuc.innerHTML = "";
  try {
    if (/^C\d+$/i.test(q)) {
      const p = await parca(q.toUpperCase());
      if (n !== nesil) return;
      if (!p) return bulunamadi(q);
      durum.textContent = "";
      return goster(p);
    }
    if (q.replace(/[^A-Za-z0-9]/g, "").length < 2) { durum.textContent = "En az iki karakter yazın."; return; }
    const { birebir, yakin, eksik } = await bul(q);
    if (n !== nesil) return;
    if (!birebir.length && !yakin.length && !eksik) return bulunamadi(q);
    durum.textContent = "";
    let html = eksik ? `<p class="uyari-kutu">"${h(q)}" çok kısa: bu önekle başlayan parçaların yalnız bir kısmına bakıldı.
      Tam sonuç için daha fazla karakter yazın.</p>` : "";
    if (birebir.length > 1) html += listeTablo(`"${h(q)}" için ${birebir.length} kayıt var (farklı üretici ya da ambalaj). Birini seçin:`, birebir);
    if (!birebir.length) html += `<p class="uyari-kutu">"${h(q)}" birebir bulunamadı. Yazdığınız kodu değiştirmiyoruz; aşağıdakiler yalnızca benzer kodlar.</p>`;
    if (yakin.length) html += `<details ${birebir.length ? "" : "open"}><summary>Benzer parça numaraları (${yakin.length})</summary>${listeTablo("", yakin)}</details>`;
    sonuc.innerHTML = html;
    if (birebir.length) sonuc.insertAdjacentHTML("beforeend", '<div id="ayrinti"></div>'), ac(birebir[0][1], n);
  } catch (e) {
    if (n === nesil) durum.textContent = `Veri okunamadı (${e.message}); sonuç gösterilemedi. Sayfayı yenileyip tekrar deneyin.`;
  }
}

function bulunamadi(q) {
  durum.textContent = "";
  sonuc.innerHTML = `<div class="kart"><h2>Bulunamadı: ${h(q)}</h2><p>Bu kod taranan stoklu JLCPCB kataloğunda yok.
    Stokta olmayan ya da JLCPCB'nin taşımadığı parçalar listede yer almaz.</p>
    <p><a href="https://jlcpcb.com/parts/componentSearch?searchTxt=${encodeURIComponent(q)}" rel="noopener">JLCPCB'de ara</a> ·
    <a href="https://www.lcsc.com/search?q=${encodeURIComponent(q)}" rel="noopener">LCSC'de ara</a></p></div>`;
}

function listeTablo(baslik, satirlar) {
  const govde = satirlar.map((s) => `<tr data-c="${h(s[1])}" tabindex="0"><td>${h(s[0])}</td><td>${h(s[2])}</td><td>${h(s[3])}</td>
    <td class="mono">${h(s[1])}</td><td style="text-align:right">${sayi(s[4])}</td></tr>`).join("");
  return `${baslik ? `<p>${baslik}</p>` : ""}<div class="tablo-kap"><table class="liste-tablo"><thead><tr><th>Parça no</th>
    <th>Üretici</th><th>Kılıf</th><th>LCSC</th><th style="text-align:right">Stok</th></tr></thead><tbody>${govde}</tbody></table></div>`;
}

async function ac(lcsc, n = ++nesil) {
  const p = await parca(lcsc).catch((e) => e);
  if (n !== nesil) return;
  const yer = $("#ayrinti") || sonuc;
  if (p instanceof Error) { yer.innerHTML = `<p>${h(lcsc)} okunamadı (${h(p.message)}). Sayfayı yenileyip tekrar deneyin.</p>`; return; }
  if (!p) { yer.innerHTML = `<p>${h(lcsc)} katalogda bulunamadı.</p>`; return; }
  yer.innerHTML = ayrinti(p);
  yer.scrollIntoView({ behavior: "smooth", block: "start" });
}

function goster(p) { sonuc.innerHTML = ayrinti(p); }

// Pin kanıtı düzeyleri, en zayıftan en güçlüye.
const GUVEN = {
  celiski: ["Pin: kaynaklar çelişiyor", "kotu", "KiCad ile LCSC/EasyEDA bu parça için farklı dizilim veriyor."],
  yok: ["Pin verisi eksik", "", "Bu parçanın pin tablosu yok."],
  "kicad ad": ["Pin: yalnız ada göre", "uyari", "KiCad sembolü yalnız parça adına göre bulundu; başka üreticinin dizilimini gösteriyor olabilir."],
  "kicad uretici": ["Pin: KiCad, aynı üretici", "vurgu", "KiCad sembolü bu parçanın üreticisinin datasheet'ine dayanıyor (tek kaynak)."],
  "parcaya ozel": ["Pin: parçaya özel kaynak", "vurgu", "LCSC/EasyEDA'nın bu parça için çizdiği sembol (tek kaynak)."],
  "tek kaynak": ["Pin: tek kaynak", "vurgu", "Tek kaynak."],
  "iki kaynak": ["Pin: iki kaynakla doğrulandı", "iyi", "KiCad ve LCSC/EasyEDA aynı dizilimi veriyor."],
};
const GUVEN_SIRA = Object.keys(GUVEN);

function pinRozet(guven) {
  if (!guven) return "";
  const en = GUVEN_SIRA.find((g) => guven.includes(g)) || "yok";
  const [ad, renk] = GUVEN[en];
  return `<span class="etiket ${renk}">${ad}</span>`;
}

const pinSirala = (o) => Object.entries(o).sort((a, b) => (parseInt(a[0]) || 999) - (parseInt(b[0]) || 999));
const pinAdi = (v) => v[0] || (v[1] === "output" ? "(çıkış)" : v[1] === "input" ? "(giriş)" : "");

function pinBolumu(p) {
  if (!p.p) return '<p class="soluk">Bu parça için pin tablosu yok.</p>';
  const [ad, renk, aciklama] = GUVEN[p.p.guven] || GUVEN["tek kaynak"];
  const kaynak = `<p class="soluk kucuk">${h(aciklama)} Kaynak: ${h(p.p.kaynak)}${p.p.kicad ? `; KiCad sembolü ${h(p.p.kicad)}` : ""}${p.p.kicad_ds ? ` (datasheet: ${h(p.p.kicad_ds)})` : ""}.</p>`;
  if (p.p.guven === "celiski" && p.p.kicad_pinler) {
    const nolar = [...new Set([...Object.keys(p.p.pinler), ...Object.keys(p.p.kicad_pinler)])].sort((a, b) => (parseInt(a) || 999) - (parseInt(b) || 999));
    return `<p><span class="etiket ${renk}">${ad}</span></p>${kaynak}
      <div class="tablo-kap"><table><thead><tr><th>Pin</th><th>LCSC/EasyEDA (bu parça)</th><th>KiCad (${h(p.p.kicad)})</th></tr></thead><tbody>
      ${nolar.map((n) => `<tr><td>${h(n)}</td><td class="mono">${h(p.p.pinler[n] ? pinAdi(p.p.pinler[n]) : "-")}</td>
        <td class="mono">${h(p.p.kicad_pinler[n] ? pinAdi(p.p.kicad_pinler[n]) : "-")}</td></tr>`).join("")}</tbody></table></div>
      <p class="uyari-kutu" style="margin-top:10px">Aynı parça numarası farklı üreticilerde farklı dizilimle üretilebilir. Doğru tabloyu bu
        parçanın kendi datasheet'inden kontrol edin.</p>`;
  }
  return `<p><span class="etiket ${renk}">${ad}</span></p>${kaynak}
    <div class="tablo-kap"><table><thead><tr><th>Pin</th><th>Ad</th></tr></thead><tbody>
    ${pinSirala(p.p.pinler).map(([no, v]) => `<tr><td>${h(no)}</td><td class="mono">${h(pinAdi(v))}</td></tr>`).join("")}</tbody></table></div>`;
}

function ayrinti(p) {
  const [jlcAd, jlcRenk] = JLC_SINIF[p.sn] || ["", ""];
  const fiyat = (p.f || []).map(([adet, f]) => `<tr><td>${sayi(adet)}+</td><td>${dolar(f)}</td></tr>`).join("");
  const ozl = Object.entries(p.o || {}).map(([k, v]) => `<tr><th scope="row">${h(k)}</th><td>${h(v)}</td></tr>`).join("");
  const pin = pinBolumu(p);
  return `<article class="kart">
    <div class="parca-ust">
      ${p.g ? `<img src="${h(p.g)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
      <div class="bilgi">
        <h2 class="mono">${h(p.m)}</h2>
        <div class="satir-bilgi"><span>${h(p.u)}</span><span>Kılıf: ${h(p.k)}</span><span>LCSC: <span class="mono">${h(p.c)}</span></span>
          <span>${h(p.alt)}</span></div>
        <p>${jlcAd ? `<span class="etiket ${jlcRenk}">${jlcAd}</span> ` : ""}<span class="etiket">Stok: ${sayi(p.s)}</span>
          ${p.a && AILE[p.a] ? `<span class="etiket vurgu">${AILE[p.a]}</span>` : ""}</p>
        <p class="kucuk">${p.ds ? `<a href="${h(p.ds)}" rel="noopener">Datasheet</a> · ` : ""}
          ${p.url ? `<a href="${h(p.url)}" rel="noopener">LCSC sayfası</a> · ` : ""}
          <a href="https://jlcpcb.com/parts/componentSearch?searchTxt=${encodeURIComponent(p.c)}" rel="noopener">JLCPCB'de güncel fiyat</a></p>
      </div>
    </div>
    ${p.d ? `<p class="soluk kucuk">${h(p.d)}</p>` : ""}
    <div class="iki">
      <div><h3>Özellikler</h3><div class="tablo-kap"><table><tbody>${ozl || "<tr><td>Özellik verisi yok.</td></tr>"}</tbody></table></div></div>
      <div><h3>Pin dizilimi</h3>${pin}
        <h3 style="margin-top:18px">Fiyat (birim, USD)</h3><div class="tablo-kap"><table><thead><tr><th>Adet</th><th>Fiyat</th></tr></thead><tbody>${fiyat}</tbody></table></div></div>
    </div>
  </article>
  ${muadilBolumu(p)}`;
}

function muadilBolumu(p) {
  if (!p.mu) {
    return `<div class="kart" style="margin-top:16px"><h2>Muadiller</h2><p>Bu kategori (${h(p.alt)}) için muadil kuralları henüz
      tanımlı değil. Kurallı aileler: ${Object.values(AILE).join(", ")}.</p></div>`;
  }
  const mu = p.mu;
  let html = `<h2 style="margin-top:28px">Muadiller</h2><p class="soluk">Aynı kategoride ve aynı zorunlu değerlere sahip ${sayi(mu.aday)} aday var;
    en uygun ${sayi(mu.incelenen)} tanesi kurallardan geçirildi. Her satırı açınca kanıtını görürsünüz.</p>`;
  for (const [kod, ad, renk] of SINIFLAR) {
    const liste = mu[kod] || [];
    if (!liste.length) continue;
    html += `<div class="sinif-baslik"><span class="etiket ${renk}">${ad}</span><h3>${liste.length} aday</h3></div>`;
    html += liste.map((a) => adaySatiri(a, kod)).join("");
  }
  if (!SINIFLAR.some(([k]) => (mu[k] || []).length)) html += "<p>Kurallardan geçen aday bulunamadı.</p>";
  return html;
}

function adaySatiri(a, sinif) {
  const notlar = [
    ...(a.i || []).map((x) => `<li class="hata"><strong>Eleme nedeni:</strong> ${h(x)}</li>`),
    ...(a.e || []).map((x) => `<li><strong>Eksik zorunlu değer:</strong> ${h(x)}</li>`),
    ...(a.n || []).map((x) => `<li><strong>Fark:</strong> ${h(x)}</li>`),
    ...(a.b || []).map((x) => `<li class="soluk">${h(x)}</li>`),
  ].join("");
  let pinTablo = "";
  if (a.pin?.satir?.length) {
    pinTablo = `<div class="tablo-kap"><table><thead><tr><th>Pin</th><th>Bu parça</th><th>Aday</th><th>Durum</th><th>Açıklama</th></tr></thead><tbody>
      ${a.pin.satir.map(([no, e, y, d, ac]) => `<tr><td>${h(no)}</td><td class="mono">${h(e ?? "-")}</td><td class="mono">${h(y ?? "-")}</td>
      <td class="${h(d)}">${PIN_DURUM[d] || h(d)}</td><td class="kucuk">${h(ac)}</td></tr>`).join("")}</tbody></table></div>`;
  } else if (a.pin && a.pin.sonuc === "veri_yok") {
    pinTablo = `<p class="kucuk soluk">Pin karşılaştırması yapılamadı: ${a.pin.guven[0] === "yok" ? "bu parçanın" : "adayın"} pin tablosu yok.</p>`;
  }
  const kaynak = a.pin?.kaynak ? `<p class="kucuk soluk">Pin kaynakları: bu parça ${h(a.pin.kaynak[0] || "-")}, aday ${h(a.pin.kaynak[1] || "-")}.</p>` : "";
  const [jlcAd] = JLC_SINIF[a.sn] || [""];
  return `<details class="aday"><summary>
      <span class="mpn">${h(a.m)}</span>
      <span class="k">${h(a.u)}<br>${h(a.k)}</span>
      <span class="sag">${dolar(a.f1)}</span>
      <span class="sag">${sayi(a.s)} adet</span>
      <span class="k">${h(jlcAd)}</span>
      <span>${sinif === "uygun_degil" ? "" : pinRozet(a.pin?.guven)}</span>
    </summary>
    <div class="kanit">
      ${notlar ? `<ul>${notlar}</ul>` : '<p class="kucuk">Tüm kurallar sağlanıyor.</p>'}
      ${pinTablo}${kaynak}
      <p class="kucuk"><a href="?q=${encodeURIComponent(a.c)}">${h(a.c)} ayrıntısını aç</a></p>
    </div></details>`;
}

sonuc.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-c]");
  if (tr) { if (!$("#ayrinti")) sonuc.insertAdjacentHTML("beforeend", '<div id="ayrinti"></div>'); ac(tr.dataset.c); }
});
sonuc.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("tr[data-c]")) e.target.click(); });
$("#form").addEventListener("submit", (e) => { e.preventDefault(); ara($("#sorgu").value); });
document.querySelectorAll(".ornekler button").forEach((b) => b.addEventListener("click", () => ara(b.dataset.q)));
window.addEventListener("popstate", () => { const q = new URLSearchParams(location.search).get("q"); if (q) ara(q); });

baslat().then(() => {
  const q = new URLSearchParams(location.search).get("q");
  if (q) ara(q);
}).catch((e) => { durum.textContent = "Veri yüklenemedi: " + e.message; });

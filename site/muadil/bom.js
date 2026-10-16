// BOM risk raporu: her satırı katalogda arar, tedarik risklerini işaretler. Tamamen tarayıcıda çalışır.
import { h, sayi, dolar, hazirla, parca, bul } from "./veri.js";

const $ = (s) => document.querySelector(s);
const ORNEK = `Comment,Designator,Footprint,LCSC,Quantity
AMS1117-3.3,U1,SOT-223,C6186,1
10k,"R1,R2,R3",0603,C25804,3
100nF,"C1,C2,C3,C4",0402,C1525,4
AO3400A,Q1,SOT-23,,1
LM358DR,U2,SOIC-8,,1
NE555DR,U3,SOIC-8,,1
SS34,D1,SMA,,1
XC6206P332MR,U4,SOT-23,,1
TL072CDR,U5,SOIC-8,,2
BU-OLMAYAN-PARCA,U6,,,1`;

/** Basit CSV ayrıştırıcı: virgül, noktalı virgül ya da sekme; tırnak içi ayraçları korur. */
function csv(metin) {
  const satirlar = metin.split(/\r?\n/).filter((s) => s.trim());
  if (!satirlar.length) return [];
  const ayrac = [",", ";", "\t"].sort((a, b) => satirlar[0].split(b).length - satirlar[0].split(a).length)[0];
  const bol = (s) => {
    const alanlar = []; let alan = ""; let tirnak = false;
    for (const c of s) {
      if (c === '"') tirnak = !tirnak;
      else if (c === ayrac && !tirnak) { alanlar.push(alan.trim()); alan = ""; }
      else alan += c;
    }
    alanlar.push(alan.trim());
    return alanlar;
  };
  return satirlar.map(bol);
}

function satirlariOku(metin) {
  const tablo = csv(metin);
  if (!tablo.length) return [];
  const baslik = tablo[0].map((x) => x.toLowerCase());
  // Adlar öncelik sırasıyla aranır: "Manufacturer Part" varsa "Comment"ten önce gelir.
  const sutun = (...adlar) => { for (const a of adlar) { const i = baslik.findIndex((b) => b.includes(a)); if (i >= 0) return i; } return -1; };
  const iLcsc = sutun("lcsc", "jlcpcb part");
  const iMpn = sutun("manufacturer part", "mpn", "part number", "comment", "value");
  const iAdet = sutun("quantity", "qty", "adet");
  const basliklimi = iLcsc >= 0 || iMpn >= 0;
  return (basliklimi ? tablo.slice(1) : tablo).slice(0, 300).map((r) => {
    const lcsc = iLcsc >= 0 ? (r[iLcsc] || "").toUpperCase() : "";
    const mpn = basliklimi ? (iMpn >= 0 ? r[iMpn] : "") : r[0];
    return { girdi: /^C\d+$/.test(lcsc) ? lcsc : (mpn || lcsc), lcsc: /^C\d+$/.test(lcsc) ? lcsc : null,
      mpn, adet: iAdet >= 0 ? parseInt(r[iAdet], 10) || 1 : 1 };
  }).filter((r) => r.girdi);
}

const KURALSIZ = "Muadil kuralı yok";
// Renkli risk yoksa da kuralı olmayan parçanın muadili incelenmedi: "sorunsuz" sayılmaz.
const sorunsuz = (r) => !r.riskler.some(([ad, renk]) => renk || ad === KURALSIZ);

async function cozumle(s) {
  let p = null, not = "";
  if (s.lcsc || /^C\d+$/i.test(s.girdi)) p = await parca((s.lcsc || s.girdi).toUpperCase());
  else {
    const { birebir } = await bul(s.girdi);
    if (birebir.length) {
      p = await parca(birebir[0][1]);
      if (birebir.length > 1) not = `${birebir.length} kayıt; en yüksek stoklu seçildi`;
    }
  }
  const riskler = [];
  if (!p) riskler.push(["Katalogda yok", "kotu"]);
  else {
    if (p.s < Math.max(1000, 10 * s.adet)) riskler.push(["Stok düşük", "uyari"]);
    if (!p.mu) riskler.push([KURALSIZ, ""]);
    else if (!(p.mu.dogrudan || []).length && !(p.mu.farkli || []).length) riskler.push(["Doğrulanmış muadil yok", "uyari"]);
    if (p.p?.guven === "celiski") riskler.push(["Pin kaynakları çelişiyor", "kotu"]);
    if (p.sn === "genis") riskler.push(["Genişletilmiş parça", ""]);
  }
  return { s, p, not, riskler };
}

async function calistir() {
  const satirlar = satirlariOku($("#girdi").value);
  if (!satirlar.length) { $("#durum").textContent = "Liste boş."; return; }
  $("#durum").textContent = `${satirlar.length} satır inceleniyor...`;
  const sonuclar = new Array(satirlar.length);
  let sira = 0;
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (sira < satirlar.length) { const i = sira++; sonuclar[i] = await cozumle(satirlar[i]).catch((e) => ({ s: satirlar[i], p: null, not: `veri okunamadı (${e.message}); tekrar deneyin`, riskler: [["Okunamadı", "kotu"]] })); }
  }));
  $("#durum").textContent = "";
  const say = {};
  sonuclar.forEach((r) => r.riskler.forEach(([ad]) => (say[ad] = (say[ad] || 0) + 1)));
  const temiz = sonuclar.filter(sorunsuz).length;
  $("#ozet").innerHTML = `<span class="etiket iyi">Sorunsuz: ${temiz}</span>` +
    Object.entries(say).map(([ad, n]) => `<span class="etiket">${h(ad)}: ${n}</span>`).join("");
  $("#rapor").innerHTML = `<thead><tr><th>#</th><th>Girdi</th><th>Bulunan parça</th><th style="text-align:right">Stok</th>
    <th style="text-align:right">Birim fiyat</th><th>Muadil</th><th>Riskler</th></tr></thead><tbody>${sonuclar.map((r, i) => {
      const p = r.p;
      const mu = p?.mu ? `${(p.mu.dogrudan || []).length} doğrudan, ${(p.mu.farkli || []).length} farklı` : "-";
      return `<tr><td>${i + 1}</td><td class="mono">${h(r.s.girdi)}${r.s.adet > 1 ? ` <span class="ince">×${r.s.adet}</span>` : ""}</td>
        <td>${p ? `<a class="mono" href="./?q=${encodeURIComponent(p.c)}">${h(p.m)}</a><br><span class="ince">${h(p.u)} · ${h(p.k)} · ${h(p.c)}</span>` : "-"}
          ${r.not ? `<br><span class="ince">${h(r.not)}</span>` : ""}</td>
        <td style="text-align:right">${p ? sayi(p.s) : "-"}</td>
        <td style="text-align:right">${p ? dolar(p.f?.[0]?.[1]) : "-"}</td>
        <td class="ince">${mu}</td>
        <td>${sorunsuz(r) ? '<span class="etiket iyi">Sorunsuz</span>' : ""}${r.riskler.map(([ad, renk]) => `<span class="etiket ${renk}">${h(ad)}</span>`).join("")}</td></tr>`;
    }).join("")}</tbody>`;
}

$("#calistir").addEventListener("click", () => calistir().catch((e) => ($("#durum").textContent = "Hata: " + e.message)));
$("#ornek").addEventListener("click", () => { $("#girdi").value = ORNEK; calistir(); });
$("#dosya").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (f) { $("#girdi").value = await f.text(); calistir(); }
});
hazirla().then(() => {
  // "?ornek" bağlantısı örnek listeyi hemen çalıştırır (paylaşılabilir demo).
  if (new URLSearchParams(location.search).has("ornek")) { $("#girdi").value = ORNEK; calistir(); }
}).catch((e) => ($("#durum").textContent = "Veri yüklenemedi: " + e.message));

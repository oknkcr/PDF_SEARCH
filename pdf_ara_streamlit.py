import streamlit as st
import pdfplumber
import re
import pandas as pd
from io import StringIO

st.set_page_config(page_title="PDF Anahtar Kelime Arama", page_icon="🔎", layout="wide")

st.title("🔎 PDF Anahtar Kelime Arama Arayüzü")
st.caption("Birden fazla PDF yükleyin, anahtar kelime girin ve geçtiği cümleleri bulun.")

with st.expander("Ayarlar", expanded=True):
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        anahtar_kelime = st.text_input("Anahtar kelime", value="", placeholder="ör. mosfet, kalite, ISO 9001")
    with col2:
        eslestirme_turu = st.selectbox("Eşleştirme", ["Büyük/küçük harfe duyarsız", "Büyük/küçük harfe duyarlı"])
    with col3:
        max_cumle_uzunluk = st.slider("Maks. cümle uzunluğu (karakter)", 80, 2000, 500, step=20)
    regex_mod = 0 if eslestirme_turu == "Büyük/küçük harfe duyarlı" else re.IGNORECASE

yuklenen_pdfler = st.file_uploader(
    "PDF dosyalarını yükleyin (birden fazla seçebilirsiniz)", 
    type=["pdf"], accept_multiple_files=True
)
st.info("İpucu: Klasör taraması yerine, bu arayüzde dosyaları sürükleyip bırakın.")

def anahtar_kelime_cumleleri(metin: str, anahtar: str, max_len: int, flags=0):
    # Nokta, soru işareti, ünlem ve satırsonlarına göre böl
    # Birden fazla boşluğu normalize et
    if not metin:
        return []
    metin = re.sub(r'\s+', ' ', metin)
    cumleler = re.split(r'(?<=[.!?])\s+', metin)
    sonuc = []
    for c in cumleler:
        if len(c) > max_len:
            # Uzun cümleleri bölmeye çalış (noktalı virgül, iki nokta, tire)
            parcali = re.split(r'(?<=[;:—-])\s+', c)
            adaylar = parcali if len(parcali) > 1 else [c]
        else:
            adaylar = [c]
        for aday in adaylar:
            try:
                if re.search(re.escape(anahtar), aday, flags=flags):
                    sonuc.append(aday.strip())
            except re.error:
                # Anahtar kelime regex değil, ama yine de bir hata olursa güvenli davran
                if anahtar.lower() in aday.lower():
                    sonuc.append(aday.strip())
    return sonuc

def tara_bir_pdf(file, anahtar, max_len, flags=0):
    sonuclar = []
    try:
        with pdfplumber.open(file) as pdf:
            for i, sayfa in enumerate(pdf.pages, start=1):
                try:
                    metin = sayfa.extract_text() or ""
                except Exception:
                    metin = ""
                if not metin:
                    continue
                cumleler = anahtar_kelime_cumleleri(metin, anahtar, max_len, flags=flags)
                for c in cumleler:
                    sonuclar.append({
                        "dosya": getattr(file, "name", "yüklü_dosya.pdf"),
                        "sayfa": i,
                        "cümle": c
                    })
    except Exception as e:
        st.error(f"'{getattr(file, 'name', 'dosya')}' okunurken hata: {e}")
    return sonuclar

calistir = st.button("Ara", use_container_width=True, type="primary", disabled=not (anahtar_kelime and yuklenen_pdfler))

if calistir:
    tum_sonuclar = []
    progress = st.progress(0.0, text="Taranıyor...")
    for idx, pdf in enumerate(yuklenen_pdfler):
        tum_sonuclar.extend(tara_bir_pdf(pdf, anahtar_kelime, max_cumle_uzunluk, flags=regex_mod))
        progress.progress((idx+1)/max(1,len(yuklenen_pdfler)), text=f"Taranıyor: {idx+1}/{len(yuklenen_pdfler)}")
    progress.empty()

    if not tum_sonuclar:
        st.warning(f"'{anahtar_kelime}' anahtar kelimesi için sonuç bulunamadı.")
    else:
        df = pd.DataFrame(tum_sonuclar).sort_values(["dosya","sayfa"]).reset_index(drop=True)

        st.success(f"{len(df)} eşleşme bulundu.")
        # Vurgulu görünüm
        def vurgula(metin, anahtar):
            try:
                pattern = re.compile(re.escape(anahtar), flags=regex_mod)
                return pattern.sub(lambda m: f"**{m.group(0)}**", metin)
            except re.error:
                return metin.replace(anahtar, f"**{anahtar}**")
        
        with st.container():
            st.subheader("Özet Tablo")
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        with st.container():
            st.subheader("Bağlama Göre Görünüm")
            for _, row in df.iterrows():
                st.markdown(f"**Dosya:** {row['dosya']} • **Sayfa:** {row['sayfa']}")
                st.markdown(vurgula(row['cümle'], anahtar_kelime))
                st.markdown("---")

        # İndirilebilir CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("CSV olarak indir", data=csv, file_name="sonuclar.csv", mime="text/csv")

        # Basit bir log metni
        log_buf = StringIO()
        for _, r in df.iterrows():
            log_buf.write(f"Dosya: {r['dosya']} | Sayfa: {r['sayfa']} | Cümle: {r['cümle']}\n")
        st.download_button("Log (TXT) indir", data=log_buf.getvalue().encode("utf-8"), file_name="sonuclar.log", mime="text/plain")

with st.expander("Nasıl Çalıştırırım?", expanded=False):
    st.markdown("""
1. Terminalde aşağıdakini çalıştırın:
   ```bash
   pip install -r requirements.txt
   streamlit run pdf_ara_streamlit.py
   ```
2. Açılan tarayıcı penceresinden PDF'leri yükleyin, anahtar kelimeyi girin ve **Ara**'ya basın.
3. Sonuçları tablo halinde görün, bağlamı inceleyin ve **CSV**/**LOG** olarak indirin.
""")

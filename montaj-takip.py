import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io
import os
#from dotenv import load_dotenv  istersenin bir .env dosyası oluşturup şifreyi orada saklayabilirsin.

# load_dotenv() # .env dosyasını yüklemek için aktif edin

# --- 1. Veritabanı ve Sayfa Ayarları ---
conn = sqlite3.connect('montaj_verisi.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS isler 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, musteri TEXT, 
              adres TEXT, is_tanimi TEXT, aciklama TEXT, durum TEXT)''')
conn.commit()

st.set_page_config(page_title="Montaj Takip Sistemi", layout="wide")

# --- 2. OTURUM YÖNETİMİ ---
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# Şifreyi .env'den al veya geçici olarak buradan yönet
ADMIN_SIFRE = os.getenv("ADMIN_PASSWORD", "192837465") 

with st.sidebar:
    st.header("🔐 Yönetici Paneli")
    if not st.session_state.is_admin:
        sifre_denemesi = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            if sifre_denemesi == ADMIN_SIFRE:
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Hatalı Şifre!")
    else:
        st.success("Yönetici Yetkisi Aktif")
        if st.button("Güvenli Çıkış"):
            st.session_state.is_admin = False
            st.rerun()

st.image("https://iseelectronics.com/wp-content/uploads/2023/05/isee-logo-beyaz-640x243.png", width=250) 
st.title("🛠️ Montaj Takip ve Yönetim Sistemi")


# --- 3. Yardımcı Fonksiyonlar ---
def istatistikleri_getir():
    bekleyen = pd.read_sql_query("SELECT COUNT(*) as sayi FROM isler WHERE durum='Beklemede'", conn).iloc[0,0]
    tamamlanan = pd.read_sql_query("SELECT COUNT(*) as sayi FROM isler WHERE durum='Tamamlandı'", conn).iloc[0,0]
    return bekleyen, tamamlanan

def bekleme_suresi_hesapla(tarih_str, durum):
    if durum == 'Beklemede' and tarih_str:
        try:
            fark = datetime.now() - datetime.strptime(tarih_str, '%Y-%m-%d')
            return f"{fark.days} Gün"
        except: return "-"
    return "-"

# --- 4. Üst Panel: İstatistikler ve Excel ---
bekleyen_sayisi, tamamlanan_sayisi = istatistikleri_getir()
col1, col2, col3 = st.columns([1, 1, 1])

col1.metric("⏳ Toplam Bekleyen İş", f"{bekleyen_sayisi}")
col2.metric("✅ Toplam Tamamlanan", f"{tamamlanan_sayisi}")

# Excel Aktarma
try:
    df_export = pd.read_sql_query("SELECT * FROM isler", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Liste')
    col3.write("")
    col3.download_button(label="📥 Tüm Listeyi Excel Olarak İndir", data=output.getvalue(), 
                         file_name=f"montaj_yedek_{datetime.now().strftime('%d-%m-%Y')}.xlsx")
except: pass

st.divider()

# --- 5. Yan Panel: Yeni Kayıt Formu (Sadece Giriş Yapıldığında Görünür) ---
if st.session_state.is_admin:
    st.sidebar.divider()
    st.sidebar.header("➕ Yeni Montaj Kaydı")
    firmalar = pd.read_sql_query("SELECT DISTINCT musteri FROM isler ORDER BY musteri ASC", conn)['musteri'].tolist()
    
    with st.sidebar.form("yeni_form", clear_on_submit=True):
        is_tarihi = st.date_input("Kayıt Tarihi", datetime.now())
        secilen = st.selectbox("Müşteri", ["--- Yeni Firma ---"] + firmalar)
        yeni_f = st.text_input("Yeni Firma Adı")
        m_adr = st.text_input("Adres")
        m_is = st.text_area("İş Tanımı")
        m_not = st.text_input("Not / Açıklama")
        if st.form_submit_button("Sisteme Kaydet"):
            f_ad = yeni_f if secilen == "--- Yeni Firma ---" else secilen
            if f_ad.strip():
                c.execute("INSERT INTO isler (tarih, musteri, adres, is_tanimi, aciklama, durum) VALUES (?,?,?,?,?,?)",
                          (is_tarihi.strftime('%Y-%m-%d'), f_ad, m_adr, m_is, m_not, "Beklemede"))
                conn.commit()
                st.rerun()

# --- 6. Firma Özeti (Daima Görünür) ---
st.subheader("🏢 Firma Bazlı Bekleyen İş Dağılımı")
df_ozet = pd.read_sql_query("SELECT musteri as 'Firma Adı', COUNT(*) as 'Bekleyen' FROM isler WHERE durum = 'Beklemede' GROUP BY musteri ORDER BY Bekleyen DESC", conn)
st.dataframe(df_ozet, hide_index=True, width="stretch")

st.divider()

# --- 7. Ana Listeler ve Sıralama Seçeneği (YENİ YERİ) ---
col_baslik, col_siralama = st.columns([2, 1])
col_baslik.subheader("📋 Detaylı İş Listeleri")

# Sıralama artık listenin hemen üzerinde
siralama = col_siralama.segmented_control(
    "Sıralama Düzeni:", 
    ["Eskiden Yeniye", "Yeniden Eskiye"], 
    default="Eskiden Yeniye"
)

order = "ASC" if siralama == "Eskiden Yeniye" else "DESC"
df = pd.read_sql_query(f"SELECT * FROM isler ORDER BY tarih {order}, id {order}", conn)
df['SÜRE'] = df.apply(lambda x: bekleme_suresi_hesapla(x['tarih'], x['durum']), axis=1)
df['SİL'] = False

# Yetki Kontrolü
if st.session_state.is_admin:
    kilitli_sutunlar = ["id", "tarih", "SÜRE"]
else:
    kilitli_sutunlar = df.columns.tolist()

tab_b, tab_t = st.tabs(["⏳ BEKLEYEN MONTAJLAR", "✅ TAMAMLANANLAR"])

yapilandirma = {
    "id": None,
    "tarih": st.column_config.TextColumn("Kayıt"),
    "SÜRE": st.column_config.TextColumn("Bekleme"),
    "durum": st.column_config.SelectboxColumn("Durum", options=["Beklemede", "Tamamlandı"], required=True),
    "SİL": st.column_config.CheckboxColumn("Sil?")
}

def kaydet(data):
    for _, row in data.iterrows():
        if row['SİL']:
            c.execute("DELETE FROM isler WHERE id=?", (row['id'],))
        else:
            c.execute("UPDATE isler SET musteri=?, adres=?, is_tanimi=?, aciklama=?, durum=? WHERE id=?", 
                      (row['musteri'], row['adres'], row['is_tanimi'], row['aciklama'], row['durum'], row['id']))
    conn.commit()
    st.rerun()

with tab_b:
    df_b = df[df['durum'] == 'Beklemede']
    if not df_b.empty:
        ed_b = st.data_editor(df_b, column_config=yapilandirma, hide_index=True, width="stretch", key="eb", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Değişiklikleri Kaydet", key="sb"):
            kaydet(ed_b)
    else: st.info("Bekleyen iş yok.")

with tab_t:
    df_t = df[df['durum'] == 'Tamamlandı']
    if not df_t.empty:
        ed_t = st.data_editor(df_t, column_config=yapilandirma, hide_index=True, width="stretch", key="et", disabled=kilitli_sutunlar)
        if st.button("💾 Değişiklikleri Kaydet", key="st") if st.session_state.is_admin else None:
            kaydet(ed_t)
    else: st.info("Henüz tamamlanmış iş yok.")

st.divider()

col_logo, col_yazi = st.columns([1, 7], gap="small")

with col_logo:
    st.image("logo.png", width=200)

with col_yazi:
    st.write("") 
    st.write("") 
    st.write("") 
    st.write("")  
    st.caption("© 2026 ÇÖZÜM MAKİNA - Tüm Hakları Saklıdır.")



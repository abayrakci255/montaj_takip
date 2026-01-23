import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io
import os
from dotenv import load_dotenv

st.set_page_config( page_icon="🔧")

load_dotenv() 

# --- 1. VERİTABANI VE SAYFA AYARLARI ---
conn = sqlite3.connect('montaj_verisi.db', check_same_thread=False)
c = conn.cursor()

# Ana iş tablosu
c.execute('''CREATE TABLE IF NOT EXISTS isler 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, musteri TEXT, 
              adres TEXT, is_tanimi TEXT, aciklama TEXT, durum TEXT,
              personel TEXT, sure_gun INTEGER DEFAULT 0)''')

# Sabit personel listesi tablosu
c.execute('''CREATE TABLE IF NOT EXISTS personeller 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, isim TEXT UNIQUE)''')

# Eski veritabanı olanlar için yeni sütunları kontrol et
try:
    c.execute("ALTER TABLE isler ADD COLUMN personel TEXT")
except: pass
try:
    c.execute("ALTER TABLE isler ADD COLUMN sure_gun INTEGER DEFAULT 0")
except: pass
conn.commit()

st.set_page_config(page_title="Çözüm Makina - Montaj Takip", layout="wide")

# --- 2. OTURUM YÖNETİMİ ---
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

ADMIN_SIFRE = os.getenv("ADMIN_PASSWORD", "192837465") 

with st.sidebar:
    st.header("🔐 Yönetici Paneli")
    if not st.session_state.is_admin:
        sifre_denemesi = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            if sifre_denemesi == ADMIN_SIFRE:
                st.session_state.is_admin = True
                st.rerun()
            else: st.error("Hatalı Şifre!")
    else:
        st.success("Yönetici Yetkisi Aktif")
        if st.button("Güvenli Çıkış"):
            st.session_state.is_admin = False
            st.rerun()

# --- 3. PERSONEL YÖNETİMİ (SADECE ADMİN) ---
personel_listesi = pd.read_sql_query("SELECT isim FROM personeller ORDER BY isim ASC", conn)['isim'].tolist()

if st.session_state.is_admin:
    st.sidebar.divider()
    st.sidebar.header("👥 Personel Listesi")
    yeni_p = st.sidebar.text_input("Yeni İsim Ekle")
    if st.sidebar.button("Ekle"):
        if yeni_p.strip():
            try:
                c.execute("INSERT INTO personeller (isim) VALUES (?)", (yeni_p.strip(),))
                conn.commit()
                st.rerun() # Sayfayı yenilemek için bu komut şart
            except sqlite3.IntegrityError: # Sadece 'zaten var' hatasını yakalar
                st.sidebar.error("Bu isim zaten kayıtlı!")
            except Exception as e: # Diğer olası hataları görmek için
                st.sidebar.error(f"Bir hata oluştu: {e}")
    
    silinecek_p = st.sidebar.selectbox("Personel Sil", ["--- Seç ---"] + personel_listesi)
    if st.sidebar.button("Sil"):
        if silinecek_p != "--- Seç ---":
            c.execute("DELETE FROM personeller WHERE isim=?", (silinecek_p,))
            conn.commit()
            st.rerun()

st.image("https://iseelectronics.com/wp-content/uploads/2023/05/isee-logo-beyaz-640x243.png", width=180) 

st.title("🛠️ Montaj Takip ve Yönetim Sistemi")

# --- 4. YARDIMCI FONKSİYONLAR ---
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

# --- 5. ÜST PANEL: METRİKLER VE EXCEL ---
bekleyen_sayisi, tamamlanan_sayisi = istatistikleri_getir()
col1, col2, col3 = st.columns([1, 1, 1])

col1.metric("⏳ Toplam Bekleyen İş", f"{bekleyen_sayisi}")
col2.metric("✅ Toplam Tamamlanan", f"{tamamlanan_sayisi}")

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

# --- 6. YENİ KAYIT FORMU (SADECE ADMİN) ---
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

# --- 7. FİRMA ÖZETİ  ---
st.subheader("🏢 Firma Bazlı Bekleyen İş Dağılımı")
df_ozet = pd.read_sql_query("SELECT musteri as 'Firma Adı', COUNT(*) as 'Bekleyen' FROM isler WHERE durum = 'Beklemede' GROUP BY musteri ORDER BY Bekleyen DESC", conn)
st.dataframe(df_ozet, hide_index=True, width="stretch")

st.divider()

# --- 8. ANA LİSTELER VE SIRALAMA ---
col_baslik, col_siralama = st.columns([2, 1])
col_baslik.subheader("📋 Detaylı İş Listeleri")

siralama = col_siralama.segmented_control("Sıralama Düzeni:", ["Eskiden Yeniye", "Yeniden Eskiye"], default="Eskiden Yeniye")
order = "ASC" if siralama == "Eskiden Yeniye" else "DESC"

df = pd.read_sql_query(f"SELECT * FROM isler ORDER BY tarih {order}, id {order}", conn)
df['SÜRE'] = df.apply(lambda x: bekleme_suresi_hesapla(x['tarih'], x['durum']), axis=1)
df['SİL'] = False

# Personel kolonunu multiselect için listeye çevir
if 'personel' in df.columns:
    df['personel'] = df['personel'].apply(lambda x: x.split(',') if x and isinstance(x, str) else [])

# Yetki Kontrolü
if not st.session_state.is_admin:
    df = df.drop(columns=["personel", "sure_gun"])
    kilitli_sutunlar = df.columns.tolist()
else:
    kilitli_sutunlar = ["id", "tarih", "SÜRE"]

# Tablo Yapılandırması 
yapilandirma = {
    "id": None,
    "tarih": st.column_config.TextColumn("Kayıt"),
    "SÜRE": st.column_config.TextColumn("Bekleme"),
    "durum": st.column_config.SelectboxColumn("Durum", options=["Beklemede", "Tamamlandı"], required=True),
    "personel": st.column_config.MultiselectColumn("Giden Ekip", options=personel_listesi),
    "sure_gun": st.column_config.NumberColumn("İş Süresi (Gün)", min_value=0, step=1),
    "SİL": st.column_config.CheckboxColumn("Sil?")
}

def kaydet(data):
    if st.session_state.is_admin:
        for _, row in data.iterrows():
            if row['SİL']:
                c.execute("DELETE FROM isler WHERE id=?", (row['id'],))
            else:
                p_str = ",".join(row['personel']) if isinstance(row['personel'], list) else ""
                c.execute("""UPDATE isler SET musteri=?, adres=?, is_tanimi=?, aciklama=?, 
                             durum=?, personel=?, sure_gun=? WHERE id=?""", 
                          (row['musteri'], row['adres'], row['is_tanimi'], row['aciklama'], 
                           row['durum'], p_str, row.get('sure_gun', 0), row['id']))
        conn.commit()
        st.rerun()

tab_b, tab_t = st.tabs(["⏳ BEKLEYEN MONTAJLAR", "✅ TAMAMLANANLAR"])

with tab_b:
    df_b = df[df['durum'] == 'Beklemede']
    if not df_b.empty:
        ed_b = st.data_editor(df_b, column_config=yapilandirma, hide_index=True, width="stretch", key="eb", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Bekleyenleri Kaydet"): kaydet(ed_b)
    else: st.info("Bekleyen iş yok.")

with tab_t:
    df_t = df[df['durum'] == 'Tamamlandı']
    if not df_t.empty:
        ed_t = st.data_editor(df_t, column_config=yapilandirma, hide_index=True, width="stretch", key="et", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Tamamlananları Kaydet"): kaydet(ed_t)
    else: st.info("Henüz tamamlanmış iş yok.")

# --- 9. PERSONEL İSTATİSTİKLERİ (SADECE ADMİN GÖREBİLİR) ---
if st.session_state.is_admin and personel_listesi:
    st.divider()
    st.subheader("👥 Personel Montaj İstatistikleri")
    stats = {isim: {"İş_Sayısı": 0, "Toplam_Gün": 0} for isim in personel_listesi}
    df_db = pd.read_sql_query("SELECT personel, sure_gun FROM isler WHERE durum='Tamamlandı'", conn)
    for _, row in df_db.iterrows():
        if row['personel']:
            gidenler = [p.strip() for p in row['personel'].split(',')]
            for p in gidenler:
                if p in stats:
                    stats[p]["İş_Sayısı"] += 1
                    stats[p]["Toplam_Gün"] += (row['sure_gun'] or 0)
    df_stats = pd.DataFrame.from_dict(stats, orient='index').reset_index()
    df_stats.columns = ["Personel", "Gidilen İş Sayısı", "Toplam Çalışma (Gün)"]
    st.dataframe(df_stats.sort_values("Toplam Çalışma (Gün)", ascending=False), hide_index=True, width="stretch")


# --- FOOTER ---
st.divider()
col_logo, col_yazi = st.columns([1, 7], gap="small")
with col_logo:
    st.image("logo-rekli.png", width=180)
with col_yazi:
    st.write("") 
    st.write("")
    st.caption("© 2026 ÇÖZÜM MAKİNA - Tüm Hakları Saklıdır.")




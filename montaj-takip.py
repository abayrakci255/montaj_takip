import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io
import os
from dotenv import load_dotenv

# --- 1. SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Çözüm Makina - Montaj & Demo Takip", layout="wide", page_icon="🔧")

load_dotenv() 

# --- 2. VERİTABANI AYARLARI ---
conn = sqlite3.connect('montaj_verisi.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS isler 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, musteri TEXT, 
              adres TEXT, is_tanimi TEXT, aciklama TEXT, durum TEXT,
              personel TEXT, sure_gun INTEGER DEFAULT 0, tur TEXT DEFAULT 'Normal')''')

c.execute('''CREATE TABLE IF NOT EXISTS personeller 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, isim TEXT UNIQUE)''')

# Sütun güncellemeleri
columns = [column[1] for column in c.execute("PRAGMA table_info(isler)")]
new_cols = {'personel': 'TEXT', 'sure_gun': 'INTEGER DEFAULT 0', 'tur': "TEXT DEFAULT 'Normal'"}
for col, dtype in new_cols.items():
    if col not in columns:
        c.execute(f"ALTER TABLE isler ADD COLUMN {col} {dtype}")
conn.commit()

# --- 3. OTURUM YÖNETİMİ ---
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

# --- 4. PERSONEL YÖNETİMİ (SADECE ADMİN) ---
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
                st.rerun()
            except sqlite3.IntegrityError:
                st.sidebar.error("Bu isim zaten kayıtlı!")
    
    silinecek_p = st.sidebar.selectbox("Personel Sil", ["--- Seç ---"] + personel_listesi)
    if st.sidebar.button("Sil"):
        if silinecek_p != "--- Seç ---":
            c.execute("DELETE FROM personeller WHERE isim=?", (silinecek_p,))
            conn.commit()
            st.rerun()

st.image("https://iseelectronics.com/wp-content/uploads/2023/05/isee-logo-beyaz-640x243.png", width=180) 
st.title("🛠️ Montaj ve Demo Yönetim Sistemi")

# --- 5. YARDIMCI FONKSİYONLAR ---
def bekleme_suresi_hesapla(tarih_str, durum):
    if durum == 'Beklemede' and tarih_str:
        try:
            fark = datetime.now() - datetime.strptime(tarih_str, '%Y-%m-%d')
            return f"{fark.days} Gün"
        except: return "-"
    return "-"

# --- 6. ÜST PANEL: METRİKLER (GÜNCELLENMİŞ SIRALAMA) ---
b_montaj = pd.read_sql_query("SELECT COUNT(*) FROM isler WHERE durum='Beklemede' AND tur='Normal'", conn).iloc[0,0]
t_montaj = pd.read_sql_query("SELECT COUNT(*) FROM isler WHERE durum='Tamamlandı' AND tur='Normal'", conn).iloc[0,0]
b_demo = pd.read_sql_query("SELECT COUNT(*) FROM isler WHERE durum='Beklemede' AND tur='Demo'", conn).iloc[0,0]
s_demo = pd.read_sql_query("SELECT COUNT(*) FROM isler WHERE durum='Tamamlandı' AND tur='Demo'", conn).iloc[0,0]
biten_demo = pd.read_sql_query("SELECT COUNT(*) FROM isler WHERE durum='Biten' AND tur='Demo'", conn).iloc[0,0]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("⏳ Bekleyen Montaj", f"{b_montaj}")
col2.metric("✅ Tamamlanan Montaj", f"{t_montaj}")
col3.metric("⏳ Bekleyen Demo", f"{b_demo}")
col4.metric("🧪 Süren Demo", f"{s_demo}")
col5.metric("🏁 Biten Demo", f"{biten_demo}")

try:
    df_export = pd.read_sql_query("SELECT * FROM isler", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Liste')
    st.download_button(label="📥 Tüm Verilerin Excel Yedeğini Al", data=output.getvalue(), 
                         file_name=f"cozum_makina_yedek_{datetime.now().strftime('%d-%m-%Y')}.xlsx")
except: pass

st.divider()

# --- 7. YENİ KAYIT FORMU (SADECE ADMİN) ---
if st.session_state.is_admin:
    st.sidebar.divider()
    st.sidebar.header("➕ Yeni Kayıt Ekle")
    firmalar = pd.read_sql_query("SELECT DISTINCT musteri FROM isler ORDER BY musteri ASC", conn)['musteri'].tolist()
    with st.sidebar.form("yeni_form", clear_on_submit=True):
        is_tarihi = st.date_input("Kayıt Tarihi", datetime.now())
        is_turu = st.radio("İş Türü", ["Normal Montaj", "Demo Montaj"], horizontal=True)
        secilen = st.selectbox("Müşteri", ["--- Yeni Firma ---"] + firmalar)
        yeni_f = st.text_input("Yeni Firma Adı")
        m_adr = st.text_input("Adres")
        m_is = st.text_area("İş Tanımı")
        m_not = st.text_input("Not / Açıklama")
        if st.form_submit_button("Sisteme Kaydet"):
            f_ad = yeni_f if secilen == "--- Yeni Firma ---" else secilen
            t_deger = "Normal" if is_turu == "Normal Montaj" else "Demo"
            if f_ad.strip():
                c.execute("INSERT INTO isler (tarih, musteri, adres, is_tanimi, aciklama, durum, tur) VALUES (?,?,?,?,?,?,?)",
                          (is_tarihi.strftime('%Y-%m-%d'), f_ad, m_adr, m_is, m_not, "Beklemede", t_deger))
                conn.commit()
                st.rerun()

# --- 8. FİRMA ÖZETİ ---
st.subheader("🏢 Firma Bazlı Bekleyen İş Dağılımı")
df_ozet = pd.read_sql_query("SELECT musteri as 'Firma Adı', COUNT(*) as 'Bekleyen' FROM isler WHERE durum = 'Beklemede' GROUP BY musteri ORDER BY Bekleyen DESC", conn)
st.dataframe(df_ozet, hide_index=True, width="stretch")

st.divider()

# --- 9. ANA LİSTELER VE SIRALAMA ---
col_baslik, col_siralama = st.columns([2, 1])
col_baslik.subheader("📋 Detaylı İş Listeleri")

siralama = col_siralama.segmented_control("Sıralama Düzeni:", ["Eskiden Yeniye", "Yeniden Eskiye"], default="Eskiden Yeniye")
order = "ASC" if siralama == "Eskiden Yeniye" else "DESC"

df = pd.read_sql_query(f"SELECT * FROM isler ORDER BY tarih {order}, id {order}", conn)
df['SÜRE'] = df.apply(lambda x: bekleme_suresi_hesapla(x['tarih'], x['durum']), axis=1)
df['SİL'] = False

if 'personel' in df.columns:
    df['personel'] = df['personel'].apply(lambda x: x.split(',') if x and isinstance(x, str) else [])

if not st.session_state.is_admin:
    df = df.drop(columns=["personel", "sure_gun"])
    kilitli_sutunlar = df.columns.tolist()
else:
    kilitli_sutunlar = ["id", "tarih", "SÜRE", "tur"]

# Durum seçeneklerine 'Biten' eklendi
yapilandirma = {
    "id": None, "tur": st.column_config.TextColumn("Tür"),
    "tarih": st.column_config.TextColumn("Kayıt"), "SÜRE": st.column_config.TextColumn("Bekleme"),
    "durum": st.column_config.SelectboxColumn("Durum", options=["Beklemede", "Tamamlandı", "Biten"], required=True),
    "personel": st.column_config.MultiselectColumn("Giden Ekip", options=personel_listesi),
    "sure_gun": st.column_config.NumberColumn("Gün", min_value=0, step=1),
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

# --- 5 SEKMELİ YAPI (İSTEDİĞİN SIRALAMA) ---
tab_bn, tab_tn, tab_bd, tab_sd, tab_bt = st.tabs(["⏳ BEKLEYEN MONTAJLAR", "✅ TAMAMLANAN MONTAJLAR", "⏳ BEKLEYEN DEMOLAR", "🧪 SÜREN DEMOLAR", "🏁 BİTEN DEMOLAR"])

with tab_bn:
    df_bn = df[(df['durum'] == 'Beklemede') & (df['tur'] == 'Normal')]
    if not df_bn.empty:
        ed_bn = st.data_editor(df_bn, column_config=yapilandirma, hide_index=True, width="stretch", key="ebn", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Bekleyen Montajları Güncelle"): kaydet(ed_bn)
    else: st.info("Bekleyen normal montaj yok.")

with tab_tn:
    df_tn = df[(df['durum'] == 'Tamamlandı') & (df['tur'] == 'Normal')]
    if not df_tn.empty:
        ed_tn = st.data_editor(df_tn, column_config=yapilandirma, hide_index=True, width="stretch", key="etn", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Tamamlanan Montajları Güncelle"): kaydet(ed_tn)
    else: st.info("Tamamlanmış montaj kaydı yok.")

with tab_bd:
    df_bd = df[(df['durum'] == 'Beklemede') & (df['tur'] == 'Demo')]
    if not df_bd.empty:
        ed_bd = st.data_editor(df_bd, column_config=yapilandirma, hide_index=True, width="stretch", key="ebd", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Bekleyen Demoları Güncelle"): kaydet(ed_bd)
    else: st.info("Bekleyen demo talebi yok.")

with tab_sd:
    # Tamamlanan Demolar artık 'Süren Demolar' olarak gösteriliyor
    df_sd = df[(df['durum'] == 'Tamamlandı') & (df['tur'] == 'Demo')]
    if not df_sd.empty:
        ed_sd = st.data_editor(df_sd, column_config=yapilandirma, hide_index=True, width="stretch", key="esd", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Süren Demoları Güncelle"): kaydet(ed_sd)
    else: st.info("Süren demo bulunmuyor.")

with tab_bt:
    # Yeni 'Biten Demolar' sekmesi eklendi
    df_bt = df[(df['durum'] == 'Biten') & (df['tur'] == 'Demo')]
    if not df_bt.empty:
        ed_bt = st.data_editor(df_bt, column_config=yapilandirma, hide_index=True, width="stretch", key="ebt", disabled=kilitli_sutunlar)
        if st.session_state.is_admin and st.button("💾 Biten Demoları Güncelle"): kaydet(ed_bt)
    else: st.info("Biten demo kaydı yok.")

# --- 10. PERSONEL İSTATİSTİKLERİ ---
if st.session_state.is_admin and personel_listesi:
    st.divider()
    st.subheader("👥 Ortak Personel İstatistikleri (Montaj + Demo)")
    stats = {isim: {"İş_Sayısı": 0, "Toplam_Gün": 0} for isim in personel_listesi}
    # İstatistikler Tamamlandı ve Biten durumlarını ortak sayar
    df_db = pd.read_sql_query("SELECT personel, sure_gun FROM isler WHERE durum IN ('Tamamlandı', 'Biten')", conn)
    for _, row in df_db.iterrows():
        if row['personel']:
            gidenler = [p.strip() for p in row['personel'].split(',')]
            for p in gidenler:
                if p in stats:
                    stats[p]["İş_Sayısı"] += 1
                    stats[p]["Toplam_Gün"] += (row['sure_gun'] or 0)
    df_stats = pd.DataFrame.from_dict(stats, orient='index').reset_index()
    df_stats.columns = ["Personel", "Gidilen İş (Toplam)", "Toplam Çalışma (Gün)"]
    st.dataframe(df_stats.sort_values("Toplam Çalışma (Gün)", ascending=False), hide_index=True, width="stretch")

# --- FOOTER ---
st.divider()
col_logo, col_yazi = st.columns([1, 7], gap="small")
with col_logo:
    st.image("logo-rekli.png", width=180) 
with col_yazi:
    st.write(""); st.write("")
    st.caption("© 2026 ÇÖZÜM MAKİNA - Montaj & Demo Takip v4.4")
@echo off
:: 1. Türkçe karakter ve UTF-8 desteğini aktif et
chcp 65001 > nul

:: 2. Bat dosyasının çalıştığı klasöre (montaj-takip) odaklan
cd /d "%~dp0"

echo ===========================================
echo    MONTAJ TAKIP SISTEMI AG PAYLASIMLI ACILIYOR
echo ===========================================
echo.

:: 3. Sanal ortam (venv) klasörünü kontrol et
if exist venv\Scripts\activate (
    echo [OK] Sanal ortam bulundu.
    call venv\Scripts\activate
    echo [OK] Streamlit sunucusu ağ üzerinden erişime açılıyor...
    
    :: --server.address 0.0.0.0 ekleyerek ağdaki diğer cihazların erişimini sağlıyoruz
    streamlit run montaj-takip.py --server.address 0.0.0.0
) else (
    echo [HATA] venv klasörü bulunamadı! 
    echo Lütfen bu .bat dosyasının montaj-takip.py ile aynı klasörde olduğundan emin olun.
    pause
)

pause
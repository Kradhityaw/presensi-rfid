# ============================================
# MATERI 06: SISTEM PRESENSI + SUPABASE CLOUD
# Program: Integrasi lengkap dengan database cloud
# Platform: MicroPython ESP32
# ============================================

from machine import Pin, SPI, I2C, PWM
import time
import ujson as json
import os
import network
import urequests as requests

# Import library
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from ds3231 import DS3231
import sdcard

# ============================================
# KONFIGURASI WIFI
# ============================================

WIFI_SSID = "NAMA_WIFI_ANDA"          # ← Ganti dengan nama WiFi Anda
WIFI_PASSWORD = "PASSWORD_WIFI_ANDA"   # ← Ganti dengan password WiFi Anda

# ============================================
# KONFIGURASI SUPABASE
# ============================================

SUPABASE_URL = "https://xxxxx.supabase.co"  # ← Ganti dengan URL Supabase Anda
SUPABASE_KEY = "xxxxx"                       # ← Ganti dengan API Key Supabase Anda
DEVICE_ID = 1                                # ← Sesuaikan dengan ID device di database
ORGANIZATION_ID = 1                          # ← Sesuaikan dengan ID organisasi Anda

# ============================================
# KONFIGURASI PIN
# ============================================

PIN_I2C_SCL = 22
PIN_I2C_SDA = 21
PIN_RFID_CS = 5
PIN_RFID_SCK = 18
PIN_RFID_MOSI = 23
PIN_RFID_MISO = 19
PIN_RFID_RST = 4
PIN_SD_CS = 25
PIN_SD_SCK = 14
PIN_SD_MOSI = 13
PIN_SD_MISO = 12
PIN_BUZZER = 15

# ============================================
# FILE SD CARD
# ============================================

FILE_PRESENSI = '/sd/presensi_pending.json'
FILE_KARTU_CACHE = '/sd/kartu_cache.json'

# ============================================
# GLOBAL VARIABLES
# ============================================

database_kartu = {}  # Cache kartu dari Supabase
is_online = False
wlan = None

# ============================================
# INISIALISASI HARDWARE
# ============================================

def init_i2c():
    try:
        i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA), freq=400000)
        print(f"✓ I2C OK")
        return i2c
    except Exception as e:
        print(f"✗ I2C error: {e}")
        return None

def init_oled(i2c):
    try:
        oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.show()
        print("✓ OLED OK")
        return oled
    except Exception as e:
        print(f"✗ OLED error: {e}")
        return None

def init_rtc(i2c):
    try:
        rtc = DS3231(i2c)
        dt = rtc.date_time()
        print(f"✓ RTC OK: {dt[0]}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}")
        return rtc
    except Exception as e:
        print(f"✗ RTC error: {e}")
        return None

def init_rfid():
    try:
        spi = SPI(1, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_RFID_SCK), mosi=Pin(PIN_RFID_MOSI), miso=Pin(PIN_RFID_MISO))
        rfid = MFRC522(spi, Pin(PIN_RFID_CS), Pin(PIN_RFID_RST))
        print("✓ RFID OK")
        return rfid
    except Exception as e:
        print(f"✗ RFID error: {e}")
        return None

def init_sd_card():
    try:
        spi = SPI(2, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_SD_SCK), mosi=Pin(PIN_SD_MOSI), miso=Pin(PIN_SD_MISO))
        sd = sdcard.SDCard(spi, Pin(PIN_SD_CS))
        
        try:
            os.mount(sd, '/sd')
        except:
            try:
                os.umount('/sd')
            except:
                pass
            os.mount(sd, '/sd')
        
        # Test
        with open('/sd/test.txt', 'w') as f:
            f.write('OK')
        os.remove('/sd/test.txt')
        
        print("✓ SD Card OK")
        return True
    except Exception as e:
        print(f"✗ SD Card error: {e}")
        return False

def init_buzzer():
    try:
        buzzer = PWM(Pin(PIN_BUZZER), freq=2000, duty=0)
        print("✓ Buzzer OK")
        return buzzer
    except:
        return None

# ============================================
# FUNGSI WIFI
# ============================================

def connect_wifi():
    """Koneksi ke WiFi"""
    global wlan, is_online
    
    print(f"\nMenghubungkan ke WiFi: {WIFI_SSID}")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        timeout = 15
        elapsed = 0
        while not wlan.isconnected() and elapsed < timeout:
            print(".", end="")
            time.sleep(1)
            elapsed += 1
        print()
    
    if wlan.isconnected():
        print(f"✓ WiFi terhubung!")
        print(f"  IP: {wlan.ifconfig()[0]}")
        is_online = True
        return True
    else:
        print("✗ WiFi gagal terhubung")
        is_online = False
        return False

def check_internet():
    """Cek koneksi internet"""
    try:
        response = requests.get("http://clients3.google.com/generate_204", timeout=5)
        response.close()
        return response.status_code in [200, 204]
    except:
        return False

# ============================================
# FUNGSI SUPABASE - SINKRONISASI KARTU
# ============================================

def sinkronisasi_kartu_dari_supabase():
    """
    Download data kartu RFID dari Supabase
    Simpan ke cache lokal
    """
    global database_kartu
    
    print("\n" + "="*60)
    print("SINKRONISASI DATA KARTU DARI SUPABASE")
    print("="*60)
    
    if not is_online:
        print("✗ Tidak ada koneksi internet")
        return False
    
    try:
        # Query untuk ambil data kartu dengan join user
        # Format: card_number, member_id, nama, kelas
        query = "card_number,organization_member_id,organization_members(user_profiles(first_name,last_name),departments(name))"
        url = f"{SUPABASE_URL}/rest/v1/rfid_cards?select={query}&organization_members.organization_id=eq.{ORGANIZATION_ID}"
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        print("Mengunduh data kartu...")
        response = requests.get(url, headers=headers, timeout=15)
        cards_data = json.loads(response.text)
        response.close()
        
        # Parse data
        database_kartu = {}
        for item in cards_data:
            uid = item['card_number']
            member_id = item['organization_member_id']
            
            # Extract nama
            nama = "Unknown"
            if item.get('organization_members') and item['organization_members'].get('user_profiles'):
                profile = item['organization_members']['user_profiles']
                first_name = profile.get('first_name', '')
                last_name = profile.get('last_name', '')
                nama = f"{first_name} {last_name}".strip()
            
            # Extract kelas/department
            kelas = "No Department"
            if item.get('organization_members') and item['organization_members'].get('departments'):
                kelas = item['organization_members']['departments'].get('name', 'No Department')
            
            database_kartu[uid] = {
                "nama": nama,
                "kelas": kelas,
                "member_id": member_id
            }
        
        print(f"✓ Berhasil download {len(database_kartu)} kartu")
        
        # Simpan ke cache SD Card
        simpan_cache_kartu()
        
        return True
        
    except Exception as e:
        print(f"✗ Error sinkronisasi: {e}")
        return False

def simpan_cache_kartu():
    """Simpan cache kartu ke SD Card"""
    try:
        with open(FILE_KARTU_CACHE, 'w') as f:
            f.write(json.dumps(database_kartu))
        print("  → Cache kartu disimpan ke SD Card")
        return True
    except Exception as e:
        print(f"  ✗ Error simpan cache: {e}")
        return False

def load_cache_kartu():
    """Load cache kartu dari SD Card"""
    global database_kartu
    
    try:
        if 'kartu_cache.json' in os.listdir('/sd'):
            with open(FILE_KARTU_CACHE, 'r') as f:
                content = f.read()
                if content:
                    database_kartu = json.loads(content)
                    print(f"✓ Loaded {len(database_kartu)} kartu dari cache SD")
                    return True
        print("⚠ Cache kartu tidak ditemukan")
        return False
    except Exception as e:
        print(f"✗ Error load cache: {e}")
        return False

# ============================================
# FUNGSI SUPABASE - UPLOAD PRESENSI
# ============================================

def upload_presensi_ke_supabase(records):
    """
    Upload batch presensi ke Supabase
    Gunakan stored procedure handle_attendance_batch
    """
    if not is_online:
        print("✗ Tidak ada koneksi internet")
        return False
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/handle_attendance_batch"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Format data untuk stored procedure
        taps = []
        for record in records:
            taps.append({
                "member_id_input": record['member_id'],
                "event_time_input": record['timestamp']
            })
        
        payload = json.dumps({"taps": taps})
        
        print(f"Mengupload {len(records)} presensi ke Supabase...")
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        response_text = response.text
        response.close()
        
        if response.status_code == 200 and "BATCH_PROCESSED" in response_text:
            print(f"✓ Upload berhasil!")
            return True
        else:
            print(f"✗ Upload gagal: {response_text}")
            return False
            
    except Exception as e:
        print(f"✗ Error upload: {e}")
        return False

# ============================================
# FUNGSI SD CARD - PRESENSI PENDING
# ============================================

def simpan_presensi_pending(record):
    """Simpan presensi yang belum terupload"""
    try:
        data_existing = []
        if 'presensi_pending.json' in os.listdir('/sd'):
            with open(FILE_PRESENSI, 'r') as f:
                content = f.read()
                if content:
                    data_existing = json.loads(content)
        
        data_existing.append(record)
        
        with open(FILE_PRESENSI, 'w') as f:
            f.write(json.dumps(data_existing))
        
        print(f"  → Tersimpan di pending ({len(data_existing)} total)")
        return True
    except Exception as e:
        print(f"  ✗ Error simpan pending: {e}")
        return False

def load_presensi_pending():
    """Load presensi pending dari SD"""
    try:
        if 'presensi_pending.json' in os.listdir('/sd'):
            with open(FILE_PRESENSI, 'r') as f:
                content = f.read()
                if content:
                    return json.loads(content)
        return []
    except:
        return []

def hapus_presensi_pending():
    """Hapus file presensi pending setelah berhasil upload"""
    try:
        if 'presensi_pending.json' in os.listdir('/sd'):
            os.remove(FILE_PRESENSI)
            print("  → File pending dibersihkan")
        return True
    except:
        return False

def coba_upload_pending():
    """Coba upload presensi pending jika ada"""
    pending = load_presensi_pending()
    
    if not pending:
        return True
    
    print(f"\nDitemukan {len(pending)} presensi pending")
    
    if upload_presensi_ke_supabase(pending):
        hapus_presensi_pending()
        print("✓ Semua pending berhasil diupload")
        return True
    else:
        print("✗ Upload pending gagal, akan dicoba lagi nanti")
        return False

# ============================================
# FUNGSI BUZZER
# ============================================

def beep(buzzer, freq, ms):
    if buzzer:
        buzzer.freq(freq)
        buzzer.duty(512)
        time.sleep_ms(ms)
        buzzer.duty(0)

def bunyi_sukses(buzzer):
    beep(buzzer, 1500, 100)
    time.sleep_ms(50)
    beep(buzzer, 2000, 100)

def bunyi_error(buzzer):
    beep(buzzer, 500, 200)
    time.sleep_ms(100)
    beep(buzzer, 500, 200)

def bunyi_upload(buzzer):
    beep(buzzer, 1000, 50)

# ============================================
# FUNGSI RTC
# ============================================

def get_timestamp_string(rtc):
    dt = rtc.date_time()
    return f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}T{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}+00:00"

def get_waktu_display(rtc):
    dt = rtc.date_time()
    return f"{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}"

# ============================================
# FUNGSI OLED
# ============================================

def tampilkan_teks(oled, lines):
    oled.fill(0)
    y = 0
    for line in lines[:4]:
        if line:
            text = str(line)[:16]
            x = max(0, (128 - len(text) * 8) // 2)
            oled.text(text, x, y, 1)
        y += 16
    oled.show()

def tampilkan_home(oled, rtc, online):
    status = "ONLINE" if online else "OFFLINE"
    tampilkan_teks(oled, [
        "SMKN 100 Malang",
        get_waktu_display(rtc),
        status,
        "Scan Kartu Anda"
    ])

def tampilkan_presensi_sukses(oled, nama, kelas, waktu):
    tampilkan_teks(oled, [
        "PRESENSI SUKSES",
        nama[:16],
        kelas[:16],
        waktu
    ])

def tampilkan_kartu_tidak_terdaftar(oled):
    tampilkan_teks(oled, [
        "KARTU TIDAK",
        "TERDAFTAR",
        "Hubungi Admin"
    ])

# ============================================
# FUNGSI RFID
# ============================================

def bytes_to_hex(data):
    return ''.join(['{:02x}'.format(b) for b in data[:4]])

def baca_kartu_rfid(rfid):
    try:
        (stat, tag_type) = rfid.request(rfid.REQIDL)
        if stat == rfid.OK:
            (stat, uid) = rfid.SelectTagSN()
            if stat == rfid.OK:
                return bytes_to_hex(uid)
    except:
        pass
    return None

# ============================================
# FUNGSI PRESENSI
# ============================================

def proses_presensi(uid, rtc, buzzer):
    """Proses presensi dengan upload ke Supabase atau simpan pending"""
    data = database_kartu.get(uid)
    
    if data:
        # Kartu TERDAFTAR
        timestamp = get_timestamp_string(rtc)
        waktu = get_waktu_display(rtc)
        
        record = {
            "member_id": data['member_id'],
            "nama": data['nama'],
            "kelas": data['kelas'],
            "uid": uid,
            "timestamp": timestamp,
            "waktu": waktu
        }
        
        print(f"\n{'='*60}")
        print(f"✓ PRESENSI BERHASIL")
        print(f"{'='*60}")
        print(f"Nama      : {data['nama']}")
        print(f"Kelas     : {data['kelas']}")
        print(f"Waktu     : {waktu}")
        print(f"Timestamp : {timestamp}")
        
        # Coba upload ke Supabase
        if is_online:
            if upload_presensi_ke_supabase([record]):
                print("✓ Data berhasil diupload ke Supabase")
                bunyi_upload(buzzer)
            else:
                print("⚠ Upload gagal, disimpan ke pending")
                simpan_presensi_pending(record)
        else:
            print("⚠ Mode offline, disimpan ke pending")
            simpan_presensi_pending(record)
        
        print(f"{'='*60}\n")
        
        bunyi_sukses(buzzer)
        return (True, data, waktu)
    else:
        # Kartu TIDAK TERDAFTAR
        print(f"\n{'='*60}")
        print(f"✗ KARTU TIDAK TERDAFTAR")
        print(f"{'='*60}")
        print(f"UID: {uid}")
        print(f"{'='*60}\n")
        
        bunyi_error(buzzer)
        return (False, None, None)

# ============================================
# PROGRAM UTAMA
# ============================================

def main():
    """Program utama"""
    global is_online
    
    print("\n" + "="*60)
    print("SISTEM PRESENSI RFID - MATERI 06")
    print("Dengan Integrasi Supabase Cloud")
    print("Teaching Factory SMKN 100 Malang")
    print("="*60 + "\n")
    
    # Inisialisasi hardware
    i2c = init_i2c()
    oled = init_oled(i2c) if i2c else None
    rtc = init_rtc(i2c) if i2c else None
    rfid = init_rfid()
    sd_available = init_sd_card()
    buzzer = init_buzzer()
    
    if not oled or not rfid:
        print("FATAL: OLED atau RFID error!")
        return
    
    # Koneksi WiFi
    tampilkan_teks(oled, ["Menghubungkan", "ke WiFi...", WIFI_SSID])
    wifi_ok = connect_wifi()
    
    if wifi_ok:
        internet_ok = check_internet()
        if internet_ok:
            tampilkan_teks(oled, ["WiFi OK", "Internet OK", "Mode ONLINE"])
            is_online = True
        else:
            tampilkan_teks(oled, ["WiFi OK", "No Internet", "Mode OFFLINE"])
            is_online = False
    else:
        tampilkan_teks(oled, ["WiFi Gagal", "Mode OFFLINE"])
        is_online = False
    
    time.sleep(2)
    
    # Sinkronisasi data
    if is_online:
        tampilkan_teks(oled, ["Sinkronisasi", "Data Kartu...", "Dari Supabase"])
        if sinkronisasi_kartu_dari_supabase():
            tampilkan_teks(oled, ["Sinkronisasi", "Berhasil!", f"{len(database_kartu)} kartu"])
            time.sleep(2)
            
            # Coba upload pending
            coba_upload_pending()
        else:
            tampilkan_teks(oled, ["Sinkronisasi", "Gagal", "Load dari cache"])
            time.sleep(2)
            load_cache_kartu()
    else:
        tampilkan_teks(oled, ["Mode Offline", "Load cache", "dari SD Card"])
        time.sleep(1)
        load_cache_kartu()
    
    # Sistem siap
    print("\n" + "="*60)
    print("SISTEM SIAP!")
    print("="*60)
    print(f"Mode         : {'ONLINE' if is_online else 'OFFLINE'}")
    print(f"Kartu cached : {len(database_kartu)}")
    print(f"SD Card      : {'OK' if sd_available else 'ERROR'}")
    print("\nTekan Ctrl+C untuk keluar")
    print("="*60 + "\n")
    
    tampilkan_home(oled, rtc, is_online)
    
    # Variable tracking
    last_card = None
    last_time = 0
    COOLDOWN_MS = 5000
    last_upload_check = time.ticks_ms()
    UPLOAD_CHECK_INTERVAL = 60000  # Cek pending setiap 1 menit
    
    # Loop utama
    try:
        while True:
            # Cek dan upload pending secara periodik
            if is_online and time.ticks_diff(time.ticks_ms(), last_upload_check) > UPLOAD_CHECK_INTERVAL:
                coba_upload_pending()
                last_upload_check = time.ticks_ms()
            
            # Baca kartu
            card_id = baca_kartu_rfid(rfid)
            
            if card_id:
                current_time = time.ticks_ms()
                
                # Cek cooldown
                if card_id == last_card:
                    if time.ticks_diff(current_time, last_time) < COOLDOWN_MS:
                        time.sleep_ms(100)
                        continue
                
                last_card = card_id
                last_time = current_time
                
                # Proses presensi
                sukses, data, waktu = proses_presensi(card_id, rtc, buzzer)
                
                if sukses:
                    tampilkan_presensi_sukses(oled, data['nama'], data['kelas'], waktu)
                else:
                    tampilkan_kartu_tidak_terdaftar(oled)
                
                time.sleep(3)
                tampilkan_home(oled, rtc, is_online)
            
            time.sleep_ms(100)
    
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("PROGRAM DIHENTIKAN")
        print("="*60)
        
        # Cek pending
        pending = load_presensi_pending()
        if pending:
            print(f"\nMasih ada {len(pending)} presensi pending belum terupload")
            print("Data tersimpan di SD Card: /sd/presensi_pending.json")
        else:
            print("\nSemua presensi sudah terupload")
        
        print("="*60 + "\n")
        
        tampilkan_teks(oled, ["Sistem", "Dihentikan"])
        if buzzer:
            buzzer.deinit()

if __name__ == "__main__":
    main()


# ============================================
# CARA SETUP & TESTING
# ============================================
"""
1. SETUP SUPABASE:
   - Buka dashboard Supabase Anda
   - Copy Project URL dan API Key (anon/public)
   - Jalankan SQL schema yang sudah diberikan
   - Insert data sample (organizations, departments, users, dll)

2. KONFIGURASI KODE:
   a. Edit bagian KONFIGURASI WIFI:
      WIFI_SSID = "NamaWiFiAnda"
      WIFI_PASSWORD = "PasswordWiFiAnda"
   
   b. Edit bagian KONFIGURASI SUPABASE:
      SUPABASE_URL = "https://xxxxx.supabase.co"
      SUPABASE_KEY = "eyJhbGc..."
      ORGANIZATION_ID = 1  (sesuaikan dengan ID organisasi Anda)

3. REGISTRASI KARTU RFID:
   a. Tap kartu baru di reader
   b. Catat UID yang muncul di Serial Monitor
   c. Buka Supabase Dashboard > Table Editor > rfid_cards
   d. Insert new row:
      - organization_member_id: pilih member yang sudah ada
      - card_number: masukkan UID (contoh: "a1b2c3d4")
      - is_active: true
   e. Jalankan sinkronisasi ulang (restart ESP32)

4. TESTING:
   - Upload program ke ESP32
   - Tunggu sistem terhubung ke WiFi
   - Sistem akan download data kartu dari Supabase
   - Tap kartu RFID untuk presensi
   - Data otomatis terupload ke Supabase
   - Cek di Supabase Dashboard > attendance_records

5. MODE OFFLINE:
   - Jika WiFi/internet mati, sistem otomatis ke mode OFFLINE
   - Presensi tetap berjalan menggunakan cache lokal
   - Data disimpan di SD Card sebagai "pending"
   - Saat online lagi, data pending otomatis terupload

6. MONITOR DATA DI SUPABASE:
   Query untuk lihat presensi hari ini:
   
   SELECT 
     up.first_name || ' ' || up.last_name AS nama,
     d.name AS kelas,
     ar.event_time
   FROM attendance_records ar
   JOIN organization_members om ON ar.organization_member_id = om.id
   JOIN user_profiles up ON om.user_profile_id = up.id
   LEFT JOIN departments d ON om.department_id = d.id
   WHERE DATE(ar.event_time) = CURRENT_DATE
   ORDER BY ar.event_time DESC;

FITUR LENGKAP:
✓ Sinkronisasi kartu dari Supabase
✓ Upload presensi real-time ke cloud
✓ Mode offline dengan cache lokal
✓ Auto-sync pending saat online
✓ Backup otomatis ke SD Card
✓ Notifikasi buzzer
✓ Timestamp akurat dengan RTC
✓ Display OLED dengan status online/offline
"""
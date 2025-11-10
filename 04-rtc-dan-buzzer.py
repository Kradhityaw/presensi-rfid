# ============================================
# MATERI 04: SISTEM PRESENSI + RTC & BUZZER
# Program: Menambahkan timestamp akurat dan notifikasi suara
# Platform: MicroPython ESP32
# ============================================

from machine import Pin, SPI, I2C, PWM
import time

# Import library
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from ds3231 import DS3231

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

PIN_BUZZER = 15

# ============================================
# DATA DUMMY
# ============================================

DATABASE_KARTU = {
    "a1b2c3d4": {"nama": "Budi Santoso", "kelas": "XII TKJ", "member_id": 1},
    "e5f6g7h8": {"nama": "Ani Wijaya", "kelas": "XII RPL", "member_id": 2},
    "i9j0k1l2": {"nama": "Candra Putra", "kelas": "XII TKJ", "member_id": 3},
}

# List untuk menyimpan data presensi (nanti akan disimpan ke SD Card)
DATA_PRESENSI = []

# ============================================
# INISIALISASI HARDWARE
# ============================================

def init_i2c():
    """Inisialisasi I2C untuk OLED dan RTC"""
    try:
        i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA), freq=400000)
        devices = i2c.scan()
        print(f"I2C devices: {[hex(d) for d in devices]}")
        return i2c
    except Exception as e:
        print(f"✗ Error I2C: {e}")
        return None

def init_oled(i2c):
    """Inisialisasi OLED"""
    try:
        oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.show()
        print("✓ OLED OK")
        return oled
    except Exception as e:
        print(f"✗ Error OLED: {e}")
        return None

def init_rtc(i2c):
    """Inisialisasi RTC DS3231"""
    try:
        rtc = DS3231(i2c)
        dt = rtc.date_time()
        
        # Cek apakah RTC perlu dikalibrasi (tahun < 2024)
        if dt[0] < 2024:
            print(f"⚠ RTC belum dikalibrasi (tahun: {dt[0]})")
            print("  RTC akan di-set ke waktu default: 2025-01-15 08:00:00")
            # Set ke waktu default
            # Format: (tahun, bulan, tanggal, jam, menit, detik, hari_dalam_seminggu)
            # Hari: 1=Senin, 2=Selasa, 3=Rabu, 4=Kamis, 5=Jumat, 6=Sabtu, 7=Minggu
            rtc.date_time((2025, 1, 15, 8, 0, 0, 3))  # 2025-01-15 08:00:00 Rabu
            dt = rtc.date_time()
            print(f"✓ RTC di-set ke: {dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}")
        else:
            print(f"✓ RTC OK: {dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}")
        
        return rtc
    except Exception as e:
        print(f"✗ Error RTC: {e}")
        return None

def init_rfid():
    """Inisialisasi RFID"""
    try:
        spi = SPI(1, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_RFID_SCK), mosi=Pin(PIN_RFID_MOSI), miso=Pin(PIN_RFID_MISO))
        rfid = MFRC522(spi, Pin(PIN_RFID_CS), Pin(PIN_RFID_RST))
        print("✓ RFID OK")
        return rfid
    except Exception as e:
        print(f"✗ Error RFID: {e}")
        return None

def init_buzzer():
    """Inisialisasi Buzzer"""
    try:
        buzzer = PWM(Pin(PIN_BUZZER), freq=2000, duty=0)
        print("✓ Buzzer OK")
        return buzzer
    except Exception as e:
        print(f"✗ Error Buzzer: {e}")
        return None

# ============================================
# FUNGSI BUZZER
# ============================================

def beep(buzzer, freq, duration_ms):
    """Bunyi buzzer dengan frekuensi dan durasi tertentu"""
    buzzer.freq(freq)
    buzzer.duty(512)
    time.sleep_ms(duration_ms)
    buzzer.duty(0)

def bunyi_sukses(buzzer):
    """Bunyi untuk presensi sukses"""
    beep(buzzer, 1500, 100)
    time.sleep_ms(50)
    beep(buzzer, 2000, 100)

def bunyi_error(buzzer):
    """Bunyi untuk kartu tidak terdaftar"""
    beep(buzzer, 500, 200)
    time.sleep_ms(100)
    beep(buzzer, 500, 200)

def bunyi_siap(buzzer):
    """Bunyi sistem siap"""
    beep(buzzer, 1000, 100)
    time.sleep_ms(50)
    beep(buzzer, 1500, 100)

# ============================================
# FUNGSI RTC
# ============================================

def set_waktu_rtc(rtc, year, month, day, hour, minute, second, weekday):
    """
    Set waktu RTC secara manual
    weekday: 1=Senin, 2=Selasa, 3=Rabu, 4=Kamis, 5=Jumat, 6=Sabtu, 7=Minggu
    
    Contoh:
    set_waktu_rtc(rtc, 2025, 1, 15, 14, 30, 0, 3)  # 2025-01-15 14:30:00 Rabu
    """
    print(f"\nSetting waktu RTC...")
    print(f"  Tanggal: {year:04d}-{month:02d}-{day:02d}")
    print(f"  Waktu  : {hour:02d}:{minute:02d}:{second:02d}")
    
    rtc.date_time((year, month, day, hour, minute, second, weekday))
    time.sleep_ms(100)
    
    # Verifikasi
    dt = rtc.date_time()
    print(f"✓ RTC berhasil di-set: {dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}")

def get_timestamp_string(rtc):
    """
    Dapatkan timestamp dalam format ISO8601
    Return: "2025-01-15T08:30:45+00:00"
    """
    dt = rtc.date_time()
    return f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}T{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}+00:00"

def get_waktu_display(rtc):
    """
    Dapatkan waktu untuk ditampilkan di OLED
    Return: "08:30:45"
    """
    dt = rtc.date_time()
    return f"{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}"

def get_tanggal_display(rtc):
    """
    Dapatkan tanggal untuk ditampilkan
    Return: "15 Jan 2025"
    """
    dt = rtc.date_time()
    bulan = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{dt[2]:02d} {bulan[dt[1]]} {dt[0]}"

# ============================================
# FUNGSI OLED
# ============================================

def tampilkan_teks(oled, lines):
    """Tampilkan teks di OLED (max 4 baris, rata tengah)"""
    oled.fill(0)
    y_pos = 0
    for line in lines[:4]:
        if line:
            text = str(line)[:16]
            text_width = len(text) * 8
            x_pos = max(0, (128 - text_width) // 2)
            oled.text(text, x_pos, y_pos, 1)
        y_pos += 16
    oled.show()

def tampilkan_home(oled, rtc):
    """Tampilan home dengan jam"""
    waktu = get_waktu_display(rtc)
    tampilkan_teks(oled, [
        "SMKN 100 Malang",
        waktu,
        "",
        "Scan Kartu Anda"
    ])

def tampilkan_presensi_sukses(oled, nama, kelas, waktu):
    """Tampilan presensi berhasil"""
    tampilkan_teks(oled, [
        "PRESENSI SUKSES",
        nama[:16],
        kelas[:16],
        waktu
    ])

def tampilkan_kartu_tidak_terdaftar(oled):
    """Tampilan kartu tidak terdaftar"""
    tampilkan_teks(oled, [
        "KARTU TIDAK",
        "TERDAFTAR",
        "Hubungi Admin"
    ])

# ============================================
# FUNGSI RFID
# ============================================

def bytes_to_hex(data):
    """Konversi bytes ke hex string"""
    return ''.join(['{:02x}'.format(b) for b in data[:4]])

def baca_kartu_rfid(rfid):
    """Baca kartu RFID, return UID atau None"""
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
    """
    Proses presensi lengkap dengan timestamp
    Return: (sukses: bool, data: dict)
    """
    # Cari data kartu
    data = DATABASE_KARTU.get(uid)
    
    if data:
        # Kartu terdaftar - PRESENSI SUKSES
        timestamp = get_timestamp_string(rtc)
        waktu_display = get_waktu_display(rtc)
        tanggal_display = get_tanggal_display(rtc)
        
        # Simpan ke list presensi
        record_presensi = {
            "member_id": data['member_id'],
            "nama": data['nama'],
            "kelas": data['kelas'],
            "uid": uid,
            "timestamp": timestamp,
            "waktu": waktu_display,
            "tanggal": tanggal_display
        }
        DATA_PRESENSI.append(record_presensi)
        
        # Print ke serial
        print(f"\n{'='*60}")
        print(f"✓ PRESENSI BERHASIL")
        print(f"{'='*60}")
        print(f"Nama      : {data['nama']}")
        print(f"Kelas     : {data['kelas']}")
        print(f"UID       : {uid}")
        print(f"Tanggal   : {tanggal_display}")
        print(f"Waktu     : {waktu_display}")
        print(f"Timestamp : {timestamp}")
        print(f"Total Presensi Hari Ini: {len(DATA_PRESENSI)}")
        print(f"{'='*60}\n")
        
        # Bunyi sukses
        if buzzer:
            bunyi_sukses(buzzer)
        
        return (True, data, waktu_display)
    else:
        # Kartu tidak terdaftar
        print(f"\n{'='*60}")
        print(f"✗ KARTU TIDAK TERDAFTAR")
        print(f"{'='*60}")
        print(f"UID: {uid}")
        print(f"Silakan hubungi admin untuk registrasi")
        print(f"{'='*60}\n")
        
        # Bunyi error
        if buzzer:
            bunyi_error(buzzer)
        
        return (False, None, None)

def tampilkan_statistik():
    """Tampilkan statistik presensi di serial monitor"""
    print("\n" + "="*60)
    print("STATISTIK PRESENSI HARI INI")
    print("="*60)
    print(f"Total presensi: {len(DATA_PRESENSI)}")
    
    if DATA_PRESENSI:
        print("\nDaftar Presensi:")
        print("-" * 60)
        for i, record in enumerate(DATA_PRESENSI, 1):
            print(f"{i}. {record['nama']:20s} | {record['kelas']:10s} | {record['waktu']}")
        print("-" * 60)
    print()

# ============================================
# PROGRAM UTAMA
# ============================================

def main():
    """Program utama"""
    print("\n" + "="*60)
    print("SISTEM PRESENSI RFID - MATERI 04")
    print("Dengan RTC DS3231 & Buzzer")
    print("Teaching Factory SMKN 100 Malang")
    print("="*60 + "\n")
    
    # Inisialisasi semua hardware
    i2c = init_i2c()
    if not i2c:
        print("FATAL: I2C error!")
        return
    
    oled = init_oled(i2c)
    if not oled:
        print("FATAL: OLED error!")
        return
    
    rtc = init_rtc(i2c)
    if not rtc:
        print("WARNING: RTC tidak tersedia, menggunakan waktu default")
    
    rfid = init_rfid()
    if not rfid:
        print("FATAL: RFID error!")
        tampilkan_teks(oled, ["ERROR!", "RFID Tidak", "Terdeteksi"])
        return
    
    buzzer = init_buzzer()
    if not buzzer:
        print("WARNING: Buzzer tidak tersedia")
    
    # Sistem siap
    print("\n" + "="*60)
    print("SISTEM SIAP!")
    print("="*60)
    print(f"Kartu terdaftar: {len(DATABASE_KARTU)}")
    print("Tekan Ctrl+C untuk melihat statistik dan keluar")
    print("="*60 + "\n")
    
    # ============================================
    # KALIBRASI WAKTU RTC (OPTIONAL)
    # ============================================
    # Uncomment baris di bawah untuk set waktu manual:
    # Format: set_waktu_rtc(rtc, tahun, bulan, tanggal, jam, menit, detik, hari)
    # Hari: 1=Senin, 2=Selasa, 3=Rabu, 4=Kamis, 5=Jumat, 6=Sabtu, 7=Minggu
    
    # Contoh set ke 15 Januari 2025 jam 14:30:00 (Rabu):
    # set_waktu_rtc(rtc, 2025, 1, 15, 14, 30, 0, 3)
    
    # Contoh set ke waktu saat ini (sesuaikan manual):
    # set_waktu_rtc(rtc, 2025, 1, 17, 10, 45, 0, 5)  # 17 Jan 2025, 10:45, Jumat
    # ============================================
    
    tampilkan_home(oled, rtc)
    if buzzer:
        bunyi_siap(buzzer)
    
    # Variable tracking
    last_card = None
    last_time = 0
    COOLDOWN_MS = 5000  # 5 detik cooldown
    
    # Loop utama
    try:
        while True:
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
                
                # Kembali ke home setelah 3 detik
                time.sleep(1)
                tampilkan_home(oled, rtc)
            
            time.sleep_ms(100)
    
    except KeyboardInterrupt:
        print("\n\nProgram dihentikan oleh user\n")
        
        # Tampilkan statistik
        tampilkan_statistik()
        
        # Tampilkan data presensi lengkap (untuk dicopy ke Excel/CSV)
        if DATA_PRESENSI:
            print("="*60)
            print("DATA PRESENSI (Format CSV)")
            print("="*60)
            print("Nama,Kelas,UID,Tanggal,Waktu,Timestamp")
            for record in DATA_PRESENSI:
                print(f"{record['nama']},{record['kelas']},{record['uid']},"
                      f"{record['tanggal']},{record['waktu']},{record['timestamp']}")
            print("="*60 + "\n")
        
        tampilkan_teks(oled, ["Sistem", "Dihentikan"])
        if buzzer:
            buzzer.deinit()

# ============================================
# JALANKAN PROGRAM
# ============================================

if __name__ == "__main__":
    main()


# ============================================
# PENJELASAN & CARA KALIBRASI RTC
# ============================================
"""
FITUR BARU DI MATERI 04:
1. ✓ RTC DS3231 untuk timestamp akurat
2. ✓ Auto-set waktu default jika RTC belum dikalibrasi
3. ✓ Fungsi manual untuk set waktu RTC
4. ✓ Buzzer untuk notifikasi suara (sukses/error)
5. ✓ Data presensi tersimpan dengan timestamp
6. ✓ Statistik presensi saat program dihentikan
7. ✓ Cooldown 5 detik untuk mencegah double tap

CARA KALIBRASI WAKTU RTC:

METODE 1: AUTO-SET (Default)
- RTC otomatis di-set ke 2025-01-15 08:00:00 jika tahun < 2024
- Cocok untuk testing awal

METODE 2: MANUAL SET
1. Cari bagian kode dengan komentar "KALIBRASI WAKTU RTC"
2. Uncomment salah satu baris set_waktu_rtc()
3. Edit parameter sesuai waktu sekarang:
   
   set_waktu_rtc(rtc, tahun, bulan, tanggal, jam, menit, detik, hari)
   
   Contoh set ke 17 Januari 2025 jam 10:45:30 (Jumat):
   set_waktu_rtc(rtc, 2025, 1, 17, 10, 45, 30, 5)

4. Upload program
5. Setelah RTC ter-set, comment kembali baris tersebut
6. Upload ulang (agar tidak reset setiap kali restart)

KODE HARI DALAM SEMINGGU:
1 = Senin
2 = Selasa  
3 = Rabu
4 = Kamis
5 = Jumat
6 = Sabtu
7 = Minggu

TIPS MENENTUKAN HARI:
Gunakan kalender atau website seperti timeanddate.com

CONTOH LENGKAP KALIBRASI:
```python
# Contoh 1: Set ke 20 Januari 2025, Senin, jam 08:00:00
set_waktu_rtc(rtc, 2025, 1, 20, 8, 0, 0, 1)

# Contoh 2: Set ke 15 Februari 2025, Sabtu, jam 14:30:45
set_waktu_rtc(rtc, 2025, 2, 15, 14, 30, 45, 6)

# Contoh 3: Set ke waktu sekarang (17 Jan 2025, 11:23:00, Jumat)
set_waktu_rtc(rtc, 2025, 1, 17, 11, 23, 0, 5)
```

CARA TESTING:
1. Upload program ke ESP32
2. Lihat waktu di OLED
3. Jika waktu salah:
   - Uncomment baris set_waktu_rtc()
   - Edit sesuai waktu sekarang
   - Upload ulang
   - Comment baris set_waktu_rtc()
   - Upload sekali lagi

4. Tap kartu RFID untuk presensi
5. Serial Monitor akan menampilkan timestamp yang akurat
6. Tekan Ctrl+C untuk melihat data lengkap

KEUNGGULAN RTC DS3231:
✓ Akurasi tinggi (±2 ppm)
✓ Baterai backup (CR2032) - waktu tetap jalan meski power off
✓ Sensor suhu built-in
✓ Lebih akurat dari DS1302
✓ Interface I2C (hanya 2 pin)

OUTPUT YANG DIHARAPKAN:
- OLED menampilkan jam real-time yang akurat
- Saat presensi sukses: tampil nama, kelas, dan waktu
- Buzzer berbunyi sesuai kondisi
- Serial monitor mencatat semua presensi dengan timestamp ISO8601
- Data dapat di-export ke format CSV

TROUBLESHOOTING:
- Waktu tidak akurat: Kalibrasi ulang dengan set_waktu_rtc()
- Waktu reset ke 2000: Ganti baterai CR2032 di modul RTC
- RTC tidak terdeteksi: Cek koneksi I2C (SCL=22, SDA=21)
- Waktu tertinggal/maju: RTC DS3231 sangat akurat, cek kalibrasi awal

NEXT STEP (Materi 05):
- Menyimpan data presensi ke SD Card
- Data tetap tersimpan meski ESP32 mati
- Backup otomatis untuk keamanan data
- Export ke format CSV untuk Excel
"""

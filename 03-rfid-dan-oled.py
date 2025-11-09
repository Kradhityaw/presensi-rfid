# ============================================
# MATERI 03: SISTEM PRESENSI - OLED & RFID
# Program: Dasar sistem presensi dengan OLED dan RFID
# Platform: MicroPython ESP32
# ============================================

from machine import Pin, SPI, I2C
import time

# Import library yang diperlukan (harus diupload ke ESP32)
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C

# ============================================
# KONFIGURASI PIN
# ============================================

# Pin OLED I2C
PIN_I2C_SCL = 22
PIN_I2C_SDA = 21

# Pin RFID RC522
PIN_RFID_CS = 5
PIN_RFID_SCK = 18
PIN_RFID_MOSI = 23
PIN_RFID_MISO = 19
PIN_RFID_RST = 4

# ============================================
# DATA DUMMY UNTUK TESTING
# (Nanti akan diganti dengan data dari database)
# ============================================

# Database dummy: kartu RFID dan pemiliknya
DATABASE_KARTU = {
    "a1b2c3d4": {"nama": "Budi Santoso", "kelas": "XII TKJ"},
    "e5f6g7h8": {"nama": "Ani Wijaya", "kelas": "XII RPL"},
    "i9j0k1l2": {"nama": "Candra Putra", "kelas": "XII TKJ"},
}

# ============================================
# INISIALISASI HARDWARE
# ============================================

def init_oled():
    """Inisialisasi layar OLED"""
    print("Menginisialisasi OLED...")
    try:
        i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA), freq=400000)
        oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.show()
        print("✓ OLED berhasil diinisialisasi")
        return oled
    except Exception as e:
        print(f"✗ Error OLED: {e}")
        return None

def init_rfid():
    """Inisialisasi RFID Reader RC522"""
    print("Menginisialisasi RFID Reader...")
    try:
        spi = SPI(1, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_RFID_SCK), 
                  mosi=Pin(PIN_RFID_MOSI), 
                  miso=Pin(PIN_RFID_MISO))
        
        rfid = MFRC522(spi, Pin(PIN_RFID_CS), Pin(PIN_RFID_RST))
        
        # Test baca version register
        version = rfid.read(0x37)
        
        if version in [0x88, 0x90, 0x91, 0x92, 0xB2]:
            print(f"✓ RFID Reader berhasil (Version: 0x{version:02X})")
            return rfid
        else:
            print("✗ RFID Reader tidak terdeteksi")
            return None
    except Exception as e:
        print(f"✗ Error RFID: {e}")
        return None

# ============================================
# FUNGSI OLED
# ============================================

def tampilkan_teks(oled, lines):
    """
    Menampilkan teks pada OLED (max 4 baris)
    Otomatis rata tengah
    """
    oled.fill(0)  # Clear screen
    
    y_pos = 0
    for line in lines[:4]:  # Max 4 lines
        if line:
            text = str(line)[:16]  # Max 16 karakter
            text_width = len(text) * 8
            x_pos = max(0, (128 - text_width) // 2)
            oled.text(text, x_pos, y_pos, 1)
        y_pos += 16
    
    oled.show()

def tampilkan_home(oled):
    """Tampilan home: Siap scan kartu"""
    tampilkan_teks(oled, [
        "SMKN 100 Malang",
        "Teaching Factory",
        "",
        "Scan Kartu Anda"
    ])

def tampilkan_presensi_sukses(oled, nama, kelas):
    """Tampilan ketika presensi berhasil"""
    tampilkan_teks(oled, [
        "PRESENSI SUKSES",
        nama[:16],
        kelas[:16],
        ""
    ])

def tampilkan_kartu_tidak_terdaftar(oled, uid):
    """Tampilan ketika kartu tidak terdaftar"""
    tampilkan_teks(oled, [
        "KARTU TIDAK",
        "TERDAFTAR",
        f"UID: {uid[:8]}",
        ""
    ])

# ============================================
# FUNGSI RFID
# ============================================

def bytes_to_hex(data):
    """Konversi bytes ke hex string (ambil 4 byte pertama)"""
    data = data[:4]
    return ''.join(['{:02x}'.format(b) for b in data])

def baca_kartu_rfid(rfid):
    """
    Membaca kartu RFID
    Return: string UID jika berhasil, None jika tidak ada kartu
    """
    try:
        (stat, tag_type) = rfid.request(rfid.REQIDL)
        
        if stat == rfid.OK:
            (stat, uid) = rfid.SelectTagSN()
            
            if stat == rfid.OK:
                card_id = bytes_to_hex(uid)
                return card_id
    except:
        pass
    
    return None

# ============================================
# FUNGSI PRESENSI
# ============================================

def cari_data_kartu(uid):
    """
    Mencari data pemilik kartu dari database dummy
    Return: dict dengan 'nama' dan 'kelas', atau None jika tidak ditemukan
    """
    return DATABASE_KARTU.get(uid)

def proses_presensi(uid):
    """
    Proses presensi: cari data dan catat waktu
    Return: (success: bool, data: dict atau None)
    """
    # Cari data kartu
    data = cari_data_kartu(uid)
    
    if data:
        # Kartu terdaftar
        waktu_presensi = time.localtime()
        jam = f"{waktu_presensi[3]:02d}:{waktu_presensi[4]:02d}:{waktu_presensi[5]:02d}"
        
        print(f"\n{'='*50}")
        print(f"PRESENSI BERHASIL")
        print(f"{'='*50}")
        print(f"UID Kartu : {uid}")
        print(f"Nama      : {data['nama']}")
        print(f"Kelas     : {data['kelas']}")
        print(f"Waktu     : {jam}")
        print(f"{'='*50}\n")
        
        return (True, data)
    else:
        # Kartu tidak terdaftar
        print(f"\n{'='*50}")
        print(f"KARTU TIDAK TERDAFTAR")
        print(f"{'='*50}")
        print(f"UID: {uid}")
        print(f"Silakan hubungi admin untuk registrasi kartu")
        print(f"{'='*50}\n")
        
        return (False, None)

# ============================================
# PROGRAM UTAMA
# ============================================

def main():
    """Program utama"""
    print("\n" + "="*60)
    print("SISTEM PRESENSI RFID - MATERI 03")
    print("Teaching Factory SMKN 100 Malang")
    print("="*60 + "\n")
    
    # Inisialisasi OLED
    oled = init_oled()
    if not oled:
        print("FATAL: OLED tidak bisa diinisialisasi!")
        print("Periksa koneksi I2C (SCL=22, SDA=21)")
        return
    
    # Inisialisasi RFID
    rfid = init_rfid()
    if not rfid:
        print("FATAL: RFID tidak bisa diinisialisasi!")
        print("Periksa koneksi SPI RFID")
        tampilkan_teks(oled, ["ERROR!", "RFID Reader", "Tidak Terdeteksi"])
        return
    
    # Tampilkan home screen
    tampilkan_home(oled)
    
    print("="*60)
    print("SISTEM SIAP!")
    print("="*60)
    print(f"Jumlah kartu terdaftar: {len(DATABASE_KARTU)}")
    print("Silakan tap kartu RFID untuk presensi...")
    print("Tekan Ctrl+C untuk keluar\n")
    
    # Variable untuk mencegah scan ganda
    last_card = None
    last_time = 0
    DEBOUNCE_MS = 3000  # 3 detik cooldown
    
    # Loop utama
    try:
        while True:
            # Baca kartu RFID
            card_id = baca_kartu_rfid(rfid)
            
            if card_id:
                current_time = time.ticks_ms()
                
                # Cek debounce: hindari scan berulang kartu yang sama
                if card_id == last_card:
                    if time.ticks_diff(current_time, last_time) < DEBOUNCE_MS:
                        time.sleep_ms(100)
                        continue
                
                # Update tracking
                last_card = card_id
                last_time = current_time
                
                # Proses presensi
                sukses, data = proses_presensi(card_id)
                
                if sukses:
                    # Tampilkan sukses di OLED
                    tampilkan_presensi_sukses(oled, data['nama'], data['kelas'])
                else:
                    # Tampilkan kartu tidak terdaftar
                    tampilkan_kartu_tidak_terdaftar(oled, card_id)
                
                # Tunggu 3 detik, lalu kembali ke home
                time.sleep(3)
                tampilkan_home(oled)
            
            # Delay kecil untuk hemat CPU
            time.sleep_ms(100)
    
    except KeyboardInterrupt:
        print("\n\nProgram dihentikan oleh user")
        tampilkan_teks(oled, ["Sistem", "Dihentikan"])

# ============================================
# JALANKAN PROGRAM
# ============================================

if __name__ == "__main__":
    main()


# ============================================
# CARA TESTING
# ============================================
"""
1. PERSIAPAN:
   - Pastikan library mfrc522.py dan ssd1306.py sudah diupload ke ESP32
   - Koneksi hardware sudah benar sesuai pin configuration

2. TESTING:
   - Upload kode ini ke ESP32
   - Buka Serial Monitor
   - Tap kartu RFID di reader
   - Lihat hasil di OLED dan Serial Monitor

3. CARA MENAMBAH DATA KARTU:
   a. Tap kartu yang belum terdaftar
   b. Catat UID yang muncul di Serial Monitor (contoh: "a1b2c3d4")
   c. Edit dictionary DATABASE_KARTU, tambahkan:
      "uid_kartu": {"nama": "Nama Siswa", "kelas": "Kelas"}
   d. Upload ulang program

4. CONTOH PENAMBAHAN KARTU:
   DATABASE_KARTU = {
       "a1b2c3d4": {"nama": "Budi Santoso", "kelas": "XII TKJ"},
       "12345678": {"nama": "Siti Nurhaliza", "kelas": "XII RPL"},  # ← Kartu baru
   }

5. OUTPUT YANG DIHARAPKAN:
   - OLED menampilkan "Scan Kartu Anda"
   - Saat kartu di-tap: OLED menampilkan "PRESENSI SUKSES" + nama + kelas
   - Serial Monitor menampilkan detail presensi
   - Setelah 3 detik, kembali ke tampilan awal

NEXT STEP (Materi 04):
- Menambahkan RTC untuk timestamp yang akurat
- Menambahkan buzzer untuk notifikasi suara
- Data presensi akan dicatat dengan waktu yang tepat
"""
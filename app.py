from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
from collections import deque
import uuid
import json
import os

# --- Inisialisasi Flask App ---
app = Flask(__name__)
# Kunci rahasia untuk sesi dan flash messages. GANTI dengan nilai yang kuat!
app.secret_key = 'kunci_super_rahasia_dan_sulit_ditebak_untuk_keamanan_aplikasi_anda_di_proyek_portofolio' 

# --- STRUKTUR DATA UTAMA ---
antrian_truk = deque()
gudang = {} # Key: ID_BARANG, Value: {'nama': 'Nama Barang', 'batches': [{'stok': X, 'kadaluarsa': date_obj}]}
riwayat_transaksi = deque() # {'timestamp': datetime_obj, 'tipe': 'MASUK/KELUAR/UPDATE', 'id_barang': ID, 'nama_barang': Nama, 'jumlah': Jumlah}

# --- Konfigurasi Persistensi Data ---
DATA_FOLDER = 'data'
DATA_FILE_PATH = os.path.join(DATA_FOLDER, 'gudang_data.json')

# --- FUNGSI PERSISTENSI DATA ---
def load_data():
    global antrian_truk, gudang, riwayat_transaksi
    # Pastikan folder data ada
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        print(f"ℹ️ Folder '{DATA_FOLDER}' dibuat.")

    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, 'r') as f:
                data = json.load(f)
                
                # Muat antrian_truk
                antrian_truk.extend(data.get('antrian_truk', []))
                
                # Muat gudang dan konversi string tanggal ke objek date
                loaded_gudang = data.get('gudang', {})
                for id_brg, brg_data in loaded_gudang.items():
                    # Pastikan 'batches' ada dan merupakan list
                    if 'batches' in brg_data and isinstance(brg_data['batches'], list):
                        for batch in brg_data['batches']:
                            # Handle kasus jika 'kadaluarsa' tidak ada atau format salah
                            if 'kadaluarsa' in batch and isinstance(batch['kadaluarsa'], str):
                                try:
                                    batch['kadaluarsa'] = datetime.datetime.strptime(batch['kadaluarsa'], "%Y-%m-%d").date()
                                except ValueError:
                                    print(f"⚠️ Peringatan: Tanggal kadaluarsa '{batch['kadaluarsa']}' untuk barang {id_brg} tidak valid. Mengabaikan.")
                                    batch['kadaluarsa'] = None # Atau tangani sesuai kebijakan Anda
                            else:
                                batch['kadaluarsa'] = None # Jika tidak ada atau bukan string
                    else:
                        brg_data['batches'] = [] # Pastikan batches adalah list
                gudang = loaded_gudang

                # Muat riwayat_transaksi dan konversi string timestamp ke objek datetime
                loaded_riwayat = data.get('riwayat_transaksi', [])
                for transaksi in loaded_riwayat:
                    if 'timestamp' in transaksi and isinstance(transaksi['timestamp'], str):
                        try:
                            transaksi['timestamp'] = datetime.datetime.strptime(transaksi['timestamp'], "%Y-%m-%d %H:%M:%S.%f")
                        except ValueError:
                            print(f"⚠️ Peringatan: Timestamp '{transaksi['timestamp']}' di riwayat transaksi tidak valid. Mengabaikan.")
                            transaksi['timestamp'] = None
                    else:
                        transaksi['timestamp'] = None
                riwayat_transaksi.extend(loaded_riwayat)

            print("✅ Data berhasil dimuat dari gudang_data.json.")
        except json.JSONDecodeError:
            print("⚠️ File data JSON korup atau kosong. Memulai dengan data baru.")
        except Exception as e:
            print(f"❌ Error saat memuat data: {e}")
    else:
        print("ℹ️ File data gudang_data.json tidak ditemukan. Memulai dengan data kosong.")

def save_data():
    data_to_save = {
        'antrian_truk': list(antrian_truk), # Convert deque to list for JSON serialization
        'gudang': {},
        'riwayat_transaksi': []
    }

    # Konversi objek date di gudang menjadi string
    for id_brg, brg_data in gudang.items():
        data_to_save['gudang'][id_brg] = {
            'nama': brg_data['nama'],
            'batches': [
                {'stok': batch['stok'], 'kadaluarsa': batch['kadaluarsa'].strftime("%Y-%m-%d") if batch['kadaluarsa'] else None}
                for batch in brg_data['batches']
            ]
        }
    
    # Konversi timestamp di riwayat transaksi menjadi string
    for transaksi in riwayat_transaksi:
        data_to_save['riwayat_transaksi'].append({
            'timestamp': transaksi['timestamp'].strftime("%Y-%m-%d %H:%M:%S.%f") if transaksi['timestamp'] else None,
            'tipe': transaksi['tipe'],
            'id_barang': transaksi['id_barang'],
            'nama_barang': transaksi['nama_barang'],
            'jumlah': transaksi['jumlah']
        })

    try:
        with open(DATA_FILE_PATH, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        print("✅ Data berhasil disimpan ke gudang_data.json.")
    except Exception as e:
        print(f"❌ Error saat menyimpan data: {e}")

# --- ALGORITMA SORTING: MERGE SORT ---
def merge_sort(batch_list):
    if len(batch_list) <= 1:
        return batch_list

    tengah = len(batch_list) // 2
    paruh_kiri = batch_list[:tengah]
    paruh_kanan = batch_list[tengah:]

    paruh_kiri_urut = merge_sort(paruh_kiri)
    paruh_kanan_urut = merge_sort(paruh_kanan)

    return merge(paruh_kiri_urut, paruh_kanan_urut)

def merge(kiri, kanan):
    hasil_gabungan = []
    indeks_kiri, indeks_kanan = 0, 0

    while indeks_kiri < len(kiri) and indeks_kanan < len(kanan):
        # Handle None for kadaluarsa if any
        if kiri[indeks_kiri]['kadaluarsa'] is None and kanan[indeks_kanan]['kadaluarsa'] is None:
            hasil_gabungan.append(kiri[indeks_kiri]) # Assume order if both are None
            indeks_kiri += 1
        elif kiri[indeks_kiri]['kadaluarsa'] is None: # None comes last
            hasil_gabungan.append(kanan[indeks_kanan])
            indeks_kanan += 1
        elif kanan[indeks_kanan]['kadaluarsa'] is None: # None comes last
            hasil_gabungan.append(kiri[indeks_kiri])
            indeks_kiri += 1
        elif kiri[indeks_kiri]['kadaluarsa'] < kanan[indeks_kanan]['kadaluarsa']:
            hasil_gabungan.append(kiri[indeks_kiri])
            indeks_kiri += 1
        else:
            hasil_gabungan.append(kanan[indeks_kanan])
            indeks_kanan += 1
    
    hasil_gabungan.extend(kiri[indeks_kiri:])
    hasil_gabungan.extend(kanan[indeks_kanan:])
    
    return hasil_gabungan

# --- ALGORITMA SEARCHING: SEQUENTIAL SEARCH ---
def sequential_search(query, data_gudang):
    hasil_pencarian = []
    for id_brg, data in data_gudang.items():
        if query.lower() in id_brg.lower() or query.lower() in data['nama'].lower():
            total_stok = sum(batch['stok'] for batch in data['batches'])
            hasil_pencarian.append({
                'id': id_brg,
                'nama': data['nama'],
                'total_stok': total_stok,
                'batches': data['batches']
            })
    return hasil_pencarian

# --- FUNGSI-FUNGSI UTILITAS ---
def generate_id_barang():
    return f"BRG-{str(uuid.uuid4().hex)[:6].upper()}"

def catat_transaksi(tipe, id_barang, nama_barang, jumlah):
    riwayat_transaksi.append({
        'timestamp': datetime.datetime.now(),
        'tipe': tipe, 
        'id_barang': id_barang,
        'nama_barang': nama_barang,
        'jumlah': jumlah
    })

# --- ROUTES APLIKASI WEB ---

@app.route('/')
def index():
    """Halaman utama (landing page) aplikasi."""
    return render_template('index.html', antrian_count=len(antrian_truk), gudang_item_count=len(gudang))

# --- ROUTES: ANTRIAN TRUK ---

@app.route('/antrian')
def antrian_list():
    """Menampilkan daftar semua truk dalam antrian."""
    return render_template('antrian_list.html', antrian_truk=list(antrian_truk))

@app.route('/antrian/add', methods=['GET', 'POST'])
def antrian_add():
    """Menambahkan truk baru ke antrian."""
    if request.method == 'POST':
        plat_nomor = request.form['plat_nomor'].upper().strip()
        nama_supir = request.form['nama_supir'].strip()
        muatan_str = request.form['muatan'].strip()
        muatan = [item.strip() for item in muatan_str.split(',') if item.strip()] if muatan_str else []

        if not plat_nomor:
            flash('Plat Nomor tidak boleh kosong!', 'error')
            return redirect(url_for('antrian_add'))
        if not nama_supir:
            flash('Nama Supir tidak boleh kosong!', 'error')
            return redirect(url_for('antrian_add'))

        truk = {'plat': plat_nomor, 'supir': nama_supir, 'muatan': muatan}
        antrian_truk.append(truk)
        save_data()
        flash(f'Truk {plat_nomor} berhasil ditambahkan ke antrian.', 'success')
        return redirect(url_for('antrian_list'))

    return render_template('antrian_add.html')

@app.route('/antrian/serve', methods=['GET', 'POST'])
def antrian_serve():
    """Melayani truk berikutnya dan memasukkan barang ke gudang."""
    if not antrian_truk:
        flash('Tidak ada truk dalam antrian untuk dilayani.', 'info')
        return redirect(url_for('antrian_list'))

    # Ambil truk paling depan tanpa menghapusnya dulu
    truk_dilayani = antrian_truk[0] 

    if request.method == 'POST':
        items_processed_count = 0
        barang_valid_untuk_dimasukkan = []
        errors = []

        # Kumpulkan semua indeks dari input dinamis yang ada di form
        # Contoh: Jika ada nama_barang_0, nama_barang_1, stok_0, kadaluarsa_0, dll.
        # Kita akan mencari semua indeks unik (0, 1, 2, ...)
        input_indices = set()
        for key in request.form:
            if key.startswith('nama_barang_'):
                try:
                    index = int(key.split('_')[-1])
                    input_indices.add(index)
                except ValueError:
                    continue # Abaikan kunci form yang tidak sesuai pola

        # Sortir indeks agar pemrosesan berurutan (opsional, tapi baik untuk debugging)
        sorted_indices = sorted(list(input_indices))

        for index in sorted_indices:
            nama_barang = request.form.get(f'nama_barang_{index}', '').strip()
            stok_str = request.form.get(f'stok_{index}', '').strip()
            kadaluarsa_str = request.form.get(f'kadaluarsa_{index}', '').strip()

            # Hanya proses jika NAMA BARANG tidak kosong
            if not nama_barang:
                # Jika ada input stok/kadaluarsa tapi nama barang kosong, anggap itu error
                if stok_str or kadaluarsa_str:
                    errors.append(f"Baris input barang {index+1}: Nama barang tidak boleh kosong jika stok atau tanggal diisi.")
                continue # Lanjutkan ke indeks berikutnya jika nama barang kosong

            # Validasi Stok
            try:
                stok = int(stok_str)
                if stok <= 0:
                    errors.append(f"Barang '{nama_barang}': Stok harus angka positif.")
                    continue
            except ValueError:
                errors.append(f"Barang '{nama_barang}': Stok tidak valid (harus angka).")
                continue

            # Validasi Tanggal Kadaluarsa
            try:
                kadaluarsa = datetime.datetime.strptime(kadaluarsa_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Barang '{nama_barang}': Format tanggal kadaluarsa tidak valid (gunakan YYYY-MM-DD).")
                continue
            
            # Jika semua valid, tambahkan ke daftar untuk diproses
            barang_valid_untuk_dimasukkan.append({
                'nama': nama_barang,
                'stok': stok,
                'kadaluarsa': kadaluarsa
            })
        
        # Jika ada error, tampilkan semua error dan kembali ke form
        if errors:
            for error_msg in errors:
                flash(error_msg, 'error')
            return render_template('antrian_serve.html', truk=truk_dilayani) # Tetap di halaman form

        if not barang_valid_untuk_dimasukkan:
            flash('Tidak ada barang yang berhasil dimasukkan dari truk.', 'warning')
            return redirect(url_for('antrian_list')) # Kembali ke daftar antrian jika tidak ada barang yang valid

        # --- Proses semua barang yang valid ---
        for item_data in barang_valid_untuk_dimasukkan:
            id_barang_ada = next((id_brg for id_brg, data in gudang.items() if data['nama'].lower() == item_data['nama'].lower()), None)
            
            if id_barang_ada:
                id_barang = id_barang_ada
            else:
                id_barang = generate_id_barang()
                gudang[id_barang] = {'nama': item_data['nama'], 'batches': []}

            batch_baru = {'stok': item_data['stok'], 'kadaluarsa': item_data['kadaluarsa']}
            gudang[id_barang]['batches'].append(batch_baru)
            gudang[id_barang]['batches'] = merge_sort(gudang[id_barang]['batches']) # Pastikan selalu terurut
            
            catat_transaksi('MASUK', id_barang, item_data['nama'], item_data['stok'])
            items_processed_count += 1
        
        # Hapus truk dari antrian setelah semua barang yang valid diproses
        antrian_truk.popleft() 
        save_data() # Simpan perubahan
        flash(f'Truk {truk_dilayani["plat"]} berhasil dilayani. {items_processed_count} jenis barang dimasukkan.', 'success')
        return redirect(url_for('antrian_list'))

    # Untuk GET request, tampilkan form
    return render_template('antrian_serve.html', truk=truk_dilayani)


# --- ROUTES: MANAJEMEN GUDANG ---

@app.route('/gudang')
def gudang_overview():
    """Halaman overview untuk manajemen gudang."""
    return render_template('gudang_list.html', gudang=gudang) # Menggunakan gudang_list.html sebagai default overview

@app.route('/gudang/list')
def gudang_list():
    """Menampilkan semua stok barang di gudang."""
    sorted_items = sorted(gudang.items(), key=lambda item: item[1]['nama'].lower())
    return render_template('gudang_list.html', gudang=gudang, items=sorted_items)

@app.route('/gudang/search', methods=['GET', 'POST'])
def gudang_search():
    """Mencari barang di gudang."""
    hasil = []
    query = ""
    if request.method == 'POST':
        query = request.form['query'].strip()
        if query:
            hasil = sequential_search(query, gudang)
            if not hasil:
                flash(f"Barang dengan query '{query}' tidak ditemukan.", 'info')
        else:
            flash("Query pencarian tidak boleh kosong.", 'error')
    return render_template('gudang_search.html', hasil=hasil, query=query)

@app.route('/gudang/take', methods=['GET', 'POST'])
def gudang_take():
    """Mengambil barang dari gudang."""
    if request.method == 'POST':
        id_barang = request.form['id_barang'].upper().strip()
        jumlah_ambil_str = request.form['jumlah_ambil'].strip()

        if id_barang not in gudang or not gudang[id_barang]['batches']:
            flash(f"Barang dengan ID {id_barang} tidak ditemukan atau stok habis.", 'error')
            return redirect(url_for('gudang_take'))
        
        try:
            jumlah_ambil = int(jumlah_ambil_str)
            if jumlah_ambil <= 0:
                flash("Jumlah harus lebih dari nol.", 'error')
                return redirect(url_for('gudang_take'))
        except ValueError:
            flash("Jumlah pengambilan tidak valid.", 'error')
            return redirect(url_for('gudang_take'))

        item = gudang[id_barang]
        # FEFO: selalu ambil dari batch yang paling awal kadaluarsa (indeks 0 setelah diurutkan)
        batch_teratas = item['batches'][0] 

        if jumlah_ambil > batch_teratas['stok']:
            flash(f"Stok tidak mencukupi. Stok tersedia di batch ini hanya {batch_teratas['stok']}.", 'error')
            return redirect(url_for('gudang_take'))

        batch_teratas['stok'] -= jumlah_ambil
        catat_transaksi('KELUAR', id_barang, item['nama'], jumlah_ambil)
        flash(f"Berhasil mengambil {jumlah_ambil} unit '{item['nama']}'.", 'success')

        if batch_teratas['stok'] == 0:
            item['batches'].pop(0)
            flash("Batch ini sekarang kosong dan telah dihapus.", 'info')
            catat_transaksi('HAPUS_BATCH_KOSONG_KELUAR', id_barang, item['nama'], 0)
        
        save_data()
        return redirect(url_for('gudang_list'))

    # Untuk GET request, kirim hanya item yang masih punya stok
    items_with_stock = {id: data for id, data in gudang.items() if sum(b['stok'] for b in data['batches']) > 0}
    return render_template('gudang_take.html', gudang_items=items_with_stock)

@app.route('/gudang/update', methods=['GET', 'POST'])
def gudang_update():
    """Memperbarui informasi barang atau batch tertentu."""
    if request.method == 'POST':
        id_barang = request.form['id_barang'].upper().strip()
        new_name = request.form.get('new_name', '').strip()
        
        item = gudang.get(id_barang)
        if not item:
            flash(f"Barang dengan ID {id_barang} tidak ditemukan.", 'error')
            return redirect(url_for('gudang_update'))

        updated = False
        if new_name and new_name != item['nama']:
            item['nama'] = new_name
            flash(f"Nama barang berhasil diupdate menjadi '{new_name}'.", 'success')
            updated = True
        
        # Logika update batch
        for key in request.form:
            if key.startswith('batch_id_'):
                batch_form_idx = key.split('_')[-1] # This is the index from the dynamic form, not list index
                
                # Retrieve the original list index of the batch from the hidden input
                original_batch_list_idx_str = request.form.get(f'original_batch_idx_{batch_form_idx}')
                
                try:
                    original_batch_list_idx = int(original_batch_list_idx_str)
                    if not (0 <= original_batch_list_idx < len(item['batches'])):
                        flash(f"Internal error: Nomor batch {original_batch_list_idx} tidak valid.", 'error')
                        continue # Skip to next batch in form
                    
                    current_batch = item['batches'][original_batch_list_idx]
                    
                    new_stok_str = request.form.get(f'new_stok_{batch_form_idx}', '').strip()
                    new_kadaluarsa_str = request.form.get(f'new_kadaluarsa_{batch_form_idx}', '').strip()

                    batch_updated_flag = False

                    if new_stok_str:
                        try:
                            new_stok_val = int(new_stok_str)
                            if new_stok_val < 0:
                                flash(f"Stok baru untuk batch kadaluarsa {current_batch['kadaluarsa']} tidak boleh negatif.", 'error')
                            elif new_stok_val != current_batch['stok']:
                                stok_diff = new_stok_val - current_batch['stok']
                                current_batch['stok'] = new_stok_val
                                catat_transaksi('UPDATE_STOK', id_barang, item['nama'], stok_diff)
                                flash(f"Stok batch kadaluarsa {current_batch['kadaluarsa']} berhasil diupdate. Stok baru: {current_batch['stok']}.", 'success')
                                if current_batch['stok'] == 0:
                                    # Tandai untuk dihapus setelah loop agar tidak mengganggu indeks
                                    item['batches'][original_batch_list_idx] = None # Set None for later removal
                                    flash(f"Batch kadaluarsa {current_batch['kadaluarsa']} sekarang kosong dan akan dihapus.", 'info')
                                    catat_transaksi('HAPUS_BATCH_KOSONG', id_barang, item['nama'], 0)
                                batch_updated_flag = True
                        except ValueError:
                            flash(f"Input stok untuk batch kadaluarsa {current_batch['kadaluarsa']} tidak valid.", 'error')

                    if new_kadaluarsa_str:
                        try:
                            new_kadaluarsa_val = datetime.datetime.strptime(new_kadaluarsa_str, "%Y-%m-%d").date()
                            if new_kadaluarsa_val != current_batch['kadaluarsa']:
                                current_batch['kadaluarsa'] = new_kadaluarsa_val
                                batch_updated_flag = True
                                flash(f"Tanggal kadaluarsa batch {original_batch_list_idx} berhasil diupdate.", 'success')
                        except ValueError:
                            flash(f"Input tanggal kadaluarsa untuk batch {original_batch_list_idx} tidak valid.", 'error')

                    if batch_updated_flag:
                        updated = True

                except ValueError:
                    flash("Nomor batch tidak valid.", 'error')
        
        if updated:
            # Hapus batch yang ditandai None (stok 0)
            item['batches'] = [b for b in item['batches'] if b is not None]
            # Selalu urutkan kembali batches setelah potensi perubahan kadaluarsa atau penghapusan
            item['batches'] = merge_sort(item['batches'])
            save_data()
            return redirect(url_for('gudang_list'))

    return render_template('gudang_update.html', gudang_items=gudang)

@app.route('/gudang/delete', methods=['GET', 'POST'])
def gudang_delete():
    """Menghapus barang dari gudang."""
    if request.method == 'POST':
        id_barang = request.form['id_barang'].upper().strip()

        if id_barang not in gudang:
            flash(f"Barang dengan ID {id_barang} tidak ditemukan.", 'error')
            return redirect(url_for('gudang_delete'))

        nama_barang_dihapus = gudang[id_barang]['nama']
        del gudang[id_barang]
        catat_transaksi('HAPUS_BARANG', id_barang, nama_barang_dihapus, 0)
        save_data()
        flash(f"Barang '{nama_barang_dihapus}' (ID: {id_barang}) berhasil dihapus dari gudang.", 'success')
        return redirect(url_for('gudang_list'))

    return render_template('gudang_delete.html', gudang_items=gudang)

@app.route('/gudang/sort')
def gudang_sort():
    """Menampilkan barang diurutkan berdasarkan stok."""
    daftar_barang = []
    for id_brg, data in gudang.items():
        total_stok = sum(batch['stok'] for batch in data['batches'])
        daftar_barang.append({'id': id_brg, 'nama': data['nama'], 'total_stok': total_stok})
    
    pilihan_sort = request.args.get('sort', 'terbanyak')
    
    if pilihan_sort == 'terbanyak':
        daftar_urut = sorted(daftar_barang, key=lambda x: x['total_stok'], reverse=True)
        judul = "Daftar Barang (Stok Terbanyak)"
    elif pilihan_sort == 'tersedikit':
        daftar_urut = sorted(daftar_barang, key=lambda x: x['total_stok'])
        judul = "Daftar Barang (Stok Tersedikit)"
    else:
        daftar_urut = daftar_barang # Fallback
        judul = "Daftar Barang (Tidak Diurutkan)"

    return render_template('gudang_sort.html', daftar_urut=daftar_urut, judul=judul)

# --- ROUTES: RIWAYAT TRANSAKSI ---

@app.route('/riwayat')
def riwayat_transaksi_web():
    """Menampilkan riwayat transaksi."""
    # Tampilkan yang terbaru di atas, batasi 50 transaksi
    riwayat_display = list(reversed(list(riwayat_transaksi)))[:50] 
    return render_template('riwayat_transaksi.html', riwayat=riwayat_display)

# --- Jalankan Aplikasi Flask ---
if __name__ == '__main__':
    load_data() # Muat data saat aplikasi dimulai
    app.run(debug=True) # debug=True akan memuat ulang server otomatis saat ada perubahan kode
# To-Do List  
## Langkah Setelah Fitur Webhook Midtrans Selesai  
**Aplikasi E-Commerce API**

---

## 1. Implementasi Fitur Cancel Order (Prioritas Utama)

Fokus utama: konsistensi **payment**, **stok**, dan **saldo user**

### 1.1 Cancel Order dari Sistem
- Validasi status order (hanya status tertentu yang boleh dibatalkan)
- Cegah double cancel (idempotency)

### 1.2 Request Cancel Order ke RajaOngkir
- Kirim request pembatalan order pengiriman
- Tangani kemungkinan:
  - Cancel berhasil
  - Cancel ditolak (sudah dikirim / diproses)
  - Timeout atau error API

### 1.3 Update Status Payment
- Ubah status payment menjadi `REFUNDED`
- Sinkronkan dengan response Midtrans
- Jangan menganggap refund selalu sukses

### 1.4 Kembalikan Stok Produk
- Tambahkan kembali jumlah stok ke inventory
- Gunakan transaksi database (`atomic`)
- Hindari race condition

### 1.5 Refund Saldo User via Midtrans
- Trigger refund ke Midtrans
- Simpan log refund:
  - success
  - failed
  - pending
- Implement retry jika gagal

---

## 2. Implementasi Tracking Status Order (RajaOngkir)

Fokus: sinkronisasi status pengiriman

### 2.1 Ambil Status Pengiriman
- Ambil status dari API RajaOngkir
- Mapping status eksternal ke status internal

### 2.2 Update Status Order Otomatis
- Jika status **sedang dikirim** → `DIKIRIM`
- Jika status **diterima** → `SELESAI`
- Simpan riwayat perubahan status (order status log)

---

## 3. Validasi & Hardening (Disarankan)

- Logging semua request ke Midtrans & RajaOngkir
- Handle timeout dan retry
- Testing edge case:
  - Cancel setelah payment sukses
  - Cancel saat paket sudah dikirim
  - Refund gagal tapi stok sudah kembali

---

## 4. Fitur Read Order & Manajemen History Order

Fokus: akses data oleh user tanpa merusak data inti sistem

### 4.1 Read Order Berdasarkan User
- Endpoint untuk menampilkan order milik user sendiri
- Pastikan user **tidak bisa membaca order user lain**
- Pastikan user **tidak bisa membaca order yang `is_archived = True`**
- Gunakan pagination

### 4.2 Filter Order
Tambahkan filter:
- Berdasarkan `order_status`
- Berdasarkan `payment_status`
- Berdasarkan tanggal (opsional)

### 4.3 Hapus History Order (Soft Delete)
- User **tidak benar-benar menghapus data**
- Update field:
  - `is_archived = True`
- Data tetap ada untuk:
  - Audit
  - Admin
  - Sengketa / refund

> Catatan:  
> Jangan gunakan hard delete untuk order — itu kesalahan desain.

---

## 5. Fitur Comment / Review Product

Fokus: validasi pembelian & kontrol spam

### 5.1 Validasi User Sudah Membeli Produk
- User hanya bisa komen jika:
  - Pernah membeli produk
  - Order berstatus `COMPLETED`
- Tolak request jika syarat tidak terpenuhi

### 5.2 CRUD Comment untuk User
User bisa:
- Create comment
- Read comment miliknya
- Update comment
- Delete comment (soft delete disarankan)

Field umum:
- product
- user
- rating (opsional)
- comment
- is_active / is_archived
- created_at

### 5.3 Manajemen Comment oleh Admin
Admin bisa:
- Melihat semua comment
- Mengarsipkan comment (`is_archived = True`)
- Tidak menghapus permanen kecuali diperlukan

---

## 6. Manajemen Data Menggunakan Django Admin

Fokus: efisiensi & kontrol backend

### 6.1 Gunakan Django Admin untuk Semua Model
- Order
- OrderItem
- Product
- User
- Comment
- Store
- CheckoutSession
- Cart

### 6.2 Optimasi Django Admin
Tambahkan:
- `list_display`
- `list_filter`
- `search_fields`
- `readonly_fields` untuk field sensitif
- `date_hierarchy` (jika relevan)

### 6.3 Keamanan Admin
- Batasi aksi delete
- Gunakan permission:
  - staff
  - admin
- Audit log untuk perubahan penting

---

## Catatan

- User **boleh mengarsipkan**, bukan menghapus
# Roadmap — Team Decul

Target: mengalahkan `spellF1` **0.2433** (baseline_smooth50, full match) dengan pipeline yang
deterministik dan bisa direproduksi. Deadline submit: **17 November 2026**.

Setiap milestone punya **prompt siap pakai** untuk Claude Code. Salin prompt-nya, ganti bagian
`<...>`, lalu kirim. Peta file dan aturan wajib ada di [CLAUDE.md](../CLAUDE.md), yang otomatis
dibaca AI di setiap sesi.

Status: ✅ selesai · 🔄 sedang dikerjakan · ⬜ belum · ⏸ menunggu data

---

## Aturan prompting

| ✅ boleh ditempel ke AI | ❌ jangan ditempel ke AI |
|---|---|
| Output `run_evaluation.py` dan `validate_submission.py` | Isi file di `data/` atau `~/mtah-data` |
| Pesan error **tanpa** isi data (nama fungsi, baris kode, jenis error) | `df.head()`, baris tracking, nilai per frame |
| Pertanyaan tentang kode, metrik, dokumentasi | Traceback yang memuat nilai dari data |
| Analisis ground truth **publik** dan `baseline_raw.csv` | Screenshot video atau plot dari data resmi |

Jika ragu apakah suatu angka termasuk "extract", jangan ditempel. Tanyakan ke panitia.

---

## M0 — Setup ✅

Repo private `zackyalgiffari/decul-mtah2027`, remote `upstream` ke repo panitia, venv uv
`~/venvs/mtah` (Python 3.11), `requirements-lock.txt`, scorer terverifikasi sama dengan README.

## M1 — Pahami masalah ✅

Ground truth publik (frame 11185–18684): 21 segmen = 17 possession + 4 dead ball.

- 12 dari 16 transisi adalah `H↔A` langsung, hanya 4 lewat `D`: inti masalahnya adalah mendeteksi
  pergantian tim saat bola hidup.
- Durasi possession 0.76 s sampai 42.4 s; 6 dari 17 di bawah 4 s. Satu window smoothing tidak
  bisa cocok untuk semuanya.
- Dead ball 5.5–20.4 s; 3 dari 4 diikuti tim yang berbeda.
- Babak dimulai langsung dengan possession, bukan `D`.

Ini contoh gaya pelabelan, **bukan** angka untuk tuning.

---

## Status 23 Okt: M3–M6 selesai, v4 dibekukan sebagai default, M7b (validasi publik) berjalan

**Run pertama di data resmi (23 Okt)**, window publik, 17 possession:

| tahap | macroF1 | spellF1 [5–95%] | poss (asli 17) | alive/dead F1 | team acc | recall D |
|---|---|---|---|---|---|---|
| v0 = smooth50 | 0.6207 | 0.3256 [0.214, 0.447] | 26 | 0.899 | 0.835 | 0.21 |
| v1 Viterbi | 0.6362 | 0.3304 [0.217, 0.444] | 29 | 0.893 | 0.789 | 0.34 |
| v2 jarak meter | 0.6518 | 0.3333 [0.200, 0.467] | 25 | 0.893 | 0.814 | 0.34 |
| v3 dead-ball | 0.6816 | 0.3707 [0.234, 0.498] | 24 | 0.913 | 0.853 | 0.32 |
| v4 Smart Tagging | **0.6821** | **0.4316** [0.284, 0.590] | 21 | **0.924** | 0.845 | 0.32 |

Seluruh pertandingan (dari `validate_submission`): jumlah possession 669 → 519 → 432 → 424 → 366,
rata-rata 7,6 → 10,5 s. `D` mengisi 39% frame yang dinilai di v4, wajar karena waktu bola
bergerak hanya sekitar 55–60 dari ~95 menit.

**Cara membaca:** semua indikator membaik tiap tahap, tapi interval bootstrap tumpang tindih, jadi
window publik belum membuktikan v4 > v0. Kelemahan terbesar: dead ball yang dikira hidup (v4:
996 dari 1.469 frame `D` publik ditebak H/A). Itu sasaran v5 dan v6.

v5 dan v6 sudah diuji dan dibuang (lihat M7). Langkah berikutnya, M7b, dikerjakan penuh oleh
Claude di data publik. Kamu baru perlu menjalankan `run_all.sh` lagi kalau validasi itu
mengubah sebuah prior.

---

## M2 — v1: Viterbi di atas sinyal baseline ✅

**Hasil (window publik, 23 Okt):** `decul_v1_public` macroF1 **0.6362**, spellF1 **0.3304**,
transF1 **0.3462**, dibandingkan `baseline_smooth50` 0.6207 / 0.3256 / 0.0816. Sinyalnya sama,
hanya decoder yang diganti. `spellF1` setara: dengan 17 possession, scorer menyatakan selisih di
bawah ~0.33 masih noise. macroF1 dan ketepatan waktu transisi lebih baik. Parameter
tidak di-tune ke window publik. Tes sintetis: `experiments/test_decode.py` (16/16).

**Tujuan:** mengganti majority vote dengan decoding Viterbi 3-state (H, A, D) yang memberi biaya
pada setiap pergantian state, dijalankan per babak.
**File:** `solution/decode.py`, tes kecil di `experiments/`.
**Input:** `evaluation/results/baseline_raw.csv` (publik).
**Selesai jika:** v1 di-skor di window publik dengan `--bootstrap 1000`, perilakunya pada urutan
buatan sesuai harapan (flicker pendek hilang, pergantian yang kuat tetap ada), dan kode
deterministik.

> **Prompt:**
> Kerjakan M2 di docs/ROADMAP.md. Buat `solution/decode.py` berisi Viterbi 3-state (H, A, D) yang
> dijalankan per babak memakai `games.half_video_blocks`. Inputnya label per frame dari
> `evaluation/results/baseline_raw.csv`. Tulis hasilnya sebagai `evaluation/results/decul_v1.csv`,
> skor di window publik dengan bootstrap, lalu jelaskan hasilnya dibandingkan baseline_smooth50.
> Jangan memilih biaya pergantian dengan mencari skor tertinggi di window publik.

## M3 — Data datang: reproduksi baseline ✅

`decul_v0` identik dengan `baseline_smooth50` di semua metrik, dan `decul_v1` (dari ATD resmi)
identik dengan `decul_v1_public` (dari `baseline_raw.csv` publik). Data, alignment, dan
environment terbukti benar.

**Tujuan:** memastikan data, alignment, dan environment benar di mesinmu.
**Kamu jalankan sendiri** (di terminal, bukan lewat AI):
```bash
source ~/venvs/mtah/bin/activate
python make_submission.py
python evaluation/validate_submission.py evaluation/results/Decul.csv
python evaluation/run_evaluation.py
```
**Selesai jika:** baris `Decul` di scoreboard sama persis dengan `baseline_smooth50`
(macroF1 0.6207, spellF1 0.3256 di window publik).

> **Prompt:**
> Kerjakan M3 di docs/ROADMAP.md. Saya sudah menjalankan tiga perintahnya. Ini output
> run_evaluation.py dan validate_submission.py: <tempel output>. Apakah Decul sudah identik dengan
> baseline_smooth50? Kalau belum, apa yang harus saya cek?

## M4 — Fitur dan bukti per frame dari ATD ✅ (`--stage v2`, hasil di tabel Status)

Parser dan fitur sudah dites di sampel publik Metrica (`experiments/check_metrica_sample.py`):
144 ribu frame diparse dalam 2,9 s, termasuk format tanpa kolom kecepatan.

**Tujuan:** mengganti label pemain terdekat yang keras dengan bukti bertingkat: jarak pemain H dan
A terdekat ke bola, bola terlihat atau tidak, kecepatan bola, interpolasi bola untuk celah pendek.
**File:** `solution/features.py`, `solution/evidence.py`; percobaan di `experiments/` memakai data
sampel publik Metrica (github.com/metrica-sports/sample-data).
**Selesai jika:** `make_submission.py` memakai bukti ini + Viterbi M2, dan kamu melaporkan skornya.

> **Prompt:**
> Kerjakan M4 di docs/ROADMAP.md. Tulis `solution/features.py` dan `solution/evidence.py` yang
> membaca ATD lewat `games.asset_paths()` dengan cara parsing yang sama seperti
> `starter/baseline.py`, lalu sambungkan ke Viterbi dari M2 di `make_submission.py`. Uji dulu di
> data sampel publik Metrica di `experiments/`. Saya yang akan menjalankannya di data resmi.

## M5 — Detektor dead-ball ✅ (`--stage v3`; lanjutan di v6)

**Tujuan:** membuat state `D` berarti "permainan berhenti", bukan sekadar "bola hilang dari
tracking". Bukti: bola di luar batas lapangan, semua pemain melambat, bola diam.
**File:** `solution/evidence.py` (bukti untuk D).
**Selesai jika:** `alive/dead F1` di output scorer naik dibanding M4, dengan interval bootstrap
yang tidak tumpang tindih.

> **Prompt:**
> Kerjakan M5 di docs/ROADMAP.md. Tambahkan bukti dead-ball ke `solution/evidence.py`. Ini output
> scorer versi M4 saya: <tempel output>. Fokus pada alive/dead F1.

## M6 — Prior dari Smart Tagging ✅ (`--stage v4`, default saat ini)

**Tujuan:** memakai tag tim dan set piece sebagai bukti tambahan, terutama saat bola lama hilang.
Ingat: tag `N/A` (semua throw-in) dan interval fase ≠ possession.
**File:** `solution/tagging.py` memakai `starter/load_smart_tagging.load`.
**Selesai jika:** kontribusinya diukur terpisah (dengan vs tanpa) dan dicatat di `docs/Decul.md`.

> **Prompt:**
> Kerjakan M6 di docs/ROADMAP.md. Buat `solution/tagging.py` yang mengubah Smart Tagging menjadi
> bukti per frame, tangani `Team = N/A` secara eksplisit, dan buat flag di `make_submission.py`
> supaya saya bisa membandingkan dengan dan tanpa Smart Tagging.

## M7 — Uji robustness dan bekukan parameter 🔄

**M7a, v5 dan v6: dicoba lalu dibuang (run kedua, 23 Okt):**

| | v4 | v5 (bola cepat ≠ kontrol) | v6 (+ isyarat restart) |
|---|---|---|---|
| spellF1 [5–95%] | **0.4316** [0.284, 0.590] | 0.4000 [0.244, 0.556] | 0.4000 (identik v5) |
| macroF1 | **0.6821** | 0.6754 | 0.6754 |
| transisi tepat (±1 s) | **7 / 20** | 4 / 20 | 4 / 20 |
| possession publik / seluruh match | 21 / 366 | 19 / 316 | 19 / 317 |

- `v5` mengurangi possession palsu, tapi batasnya meleset: intersep terjadi tepat saat umpan
  cepat dipotong, sehingga bukti pergantian tim hilang di momen yang paling penting.
- `v6` hampir tidak berpengaruh (~390 frame berubah di seluruh pertandingan). Stoppage di data
  ini jarang berupa "bola diam di garis".
- **Keputusan: v4 tetap default.** Keduanya dipertahankan di kode sebagai ablation untuk dokumen
  teknis.

**M7b, validasi di pertandingan publik Metrica ✅:** label H/A/D diturunkan dari event data
Sample Game 1 dan 2 (328 dan 330 possession). Kode di `validation/metrica_public.py`.

| tahap | Game 1 spellF1 [5–95%] | Game 2 spellF1 [5–95%] |
|---|---|---|
| v0 baseline | 0.399 [0.367, 0.433] | 0.397 [0.366, 0.429] |
| v1 Viterbi | 0.472 [0.437, 0.510] | 0.476 [0.441, 0.514] |
| v2 jarak | 0.527 [0.489, 0.567] | 0.534 [0.494, 0.575] |
| v3 dead-ball | 0.511 [0.473, 0.550] | 0.533 [0.492, 0.573] |
| v5 bola cepat | 0.520 [0.468, 0.571] | 0.542 [0.492, 0.591] |

- **Hasil pertama yang signifikan:** v2 mengalahkan baseline di kedua pertandingan, dengan
  interval yang tidak tumpang tindih (+0,13 spellF1).
- v3 setara di spellF1, tapi menaikkan recall `D` dan alive/dead F1, jadi tetap dipakai. v5
  memprediksi terlalu sedikit possession, jadi tetap dibuang.
- **Prior stabil:** durasi possession 6, 12, atau 24 s hasilnya sama. TEMPER 0.6 jelas lebih
  buruk, dan 0.15 memotong jumlah possession separuh. Nilai yang dipakai (12 s, 0.3) tidak
  diubah, jadi tidak perlu run ulang di data resmi.
- **Batas:** label dari event ≠ definisi kompetisi, dan tracking sampel lebih bersih. v4 (Smart
  Tagging) tidak bisa diuji di sini.

**Keputusan M7: v4 dibekukan.** Berikutnya M8 (paket dan submit).

**Tujuan:** memastikan perbaikan itu nyata, bukan kebetulan dari 17 possession.
**Cek:** `--bootstrap 1000`; jumlah dan durasi possession masuk akal untuk dua babak; kedua babak
berperilaku mirip; pilih versi yang lebih sederhana kalau dua versi tidak bisa dibedakan.
**Selesai jika:** semua parameter tertulis di blok `# Params` dengan alasan sepak bolanya.

> **Prompt:**
> Kerjakan M7 di docs/ROADMAP.md. Ini output scorer dengan bootstrap untuk versi-versi yang saya
> punya: <tempel output>. Versi mana yang sebaiknya dibekukan, dan apa alasannya?

## M8 — Paket dan submit 🔄

**Checklist:**
- [x] `docs/Decul.md` lengkap: ringkasan, pendekatan, hasil, validasi, aset, aturan possession,
      keterbatasan, reproduksi, penggunaan AI
- [x] Audit `git ls-files` terhadap peta file di `CLAUDE.md`: tidak ada file coba-coba di luar
      `experiments/` (23 Okt)
- [x] Riwayat git tidak memuat data: semua path yang pernah di-commit adalah file panitia atau
      file Decul; blob terbesar adalah CSV publik panitia (23 Okt)
- [ ] **Kamu:** `bash experiments/final_checks.sh` mengecek sekaligus:
  - [ ] determinisme (run kedua, tanpa cache, harus identik)
  - [ ] clone bersih + environment baru dari lockfile menghasilkan CSV yang sama
  - [ ] `validate_submission.py` pada file persis yang akan diupload
  - [ ] menyiapkan `~/decul-upload/Decul.csv` dan `~/decul-upload/Decul.md`
- [ ] **Kamu:** minimal 3 anggota berprofil teknis sudah terdaftar dengan nama tim `Decul`
      (pendaftaran tutup 10 Nov)
- [ ] **Kamu, setelah semua cek OK:** repo jadi public:
      `gh repo edit zackyalgiffari/decul-mtah2027 --visibility public --accept-visibility-change-consequences`
- [ ] **Kamu:** Google Form: nama tim `Decul`, upload kedua file dari `~/decul-upload/`, URL repo
- [ ] Target submit **16 November** (sehari cadangan). Form bisa diedit sampai deadline, dan
      hanya respons terakhir yang dinilai.

> **Prompt:**
> Ini output `bash experiments/final_checks.sh`: <tempel output>. Apakah semua cek lolos dan
> repo siap dibuat public?

## M9 — Setelah kompetisi selesai ⬜

Wajib menurut syarat dan ketentuan yang disetujui saat pendaftaran, juga kalau tim berhenti
setelah tahap ini.
- [ ] Hapus `data/` (termasuk `data/cache/`) dan `~/mtah-data` kalau dipakai
- [ ] Hapus output turunan data di `experiments/` dan `evaluation/results/[Dd]ecul*.csv`
- [ ] Hapus salinan di tempat lain (cloud, laptop anggota tim)
- [ ] Yang boleh disimpan: kode, dokumentasi, dan deliverable yang tidak memuat data

---

## Jadwal

| minggu | tanggal | milestone |
|---|---|---|
| 1 | 23–29 Okt | M2, mulai M3 begitu data ada |
| 2 | 30 Okt – 5 Nov | M3, M4 |
| 3 | 6–12 Nov | M5, M6, M7 |
| 4 | 13–17 Nov | M8, submit 16 Nov |

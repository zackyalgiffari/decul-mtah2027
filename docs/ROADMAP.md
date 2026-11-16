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
tidak di-tune ke window publik. Tes sintetis: `experiments/test_decode.py` (16/16), sekarang `tests/test_pipeline.py`.

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

## M7 — Uji robustness dan bekukan parameter ✅

> **Catatan 6 Nov, setelah klarifikasi aturan panitia** (upstream `f8f2629` dan email ke semua
> peserta): window publik hanya untuk cek kebenaran pipeline, tidak untuk memilih antar versi.
> Log di bawah ini dibiarkan apa adanya sebagai catatan jujur dari proses 23 Okt. Angka window
> publik di dalamnya adalah diagnostik pada saat itu, **bukan** dasar keputusan yang berlaku.
> Dasar yang berlaku ada di `docs/Decul.md`, bagian "How the submitted stage was chosen": v4
> sudah jadi default sebelum ada skor apa pun (`75b971e`), dan v5–v8 tidak diadopsi berdasarkan
> data eksternal Metrica atau tanpa memakai ground truth. Eksperimen baru mengikuti aturan
> `CLAUDE.md`: diadopsi hanya kalau terbukti lebih baik di data eksternal.

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

**M7c, v7: dead-ball dipelajari dari pertandingan sendiri (EM), dicoba lalu dibuang (run
keempat, 23 Okt):**

| | v4 | v7 |
|---|---|---|
| spellF1 publik [5–95%] | **0.4316** [0.284, 0.590] | 0.3800 [0.240, 0.520] |
| recall D / presisi D | 0.322 / **1.00** | 0.323 / 0.75 |
| alive/dead F1 | **0.924** | 0.911 |
| possession publik / seluruh match | **21** / 366 | 23 / 402 |

Di Metrica v7 setara v3, tapi di data kompetisi recall `D` tidak bergerak sama sekali. Artinya
dead ball yang terlewat **tidak bisa dibedakan dari permainan hidup dengan fitur tracking mana
pun yang kita punya**. Ini batas informasi, bukan masalah penyetelan. Langkah berikutnya butuh
sumber informasi baru: **v8**, waktu restart dari Smart Tagging.

**M7d, v8: waktu restart dari Smart Tagging, dicoba lalu dibuang (run kelima, 23 Okt):**

| syarat | v4 | v8 | |
|---|---|---|---|
| recall D > 0.45 | 0.322 | 0.459 | ✅ tipis |
| presisi D ≥ 0.9 | 1.00 | 0.66 | ❌ |
| possession publik ≤ 21 | 21 | 20 | ✅ |
| alive/dead F1 naik | 0.924 | 0.909 | ❌ |
| spellF1 turun ≤ 0.04 | 0.4316 | 0.3784 | ❌ |
| porsi D seluruh match 35–45% | 39% | 45.4% | ❌ |

v8 menangkap 201 frame D tambahan, tapi 347 frame permainan hidup ikut berubah menjadi D. Waktu
tag Smart Tagging terlalu kasar untuk menandai batas dead ball per frame. Menyetel ulang
jendelanya berarti tuning ke 4 stoppage publik, jadi tidak dilakukan.

**M7e, parameter v2/v3 yang belum divalidasi, diuji di Metrica lalu tidak diadopsi (16 Nov):**
`TURNOVER_SHARE` dan `DEAD_S` tidak berpengaruh, `SCALE_M` lebih buruk. `CONTROL_M` yang lebih
kecil terlihat lebih baik, tapi nilai terbaiknya tidak konsisten: 2 m di Game 1 (+0,059, bootstrap
berpasangan [+0,038, +0,080]), 1–1,5 m di Game 2 (+0,03). Kalau nilai dipilih di satu pertandingan,
keuntungannya tidak signifikan di pertandingan lain. Selain itu tracking Metrica lebih bersih, dan
interaksinya dengan Smart Tagging tidak bisa diuji. Jadi tidak terbukti lebih baik, dan 3 m tetap
dipakai. Script scratch: `experiments/sweep_metrica.py`, `experiments/paired_control_m.py`.

**Kesimpulan v5–v8:** dengan aset yang dipakai (tracking + Smart Tagging), v4 sudah dekat batas
yang bisa dicapai tanpa video. **v4 final**, kecuali kamu memulai eksperimen baru. Sebelum
submit, jalankan `final_checks.sh` di branch `main`.

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
- [x] **Kamu:** `bash experiments/final_checks.sh` (sekarang `scripts/final_checks.sh`), **ALL CHECKS PASSED** (23 Okt, `main` =
      `f5b3413`, `Decul.csv` sha256 `c499eee84cf9ec00`):
  - [x] determinisme: run kedua tanpa cache byte-identik
  - [x] clone bersih + environment baru dari lockfile menghasilkan CSV yang sama
  - [x] `validate_submission.py` OK pada file persis yang akan diupload (366 possession, 10,5 s)
  - [x] `~/decul-upload/Decul.csv` dan `~/decul-upload/Decul.md` siap
- [x] **Kamu:** minimal 3 anggota berprofil teknis sudah terdaftar dengan nama tim `Decul`
      (dikonfirmasi 23 Okt)
- [x] Struktur repo dirapikan untuk submission (23 Okt): `README.md` menjadi halaman depan
      Decul, README panitia dipindah utuh ke `STARTER_KIT.md`, dan script yang dikutip dokumen
      teknis dipindah dari `experiments/` (gitignored) ke `scripts/`, `tests/`, dan `validation/`,
      supaya juri bisa menjalankannya. `docs/Decul.md` dilengkapi bagian wajib "Handling missing
      and noisy tracking", tabel cara mereproduksi, dan peta repository.
- [x] Klarifikasi aturan panitia (upstream `f8f2629` + email ke semua peserta): window publik
      tidak boleh dipakai untuk memilih versi, tuning hanya di data eksternal, dan dokumen teknis
      wajib mendaftar data berlabel. Upstream di-merge, `docs/Decul.md` disesuaikan (bagian "How
      the submitted stage was chosen" dan "Labelled data"), 6 Nov
- [x] **Kamu:** `final_checks.sh` diulang di `main` = `b3226f8`, **ALL CHECKS PASSED** (16 Nov).
      `Decul.csv` sha256 `c499eee84cf9ec00`, sama dengan 23 Okt: v5–v8 tidak mengubah v4.
      `Decul.md` yang diupload: `711db8a48e274658`
- [x] Audit riwayat git sebelum public (16 Nov): path yang cocok hanya `.claude/settings.json`,
      `data/README.md` (pengecualian panitia) dan metadata ground truth publik
- [x] Repo jadi public (16 Nov). `gh` 2.46 tidak punya `--accept-visibility-change-consequences`;
      cukup `gh repo edit zackyalgiffari/decul-mtah2027 --visibility public`
- [ ] **Kamu:** Google Form: nama tim `Decul`, upload kedua file dari `~/decul-upload/`, URL repo
- [ ] Target submit **16 November** (sehari cadangan). Form bisa diedit sampai deadline, dan
      hanya respons terakhir yang dinilai.

**Saat siap submit (rencana: 14–16 Nov, repo tetap private sampai saat itu):**
1. Jalankan sekali lagi `bash scripts/final_checks.sh`. `main` bergeser setiap ada commit
   baru, termasuk yang hanya mengubah dokumen, jadi cek ini membuktikan commit terakhir yang akan
   di-clone juri. Harus muncul `ALL CHECKS PASSED`.
2. Minta Claude membuat repo public (prompt di bawah).
3. Isi Google Form: nama tim `Decul`, upload `~/decul-upload/Decul.csv` dan
   `~/decul-upload/Decul.md`, URL `https://github.com/zackyalgiffari/decul-mtah2027`.

> **Prompt:**
> Ini output `bash scripts/final_checks.sh` yang terbaru: <tempel output>. Kalau semua lolos,
> buat repo decul-mtah2027 jadi public sekarang.

## Pindah ke perangkat lain

Repo ini public, jadi cukup di-clone. Data, environment, dan catatan lokal tidak ikut dan harus
disiapkan sendiri di perangkat itu.

**1. Clone dan buat environment** (butuh `git` dan `uv`; Python 3.11, versi library dikunci di
lockfile). Venv harus di `~/venvs/mtah`, karena di situ `scripts/final_checks.sh` mencarinya
(`PY`, baris 17):
```bash
git clone https://github.com/zackyalgiffari/decul-mtah2027.git
cd decul-mtah2027
git config user.email "89745820+zackyalgiffari@users.noreply.github.com"   # supaya push tidak ditolak (GH007)
uv venv --python 3.11 ~/venvs/mtah
uv pip sync --python ~/venvs/mtah/bin/python requirements-lock.txt
source ~/venvs/mtah/bin/activate
```
Kalau venv ada di tempat lain, jalankan dengan `PY=/path/ke/python bash scripts/final_checks.sh`.

**2. Taruh data di `./data/` di dalam repo** (ikuti `data/README.md`). Data guard Claude hanya
melindungi tiga lokasi (`.claude/hooks/guard_data.py`, `PROTECTED_ROOTS`):
- `./data/` di dalam repo, pilihan teraman karena selalu terlindungi
- `~/mtah-data`
- lokasi `MTAH_DATA_DIR`, **hanya kalau variabel itu sudah di-export sebelum `claude` dijalankan**.
  Data di tempat lain, misalnya `~/Downloads`, **tidak** terlindungi.

Jangan taruh data di folder yang tersinkron ke cloud (OneDrive, Google Drive, Dropbox).

**3. Cek bahwa data guard aktif sebelum memakai Claude Code.** Hook butuh `python3` di PATH dan
Claude Code ≥ 2.1.295 (`claude --version`). Di versi lama, `onFailure: "block"` diabaikan, sehingga
hook yang crash meloloskan perintah. Kalau `python3` tidak ada, hook sengaja memblokir semua tool
(fail-closed), jadi gejalanya semua perintah Claude ditolak. Di Linux/WSL2, pasang dulu
`bubblewrap` dan `socat` agar sandbox bisa jalan; di macOS tidak perlu. Tes:
```bash
python3 .claude/hooks/test_guard_data.py      # harus: 85 of 85 cases correct (atau lebih)
```
Lalu di Claude Code jalankan `/sandbox`: sandbox harus aktif, dengan `./data` dan `~/mtah-data` di
denyRead.

**4. Reproduksi dan cocokkan hash** (kamu yang menjalankan, karena membaca data):
```bash
python make_submission.py
python evaluation/validate_submission.py evaluation/results/Decul.csv
sha256sum evaluation/results/Decul.csv        # harus diawali c499eee84cf9ec00
```
Validator harus melaporkan 366 possession, rata-rata 10,5 s. Run pertama lebih lama karena tracking
diparse lalu disimpan di `data/cache/`. `bash scripts/final_checks.sh` menjalankan semuanya
sekaligus: dua run, clone bersih dari `main` dengan environment baru (butuh internet untuk `uv`),
validasi, lalu menyalin `Decul.csv` dan `Decul.md` ke `~/decul-upload/` kalau semua cek lolos.
Di Windows tanpa WSL, pakai Git Bash.

Hasil byte-identik sudah dibuktikan di **dua mesin**:
- mesin pertama: clone bersih + environment baru
- 16 Nov, mesin kedua: macOS arm64, Python 3.11.15, venv baru dari `requirements-lock.txt`.
  `make_submission.py` menghasilkan SHA-256 `c499eee84cf9ec00…85c85a2`, dan validator melaporkan
  366 possession, rata-rata 10,5 s.

Kalau hash di perangkat lain berbeda, tempel ke Claude hash-nya dan output `validate_submission.py`
saja.

**5. Yang tidak ikut ter-clone:**
- `CLAUDE.local.md` (ringkasan T&C, rahasia menurut §18). Salin manual, jangan lewat git.
- Memori Claude Code (`~/.claude/projects/...`) dan `~/decul-upload/`. Keduanya ada per perangkat.

**6. Setelah kompetisi:** salinan data di perangkat ini juga wajib dihapus (M9).

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

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

## M2 — v1: Viterbi di atas sinyal baseline ⬜ (tidak perlu data)

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

## M3 — Data datang: reproduksi baseline ⏸

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

## M4 — Fitur dan bukti per frame dari ATD ⬜

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

## M5 — Detektor dead-ball ⬜

**Tujuan:** membuat state `D` berarti "permainan berhenti", bukan sekadar "bola hilang dari
tracking". Bukti: bola di luar batas lapangan, semua pemain melambat, bola diam.
**File:** `solution/evidence.py` (bukti untuk D).
**Selesai jika:** `alive/dead F1` di output scorer naik dibanding M4, dengan interval bootstrap
yang tidak tumpang tindih.

> **Prompt:**
> Kerjakan M5 di docs/ROADMAP.md. Tambahkan bukti dead-ball ke `solution/evidence.py`. Ini output
> scorer versi M4 saya: <tempel output>. Fokus pada alive/dead F1.

## M6 — Prior dari Smart Tagging ⬜

**Tujuan:** memakai tag tim dan set piece sebagai bukti tambahan, terutama saat bola lama hilang.
Ingat: tag `N/A` (semua throw-in) dan interval fase ≠ possession.
**File:** `solution/tagging.py` memakai `starter/load_smart_tagging.load`.
**Selesai jika:** kontribusinya diukur terpisah (dengan vs tanpa) dan dicatat di `docs/Decul.md`.

> **Prompt:**
> Kerjakan M6 di docs/ROADMAP.md. Buat `solution/tagging.py` yang mengubah Smart Tagging menjadi
> bukti per frame, tangani `Team = N/A` secara eksplisit, dan buat flag di `make_submission.py`
> supaya saya bisa membandingkan dengan dan tanpa Smart Tagging.

## M7 — Uji robustness dan bekukan parameter ⬜

**Tujuan:** memastikan perbaikan itu nyata, bukan kebetulan dari 17 possession.
**Cek:** `--bootstrap 1000`; jumlah dan durasi possession masuk akal untuk dua babak; kedua babak
berperilaku mirip; pilih versi yang lebih sederhana kalau dua versi tidak bisa dibedakan.
**Selesai jika:** semua parameter tertulis di blok `# Params` dengan alasan sepak bolanya.

> **Prompt:**
> Kerjakan M7 di docs/ROADMAP.md. Ini output scorer dengan bootstrap untuk versi-versi yang saya
> punya: <tempel output>. Versi mana yang sebaiknya dibekukan, dan apa alasannya?

## M8 — Paket dan submit ⬜

**Checklist:**
- [ ] Determinisme: jalankan `make_submission.py` dua kali, `cmp` kedua CSV harus identik
- [ ] `docs/Decul.md` lengkap: pendekatan, aset dipakai/dibuang, aturan possession, keterbatasan, reproduksi
- [ ] Audit `git ls-files` terhadap peta file di `CLAUDE.md`: tidak ada file coba-coba di luar `experiments/`
- [ ] Riwayat git tidak memuat data: `git log --all --stat` hanya berisi file dari peta
- [ ] Clone bersih + data + satu perintah menghasilkan CSV yang sama
- [ ] `validate_submission.py` pada **file persis** yang akan diupload
- [ ] Repo jadi public: `gh repo edit zackyalgiffari/decul-mtah2027 --visibility public --accept-visibility-change-consequences`
- [ ] Google Form: nama tim `Decul`, upload `Decul.csv` dan `Decul.md`, URL repo
- [ ] Target submit **16 November** (sehari cadangan)

> **Prompt:**
> Kerjakan M8 di docs/ROADMAP.md. Audit repo sebelum dibuat public: bandingkan `git ls-files` dan
> riwayat git dengan peta file di CLAUDE.md, lengkapi docs/Decul.md dari catatan di roadmap, dan
> beri saya perintah untuk tes determinisme yang akan saya jalankan sendiri.

---

## Jadwal

| minggu | tanggal | milestone |
|---|---|---|
| 1 | 23–29 Okt | M2, mulai M3 begitu data ada |
| 2 | 30 Okt – 5 Nov | M3, M4 |
| 3 | 6–12 Nov | M5, M6, M7 |
| 4 | 13–17 Nov | M8, submit 16 Nov |

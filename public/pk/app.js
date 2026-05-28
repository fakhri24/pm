import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.1/firebase-app.js";
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  collection,
  getDocs,
  writeBatch,
} from "https://www.gstatic.com/firebasejs/9.22.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyCy4tM3HAvRheJQDA8c4__YFg1_l66whag",
  authDomain: "try-out-snbt-kelas-x-dan-xi.firebaseapp.com",
  projectId: "try-out-snbt-kelas-x-dan-xi",
  storageBucket: "try-out-snbt-kelas-x-dan-xi.firebasestorage.app",
  messagingSenderId: "579790161373",
  appId: "1:579790161373:web:64292fb85397eee52c6234",
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// --- DATA SOAL KOSONG ---
let dataSoal = [];
let timerInterval;
// let currentSoalIndex_pk = 0; // Tambahan untuk melacak posisi soal saat ini
// let listRagu_pk = {}; // Menyimpan status ragu: { index: true/false }

// --- STATE UJIAN (Disinkronkan dengan Local Storage) ---
let nisSiswa_pk = localStorage.getItem("nisSiswa_pk") || "";
let jawabanSiswa_pk = JSON.parse(localStorage.getItem("jawabanSiswa_pk")) || {};
// listRagu_pk sudah kita deklarasikan sebelumnya, kita update menjadi:
let listRagu_pk = JSON.parse(localStorage.getItem("listRagu_pk")) || {};
let currentSoalIndex_pk =
  parseInt(localStorage.getItem("currentSoalIndex_pk")) || 0;
let sisaWaktu_pk = parseInt(localStorage.getItem("sisaWaktu_pk")) || 1200; // 20 menit

// Menangkap elemen tombol
const btnMasuk = document.getElementById("tombolMasuk");

btnMasuk.addEventListener("click", async function () {
  btnMasuk.textContent = "Memeriksa...";
  btnMasuk.disabled = true;

  const nisInput = document.getElementById("nis").value;
  const tglLahirInput = document.getElementById("password").value;

  if (!nisInput || !tglLahirInput) {
    alert("Isi NIS dan Password dulu!");
    resetTombol();
    return;
  }

  try {
    const userRef = doc(db, "users", nisInput);
    const userSnap = await getDoc(userRef);

    if (userSnap.exists()) {
      const userData = userSnap.data();

      if (userData.tanggal_lahir === tglLahirInput) {
        if (userData.role === "admin") {
          document.getElementById("loginPage").classList.remove("active");
          document.getElementById("adminPage").classList.add("active");
          if (typeof muatDataAdmin === "function") muatDataAdmin();
        } else {
          // JIKA SISWA: Cek dulu sudah ujian atau belum
          const cekHasilRef = doc(db, "hasil_ujian_pk", nisInput);
          const cekHasilSnap = await getDoc(cekHasilRef);

          if (cekHasilSnap.exists()) {
            alert(
              "Akses Ditolak! Kamu sudah menyelesaikan ujian ini sebelumnya.",
            );

            // Tambahan: Bersihkan input agar siswa selanjutnya tidak bingung
            document.getElementById("nis").value = "";
            document.getElementById("password").value = "";

            resetTombol();
            // Layar login tetap ada karena 'active'-nya belum kita remove
            return;
          }
          // --------------------------------------------------

          document.addEventListener("DOMContentLoaded", () => {
            // Jika ditemukan sesi siswa yang belum dikumpulkan
            if (nisSiswa_pk && localStorage.getItem("sisaWaktu_pk")) {
              document.getElementById("loginPage").classList.remove("active");
              document.getElementById("examPage").classList.add("active");

              // Tanamkan NIS ke form secara gaib (karena submitUjian butuh value dari sini)
              document.getElementById("nis").value = nisSiswa_pk;

              if (typeof muatSoal === "function") muatSoal();
              if (typeof mulaiTimer === "function") mulaiTimer(); // Tidak perlu parameter lagi
            }
          });

          // JIKA LOLOS SEMUA CEK: Baru pindah halaman
          nisSiswa_pk = nisInput;
          localStorage.setItem("nisSiswa_pk", nisSiswa_pk);

          // Inisialisasi awal memori jika kosong
          if (!localStorage.getItem("jawabanSiswa_pk"))
            localStorage.setItem("jawabanSiswa_pk", JSON.stringify({}));
          if (!localStorage.getItem("listRagu_pk"))
            localStorage.setItem("listRagu_pk", JSON.stringify({}));
          if (!localStorage.getItem("sisaWaktu_pk"))
            localStorage.setItem("sisaWaktu_pk", 1200);
          if (!localStorage.getItem("currentSoalIndex_pk"))
            localStorage.setItem("currentSoalIndex_pk", 0);

          document.getElementById("loginPage").classList.remove("active");
          document.getElementById("examPage").classList.add("active");
          if (typeof muatSoal === "function") muatSoal();
          if (typeof mulaiTimer === "function") mulaiTimer(); // Hilangkan angka 1800 di sini
        }
      } else {
        alert("Password tidak sesuai!");
        resetTombol();
      }
    } else {
      alert("NIS tidak terdaftar dalam sistem!");
      resetTombol();
    }
  } catch (error) {
    console.error("Error Firebase:", error);
    alert("Gagal terhubung! Lihat Inspect > Console untuk detail error.");
    resetTombol();
  }
});

function resetTombol() {
  btnMasuk.textContent = "Masuk";
  btnMasuk.disabled = false;
}

window.muatSoal = async function () {
  const container = document.getElementById("soalContainer");
  container.innerHTML = "<p>Mempersiapkan soal ujian...</p>";

  try {
    const response = await fetch("data-soal.json");

    if (!response.ok) throw new Error("Gagal mengambil data soal");
    dataSoal = await response.json();

    // 1. Panggil fungsi untuk membuat kotak-kotak nomor navigasi di kiri
    renderNavigasi();

    let htmlSoal = "";

    dataSoal.forEach((soal, index) => {
      // GANTI MENJADI INI:
      const displayStatus = index === currentSoalIndex_pk ? "block" : "none";
      htmlSoal += `<div class="item-soal" id="soal_${index}" style="display: ${displayStatus}; border-bottom: none;">`;
      htmlSoal += `<div class="teks-soal"><strong>${index + 1}.</strong> ${soal.pertanyaan}</div>`;
      // --- MODIFIKASI: PENGECEKAN DAN RENDER GAMBAR SVG ---
      if (soal.gambar) {
        // Kita bungkus dengan div tambahan untuk memberi jarak (margin) dengan opsi jawaban
        htmlSoal += `<div class="gambar-soal" style="margin-bottom: 20px; text-align: center;">
                       ${soal.gambar}
                     </div>`;
      }
      // ----------------------------------------------------
      htmlSoal += `<div class="opsi-container">`;

      // --- DI DALAM muatSoal(), GANTI BAGIAN LOOPING OPSI MENJADI INI: ---
      soal.opsi.forEach((opsi) => {
        const huruf = opsi.charAt(0);
        // Cek apakah di memori opsi ini sebelumnya dipilih
        const isChecked = jawabanSiswa_pk[soal.id] === huruf ? "checked" : "";

        htmlSoal += `
          <label class="opsi-label">
            <input type="radio" name="jawaban_${soal.id}" value="${huruf}" ${isChecked}>
            <span class="teks-opsi">${opsi}</span>
          </label>`;
      });
      htmlSoal += `</div></div>`;
    });

    container.innerHTML = htmlSoal;

    // Pasang "pendengar" ke setiap opsi jawaban
    const radioButtons = container.querySelectorAll('input[type="radio"]');
    radioButtons.forEach((radio) => {
      radio.addEventListener("change", (e) => {
        // 1. Matikan status ragu secara otomatis & simpan
        listRagu_pk[currentSoalIndex_pk] = false;
        localStorage.setItem("listRagu_pk", JSON.stringify(listRagu_pk));

        // 2. Simpan jawaban ke State & Local Storage
        const idSoal = e.target.name.replace("jawaban_", "");
        jawabanSiswa_pk[idSoal] = e.target.value;
        localStorage.setItem(
          "jawabanSiswa_pk",
          JSON.stringify(jawabanSiswa_pk),
        );

        updateTombolNavigasi();
        cekSemuaTerjawab(e);
      });
    });

    // ==========================================
    // TAMBAHKAN BARIS INI:
    // Paksa sistem untuk mengecek dan mewarnai grid
    // sesuai memori yang baru saja dimuat
    cekSemuaTerjawab();
    // ==========================================

    updateTombolNavigasi();

    // Pastikan tombol selesai mati di awal
    document.getElementById("tombolSelesai").disabled = true;
    document.getElementById("tombolSelesai").style.backgroundColor =
      "var(--btn-disabled)";
    document.getElementById("tombolSelesai").textContent =
      `Belum Selesai (0/${dataSoal.length})`;

    if (window.MathJax) {
      MathJax.typesetPromise([container]).catch((err) =>
        console.log("MathJax error:", err),
      );
    }
  } catch (error) {
    console.error("Error muat soal:", error);
    container.innerHTML = "<p>Gagal memuat soal. Silakan refresh halaman.</p>";
  }
};

// Hapus parameter durasiDetik di dalam kurung
function mulaiTimer() {
  const display = document.getElementById("timer");

  // Pastikan kita menggunakan sisaWaktu_pk dari variabel global
  timerInterval = setInterval(function () {
    let menit = parseInt(sisaWaktu_pk / 60, 10);
    let detik = parseInt(sisaWaktu_pk % 60, 10);

    menit = menit < 10 ? "0" + menit : menit;
    detik = detik < 10 ? "0" + detik : detik;

    display.textContent = "Sisa Waktu: " + menit + ":" + detik;

    sisaWaktu_pk--; // Kurangi waktu
    localStorage.setItem("sisaWaktu_pk", sisaWaktu_pk); // Update ke memori

    if (sisaWaktu_pk < 0) {
      clearInterval(timerInterval);
      alert("Waktu habis! Jawaban akan dikumpulkan otomatis.");
      window.submitUjian();
    }
  }, 1000);
}

window.submitUjian = async function () {
  clearInterval(timerInterval);
  const btnSelesai = document.getElementById("tombolSelesai");
  btnSelesai.textContent = "Mengirim Jawaban...";
  btnSelesai.disabled = true;

  let benar = 0;
  let salah = 0;
  let kosong = 0;

  dataSoal.forEach((soal) => {
    const jawabanDipilih = document.querySelector(
      `input[name="jawaban_${soal.id}"]:checked`,
    );

    if (jawabanDipilih) {
      if (jawabanDipilih.value === soal.kunci) {
        benar++;
      } else {
        salah++;
      }
    } else {
      kosong++;
    }
  });

  const nisSiswa_pk = document.getElementById("nis").value;

  // Hitung Skor TO: (Jumlah Benar / Total Soal) * 1000
  // Menggunakan Math.round agar tidak ada angka desimal yang terlalu panjang
  const skorTO = Math.round((benar / dataSoal.length) * 1000);

  const paketHasil = {
    nis: nisSiswa_pk,
    benar: benar,
    salah: salah,
    kosong: kosong,
    skor: skorTO, // Sekalian kita simpan skornya ke database Firebase bro!
    waktu_pengumpulan: new Date().toISOString(),
  };

  try {
    const hasilRef = doc(db, "hasil_ujian_pk", nisSiswa_pk);
    await setDoc(hasilRef, paketHasil);

    // HAPUS SEMUA JEJAK LOCAL STORAGE
    localStorage.removeItem("nisSiswa_pk");
    localStorage.removeItem("jawabanSiswa_pk");
    localStorage.removeItem("listRagu_pk");
    localStorage.removeItem("currentSoalIndex_pk");
    localStorage.removeItem("sisaWaktu_pk");

    // Masukkan data ke halaman hasil
    document.getElementById("skorAkhir").textContent = skorTO;
    document.getElementById("detailStatistik").innerHTML =
      `Benar: <b>${benar}</b> &nbsp;|&nbsp; Salah: <b>${salah}</b> &nbsp;|&nbsp; Kosong: <b>${kosong}</b>`;

    // Pindah dari halaman ujian ke halaman hasil
    document.getElementById("examPage").classList.remove("active");
    document.getElementById("resultPage").classList.add("active");

    // Fungsi tombol keluar untuk refresh halaman
    document
      .getElementById("btnKembaliKeAwal")
      .addEventListener("click", () => {
        window.location.reload();
      });
  } catch (error) {
    console.error("Gagal mengirim hasil:", error);
    alert("Gagal menyimpan ke server. Pastikan koneksi internet stabil.");
    btnSelesai.textContent = "Selesai & Kumpulkan";
    btnSelesai.disabled = false;
  }
};

// --- FUNGSI NAVIGASI SOAL ---
document.getElementById("btnSebelumnya").addEventListener("click", () => {
  if (currentSoalIndex_pk > 0) {
    // Sembunyikan soal saat ini
    document.getElementById(`soal_${currentSoalIndex_pk}`).style.display =
      "none";
    currentSoalIndex_pk--;
    // Tampilkan soal sebelumnya
    document.getElementById(`soal_${currentSoalIndex_pk}`).style.display =
      "block";
    updateTombolNavigasi();
  }
});

document.getElementById("btnSelanjutnya").addEventListener("click", () => {
  if (currentSoalIndex_pk < dataSoal.length - 1) {
    // Sembunyikan soal saat ini
    document.getElementById(`soal_${currentSoalIndex_pk}`).style.display =
      "none";
    currentSoalIndex_pk++;
    // Tampilkan soal selanjutnya
    document.getElementById(`soal_${currentSoalIndex_pk}`).style.display =
      "block";
    updateTombolNavigasi();
  }
});

function updateTombolNavigasi() {
  const btnSebelumnnya = document.getElementById("btnSebelumnya");
  const btnSelanjutnya = document.getElementById("btnSelanjutnya");

  // Jika berada di soal pertama, matikan tombol "Sebelumnya"
  if (currentSoalIndex_pk === 0) {
    btnSebelumnnya.disabled = true;
    btnSebelumnnya.style.backgroundColor = "var(--btn-disabled)";
  } else {
    btnSebelumnnya.disabled = false;
    btnSebelumnnya.style.backgroundColor = "var(--btn-primary)";
  }

  // Jika berada di soal terakhir, matikan tombol "Selanjutnya"
  if (currentSoalIndex_pk === dataSoal.length - 1) {
    btnSelanjutnya.disabled = true;
    btnSelanjutnya.style.backgroundColor = "var(--btn-disabled)";
  } else {
    btnSelanjutnya.disabled = false;
    btnSelanjutnya.style.backgroundColor = "var(--btn-primary)";
  }

  // TAMBAHAN: Logika tampilan tombol Ragu
  if (listRagu_pk[currentSoalIndex_pk]) {
    // Jika sedang ragu
    btnRagu.textContent = "Batal Ragu";
    btnRagu.style.backgroundColor = "transparent";
    btnRagu.style.color = "#d97706";
    btnRagu.style.border = "2px solid #f59e0b";
  } else {
    // Jika tidak ragu
    btnRagu.textContent = "Ragu";
    btnRagu.style.backgroundColor = "#f59e0b";
    btnRagu.style.color = "white";
    btnRagu.style.border = "2px solid transparent";
  }
}

function renderNavigasi() {
  const grid = document.getElementById("gridNomor");
  grid.innerHTML = "";

  dataSoal.forEach((_, index) => {
    const btn = document.createElement("div");
    btn.className = "btn-nav-nomor";
    btn.id = `nav_no_${index}`;
    btn.textContent = index + 1;

    // Logika klik nomor: langsung lompat ke soal tersebut
    btn.onclick = () => lompatKeSoal(index);

    grid.appendChild(btn);
  });

  updateHighlightNavigasi();
}

function lompatKeSoal(indexBaru) {
  document.getElementById(`soal_${currentSoalIndex_pk}`).style.display = "none";
  currentSoalIndex_pk = indexBaru;

  // Simpan posisi halaman saat ini ke memori
  localStorage.setItem("currentSoalIndex_pk", currentSoalIndex_pk);

  document.getElementById(`soal_${currentSoalIndex_pk}`).style.display =
    "block";
  updateTombolNavigasi();
  updateHighlightNavigasi();
}

// Tambahan untuk menyimpan memori saat klik Ragu
document.getElementById("btnRagu").addEventListener("click", function () {
  listRagu_pk[currentSoalIndex_pk] = !listRagu_pk[currentSoalIndex_pk];
  localStorage.setItem("listRagu_pk", JSON.stringify(listRagu_pk)); // Simpan ke storage
  updateHighlightNavigasi();
  cekSemuaTerjawab();

  // ---> TAMBAHKAN BARIS INI <---
  updateTombolNavigasi();
});

function updateHighlightNavigasi() {
  // Hapus semua class 'aktif', lalu pasang di index saat ini
  document.querySelectorAll(".btn-nav-nomor").forEach((b, i) => {
    b.classList.remove("aktif");
    if (i === currentSoalIndex_pk) b.classList.add("aktif");
  });
}

// --- FUNGSI CEK KELENGKAPAN JAWABAN ---
function cekSemuaTerjawab() {
  let terjawab = 0;

  dataSoal.forEach((soal, index) => {
    const jawabanDipilih = document.querySelector(
      `input[name="jawaban_${soal.id}"]:checked`,
    );
    const btnNav = document.getElementById(`nav_no_${index}`);

    if (btnNav) {
      btnNav.classList.remove("terisi", "ragu");

      if (jawabanDipilih) {
        terjawab++;
        btnNav.classList.add("terisi");
      }

      // Jika ditandai ragu, warna kuning akan menimpa (override)
      if (listRagu_pk[index]) {
        btnNav.classList.add("ragu");
      }
    }
  });

  // Tombol selesai tetap bisa diklik jika sudah terjawab semua,
  // meskipun masih ada yang kuning (standar ujian SNBT)
  const btnSelesai = document.getElementById("tombolSelesai");
  if (terjawab === dataSoal.length) {
    btnSelesai.disabled = false;
    btnSelesai.style.backgroundColor = "var(--btn-success)";
    btnSelesai.textContent = "Selesai & Kumpulkan";
  } else {
    btnSelesai.disabled = true;
    btnSelesai.textContent = `Belum Selesai (${terjawab}/${dataSoal.length})`;
  }
}

document
  .getElementById("tombolSelesai")
  .addEventListener("click", window.submitUjian);

window.muatDataAdmin = async function () {
  const tabel = document.getElementById("tabelHasil");

  // Mengembalikan header Nama sesuai dengan index.html
  tabel.innerHTML = `
    <tr>
      <th>NIS</th>
      <th>Nama</th>
      <th>Benar</th>
      <th>Salah</th>
      <th>Kosong</th>
    </tr>
  `;

  try {
    // 1. Ambil data semua user untuk membuat "Kamus Siswa"
    const usersSnap = await getDocs(collection(db, "users"));
    const kamusSiswa = {};
    usersSnap.forEach((docSnap) => {
      const userData = docSnap.data();
      kamusSiswa[docSnap.id] = userData.nama || "Tanpa Nama";
    });

    // 2. Ambil data hasil ujian
    const querySnapshot = await getDocs(collection(db, "hasil_ujian_pk"));

    let barisTabel = "";

    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();

      // 3. Cocokkan NIS ujian dengan Nama di kamus
      const namaSiswa = kamusSiswa[data.nis] || "Tidak Diketahui";

      barisTabel += `
        <tr>
          <td style="text-align: center;">${data.nis}</td>
          <td style="text-align: left; padding-left: 15px;">${namaSiswa}</td>
          <td style="text-align: center;">${data.benar}</td>
          <td style="text-align: center;">${data.salah}</td>
          <td style="text-align: center;">${data.kosong}</td>
        </tr>
      `;
    });

    // Masukkan semua baris sekaligus ke dalam tabel
    tabel.innerHTML += barisTabel;
  } catch (error) {
    console.error("Gagal menarik data admin:", error);
    alert("Gagal memuat rekap nilai siswa.");
  }
};

// --- MESIN IMPORT DATA SISWA (DARI FILE JSON EKSTERNAL) ---

document
  .getElementById("tombolImport")
  .addEventListener("click", async function () {
    const btnImport = document.getElementById("tombolImport");
    btnImport.textContent = "Membaca File JSON...";
    btnImport.disabled = true;

    try {
      // 1. Kurir menjemput data dari file data-siswa.json
      const response = await fetch("data-siswa.json");

      // Cek jika file tidak ditemukan
      if (!response.ok) {
        throw new Error(
          "File data-siswa.json tidak ditemukan atau gagal dibaca!",
        );
      }

      // 2. Ubah isi file menjadi Array JavaScript
      const dataSiswaBaru = await response.json();

      // 3. Konfirmasi ganda ke Admin
      const yakin = confirm(
        `Ditemukan ${dataSiswaBaru.length} data siswa di dalam file. Yakin ingin mengunggah semuanya ke database?`,
      );

      if (yakin) {
        btnImport.textContent = "Mengunggah ke Database...";

        // Siapkan keranjang batch Firestore
        const batch = writeBatch(db);

        // Masukkan setiap siswa ke dalam keranjang
        dataSiswaBaru.forEach((siswa) => {
          const docRef = doc(db, "users", siswa.nis);
          batch.set(docRef, siswa);
        });

        // Eksekusi / Kirim keranjang ke server
        await batch.commit();

        alert("Impor Berhasil! Seluruh data siswa telah masuk ke Firestore.");
      }
    } catch (error) {
      console.error("Gagal Import:", error);
      alert("Terjadi kesalahan: " + error.message);
    } finally {
      // Kembalikan status tombol
      btnImport.textContent = "Import Data Siswa (JSON)";
      btnImport.disabled = false;
    }
  });

document.getElementById("tombolKeluar").addEventListener("click", function () {
  window.location.reload();
});

// --- FITUR EKSPOR CSV ---
document.getElementById("tombolEkspor").addEventListener("click", function () {
  const tabel = document.getElementById("tabelHasil");
  const baris = tabel.querySelectorAll("tr");
  let kontenCsv = "";

  // Iterasi setiap baris tabel
  baris.forEach((row) => {
    const kolom = row.querySelectorAll("th, td");
    const dataBaris = [];

    kolom.forEach((col) => {
      // Bersihkan teks dan bungkus dengan kutip untuk menangani koma di dalam teks
      dataBaris.push(`"${col.innerText.trim()}"`);
    });

    kontenCsv += dataBaris.join(",") + "\n";
  });

  // Membuat file Blob (Binary Large Object)
  const blob = new Blob([kontenCsv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  // Membuat link unduhan gaib
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", "rekap_nilai_pk_siswa.csv");
  link.style.visibility = "hidden";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
});

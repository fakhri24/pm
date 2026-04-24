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

// --- DATA DUMMY SOAL ---
const dataSoal = [
  {
    id: "s1",
    pertanyaan: "Berapa hasil dari 5 + (-3)?",
    opsi: ["A. 1", "B. 2", "C. -2", "D. 8"],
    kunci: "B",
  },
  {
    id: "s2",
    pertanyaan: "Jika x + 5 = 12, maka nilai x adalah?",
    opsi: ["A. 5", "B. 6", "C. 7", "D. 8"],
    kunci: "C",
  },
];

let timerInterval;

// Menangkap elemen tombol
const btnMasuk = document.getElementById("tombolMasuk");

btnMasuk.addEventListener("click", async function () {
  btnMasuk.textContent = "Memeriksa...";
  btnMasuk.disabled = true;

  const nisInput = document.getElementById("nis").value;
  const tglLahirInput = document.getElementById("password").value;

  if (!nisInput || !tglLahirInput) {
    alert("Isi NIS dan Tanggal Lahir dulu Bro!");
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
          const cekHasilRef = doc(db, "hasil_ujian", nisInput);
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

          // JIKA LOLOS SEMUA CEK: Baru pindah halaman
          document.getElementById("loginPage").classList.remove("active");
          document.getElementById("examPage").classList.add("active");
          if (typeof muatSoal === "function") muatSoal();
          if (typeof mulaiTimer === "function") mulaiTimer(1800);
        }
      } else {
        alert("Tanggal lahir tidak sesuai!");
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

function muatSoal() {
  const container = document.getElementById("soalContainer");
  let htmlSoal = "";

  dataSoal.forEach((soal, index) => {
    htmlSoal += `<div style="margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 15px;">`;
    htmlSoal += `<p><strong>${index + 1}.</strong> ${soal.pertanyaan}</p>`;

    // Format opsi teks biasa yang mudah dicopy ke word processor
    soal.opsi.forEach((opsi) => {
      const huruf = opsi.charAt(0);
      htmlSoal += `
          <div style="margin-bottom: 8px;">
              <label style="cursor: pointer;">
                  <input type="radio" name="jawaban_${soal.id}" value="${huruf}">
                  ${opsi}
              </label>
          </div>`;
    });
    htmlSoal += `</div>`;
  });

  container.innerHTML = htmlSoal;
}

function mulaiTimer(durasiDetik) {
  let waktu = durasiDetik;
  const display = document.getElementById("timer");

  timerInterval = setInterval(function () {
    let menit = parseInt(waktu / 60, 10);
    let detik = parseInt(waktu % 60, 10);

    menit = menit < 10 ? "0" + menit : menit;
    detik = detik < 10 ? "0" + detik : detik;

    display.textContent = "Sisa Waktu: " + menit + ":" + detik;

    if (--waktu < 0) {
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

  const nisSiswa = document.getElementById("nis").value;
  const paketHasil = {
    nis: nisSiswa,
    benar: benar,
    salah: salah,
    kosong: kosong,
    waktu_pengumpulan: new Date().toISOString(),
  };

  try {
    const hasilRef = doc(db, "hasil_ujian", nisSiswa);
    await setDoc(hasilRef, paketHasil);
    alert(
      `Ujian Berhasil Diselesaikan!\n\nStatistik Kamu:\nBenar: ${benar}\nSalah: ${salah}\nKosong: ${kosong}\n\nData telah terekam di sistem server.`,
    );
    window.location.reload();
  } catch (error) {
    console.error("Gagal mengirim hasil:", error);
    alert("Gagal menyimpan ke server. Pastikan koneksi internet stabil.");
    btnSelesai.textContent = "Selesai & Kumpulkan";
    btnSelesai.disabled = false;
  }
};

document
  .getElementById("tombolSelesai")
  .addEventListener("click", window.submitUjian);

window.muatDataAdmin = async function () {
  const tabel = document.getElementById("tabelHasil");
  tabel.innerHTML = `
    <tr>
      <th>NIS</th>
      <th>Waktu (Jam)</th>
      <th>Benar</th>
      <th>Salah</th>
      <th>Kosong</th>
    </tr>
  `;

  try {
    const querySnapshot = await getDocs(collection(db, "hasil_ujian"));
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      const waktuFormat = new Date(data.waktu_pengumpulan).toLocaleTimeString(
        "id-ID",
      );

      tabel.innerHTML += `
        <tr>
          <td style="text-align: center;">${data.nis}</td>
          <td style="text-align: center;">${waktuFormat}</td>
          <td style="text-align: center;">${data.benar}</td>
          <td style="text-align: center;">${data.salah}</td>
          <td style="text-align: center;">${data.kosong}</td>
        </tr>
      `;
    });
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

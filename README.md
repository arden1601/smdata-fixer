# SMDATA Fixer

Repairs **SMART Mobile build 1.0.612** patrol exports (`SMDATA_*.json`) so they
can be imported into **SMART Desktop** again.

[🇮🇩 Bahasa Indonesia](#bahasa-indonesia) ·
[Download](https://github.com/arden1601/smdata-fixer/releases/latest)

## The problem

SMART Mobile 1.0.612 writes empty patrol/observation fields as JSON `null`
(`SMART_Observer`, `SMART_Team`, `SMART_Comments`, `SMART_IncidentType`,
`SMART_Objective`, and unfilled attributes `a:<n>:<uuid>`). Build 1.0.602
omitted those keys.

SMART Desktop's importer
([`CtJsonObservationParser.createWaypoint`](https://github.com/Wildlife-Protection-Solutions/SMART-Platform/blob/main/source/extensions/cybertracker/org.wcs.smart.cybertracker/shared/org/wcs/smart/cybertracker/json/CtJsonObservationParser.java))
does:

```java
String ob = (String) observations.get("SMART_Observer");
if (ob.startsWith("e:")) ...          // NullPointerException when null
```

The failing observation is skipped. The importer requires `SMART_ObsCounter`
to be strictly sequential, so every later observation of that patrol, including
`StopPatrol`, is skipped too. The result is a patrol with only its start point.
Mobile build 1.0.615 stops writing the nulls, but files already exported with
1.0.612 stay unreadable.

## The fix

For every feature's `sighting` object the tool removes:

- keys whose value is `null`
- attributes (`a:…`) whose value is an empty string `""` (for example an unfilled
  DATE, which otherwise triggers *"Unable to parse date"* warnings)

This restores the 1.0.602 layout. Coordinates, photos, filled attributes and
track points are not touched. The tool also checks that `SMART_ObsCounter` runs
1..N per patrol and warns when observations are missing. Running it on files
that are already fine changes nothing.

## Usage

### Windows / Linux GUI

1. Download `SMDATA-Fixer.exe` (Windows) or `SMDATA-Fixer-linux-x86_64` from
   [Releases](https://github.com/arden1601/smdata-fixer/releases/latest).
   Nothing to install.
2. **Tambah file…** to select one or more `SMDATA_*.json` files.
3. **Pilih…** to choose an output folder. It must differ from the source folder,
   so originals are never overwritten.
4. **Perbaiki**, then **Buka folder output**, and import the fixed files in
   SMART Desktop.

If a patrol was already imported half-way, delete that patrol in SMART Desktop
before importing the fixed file, otherwise track points may be duplicated.

> Windows SmartScreen may warn about an unsigned app: *More info → Run anyway*.

### Command line (Python ≥ 3.9, no dependencies)

```bash
python fix_smdata_612.py SMDATA_*.json -o fixed/
python smdata_fixer_gui.py            # GUI (needs Tk: python3-tk / tk package)
```

## Development

```bash
python -m unittest discover -s tests -v
./build_exe.sh                        # Windows .exe from Linux via Docker + Wine
```

Pushing a `v*` tag builds the Windows and Linux binaries on GitHub Actions and
attaches them to a release.

Never commit real patrol exports. They contain locations, photos and device
IDs. `*.json` is git-ignored.

## License

[MIT](LICENSE). Not affiliated with the SMART Partnership or CyberTracker.

---

## Bahasa Indonesia

Tool ini memperbaiki file `SMDATA_*.json` hasil export **SMART Mobile build
1.0.612** agar bisa diimpor kembali ke **SMART Desktop**.

**Masalahnya:** build 1.0.612 menulis field kosong sebagai `null`. Importer
SMART Desktop crash pada `SMART_Observer: null`, sehingga observasi tersebut
dan semua observasi sesudahnya tidak masuk. Patroli hanya berisi titik awal.

**Perbaikannya:** field `null` dan atribut kosong `""` dibuang. Format file
kembali sama dengan build 1.0.602. Data lain (koordinat, foto, atribut, track)
tidak diubah. File asli juga tidak diubah, karena hasil perbaikan ditulis ke
folder output.

**Cara pakai:**

1. Unduh `SMDATA-Fixer.exe` dari
   [Releases](https://github.com/arden1601/smdata-fixer/releases/latest), lalu
   jalankan. Tidak perlu instalasi.
2. Klik **Tambah file…** dan pilih satu atau beberapa file `SMDATA_*.json`.
3. Klik **Pilih…** untuk memilih folder output. Folder ini harus berbeda dari
   folder file asli.
4. Klik **Perbaiki**, lalu **Buka folder output**, kemudian impor hasilnya ke
   SMART Desktop.
5. Jika patroli yang sama pernah diimpor setengah jadi, hapus patroli itu dulu
   di SMART Desktop.

Jika log menampilkan **PERINGATAN … ObsCounter**, ada observasi yang hilang di
file tersebut, dan SMART Desktop akan berhenti mengimpor di titik itu.

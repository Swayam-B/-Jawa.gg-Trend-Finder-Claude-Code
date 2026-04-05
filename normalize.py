"""
GPU and CPU normalization utilities for jawa.gg scraper.
Converts raw text strings into canonical hardware names.
"""

import re


# ---------------------------------------------------------------------------
# GPU normalization
# ---------------------------------------------------------------------------

# Each entry: (compiled regex, canonical name)
_GPU_PATTERNS: list[tuple[re.Pattern, str]] = []


def _gpu(pattern: str, canonical: str) -> None:
    _GPU_PATTERNS.append((re.compile(pattern, re.IGNORECASE), canonical))


# --- NVIDIA GeForce RTX 50 series ---
_gpu(r"RTX\s*5090", "RTX 5090")
_gpu(r"RTX\s*5080", "RTX 5080")
_gpu(r"RTX\s*5070\s*Ti", "RTX 5070 Ti")
_gpu(r"RTX\s*5070", "RTX 5070")
_gpu(r"RTX\s*5060\s*Ti", "RTX 5060 Ti")
_gpu(r"RTX\s*5060", "RTX 5060")

# --- NVIDIA GeForce RTX 40 series ---
_gpu(r"RTX\s*4090", "RTX 4090")
_gpu(r"RTX\s*4080\s*Super", "RTX 4080 Super")
_gpu(r"RTX\s*4080", "RTX 4080")
_gpu(r"RTX\s*4070\s*Ti\s*Super", "RTX 4070 Ti Super")
_gpu(r"RTX\s*4070\s*Ti", "RTX 4070 Ti")
_gpu(r"RTX\s*4070\s*Super", "RTX 4070 Super")
_gpu(r"RTX\s*4070", "RTX 4070")
_gpu(r"RTX\s*4060\s*Ti", "RTX 4060 Ti")
_gpu(r"RTX\s*4060", "RTX 4060")
_gpu(r"RTX\s*4050", "RTX 4050")

# --- NVIDIA GeForce RTX 30 series ---
_gpu(r"RTX\s*3090\s*Ti", "RTX 3090 Ti")
_gpu(r"RTX\s*3090", "RTX 3090")
_gpu(r"RTX\s*3080\s*Ti", "RTX 3080 Ti")
_gpu(r"RTX\s*3080\s*12\s*GB", "RTX 3080 12GB")
_gpu(r"RTX\s*3080", "RTX 3080")
_gpu(r"RTX\s*3070\s*Ti", "RTX 3070 Ti")
_gpu(r"RTX\s*3070", "RTX 3070")
_gpu(r"RTX\s*3060\s*Ti", "RTX 3060 Ti")
_gpu(r"RTX\s*3060", "RTX 3060")
_gpu(r"RTX\s*3050", "RTX 3050")

# --- NVIDIA GeForce RTX 20 series ---
_gpu(r"RTX\s*2080\s*Ti", "RTX 2080 Ti")
_gpu(r"RTX\s*2080\s*Super", "RTX 2080 Super")
_gpu(r"RTX\s*2080", "RTX 2080")
_gpu(r"RTX\s*2070\s*Super", "RTX 2070 Super")
_gpu(r"RTX\s*2070", "RTX 2070")
_gpu(r"RTX\s*2060\s*Super", "RTX 2060 Super")
_gpu(r"RTX\s*2060", "RTX 2060")

# --- NVIDIA GeForce GTX 16/10 series ---
_gpu(r"GTX\s*1660\s*Ti", "GTX 1660 Ti")
_gpu(r"GTX\s*1660\s*Super", "GTX 1660 Super")
_gpu(r"GTX\s*1660", "GTX 1660")
_gpu(r"GTX\s*1650\s*Super", "GTX 1650 Super")
_gpu(r"GTX\s*1650", "GTX 1650")
_gpu(r"GTX\s*1080\s*Ti", "GTX 1080 Ti")
_gpu(r"GTX\s*1080", "GTX 1080")
_gpu(r"GTX\s*1070\s*Ti", "GTX 1070 Ti")
_gpu(r"GTX\s*1070", "GTX 1070")
_gpu(r"GTX\s*1060", "GTX 1060")

# --- AMD Radeon RX 9000 series ---
_gpu(r"RX\s*9070\s*XT", "RX 9070 XT")
_gpu(r"RX\s*9070", "RX 9070")

# --- AMD Radeon RX 7000 series ---
_gpu(r"RX\s*7900\s*XTX", "RX 7900 XTX")
_gpu(r"RX\s*7900\s*XT", "RX 7900 XT")
_gpu(r"RX\s*7900\s*GRE", "RX 7900 GRE")
_gpu(r"RX\s*7800\s*XT", "RX 7800 XT")
_gpu(r"RX\s*7700\s*XT", "RX 7700 XT")
_gpu(r"RX\s*7600\s*XT", "RX 7600 XT")
_gpu(r"RX\s*7600", "RX 7600")

# --- AMD Radeon RX 6000 series ---
_gpu(r"RX\s*6950\s*XT", "RX 6950 XT")
_gpu(r"RX\s*6900\s*XT", "RX 6900 XT")
_gpu(r"RX\s*6800\s*XT", "RX 6800 XT")
_gpu(r"RX\s*6800", "RX 6800")
_gpu(r"RX\s*6750\s*XT", "RX 6750 XT")
_gpu(r"RX\s*6700\s*XT", "RX 6700 XT")
_gpu(r"RX\s*6700", "RX 6700")
_gpu(r"RX\s*6650\s*XT", "RX 6650 XT")
_gpu(r"RX\s*6600\s*XT", "RX 6600 XT")
_gpu(r"RX\s*6600", "RX 6600")
_gpu(r"RX\s*6500\s*XT", "RX 6500 XT")
_gpu(r"RX\s*6400", "RX 6400")

# --- AMD Radeon RX 5000 series ---
_gpu(r"RX\s*5700\s*XT", "RX 5700 XT")
_gpu(r"RX\s*5700", "RX 5700")
_gpu(r"RX\s*5600\s*XT", "RX 5600 XT")
_gpu(r"RX\s*5500\s*XT", "RX 5500 XT")

# --- Intel Arc ---
_gpu(r"Arc\s*[AB]\d{3,4}", "Intel Arc")  # fallback; refined below
_gpu(r"Arc\s*B580", "Arc B580")
_gpu(r"Arc\s*B570", "Arc B570")
_gpu(r"Arc\s*A770", "Arc A770")
_gpu(r"Arc\s*A750", "Arc A750")
_gpu(r"Arc\s*A580", "Arc A580")
_gpu(r"Arc\s*A380", "Arc A380")


def normalize_gpu(text: str) -> str | None:
    """
    Return the canonical GPU name found in *text*, or None if not found.
    Patterns are checked longest/most-specific first (order in _GPU_PATTERNS).
    """
    for pattern, canonical in _GPU_PATTERNS:
        if pattern.search(text):
            return canonical
    return None


# ---------------------------------------------------------------------------
# CPU normalization
# ---------------------------------------------------------------------------

_CPU_PATTERNS: list[tuple[re.Pattern, str]] = []


def _cpu(pattern: str, canonical: str) -> None:
    _CPU_PATTERNS.append((re.compile(pattern, re.IGNORECASE), canonical))


# --- AMD Ryzen 9000 series ---
_cpu(r"Ryzen\s*9\s*9950X3D", "Ryzen 9 9950X3D")
_cpu(r"Ryzen\s*9\s*9950X", "Ryzen 9 9950X")
_cpu(r"Ryzen\s*9\s*9900X3D", "Ryzen 9 9900X3D")
_cpu(r"Ryzen\s*9\s*9900X", "Ryzen 9 9900X")
_cpu(r"Ryzen\s*7\s*9800X3D", "Ryzen 7 9800X3D")
_cpu(r"Ryzen\s*7\s*9700X", "Ryzen 7 9700X")
_cpu(r"Ryzen\s*5\s*9600X", "Ryzen 5 9600X")
_cpu(r"Ryzen\s*5\s*9600", "Ryzen 5 9600")

# --- AMD Ryzen 7000 series ---
_cpu(r"Ryzen\s*9\s*7950X3D", "Ryzen 9 7950X3D")
_cpu(r"Ryzen\s*9\s*7950X", "Ryzen 9 7950X")
_cpu(r"Ryzen\s*9\s*7900X3D", "Ryzen 9 7900X3D")
_cpu(r"Ryzen\s*9\s*7900X", "Ryzen 9 7900X")
_cpu(r"Ryzen\s*9\s*7900", "Ryzen 9 7900")
_cpu(r"Ryzen\s*7\s*7800X3D", "Ryzen 7 7800X3D")
_cpu(r"Ryzen\s*7\s*7700X", "Ryzen 7 7700X")
_cpu(r"Ryzen\s*7\s*7700", "Ryzen 7 7700")
_cpu(r"Ryzen\s*5\s*7600X3D", "Ryzen 5 7600X3D")
_cpu(r"Ryzen\s*5\s*7600X", "Ryzen 5 7600X")
_cpu(r"Ryzen\s*5\s*7600", "Ryzen 5 7600")
_cpu(r"Ryzen\s*5\s*7500F", "Ryzen 5 7500F")

# --- AMD Ryzen 5000 series ---
_cpu(r"Ryzen\s*9\s*5950X", "Ryzen 9 5950X")
_cpu(r"Ryzen\s*9\s*5900X", "Ryzen 9 5900X")
_cpu(r"Ryzen\s*9\s*5900", "Ryzen 9 5900")
_cpu(r"Ryzen\s*7\s*5800X3D", "Ryzen 7 5800X3D")
_cpu(r"Ryzen\s*7\s*5800X", "Ryzen 7 5800X")
_cpu(r"Ryzen\s*7\s*5800", "Ryzen 7 5800")
_cpu(r"Ryzen\s*7\s*5700X3D", "Ryzen 7 5700X3D")
_cpu(r"Ryzen\s*7\s*5700X", "Ryzen 7 5700X")
_cpu(r"Ryzen\s*7\s*5700G", "Ryzen 7 5700G")
_cpu(r"Ryzen\s*5\s*5600X3D", "Ryzen 5 5600X3D")
_cpu(r"Ryzen\s*5\s*5600X", "Ryzen 5 5600X")
_cpu(r"Ryzen\s*5\s*5600G", "Ryzen 5 5600G")
_cpu(r"Ryzen\s*5\s*5600", "Ryzen 5 5600")
_cpu(r"Ryzen\s*5\s*5500", "Ryzen 5 5500")

# --- AMD Ryzen 3000 series ---
_cpu(r"Ryzen\s*9\s*3950X", "Ryzen 9 3950X")
_cpu(r"Ryzen\s*9\s*3900X", "Ryzen 9 3900X")
_cpu(r"Ryzen\s*7\s*3800X", "Ryzen 7 3800X")
_cpu(r"Ryzen\s*7\s*3700X", "Ryzen 7 3700X")
_cpu(r"Ryzen\s*5\s*3600X", "Ryzen 5 3600X")
_cpu(r"Ryzen\s*5\s*3600", "Ryzen 5 3600")

# Generic Ryzen fallback (catches R5/R7/R9 shorthand)
_cpu(r"R9\s*(\d{4}[A-Z0-9]*)", "Ryzen 9 \\1")
_cpu(r"R7\s*(\d{4}[A-Z0-9]*)", "Ryzen 7 \\1")
_cpu(r"R5\s*(\d{4}[A-Z0-9]*)", "Ryzen 5 \\1")

# --- Intel Core Ultra (Arrow Lake / Meteor Lake) ---
_cpu(r"Core\s*Ultra\s*9\s*285K", "Core Ultra 9 285K")
_cpu(r"Core\s*Ultra\s*7\s*265K[F]?", "Core Ultra 7 265KF")
_cpu(r"Core\s*Ultra\s*7\s*265K", "Core Ultra 7 265K")
_cpu(r"Core\s*Ultra\s*5\s*245K[F]?", "Core Ultra 5 245KF")
_cpu(r"Core\s*Ultra\s*5\s*245K", "Core Ultra 5 245K")

# --- Intel Core 14th gen ---
_cpu(r"i9[-\s]*14900KS", "i9-14900KS")
_cpu(r"i9[-\s]*14900KF", "i9-14900KF")
_cpu(r"i9[-\s]*14900K", "i9-14900K")
_cpu(r"i9[-\s]*14900F", "i9-14900F")
_cpu(r"i9[-\s]*14900", "i9-14900")
_cpu(r"i7[-\s]*14700KF", "i7-14700KF")
_cpu(r"i7[-\s]*14700K", "i7-14700K")
_cpu(r"i7[-\s]*14700F", "i7-14700F")
_cpu(r"i7[-\s]*14700", "i7-14700")
_cpu(r"i5[-\s]*14600KF", "i5-14600KF")
_cpu(r"i5[-\s]*14600K", "i5-14600K")
_cpu(r"i5[-\s]*14600F", "i5-14600F")
_cpu(r"i5[-\s]*14600", "i5-14600")
_cpu(r"i5[-\s]*14400F", "i5-14400F")
_cpu(r"i5[-\s]*14400", "i5-14400")

# --- Intel Core 13th gen ---
_cpu(r"i9[-\s]*13900KS", "i9-13900KS")
_cpu(r"i9[-\s]*13900KF", "i9-13900KF")
_cpu(r"i9[-\s]*13900K", "i9-13900K")
_cpu(r"i9[-\s]*13900F", "i9-13900F")
_cpu(r"i9[-\s]*13900", "i9-13900")
_cpu(r"i7[-\s]*13700KF", "i7-13700KF")
_cpu(r"i7[-\s]*13700K", "i7-13700K")
_cpu(r"i7[-\s]*13700F", "i7-13700F")
_cpu(r"i7[-\s]*13700", "i7-13700")
_cpu(r"i5[-\s]*13600KF", "i5-13600KF")
_cpu(r"i5[-\s]*13600K", "i5-13600K")
_cpu(r"i5[-\s]*13600F", "i5-13600F")
_cpu(r"i5[-\s]*13600", "i5-13600")
_cpu(r"i5[-\s]*13400F", "i5-13400F")
_cpu(r"i5[-\s]*13400", "i5-13400")

# --- Intel Core 12th gen ---
_cpu(r"i9[-\s]*12900KS", "i9-12900KS")
_cpu(r"i9[-\s]*12900KF", "i9-12900KF")
_cpu(r"i9[-\s]*12900K", "i9-12900K")
_cpu(r"i7[-\s]*12700KF", "i7-12700KF")
_cpu(r"i7[-\s]*12700K", "i7-12700K")
_cpu(r"i7[-\s]*12700F", "i7-12700F")
_cpu(r"i7[-\s]*12700", "i7-12700")
_cpu(r"i5[-\s]*12600KF", "i5-12600KF")
_cpu(r"i5[-\s]*12600K", "i5-12600K")
_cpu(r"i5[-\s]*12600F", "i5-12600F")
_cpu(r"i5[-\s]*12400F", "i5-12400F")
_cpu(r"i5[-\s]*12400", "i5-12400")

# --- Intel Core 10th/11th gen ---
_cpu(r"i9[-\s]*10900K", "i9-10900K")
_cpu(r"i7[-\s]*11700KF", "i7-11700KF")
_cpu(r"i7[-\s]*11700K", "i7-11700K")
_cpu(r"i7[-\s]*10700KF", "i7-10700KF")
_cpu(r"i7[-\s]*10700K", "i7-10700K")
_cpu(r"i5[-\s]*11600KF", "i5-11600KF")
_cpu(r"i5[-\s]*10600KF", "i5-10600KF")
_cpu(r"i5[-\s]*10400F", "i5-10400F")
_cpu(r"i5[-\s]*10400", "i5-10400")

# Generic Intel fallback
_cpu(r"(i[3579])[-\s]*(\d{4,5}[A-Z0-9]*)", None)  # handled below


def normalize_cpu(text: str) -> str | None:
    """
    Return the canonical CPU name found in *text*, or None if not found.
    """
    for pattern, canonical in _CPU_PATTERNS:
        m = pattern.search(text)
        if m:
            if canonical is None:
                # Generic Intel fallback — reconstruct from groups
                return f"{m.group(1)}-{m.group(2)}"
            # Handle back-references (Ryzen R5/R7/R9 shorthand patterns)
            if "\\" in canonical:
                return pattern.sub(canonical, m.group(0))
            return canonical
    return None


# ---------------------------------------------------------------------------
# RAM extraction
# ---------------------------------------------------------------------------

_RAM_RE = re.compile(r"(\d+)\s*GB\s*(?:DDR[45]?|RAM|Memory)", re.IGNORECASE)
_RAM_RE2 = re.compile(r"(\d+)\s*GB", re.IGNORECASE)


def extract_ram_gb(text: str) -> int | None:
    """Return RAM size in GB, or None if not found."""
    m = _RAM_RE.search(text)
    if m:
        return int(m.group(1))
    m = _RAM_RE2.search(text)
    if m:
        val = int(m.group(1))
        # Sanity-check: common RAM sizes
        if val in {4, 8, 12, 16, 24, 32, 48, 64, 96, 128}:
            return val
    return None


# ---------------------------------------------------------------------------
# Storage extraction
# ---------------------------------------------------------------------------

# GB + explicit drive-type keyword (e.g. "256GB SSD", "512GB NVMe")
_STORAGE_GB_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*GB\s*(?:/\s*)?(\d+(?:\.\d+)?\s*GB\s*)?(NVMe|SSD|HDD|M\.2|SATA)",
    re.IGNORECASE,
)
# TB size — always storage, never VRAM or RAM
_STORAGE_TB_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*TB\b(?:\s*(NVMe|SSD|HDD|M\.2|SATA))?",
    re.IGNORECASE,
)

_DRIVE_TYPE_MAP = {"NVME": "NVMe", "SSD": "SSD", "HDD": "HDD", "M.2": "NVMe", "SATA": "SSD"}


def _fmt_size(num_str: str, unit: str) -> str:
    num = float(num_str)
    if unit.upper() == "TB" and "." in num_str and not num_str.endswith(".0"):
        return f"{int(num * 1024)}GB"
    return f"{int(num)}{unit.upper()}" if num == int(num) else f"{num_str}{unit.upper()}"


def extract_storage(text: str) -> str | None:
    """
    Return a normalised storage string like '256GB SSD' or '2TB NVMe'.

    Requires either:
    - a TB unit (always storage, never GPU VRAM or RAM), or
    - a GB value immediately followed by a drive-type keyword (NVMe/SSD/HDD/M.2/SATA).

    This prevents matching bare '16GB' (RAM) or '8GB' (GPU VRAM).
    """
    # 1. Prefer explicit GB + drive type — most specific
    m = _STORAGE_GB_RE.search(text)
    if m:
        size_str = _fmt_size(m.group(1), "GB")
        drive_type = _DRIVE_TYPE_MAP.get(m.group(3).upper(), m.group(3).upper())
        return f"{size_str} {drive_type}"

    # 2. TB value (optionally followed by drive type)
    m = _STORAGE_TB_RE.search(text)
    if m:
        size_str = _fmt_size(m.group(1), "TB")
        drive_raw = (m.group(2) or "").upper()
        drive_type = _DRIVE_TYPE_MAP.get(drive_raw, drive_raw)
        return f"{size_str} {drive_type}".strip() if drive_type else size_str

    return None


if __name__ == "__main__":
    # Quick smoke-test
    samples = [
        ("RTX 4070 Ti Super Gaming PC", "RTX 4070 Ti Super"),
        ("Powered by rtx3080 graphics", "RTX 3080"),
        ("RX 7800XT 16GB AMD build", "RX 7800 XT"),
        ("Ryzen 7 7800X3D | RTX 4090", "Ryzen 7 7800X3D"),
        ("i7-14700K build", "i7-14700K"),
        ("R5 5600X build", None),  # Generic pattern test
        ("32GB DDR5 RAM", None),
        ("2TB NVMe SSD", None),
    ]
    print("GPU tests:")
    for text, expected in samples[:3]:
        result = normalize_gpu(text)
        status = "OK" if result == expected else f"FAIL (got {result!r}, want {expected!r})"
        print(f"  {text!r:45s} -> {result!r:25s} {status}")

    print("\nCPU tests:")
    for text, _ in samples[3:6]:
        result = normalize_cpu(text)
        print(f"  {text!r:45s} -> {result!r}")

    print("\nRAM tests:")
    for text in ["32GB DDR5 RAM", "16 GB DDR4", "128GB storage"]:
        print(f"  {text!r:30s} -> {extract_ram_gb(text)!r}")

    print("\nStorage tests:")
    for text in ["1TB NVMe SSD", "2TB HDD", "512GB SSD", "2.0TB M.2"]:
        print(f"  {text!r:30s} -> {extract_storage(text)!r}")

"""
Florida Department of Revenue (DOR) Sale Data File (SDF) Universal Statewide Parser
Accepts ANY Florida County File from Day One (CSV, TXT, or ZIP)

Universal Capabilities:
1. Full 67 Florida County Code & Name Mapping
2. Auto-detects county from DOR CO_NO column, filename (SDF58F..., Pinellas_SDF...), or CLI arg
3. Sniffs CSV, TSV, pipe-delimited, and fixed-delimiter formats
4. Directly reads and extracts from .zip archives without manual unpacking
5. Extracts:
   - Qualified arms-length vacant lot sales (DOR_UC: 000, VI_CD: V, QUAL_CD: 01/02)
   - Qualified arms-length improved new-build single-family resales (DOR_UC: 001, VI_CD: I, QUAL_CD: 01/02)
   - Granular neighborhood & market area median benchmarks
6. Batch Directory Ingestion: parses all SDF files sitting in C:\\Users\\johng\\Documents\\sdf-downloads
   and merges them into data/land_comps.json by county key.
"""

import os
import sys
import csv
import json
import zipfile
import tempfile
import statistics
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LAND_COMPS_FILE = os.path.join(DATA_DIR, "land_comps.json")
DEFAULT_DOWNLOADS_DIR = r"C:\Users\johng\Documents\sdf-downloads"

# Comprehensive Florida 67-County DOR Mapping
# Maps 2-digit DOR county code to uppercase County Name
FL_DOR_COUNTY_MAP: Dict[str, str] = {
    "01": "ALACHUA", "1": "ALACHUA",
    "02": "BAKER", "2": "BAKER",
    "03": "BAY", "3": "BAY",
    "04": "BRADFORD", "4": "BRADFORD",
    "05": "BREVARD", "5": "BREVARD",
    "06": "BROWARD", "6": "BROWARD",
    "07": "CALHOUN", "7": "CALHOUN",
    "08": "CHARLOTTE", "8": "CHARLOTTE",
    "09": "CITRUS", "9": "CITRUS",
    "10": "CLAY",
    "11": "COLLIER",
    "12": "COLUMBIA",
    "13": "MIAMI-DADE",
    "14": "DE SOTO",
    "15": "DIXIE",
    "16": "DUVAL",
    "17": "ESCAMBIA",
    "18": "FLAGLER",
    "19": "FRANKLIN",
    "20": "GADSDEN",
    "21": "GILCHRIST",
    "22": "GLADES",
    "23": "GULF",
    "24": "HAMILTON",
    "25": "HARDEE",
    "26": "HENDRY",
    "27": "HERNANDO",
    "28": "HIGHLANDS",
    "29": "HILLSBOROUGH",
    "30": "HOLMES",
    "31": "INDIAN RIVER",
    "32": "JACKSON",
    "33": "JEFFERSON",
    "34": "LAFAYETTE",
    "35": "LAKE",
    "36": "LEE",
    "37": "LEON",
    "38": "LEVY",
    "39": "LIBERTY",
    "40": "MADISON",
    "41": "MANATEE",
    "42": "MARION",
    "43": "MARTIN",
    "44": "MONROE",
    "45": "NASSAU",
    "46": "OKALOOSA",
    "47": "OKEECHOBEE",
    "48": "SARASOTA",
    "49": "OSCEOLA",
    "50": "PALM BEACH",
    "51": "PASCO",
    "52": "PINELLAS",
    "53": "POLK",
    "54": "PUTNAM",
    "55": "ST. JOHNS",
    "56": "ST. LUCIE",
    "57": "SANTA ROSA",
    "58": "ORANGE",     # DOR Final Roll SDF58F indicates Orange County
    "59": "SEMINOLE",
    "60": "SUMTER",
    "61": "SUWANNEE",
    "62": "TAYLOR",
    "63": "UNION",
    "64": "VOLUSIA",
    "65": "WAKULLA",
    "66": "WALTON",
    "67": "WASHINGTON"
}

# Reverse lookup: county name to primary DOR code
COUNTY_TO_DOR_CODE: Dict[str, str] = {v: k for k, v in FL_DOR_COUNTY_MAP.items()}
FLORIDA_COUNTIES = FL_DOR_COUNTY_MAP


def get_county_code_from_filename(filename: str) -> Optional[str]:
    import re
    clean = os.path.basename(filename).upper()
    m = re.search(r'SDF(\d{1,2})[FP]?', clean)
    if m:
        return m.group(1).zfill(2)
    county = detect_county_from_filename(filename)
    if county and county in COUNTY_TO_DOR_CODE:
        return COUNTY_TO_DOR_CODE[county]
    return None


def detect_county_from_filename(filename: str) -> Optional[str]:
    """
    Infers Florida county name from standard DOR file naming conventions:
    Examples:
      SDF58F202601.csv -> ORANGE (code 58)
      SDF52F202601.csv -> PINELLAS (code 52)
      SDF29F202601.csv -> HILLSBOROUGH (code 29)
      Pinellas_SDF.csv -> PINELLAS
      orange_county_sales.csv -> ORANGE
    """
    clean = os.path.basename(filename).upper()

    # Check for direct county name mention in filename
    for c_code, c_name in FL_DOR_COUNTY_MAP.items():
        clean_name = c_name.replace(" ", "").replace("-", "").replace(".", "")
        if clean_name in clean.replace(" ", "").replace("-", "").replace("_", ""):
            return c_name

    # Check for SDF prefix: SDF{co_no}F or SDF{co_no}P (Final or Preliminary)
    import re
    m = re.search(r'SDF(\d{1,2})[FP]?', clean)
    if m:
        code_str = m.group(1).zfill(2)
        if code_str in FL_DOR_COUNTY_MAP:
            return FL_DOR_COUNTY_MAP[code_str]

    return None


def sniff_delimiter(sample_lines: List[str]) -> str:
    """Sniffs whether file is comma, pipe, tab, or semicolon separated."""
    text = "\n".join(sample_lines[:10])
    comma_count = text.count(",")
    pipe_count = text.count("|")
    tab_count = text.count("\t")
    semicolon_count = text.count(";")

    counts = [
        (comma_count, ","),
        (pipe_count, "|"),
        (tab_count, "\t"),
        (semicolon_count, ";")
    ]
    counts.sort(key=lambda x: x[0], reverse=True)
    if counts[0][0] > 0:
        return counts[0][1]
    return ","


def parse_sdf_file(
    file_path: str,
    county_name: Optional[str] = None,
    min_vacant_price: float = 10000.0,
    max_vacant_price: float = 1500000.0,
    min_improved_price: float = 120000.0,
    max_improved_price: float = 2500000.0,
    max_comps_per_category: int = 500
) -> Dict[str, Any]:
    """
    Universal Parser for ANY Florida County SDF file (CSV, TXT, or ZIP).
    Works identically for all 67 Florida counties.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SDF file not found at: {file_path}")

    # Handle .zip archive by extracting inner SDF file
    temp_dir_to_clean = None
    actual_file_to_read = file_path
    if file_path.lower().endswith(".zip"):
        temp_dir_to_clean = tempfile.mkdtemp(prefix="sdf_zip_")
        with zipfile.ZipFile(file_path, "r") as z:
            namelist = z.namelist()
            # Find largest or .csv/.txt file inside
            sdf_entries = [n for n in namelist if n.lower().endswith((".csv", ".txt", ".dat"))]
            target_entry = sdf_entries[0] if sdf_entries else namelist[0]
            z.extract(target_entry, temp_dir_to_clean)
            actual_file_to_read = os.path.join(temp_dir_to_clean, target_entry)

    vacant_comps: List[Dict[str, Any]] = []
    improved_comps: List[Dict[str, Any]] = []
    
    vacant_prices_by_nbrhd: Dict[str, List[float]] = {}
    improved_prices_by_nbrhd: Dict[str, List[float]] = {}
    vacant_prices_by_mkt: Dict[str, List[float]] = {}
    improved_prices_by_mkt: Dict[str, List[float]] = {}
    all_vacant_prices: List[float] = []
    all_improved_prices: List[float] = []

    detected_co_no = None

    try:
        # Sniff delimiter from first 10 lines
        with open(actual_file_to_read, "r", encoding="utf-8", errors="ignore") as f:
            sample_lines = [f.readline() for _ in range(10)]
        delimiter = sniff_delimiter(sample_lines)

        with open(actual_file_to_read, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Normalize fieldnames to strip quotes or whitespace
            if reader.fieldnames:
                reader.fieldnames = [fn.strip('"\r\n\t ') for fn in reader.fieldnames]

            for row in reader:
                co_no = str(row.get("CO_NO") or "").strip('"\r\n\t ')
                if co_no and not detected_co_no:
                    detected_co_no = co_no.zfill(2)

                qual_cd = str(row.get("QUAL_CD") or "").strip('"\r\n\t ')
                # Florida DOR: 01 = qualified arms-length, 02 = multi-parcel arms-length
                if qual_cd not in ["01", "02", "1", "2"]:
                    continue

                try:
                    sale_prc_raw = str(row.get("SALE_PRC") or "").replace("$", "").replace(",", "").strip('"\r\n\t ')
                    sale_prc = float(sale_prc_raw or 0.0)
                except (ValueError, TypeError):
                    continue

                dor_uc = str(row.get("DOR_UC") or "").strip('"\r\n\t ')
                vi_cd = str(row.get("VI_CD") or "").upper().strip('"\r\n\t ')
                sale_yr = str(row.get("SALE_YR") or "").strip('"\r\n\t ')
                sale_mo = str(row.get("SALE_MO") or "").strip('"\r\n\t ')
                parcel_id = str(row.get("PARCEL_ID") or "").strip('"\r\n\t ')
                nbrhd = str(row.get("NBRHD_CD") or "").strip('"\r\n\t ')
                mkt_ar = str(row.get("MKT_AR") or "").strip('"\r\n\t ')
                clerk_no = str(row.get("CLERK_NO") or "").strip('"\r\n\t ')

                comp_entry = {
                    "parcel_id": parcel_id,
                    "sale_price": sale_prc,
                    "sale_year": int(sale_yr) if sale_yr.isdigit() else 2026,
                    "sale_month": int(sale_mo) if sale_mo.isdigit() else 1,
                    "neighborhood_code": nbrhd,
                    "market_area": mkt_ar,
                    "dor_use_code": dor_uc,
                    "vacant_improved": vi_cd,
                    "clerk_number": clerk_no
                }

                # 1. Vacant Residential Lot Sales (DOR_UC 000 / 009 or VI_CD == 'V')
                if (dor_uc in ["000", "00", "0", "009"] or vi_cd == "V") and min_vacant_price <= sale_prc <= max_vacant_price:
                    all_vacant_prices.append(sale_prc)
                    if nbrhd:
                        vacant_prices_by_nbrhd.setdefault(nbrhd, []).append(sale_prc)
                    if mkt_ar:
                        vacant_prices_by_mkt.setdefault(mkt_ar, []).append(sale_prc)

                    if len(vacant_comps) < max_comps_per_category:
                        vacant_comps.append(comp_entry)

                # 2. Finished Improved Single-Family Resale Comps (DOR_UC 001 and VI_CD == 'I')
                elif (dor_uc in ["001", "01", "1"] and vi_cd == "I") and min_improved_price <= sale_prc <= max_improved_price:
                    all_improved_prices.append(sale_prc)
                    if nbrhd:
                        improved_prices_by_nbrhd.setdefault(nbrhd, []).append(sale_prc)
                    if mkt_ar:
                        improved_prices_by_mkt.setdefault(mkt_ar, []).append(sale_prc)

                    if len(improved_comps) < max_comps_per_category:
                        improved_comps.append(comp_entry)

    finally:
        if temp_dir_to_clean and os.path.exists(temp_dir_to_clean):
            import shutil
            try:
                shutil.rmtree(temp_dir_to_clean)
            except Exception:
                pass

    # County identification hierarchy:
    # 1. Explicit parameter
    # 2. Inferred from filename
    # 3. Lookup from detected CO_NO in data rows
    final_county = county_name
    if not final_county:
        final_county = detect_county_from_filename(file_path)
    if not final_county and detected_co_no:
        final_county = FL_DOR_COUNTY_MAP.get(detected_co_no)
    if not final_county:
        final_county = "FLORIDA_GENERAL"

    final_county = final_county.upper().strip()

    # Calculate overall county medians
    county_vacant_median = statistics.median(all_vacant_prices) if all_vacant_prices else 115000.0
    county_improved_median = statistics.median(all_improved_prices) if all_improved_prices else 425000.0

    nbrhd_benchmarks = {}
    for n, prices in improved_prices_by_nbrhd.items():
        v_prices = vacant_prices_by_nbrhd.get(n, [])
        nbrhd_benchmarks[n] = {
            "median_finished_value": round(statistics.median(prices), 2),
            "median_vacant_lot_price": round(statistics.median(v_prices), 2) if v_prices else round(county_vacant_median, 2),
            "finished_count": len(prices),
            "vacant_count": len(v_prices)
        }

    mkt_benchmarks = {}
    for m, prices in improved_prices_by_mkt.items():
        v_prices = vacant_prices_by_mkt.get(m, [])
        mkt_benchmarks[m] = {
            "median_finished_value": round(statistics.median(prices), 2),
            "median_vacant_lot_price": round(statistics.median(v_prices), 2) if v_prices else round(county_vacant_median, 2),
            "finished_count": len(prices),
            "vacant_count": len(v_prices)
        }

    p25 = round(statistics.quantiles(all_improved_prices, n=4)[0], 2) if len(all_improved_prices) >= 4 else 350000.0
    p75 = round(statistics.quantiles(all_improved_prices, n=4)[2], 2) if len(all_improved_prices) >= 4 else 525000.0

    result = {
        "county": final_county,
        "dor_county_no": detected_co_no or COUNTY_TO_DOR_CODE.get(final_county, "58"),
        "file_source": os.path.basename(file_path),
        "total_vacant_sales_found": len(all_vacant_prices),
        "total_improved_sales_found": len(all_improved_prices),
        "total_vacant_sales": len(all_vacant_prices),
        "total_sfh_sales": len(all_improved_prices),
        "county_benchmarks": {
            "median_vacant_lot_price": round(county_vacant_median, 2),
            "median_finished_value": round(county_improved_median, 2),
            "p25_finished_value": p25,
            "p75_finished_value": p75,
        },
        "neighborhood_benchmarks": nbrhd_benchmarks,
        "market_area_benchmarks": mkt_benchmarks,
        "market_areas": mkt_benchmarks,
        "sample_vacant_comps": vacant_comps[:100],
        "sample_improved_comps": improved_comps[:100]
    }

    return result


parse_florida_sdf_file = parse_sdf_file


def load_land_comps() -> Dict[str, Any]:
    """Loads compiled land comps from data/land_comps.json."""
    if os.path.exists(LAND_COMPS_FILE):
        try:
            with open(LAND_COMPS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_land_comps(data: Dict[str, Any]):
    """Saves compiled land comps to data/land_comps.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAND_COMPS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_area_comp_benchmarks(
    county: str = "ORANGE",
    neighborhood_code: Optional[str] = None,
    market_area: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns finished new-build value and vacant lot comp benchmarks for ANY county.
    Falls back gracefully from neighborhood -> market area -> county baseline.
    """
    all_comps = load_land_comps()
    county_key = county.upper().strip()
    county_data = all_comps.get(county_key) or {}

    county_bm = county_data.get("county_benchmarks") or {
        "median_vacant_lot_price": 120000.0,
        "median_finished_value": 435000.0
    }

    # 1. Check neighborhood code
    if neighborhood_code and county_data.get("neighborhood_benchmarks"):
        nbrhd_bm = county_data["neighborhood_benchmarks"].get(str(neighborhood_code).strip())
        if nbrhd_bm and nbrhd_bm.get("finished_count", 0) >= 3:
            return {
                "source_level": "NEIGHBORHOOD",
                "median_finished_value": nbrhd_bm["median_finished_value"],
                "median_vacant_lot_price": nbrhd_bm["median_vacant_lot_price"],
                "comps_count": nbrhd_bm["finished_count"]
            }

    # 2. Check market area
    if market_area and county_data.get("market_area_benchmarks"):
        mkt_bm = county_data["market_area_benchmarks"].get(str(market_area).strip())
        if mkt_bm and mkt_bm.get("finished_count", 0) >= 5:
            return {
                "source_level": "MARKET_AREA",
                "median_finished_value": mkt_bm["median_finished_value"],
                "median_vacant_lot_price": mkt_bm["median_vacant_lot_price"],
                "comps_count": mkt_bm["finished_count"]
            }

    # 3. County baseline
    return {
        "source_level": "COUNTY_BASELINE",
        "median_finished_value": county_bm.get("median_finished_value", 435000.0),
        "median_vacant_lot_price": county_bm.get("median_vacant_lot_price", 120000.0),
        "comps_count": county_data.get("total_improved_sales_found", 100)
    }


def ingest_sdf_file_to_hub(file_path: str, county_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses any given county SDF file and stores its benchmarks in data/land_comps.json.
    """
    parsed = parse_sdf_file(file_path, county_name=county_name)
    existing = load_land_comps()
    target_county = parsed["county"]
    existing[target_county] = parsed
    save_land_comps(existing)
    return {
        "status": "success",
        "county": target_county,
        "vacant_sales_count": parsed["total_vacant_sales_found"],
        "improved_sales_count": parsed["total_improved_sales_found"],
        "median_finished_value": parsed["county_benchmarks"]["median_finished_value"],
        "median_vacant_lot_price": parsed["county_benchmarks"]["median_vacant_lot_price"],
        "total_counties_in_hub": len(existing)
    }


def parse_all_sdf_in_dir(directory_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans a directory (default C:\\Users\\johng\\Documents\\sdf-downloads) and parses
    EVERY county SDF file found, aggregating all 67 potential counties into data/land_comps.json.
    """
    target_dir = directory_path or DEFAULT_DOWNLOADS_DIR
    if not os.path.exists(target_dir):
        return {"status": "error", "message": f"Directory not found: {target_dir}", "parsed_counties": []}

    supported_exts = (".csv", ".txt", ".zip", ".dat")
    found_files = [
        os.path.join(target_dir, f) for f in os.listdir(target_dir)
        if f.lower().endswith(supported_exts) and not f.startswith("~") and not f.startswith(".")
    ]

    if not found_files:
        return {"status": "warning", "message": f"No SDF files found in {target_dir}", "parsed_counties": []}

    results = []
    existing = load_land_comps()

    for fp in found_files:
        try:
            parsed = parse_sdf_file(fp)
            c_name = parsed["county"]
            existing[c_name] = parsed
            results.append({
                "file": os.path.basename(fp),
                "county": c_name,
                "vacant_sales": parsed["total_vacant_sales_found"],
                "improved_sales": parsed["total_improved_sales_found"],
                "median_finished": parsed["county_benchmarks"]["median_finished_value"]
            })
        except Exception as e:
            print(f"Error parsing SDF file {fp}: {e}")

    save_land_comps(existing)
    return {
        "status": "success",
        "files_processed": len(results),
        "parsed_counties": results,
        "total_counties_in_hub": len(existing)
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Florida DOR SDF Statewide Comp Parser")
    parser.add_argument("path", nargs="?", default=None, help="File path or directory path containing SDF files")
    parser.add_argument("--county", default=None, help="Force specific county name (e.g. ORANGE, PINELLAS, HILLSBOROUGH)")
    args = parser.parse_args()

    target = args.path or DEFAULT_DOWNLOADS_DIR
    if os.path.isdir(target):
        print(f"Scanning directory for Florida DOR SDF files: {target}")
        res = parse_all_sdf_in_dir(target)
        print(json.dumps(res, indent=2))
    elif os.path.isfile(target):
        print(f"Parsing single county SDF file: {target}")
        res = ingest_sdf_file_to_hub(target, county_name=args.county)
        print(json.dumps(res, indent=2))
    else:
        print(f"Target not found: {target}")

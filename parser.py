"""
parser.py — Parse all real VisualSim PlotML (.plt) and text (.txt) output files.
Handles time-series datasets and bar-graph datasets from Corelink CMN Cyprus Hackathon.

REAL DATA STRUCTURE (verified from actual files):
  - RXDAT/RXRSP:  64 datasets, named RND_x / RNI_x / RNF_x / CCG_x
  - RXSNP:        64 datasets, names are empty strings (positional)
  - E2E/Network latency: 1 dataset per file, name is empty string
  - Buffer Occupancy: 0 datasets (instrumentation not enabled in model)
  - ArchitectureStats.txt: Cache_SLC, MC_DRAM, CMN600, CXL, PCIe stats
"""
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)


# ── PLT parser ────────────────────────────────────────────────────────────────

def parse_plt(filepath: Path) -> dict:
    """
    Parse a VisualSim PlotML file.
    Returns dict: {title, xlabel, ylabel, datasets: list of {name, points: DataFrame(x,y)}}
    Handles both named datasets (RXDAT/RXRSP) and unnamed datasets (latency files).
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        log.warning(f"XML parse error in {filepath.name}: {e}")
        return {"title": filepath.stem, "xlabel": "", "ylabel": "", "datasets": []}

    title  = root.findtext("title",  default=filepath.stem)
    xlabel = root.findtext("xLabel", default="")
    ylabel = root.findtext("yLabel", default="")
    datasets = []

    for idx, ds in enumerate(root.findall("dataset")):
        raw_name = ds.get("name", "")
        # For unnamed datasets, derive name from file context or use positional index
        name = raw_name if raw_name.strip() else f"system"

        pts = []
        for tag in ["m", "p"]:
            for pt in ds.findall(tag):
                try:
                    x = float(pt.get("x"))
                    y = float(pt.get("y"))
                    pts.append((x, y))
                except (TypeError, ValueError):
                    pass

        if pts:
            df = (pd.DataFrame(pts, columns=["x", "y"])
                    .drop_duplicates("x")
                    .sort_values("x")
                    .reset_index(drop=True))
            datasets.append({"name": name, "points": df})

    return {"title": title, "xlabel": xlabel, "ylabel": ylabel, "datasets": datasets}


# ── ArchitectureStats parser ──────────────────────────────────────────────────

def parse_architecture_stats(filepath: Path) -> dict:
    """
    Parse the rich ArchitectureStats.txt file.
    Extracts:
      - Per-component CMN600 latency (RNF, RNI, RND, CCG)
      - Cache SLC statistics (hit ratio, buffer occupancy, overflow, latency)
      - DRAM controller statistics (requests, throughput, bank usage)
      - CXL link statistics (throughput, drop counts, latency)
      - PCIe switch statistics (port throughput, latency)
      - CMN600 router buffer occupancy (8x8 mesh)
    """
    text = filepath.read_text(errors="ignore")

    # Use the LAST occurrence (500us = end of simulation = most complete data)
    # Split on simulation time markers and take the last block
    blocks = re.split(r"------ \d+\.?\d* us ------", text)
    final_block = blocks[-1] if blocks else text

    result = {}

    # ── CMN600 per-component latency ──────────────────────────────────────────
    cmn_lat = {}
    pat = re.compile(
        r"CMN600_(\w+)_Max_End_to_End_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CMN600_\1_Max_Network_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CMN600_\1_Mean_End_to_End_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CMN600_\1_Mean_Network_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CMN600_\1_Min_End_to_End_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CMN600_\1_Min_Network_Latency\s*=\s*([\d.E+\-]+)",
        re.DOTALL
    )
    for m in pat.finditer(final_block):
        comp = m.group(1)
        cmn_lat[comp] = {
            "max_e2e_us":      float(m.group(2)) * 1e6,
            "max_net_ns":      float(m.group(3)) * 1e9,
            "mean_e2e_us":     float(m.group(4)) * 1e6,
            "mean_net_ns":     float(m.group(5)) * 1e9,
            "min_e2e_us":      float(m.group(6)) * 1e6,
            "min_net_ns":      float(m.group(7)) * 1e9,
        }
    result["cmn_component_latency"] = cmn_lat
    log.info(f"Parsed {len(cmn_lat)} CMN600 component latency entries")

    # ── Cache SLC stats ───────────────────────────────────────────────────────
    cache_stats = {}
    # Find all Cache_SLC_N blocks in final block
    for m in re.finditer(
        r"Cache_SLC_(\d+)_A_Hit_Ratio\s*=\s*([\d.E+\-]+).*?"
        r"Cache_SLC_\1_A_Miss_Ratio\s*=\s*([\d.E+\-]+).*?"
        r"Cache_SLC_\1_A_Number_Entered\s*=\s*(\d+).*?"
        r"Cache_SLC_\1_Buffer_Occupancy\s*=\s*(\d+).*?"
        r"Cache_SLC_\1_Buffer_Overflow\s*=\s*(\d+).*?"
        r"Cache_SLC_\1_Latency_Avg\s*=\s*([\d.E+\-]+).*?"
        r"Cache_SLC_\1_Latency_Max\s*=\s*([\d.E+\-]+).*?"
        r"Cache_SLC_\1_Total_MBs\s*=\s*([\d.E+\-]+).*?"
        r"Cache_SLC_\1_Total_MBs_per_Second\s*=\s*([\d.E+\-]+)",
        final_block, re.DOTALL
    ):
        n = int(m.group(1))
        cache_stats[n] = {
            "hit_ratio_pct":    float(m.group(2)),
            "miss_ratio_pct":   float(m.group(3)),
            "entries":          int(m.group(4)),
            "buffer_occupancy": int(m.group(5)),
            "buffer_overflow":  int(m.group(6)),
            "avg_latency_us":   float(m.group(7)) * 1e6,
            "max_latency_us":   float(m.group(8)) * 1e6,
            "total_mbs":        float(m.group(9)),
            "throughput_mbps":  float(m.group(10)),
        }
    result["cache_slc"] = cache_stats
    log.info(f"Parsed {len(cache_stats)} Cache_SLC entries")

    # ── DRAM controller stats ─────────────────────────────────────────────────
    dram_stats = {}
    for m in re.finditer(
        r"MC_DRAM_DRAM_(\d+)_00_Total_Requests\s*=\s*(\d+).*?"
        r"MC_DRAM_DRAM_\1_01_Completed_Requests\s*=\s*(\d+).*?"
        r"MC_DRAM_DRAM_\1_02_Total_MB_per_Second\s*=\s*([\d.E+\-]+).*?"
        r"MC_DRAM_DRAM_\1_08_Read_Requests\s*=\s*(\d+).*?"
        r"MC_DRAM_DRAM_\1_10_Max_Queue_Usage\s*=\s*(\d+)",
        final_block, re.DOTALL
    ):
        n = int(m.group(1))
        dram_stats[n] = {
            "total_requests":    int(m.group(2)),
            "completed":         int(m.group(3)),
            "throughput_mbps":   float(m.group(4)),
            "read_requests":     int(m.group(5)),
            "max_queue_usage":   int(m.group(6)),
        }
        # Bank parallelism check (single-bank concentration = Bug)
        bank_pat = re.search(
            rf"MC_DRAM_DRAM_{n}_17_Reads_Per_Bank\s*=\s*\{{([^}}]+)\}}",
            final_block
        )
        if bank_pat:
            bank_vals = [int(v.strip()) for v in bank_pat.group(1).split(",") if v.strip().isdigit()]
            total_reads = sum(bank_vals)
            bank0_reads = bank_vals[0] if bank_vals else 0
            dram_stats[n]["bank0_concentration_pct"] = (
                (bank0_reads / total_reads * 100) if total_reads > 0 else 0
            )
            dram_stats[n]["active_banks"] = sum(1 for b in bank_vals if b > 0)

    result["dram"] = dram_stats
    log.info(f"Parsed {len(dram_stats)} DRAM controller entries")

    # ── CXL link stats ────────────────────────────────────────────────────────
    cxl_stats = {}
    for m in re.finditer(
        r"CXL_CXL_(\d+)_Port_1_CXL_cache_mem_Drop_Count\s*=\s*(\d+).*?"
        r"CXL_CXL_\1_Port_1_CXL_cache_mem_Rx_MBps\s*=\s*([\d.E+\-]+).*?"
        r"CXL_CXL_\1_Port_1_CXL_cache_mem_Tx_MBps\s*=\s*([\d.E+\-]+).*?"
        r"CXL_RC_CXL_\1_Port_1_to_Port_2_CXL_cache_mem_Max_Latency\s*=\s*([\d.E+\-]+).*?"
        r"CXL_RC_CXL_\1_Port_1_to_Port_2_CXL_cache_mem_Mean_Latency\s*=\s*([\d.E+\-]+)",
        final_block, re.DOTALL
    ):
        n = int(m.group(1))
        cxl_stats[n] = {
            "port1_drop_count":  int(m.group(2)),
            "port1_rx_mbps":     float(m.group(3)),
            "port1_tx_mbps":     float(m.group(4)),
            "max_latency_us":    float(m.group(5)) * 1e6,
            "mean_latency_us":   float(m.group(6)) * 1e6,
        }
    result["cxl"] = cxl_stats
    log.info(f"Parsed {len(cxl_stats)} CXL link entries")

    # ── PCIe switch stats ─────────────────────────────────────────────────────
    pcie_stats = {}
    for m in re.finditer(
        r"PCIe_Switch_PCIe_Switch_(\d+)_Port_10_Rx_GBps\s*=\s*([\d.E+\-]+).*?"
        r"PCIe_Switch_PCIe_Switch_\1_Port_10_Rx_Useful_GBps\s*=\s*([\d.E+\-]+).*?"
        r"PCIe_Switch_PCIe_Switch_\1_Port_10_Total_Flits_Received\s*=\s*(\d+).*?"
        r"PCIe_Switch_PCIe_Switch_\1_Port_10_Total_Flits_Sent\s*=\s*(\d+).*?"
        r"PCIe_Switch_PCIe_Switch_\1_Port_10_to_Port_4_Max_Latency\s*=\s*([\d.E+\-]+).*?"
        r"PCIe_Switch_PCIe_Switch_\1_Port_10_to_Port_4_Mean_Latency\s*=\s*([\d.E+\-]+)",
        final_block, re.DOTALL
    ):
        n = int(m.group(1))
        rx_gbps      = float(m.group(2))
        useful_gbps  = float(m.group(3))
        pcie_stats[n] = {
            "rx_gbps":          rx_gbps,
            "useful_rx_gbps":   useful_gbps,
            "efficiency_pct":   (useful_gbps / rx_gbps * 100) if rx_gbps > 0 else 0,
            "flits_received":   int(m.group(4)),
            "flits_sent":       int(m.group(5)),
            "max_latency_ns":   float(m.group(6)) * 1e9,
            "mean_latency_ns":  float(m.group(7)) * 1e9,
        }
    result["pcie"] = pcie_stats
    log.info(f"Parsed {len(pcie_stats)} PCIe switch entries")

    # ── CMN600 router buffer occupancy (8x8 mesh) ────────────────────────────
    buf_occ = {}
    for m in re.finditer(
        r"CMN600_R_(\d+)_(\d+)_(EAST|NORTH|SOUTH|WEST)_In_Buffer_Max_Buffer_Occupancy\s*=\s*([\d.]+)",
        final_block
    ):
        row, col, direction = int(m.group(1)), int(m.group(2)), m.group(3)
        occ = float(m.group(4))
        key = (row, col)
        if key not in buf_occ:
            buf_occ[key] = {}
        buf_occ[key][direction] = occ
    result["router_buffer_occupancy"] = buf_occ
    log.info(f"Parsed {len(buf_occ)} CMN600 router buffer entries")

    return result


# ── Network source list parser ────────────────────────────────────────────────

def parse_network_src_list(filepath: Path) -> list:
    """Parse network source list text file, returns ordered list of component names."""
    text = filepath.read_text(errors="ignore")
    names = re.findall(r'"([^"]+)"', text)
    return names


# ── Master loader ─────────────────────────────────────────────────────────────

def load_all(uploads_dir: Path) -> dict:
    """
    Load all VisualSim output files from the uploads directory.
    Returns a structured dict with all parsed data.
    """
    d = Path(uploads_dir)
    result = {}

    # PLT file map — keyed by semantic name
    plt_map = {
        "rxdat":        "Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXDAT_Bps.plt",
        "rxrsp":        "Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXRSP_Bps.plt",
        "rxsnp":        "Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXSNP_Bps.plt",
        "buf_east":     "Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_East.plt",
        "buf_north":    "Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_North.plt",
        "buf_south":    "Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_South.plt",
        "buf_west":     "Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_West.plt",
        "max_e2e":      "Corelink_CMN_Cyprus_Hackathon_Stats_Max_End_to_End_Latency.plt",
        "min_e2e":      "Corelink_CMN_Cyprus_Hackathon_Stats_Min_End_to_End_Latency.plt",
        "mean_e2e":     "Corelink_CMN_Cyprus_Hackathon_Stats_Mean_End_to_End_Latency.plt",
        "max_net_lat":  "Corelink_CMN_Cyprus_Hackathon_Stats_Max_Network_Latency.plt",
        "min_net_lat":  "Corelink_CMN_Cyprus_Hackathon_Stats_Min_Network_Latency.plt",
        "mean_net_lat": "Corelink_CMN_Cyprus_Hackathon_Stats_Mean_Network_Latency.plt",
    }

    for key, fname in plt_map.items():
        fpath = d / fname
        if fpath.exists():
            result[key] = parse_plt(fpath)
            n = len(result[key]["datasets"])
            log.info(f"Loaded {key}: {n} dataset(s) from {fname}")
        else:
            log.warning(f"Missing PLT file: {fname}")
            result[key] = {"title": key, "xlabel": "", "ylabel": "", "datasets": []}

    # Architecture stats (primary rich data source)
    arch_path = d / "Corelink_CMN_Cyprus_Hackathon_ArchitectureStats.txt"
    if arch_path.exists():
        result["arch_stats"] = parse_architecture_stats(arch_path)
    else:
        log.warning("Missing: ArchitectureStats.txt — many analyses will be unavailable")
        result["arch_stats"] = {}

    # Network source list
    src_path = d / "Corelink_CMN_Cyprus_Hackathon_Stats_Network_Src_List.txt"
    if src_path.exists():
        result["network_sources"] = parse_network_src_list(src_path)
        log.info(f"Loaded network sources: {len(result['network_sources'])} components")
    else:
        result["network_sources"] = []

    return result


# ── Summary table builder ─────────────────────────────────────────────────────

def _classify_component(name: str) -> str:
    """Classify a CMN component name into its type."""
    prefixes = {"RNF": "RNF", "RND": "RND", "RNI": "RNI",
                "CCG": "CCG", "HNS": "HNS", "SN_": "SNF"}
    for prefix, ctype in prefixes.items():
        if name.startswith(prefix):
            return ctype
    return "OTHER"


def summarise_datasets(data: dict) -> pd.DataFrame:
    """
    Build a comprehensive per-component summary table from all data sources.

    Priority of latency data:
      1. CMN600 per-component stats from ArchitectureStats.txt (most accurate)
      2. PLT file datasets (RXDAT/RXRSP peaks)

    Returns DataFrame with columns:
      component, type, max_e2e_us, mean_e2e_us, min_e2e_us,
      max_net_ns, mean_net_ns, rxdat_peak_gbps, rxrsp_peak_gbps, tx_count
    """
    rows = {}

    # ── Primary: CMN600 per-component latency from ArchStats ──────────────────
    arch = data.get("arch_stats", {})
    cmn_lat = arch.get("cmn_component_latency", {})

    for comp, lat in cmn_lat.items():
        rows[comp] = {
            "component":      comp,
            "type":           _classify_component(comp),
            "max_e2e_us":     round(lat["max_e2e_us"], 4),
            "mean_e2e_us":    round(lat["mean_e2e_us"], 4),
            "min_e2e_us":     round(lat["min_e2e_us"], 4),
            "max_net_ns":     round(lat["max_net_ns"], 4),
            "mean_net_ns":    round(lat["mean_net_ns"], 4),
            "rxdat_peak_gbps": 0.0,
            "rxrsp_peak_gbps": 0.0,
            "tx_count":        0,
        }

    # ── RXDAT throughput peaks per component ──────────────────────────────────
    for ds in data.get("rxdat", {}).get("datasets", []):
        name = ds["name"]
        peak = round(ds["points"]["y"].max() / 1e9, 4)
        if name in rows:
            rows[name]["rxdat_peak_gbps"] = peak
            rows[name]["tx_count"] = max(rows[name]["tx_count"], len(ds["points"]))
        else:
            rows[name] = {
                "component":       name,
                "type":            _classify_component(name),
                "max_e2e_us":      0.0,
                "mean_e2e_us":     0.0,
                "min_e2e_us":      0.0,
                "max_net_ns":      0.0,
                "mean_net_ns":     0.0,
                "rxdat_peak_gbps": peak,
                "rxrsp_peak_gbps": 0.0,
                "tx_count":        len(ds["points"]),
            }

    # ── RXRSP throughput peaks per component ──────────────────────────────────
    for ds in data.get("rxrsp", {}).get("datasets", []):
        name = ds["name"]
        peak = round(ds["points"]["y"].max() / 1e9, 4)
        if name in rows:
            rows[name]["rxrsp_peak_gbps"] = peak
        elif name:
            rows[name] = {
                "component":       name,
                "type":            _classify_component(name),
                "max_e2e_us":      0.0,
                "mean_e2e_us":     0.0,
                "min_e2e_us":      0.0,
                "max_net_ns":      0.0,
                "mean_net_ns":     0.0,
                "rxdat_peak_gbps": 0.0,
                "rxrsp_peak_gbps": peak,
                "tx_count":        0,
            }

    if not rows:
        log.warning("summarise_datasets: no data found — returning empty table")
        return pd.DataFrame(columns=[
            "component", "type", "max_e2e_us", "mean_e2e_us", "min_e2e_us",
            "max_net_ns", "mean_net_ns", "rxdat_peak_gbps", "rxrsp_peak_gbps", "tx_count"
        ])

    df = pd.DataFrame(list(rows.values())).fillna(0.0)
    df = df.sort_values("max_e2e_us", ascending=False).reset_index(drop=True)
    log.info(f"Summary table: {len(df)} components")
    return df


# ── Convenience getters ───────────────────────────────────────────────────────

def get_e2e_latency_series(data: dict) -> dict:
    """
    Return min/mean/max E2E latency time series as DataFrames (x in µs, y in µs).
    """
    out = {}
    for key in ["min_e2e", "mean_e2e", "max_e2e"]:
        ds_list = data.get(key, {}).get("datasets", [])
        if ds_list:
            pts = ds_list[0]["points"].copy()
            pts["x"] = pts["x"] * 1e6
            pts["y"] = pts["y"] * 1e6
            out[key] = pts
    return out


def get_network_latency_series(data: dict) -> dict:
    """Return min/mean/max network latency series (x=index, y in ns)."""
    out = {}
    for key in ["min_net_lat", "mean_net_lat", "max_net_lat"]:
        ds_list = data.get(key, {}).get("datasets", [])
        if ds_list:
            pts = ds_list[0]["points"].copy()
            pts["y"] = pts["y"] * 1e9
            out[key] = pts
    return out


def get_rxdat_summary(data: dict) -> pd.DataFrame:
    """Return peak RXDAT throughput per component, sorted descending."""
    rows = []
    for ds in data.get("rxdat", {}).get("datasets", []):
        if ds["name"]:
            rows.append({
                "component":     ds["name"],
                "type":          _classify_component(ds["name"]),
                "peak_gbps":     ds["points"]["y"].max() / 1e9,
                "mean_gbps":     ds["points"]["y"].mean() / 1e9,
                "n_samples":     len(ds["points"]),
            })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
              .sort_values("peak_gbps", ascending=False)
              .reset_index(drop=True))


def get_rxrsp_summary(data: dict) -> pd.DataFrame:
    """Return peak RXRSP throughput per component, sorted descending."""
    rows = []
    for ds in data.get("rxrsp", {}).get("datasets", []):
        if ds["name"]:
            rows.append({
                "component":  ds["name"],
                "type":       _classify_component(ds["name"]),
                "peak_gbps":  ds["points"]["y"].max() / 1e9,
                "mean_gbps":  ds["points"]["y"].mean() / 1e9,
            })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
              .sort_values("peak_gbps", ascending=False)
              .reset_index(drop=True))


def get_mesh_buffer_heatmap(data: dict) -> pd.DataFrame:
    """
    Build 8x8 mesh buffer occupancy heatmap from ArchStats router data.
    Returns DataFrame with columns: row, col, max_occ, directions_active.
    """
    buf = data.get("arch_stats", {}).get("router_buffer_occupancy", {})
    if not buf:
        return pd.DataFrame()
    rows = []
    for (row, col), dirs in buf.items():
        max_occ = max(dirs.values()) if dirs else 0
        rows.append({
            "row": row, "col": col,
            "max_occ": max_occ,
            "east":  dirs.get("EAST", 0),
            "north": dirs.get("NORTH", 0),
            "south": dirs.get("SOUTH", 0),
            "west":  dirs.get("WEST", 0),
        })
    return pd.DataFrame(rows).sort_values(["row", "col"])
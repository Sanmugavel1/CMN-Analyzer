# CoreLink CMN Cyprus — Automated Analysis Framework

**Team El Shaddai · VisualSim Electronics Hackathon 2026 · Challenge 3**
*Data Visualization, Bottleneck Detection & Debugging*

---

## Bugs Found in the Real Data

The analysis engine detected **5 real bugs** in the provided simulation data:

| # | Severity | Component | Finding | Evidence |
|---|----------|-----------|---------|----------|
| 1 | 🔴 CRITICAL | `Cache_SLC_1` | Hotspot — 5.35× traffic vs all other SLC nodes | 115,094 entries vs ~21,500 average |
| 2 | 🔴 CRITICAL | `MC_DRAM_DRAM_*` | Bank non-parallelism — 100% reads to Bank 0 across all 12 DRAMs | Zero reads on Banks 1–15 |
| 3 | 🟠 HIGH | `CXL_*` (all 10 links) | Asymmetric drops — 3,894–4,017 drops on Port 1, zero on Port 2 | ~39,427 total drops; asymmetry = protocol bug |
| 4 | 🟠 HIGH | `PCIe_Switch_*` | Useful efficiency only ~12.5% | 0.64 GBps useful vs 5.12 GBps raw throughput |
| 5 | 🟡 MEDIUM | `MC_DRAM_DRAM_13` | Missing — no entry in ArchStats data | Likely failed to initialize during simulation |

---

## Folder Structure

```
CMN_Analyzer/
│
├── Graphs/                                          ← Pre-generated chart images (PNG)
│   ├── Cache SLC Buffer overflow Events.png
│   ├── Cache SLC total Entries - Hotspot Detection.png
│   ├── CMN00 8x8 Mesh- Max Router Buffer Occupancy.png
│   ├── CXL Link packet drop-Bug 3: Asymetric port drops.png
│   ├── DRAM controller Analysis -Bug 2:Single bank.png
│   ├── End-End latency over Simulation time(us).png
│   ├── Latency scatter max vs mean E2E per component.png
│   ├── Max E2E latency distribution by node type.png
│   ├── Network Latency over Simulation time(ns).png
│   ├── PCIE Switch Bandwidth BUG 4: 87.5% protocol overhead.png
│   ├── RXNSP channel throughput over time - Top.png
│   ├── Top 20 Components - max vs mean E2E latency.png
│   ├── Top 25-RXDAT channel peak throughput.png
│   └── Top 25-RXRSP channel peak throughput.png
│
├── outputs/
│   └── CMN_Cyprus_Analysis_Report_ElShaddai.pdf     ← Auto-generated PDF report
│
├── results/                                         ← Additional result exports
│
├── uploads/                                         ← ⚠ PUT ALL SIMULATION FILES HERE
│   ├── Corelink_CMN_Cyprus_Hackathon_ArchitectureStats.txt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXDAT_Bps.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXRSP_Bps.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Avg_Throughput_RXSNP_Bps.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_East.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_North.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_South.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Buffer_Occupancy_West.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Max_End_to_End_Latency.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Mean_End_to_End_Latency.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Min_End_to_End_Latency.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Max_Network_Latency.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Mean_Network_Latency.plt
│   ├── Corelink_CMN_Cyprus_Hackathon_Stats_Min_Network_Latency.plt
│   └── Corelink_CMN_Cyprus_Hackathon_Stats_Network_Src_List.txt
│
├── analyze.py           ← Bug detection + bottleneck scoring engine
├── app.py               ← Interactive Dash dashboard (8 tabs)
├── parser.py            ← .plt XML + ArchitectureStats.txt parser
├── report.py            ← PDF report generator (ReportLab)
└── run_pipeline.py      ← ONE-COMMAND ENTRY POINT — run this
```

> **Important:** All `.plt` and `.txt` simulation files must be inside the `uploads/` folder before running anything.

---

## Installation

### Requirements

- **Python 3.9 or higher**
- **pip** (comes bundled with Python)

Check your Python version:
```bash
python3 --version
```

---

### Install all required libraries — ONE command

```bash
pip install pandas numpy dash plotly reportlab
```

What each library does:

| Library | Purpose |
|---------|---------|
| `pandas` | Stores per-component metrics in structured tables |
| `numpy` | Normalization and composite scoring calculations |
| `dash` | Runs the interactive web dashboard |
| `plotly` | Renders all charts and graphs in the dashboard |
| `reportlab` | Generates the professional PDF analysis report |

---

### Verify everything installed correctly

```bash
python3 -c "import pandas, numpy, dash, plotly, reportlab; print('All libraries OK')"
```

Expected output:
```
All libraries OK
```

---

## How to Run

### Option 1 — Full pipeline: PDF report + Dashboard (RECOMMENDED)

```bash
cd CMN_Analyzer
python3 run_pipeline.py
```

This runs all 4 steps automatically:
1. Parses all files in `uploads/`
2. Detects bugs and bottlenecks
3. Prints color-coded findings in terminal
4. Saves PDF → `outputs/CMN_Cyprus_Analysis_Report_ElShaddai.pdf`
5. Opens dashboard → `http://127.0.0.1:8050`

---

### Option 2 — PDF report only (no browser window)

```bash
python3 run_pipeline.py --no-dashboard
```

---

### Option 3 — Dashboard only (no PDF)

```bash
python3 app.py
```

Then open your browser and go to: **http://127.0.0.1:8050**

---

### Option 4 — Custom port

```bash
python3 run_pipeline.py --port 8080
```

Then open: **http://127.0.0.1:8080**

---

### Option 5 — Custom data folder

```bash
python3 run_pipeline.py --uploads /path/to/your/folder
```

---

### All available options

```
python3 run_pipeline.py [OPTIONS]

  --no-dashboard        Export PDF only, skip launching the dashboard
  --port PORT           Port for the dashboard (default: 8050)
  --uploads PATH        Path to folder with .plt and .txt files
                        (default: ./uploads)
  -h, --help            Show help
```

---

## What You See in the Terminal

Running `python3 run_pipeline.py` prints this:

```
=================================================================
  CoreLink CMN Cyprus — Simulation Analyzer
  Team El Shaddai | VisualSim Hackathon 2026 | Challenge 3
=================================================================

INFO | Step 1/4 — Parsing simulation output files...
INFO |   Parsed 64 components | 64 RN source nodes
INFO |   CMN latency entries : 64
INFO |   Cache SLC entries   : 16
INFO |   DRAM controllers    : 12
INFO |   CXL links           : 10
INFO |   PCIe switches       : 4

INFO | Step 2/4 — Running automated analysis...
INFO |   Bottlenecks : 5
INFO |   Bugs        : 5
INFO |   Max E2E Lat : 39.71 µs

INFO | Step 3/4 — Analysis findings:

── SYSTEM KPIs ─────────────────────────────────────────
  Total RN Nodes       : 64
  Simulation Duration  : 500 µs
  System Max E2E Lat   : 39.71 µs
  Peak RXDAT           : 1.397 Gbps
  Cache SLC_1 Imbalance: 5.35×
  CXL Total Drops      : 39,427
  PCIe Efficiency      : 12.5%

── BUGS DETECTED (5) ────────────────────────────────────

  [CRITICAL]  Bug #1: Cache_SLC_1
  Metric   : entries
  Value    : 115094   |  Median: 21500   |  Ratio: 5.4×
  Evidence : Cache_SLC_1 received 115,094 entries vs system median...

  [CRITICAL]  Bug #2: MC_DRAM_DRAM (all 12)
  ...

── TOP BOTTLENECKS (5) ──────────────────────────────────
  [HIGH    ]  #1: RNF_27         Max: 39.71 µs  (8.23× median)
  [HIGH    ]  #2: RNI_2          Max:  7.70 µs  (1.60× median)
  ...

INFO | Step 4/4 — Generating PDF report...
INFO |   PDF saved: outputs/CMN_Cyprus_Analysis_Report_ElShaddai.pdf (312 KB)

=================================================================
  ✓ Analysis complete
  PDF report  → outputs/CMN_Cyprus_Analysis_Report_ElShaddai.pdf
  Dashboard   → http://127.0.0.1:8050
=================================================================
```

---

## Dashboard — 8 Tabs

After the pipeline runs, open **http://127.0.0.1:8050**:

| Tab | What It Shows |
|-----|--------------|
| **System Overview** | KPI summary cards: max latency, CXL drops, PCIe efficiency, cache imbalance. Bug severity breakdown. |
| **Latency** | Min/mean/max E2E latency over simulation time. Per-component latency bar chart. Histogram by node type. |
| **Throughput** | RXDAT + RXRSP peak throughput ranked by component. Time-series overlays for top 25 nodes. |
| **Bugs & Bottlenecks** | Composite bottleneck score chart for all 64 nodes. Bug cards with evidence, ratio, and fix recommendation. |
| **Cache & Memory** | SLC hit/miss ratios, entry imbalance heatmap (Bug 1), DRAM bank utilization (Bug 2). |
| **CXL & PCIe** | CXL drop asymmetry per link (Bug 3). PCIe useful vs raw throughput comparison (Bug 4). |
| **Data Explorer** | Full 64-node sortable and filterable table. Export to CSV. |
| **Upload** | Drag and drop new `.plt` or `.txt` files to reload data live without restarting the server. |

---

## PDF Report — 8 Sections

Saved to: `outputs/CMN_Cyprus_Analysis_Report_ElShaddai.pdf`

| Section | Contents |
|---------|---------|
| **Cover** | Title, team name, hackathon, date |
| **§1 Executive Summary** | KPI table, total bugs and bottlenecks found |
| **§2 Graph-by-Graph Analysis** | Written analysis of all 14 simulation charts |
| **§3 Bug Deep-Dives** | Root cause + system impact + fix for each of the 5 bugs |
| **§4 Bottleneck Analysis** | Ranked table with composite score breakdown per node |
| **§5 Component Ranking** | All 64 nodes sorted by max E2E latency |
| **§6 Recommendations** | Prioritized system-level optimization actions |
| **§7 Automation Framework** | How the pipeline works end-to-end |
| **§8 AI Prompt Engineering Log** | Prompts used, what was automated vs manual |

---

## Pre-generated Graphs (`Graphs/` folder)

These PNG files were exported directly from the dashboard and are included as standalone evidence for the submission:

| File | What It Shows |
|------|--------------|
| `Cache SLC Buffer overflow Events.png` | SLC buffer overflow counts across all SLC nodes |
| `Cache SLC total Entries - Hotspot Detection.png` | **Bug 1** — SLC_1 at 5.35× all other nodes |
| `CMN00 8x8 Mesh - Max Router Buffer Occupancy.png` | 8×8 NoC mesh heatmap of max router congestion |
| `CXL Link packet drop - Bug 3: Asymetric port drops.png` | **Bug 3** — Port 1 drops vs zero drops on Port 2 |
| `DRAM controller Analysis - Bug 2: Single bank.png` | **Bug 2** — 100% reads hitting Bank 0 only |
| `End-End latency over Simulation time(us).png` | E2E latency time-series — min, mean, max |
| `Latency scatter max vs mean E2E per component.png` | Scatter plot isolating RNF_27 outlier spike |
| `Max E2E latency distribution by node type.png` | Box plot grouped by node type (RNF/RNI/RND/CCG) |
| `Network Latency over Simulation time(ns).png` | Network-only latency time-series |
| `PCIE Switch Bandwidth BUG 4: 87.5% protocol overhead.png` | **Bug 4** — Only 12.5% of PCIe bandwidth is useful |
| `RXNSP channel throughput over time - Top.png` | Top RXSNP nodes throughput over simulation time |
| `Top 20 Components - max vs mean E2E latency.png` | Side-by-side comparison for top 20 nodes |
| `Top 25-RXDAT channel peak throughput.png` | Top 25 nodes ranked by RXDAT peak throughput |
| `Top 25-RXRSP channel peak throughput.png` | Top 25 nodes ranked by RXRSP peak throughput |

---

## How the Analysis Works

### Bottleneck Detection — Composite Weighted Scoring

Every node gets a normalized score across 4 metrics:

```
bottleneck_score =
    0.35 × norm(max_e2e_latency)      ← most important: worst-case stall
  + 0.30 × norm(mean_e2e_latency)     ← sustained congestion
  + 0.20 × norm(mean_network_latency) ← isolates fabric contribution
  + 0.15 × norm(peak_rxrsp_throughput)← response channel saturation
```

Top 5 nodes by composite score are flagged as bottlenecks.

### Bug Detection — Ratio-to-Median Analysis

A component is flagged as a bug when its metric is unusually far from the system median:

```
ratio = component_value / system_median

ratio > 5.0  →  CRITICAL
ratio > 3.0  →  HIGH
ratio > 1.5  →  MEDIUM
```

Every bug includes the exact value, system median, ratio, and raw evidence — so all findings are independently verifiable.

### Parser — Three File Formats

| File Type | Format | How It's Parsed |
|-----------|--------|----------------|
| `.plt` files | PlotML XML | `<dataset>` elements with `<m>` / `<p>` point tags |
| `ArchitectureStats.txt` | Free-text log | Regex on final timestamped block (500 µs) |
| `Network_Src_List.txt` | Quoted string list | Regex to resolve positional RXSNP datasets |

> The parser always reads the **last** timestamped block from ArchStats — this is the 500 µs end-of-simulation state where all queues have drained and metrics are stable.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'dash'`**
```bash
pip install dash plotly
```

**`ModuleNotFoundError: No module named 'reportlab'`**
```bash
pip install reportlab
```

**`WARNING | Missing PLT file: ...`**
Check that all `.plt` and `.txt` files are inside the `uploads/` folder with exact filenames.

**Dashboard shows blank / won't load**
Open manually: `http://127.0.0.1:8050`
If port is busy: `python3 run_pipeline.py --port 8051`

**PDF not generated, no error**
```bash
pip install reportlab
python3 run_pipeline.py --no-dashboard
```

**On Linux / Ubuntu — pip not found**
```bash
sudo apt install python3-pip
pip3 install pandas numpy dash plotly reportlab
python3 run_pipeline.py
```

**On Windows — use `python` instead of `python3`**
```bash
python -m pip install pandas numpy dash plotly reportlab
python run_pipeline.py
```

**On macOS — permission error**
```bash
pip install --user pandas numpy dash plotly reportlab
python3 run_pipeline.py
```

---

## AI Usage Summary

Full prompt log is in **§8 of the PDF report**. Summary:

| Task | AI Role | Human Role |
|------|---------|-----------|
| CMN-600 architecture | Explained CHI protocol, XP mesh, RN/HN node types | Verified against VisualSim model structure |
| Parser regex | Suggested initial patterns for ArchStats format | Debugged on real files, fixed unit conversions (s → µs/ns) |
| Bottleneck score weights | Proposed equal-weight baseline | Tuned for CMN-fabric-specific behavior |
| Bug hypothesis | Flagged statistical anomalies | Validated each against domain knowledge |
| Dashboard layout | Generated Dash boilerplate | Redesigned tab structure for architect workflow |
| PDF report text | Drafted section narratives | Rewrote root-cause sections with specific numeric evidence |
| Recommendations | Suggested generic CHI optimizations | Filtered and ranked by relevance to bugs actually found |

**Principle:** AI was used to accelerate pattern recognition and code generation. Every finding was validated by cross-referencing the raw data numbers directly.

---

## Team

**Team El Shaddai** — VisualSim Electronics Hackathon 2026
Challenge 3: Data Visualization, Bottleneck Detection & Debugging
"""
run_pipeline.py — One-command pipeline for CMN Cyprus analysis.
Team El Shaddai | VisualSim Hackathon 2026 | Challenge 3

Steps:
  1. Parse all .plt and .txt simulation output files
  2. Run automated analysis (bottlenecks + bugs + KPIs)
  3. Print findings summary to console
  4. Export professional PDF report
  5. Launch interactive Dash dashboard

Usage:
    python3 run_pipeline.py
    python3 run_pipeline.py --no-dashboard    (export PDF only, skip dashboard)
    python3 run_pipeline.py --port 8080       (custom dashboard port)
"""
import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR  = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Severity color codes for terminal output ───────────────────────────────────
RED    = "\033[91m"
ORANGE = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEV_COLOR = {
    "critical": RED,
    "high":     ORANGE,
    "medium":   "\033[33m",
    "info":     CYAN,
}


def print_banner():
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  CoreLink CMN Cyprus — Simulation Analyzer{RESET}")
    print(f"  Team El Shaddai | VisualSim Hackathon 2026 | Challenge 3")
    print(f"{BOLD}{'='*65}{RESET}\n")


def print_findings(report: dict):
    bugs  = report["bugs"]
    bots  = report["bottlenecks"]
    kpis  = report["kpis"]

    # ── KPI Summary ────────────────────────────────────────────────────────────
    print(f"{BOLD}{CYAN}── SYSTEM KPIs ─────────────────────────────────────────{RESET}")
    print(f"  Total RN Nodes       : {kpis.get('total_rn_nodes', '-')}")
    print(f"  Simulation Duration  : 500 µs")
    print(f"  System Max E2E Lat   : {kpis.get('system_max_latency_us', '-')} µs")
    print(f"  System Mean E2E Lat  : {kpis.get('mean_e2e_latency_us', '-')} µs")
    print(f"  Peak RXDAT           : {kpis.get('peak_rxdat_gbps', '-')} Gbps")
    print(f"  Peak RXRSP           : {kpis.get('peak_rxrsp_gbps', '-')} Gbps")
    print(f"  Cache SLC_1 Imbalance: {kpis.get('cache_slc1_imbalance', '-')}×")
    print(f"  CXL Total Drops      : {kpis.get('cxl_total_drops', 0):,}")
    print(f"  PCIe Efficiency      : {kpis.get('pcie_avg_efficiency', '-'):.1f}%")

    # ── Bugs ───────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{RED}── BUGS DETECTED ({len(bugs)}) ──────────────────────────────────{RESET}")
    for i, bug in enumerate(bugs, 1):
        col = SEV_COLOR.get(bug.severity, "")
        print(f"\n  {col}{BOLD}[{bug.severity.upper():8s}]{RESET}  Bug #{i}: {bug.component}")
        print(f"  Metric    : {bug.metric}")
        print(f"  Value     : {bug.value:.3f}  |  Median: {bug.system_median:.3f}  |  Ratio: {bug.ratio:.1f}×")
        # Print first 120 chars of evidence
        ev_short = bug.evidence[:150].replace("\n", " ")
        print(f"  Evidence  : {ev_short}...")

    # ── Bottlenecks ────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{ORANGE}── TOP BOTTLENECKS ({len(bots)}) ─────────────────────────────────{RESET}")
    for i, bn in enumerate(bots, 1):
        col = SEV_COLOR.get(bn.severity, "")
        print(f"  {col}[{bn.severity.upper():8s}]{RESET}  #{i}: {bn.component:20s}  "
              f"Max: {bn.value:.2f} µs  ({bn.ratio:.2f}× median)")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="CMN Cyprus Analysis Pipeline — Team El Shaddai"
    )
    parser.add_argument("--no-dashboard", action="store_true",
                        help="Export PDF only, do not launch dashboard")
    parser.add_argument("--port", type=int, default=8050,
                        help="Dashboard port (default: 8050)")
    parser.add_argument("--uploads", type=str, default=str(UPLOADS_DIR),
                        help="Path to uploads directory containing .plt and .txt files")
    args = parser.parse_args()

    uploads = Path(args.uploads)
    if not uploads.exists():
        log.error(f"Uploads directory not found: {uploads}")
        sys.exit(1)

    print_banner()

    # ── Step 1: Parse ──────────────────────────────────────────────────────────
    log.info("Step 1/4 — Parsing simulation output files...")
    from parser import load_all, summarise_datasets
    data    = load_all(uploads)
    summary = summarise_datasets(data)

    n_sources = len(data.get("network_sources", []))
    n_comp    = len(summary)
    log.info(f"  Parsed {n_comp} components | {n_sources} RN source nodes")

    arch = data.get("arch_stats", {})
    log.info(f"  CMN latency entries : {len(arch.get('cmn_component_latency', {}))}")
    log.info(f"  Cache SLC entries   : {len(arch.get('cache_slc', {}))}")
    log.info(f"  DRAM controllers    : {len(arch.get('dram', {}))}")
    log.info(f"  CXL links           : {len(arch.get('cxl', {}))}")
    log.info(f"  PCIe switches       : {len(arch.get('pcie', {}))}")

    # ── Step 2: Analyze ────────────────────────────────────────────────────────
    log.info("Step 2/4 — Running automated analysis...")
    from analyze import run_analysis
    report = run_analysis(data, summary)
    kpis   = report["kpis"]

    log.info(f"  Bottlenecks : {len(report['bottlenecks'])}")
    log.info(f"  Bugs        : {len(report['bugs'])}")
    log.info(f"  Trends      : {len(report.get('trends', []))}")
    log.info(f"  Max E2E Lat : {kpis.get('system_max_latency_us', '?')} µs")

    # ── Step 3: Print findings ─────────────────────────────────────────────────
    log.info("Step 3/4 — Analysis findings:")
    print_findings(report)

    # ── Step 4: Export PDF ────────────────────────────────────────────────────
    log.info("Step 4/4 — Generating PDF report...")
    try:
        from report import generate_pdf_report
        pdf_bytes = generate_pdf_report(report, data, summary)
        pdf_path  = OUTPUT_DIR / "CMN_Cyprus_Analysis_Report_ElShaddai.pdf"
        pdf_path.write_bytes(pdf_bytes)
        log.info(f"  PDF saved: {pdf_path}  ({len(pdf_bytes) // 1024} KB)")
    except ImportError:
        log.warning("  reportlab not installed — skipping PDF. Run: pip install reportlab")
    except Exception as e:
        log.error(f"  PDF generation failed: {e}")

    # ── Step 5: Launch dashboard ───────────────────────────────────────────────
    if args.no_dashboard:
        print(f"\n{GREEN}✓ Analysis complete. PDF → {OUTPUT_DIR}{RESET}\n")
        return

    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"  {GREEN}✓ Analysis complete{RESET}")
    print(f"  PDF report  → {OUTPUT_DIR / 'CMN_Cyprus_Analysis_Report_ElShaddai.pdf'}")
    print(f"  Dashboard   → http://127.0.0.1:{args.port}")
    print(f"{BOLD}{'='*65}{RESET}\n")

    import app as dashboard
    dashboard.app.run(
        debug=False,
        host="0.0.0.0",
        port=args.port,
        dev_tools_hot_reload=False,
    )


if __name__ == "__main__":
    main()

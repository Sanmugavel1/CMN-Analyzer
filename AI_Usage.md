# AI Usage Description
## Team El Shaddai — VisualSim Hackathon 2026 — Challenge 3
### Data Visualization, Bottleneck Detection & Debugging

---

## Overview

AI tools were used **strategically and systematically** throughout this project — not as a shortcut, but as a force multiplier. Every AI output was validated against the raw simulation data before being accepted. This document records every prompt used, the reasoning behind it, what the AI produced, what we changed, and which decisions remained entirely manual.

**Primary AI tool used:** Claude (Anthropic) — claude-sonnet model  
**Secondary AI tool used:** GitHub Copilot — inline code completion during development  
**Total distinct prompting sessions:** 11  
**Decisions fully automated by AI:** 4  
**Decisions guided by AI then manually validated:** 9  
**Decisions made entirely without AI:** 6  

---

## Phase 1 — Understanding the System Architecture

### Session 1 — CMN-600 Architecture Extraction

**Goal:** Before writing a single line of parser code, we needed to understand the Arm CoreLink CMN-600 mesh topology, node types, and transaction flow — so we could correctly interpret what the simulation output files were measuring.

**Prompt used:**
```
You are an expert in Arm AMBA CHI and CMN-600 mesh interconnect architecture.

I have simulation output data from a 64-node CMN-600 NoC running a 500 µs workload.
The node types I see in the data are: RNF, RNI, RND, CCG, HNS.

Please explain:
1. What each node type does architecturally (RNF, RNI, RND, CCG, HNS)
2. What RXDAT, RXRSP, RXSNP channels carry and why they matter for performance
3. What "End-to-End latency" vs "Network latency" means specifically in CMN context
4. What Cache_SLC is and why its hit/miss ratio matters
5. What DRAM bank interleaving should look like in a healthy system
6. What CXL port drops would indicate architecturally
```

**What AI produced:**  
A detailed breakdown of all node types, channel semantics, and expected healthy-system behavior. Key insight provided: in a healthy CMN system, DRAM reads should be distributed evenly across all banks via address interleaving — concentration on a single bank indicates the address mapping or interleaving configuration is broken.

**How we used it:**  
This became the reference model for what "normal" looked like. Every anomaly we later detected was compared against this baseline — not just statistically, but architecturally. For example, the AI correctly predicted that 100% Bank 0 concentration would be impossible in a correctly configured system regardless of workload, which gave us confidence that DRAM bank non-parallelism was a real bug and not a workload artifact.

**Manual validation:**  
Cross-referenced node type descriptions against the VisualSim model component names visible in the uploads directory. All node classifications matched.

---

### Session 2 — ArchitectureStats.txt Format Decoding

**Goal:** The `ArchitectureStats.txt` file is a 500+ KB free-text log with multiple timestamped blocks and hundreds of metric names. We needed to understand its structure before writing the parser.

**Prompt used:**
```
I have a VisualSim simulation log file called ArchitectureStats.txt.
It contains blocks separated by markers like "------ 100.0 us ------",
"------ 200.0 us ------" up to "------ 500.0 us ------".

Each block has metrics in the format:
  ComponentType_ComponentName_MetricName = value

Examples I see:
  CMN600_RNF_1_Max_End_to_End_Latency = 3.45E-6
  Cache_SLC_1_A_Number_Entered = 115094
  MC_DRAM_DRAM_0_17_Reads_Per_Bank = {45231, 0, 0, 0, 0, 0, 0, 0}
  CXL_CXL_1_Port_1_CXL_cache_mem_Drop_Count = 3894

For each metric type above:
1. Which timestamped block should I use for final analysis and why?
2. What unit conversions are needed (the latency values appear to be in seconds)?
3. What does the Reads_Per_Bank array format mean?
4. What would a healthy vs unhealthy value look like for each metric?
```

**What AI produced:**  
Confirmed that the last block (500 µs) should always be used for final analysis because earlier blocks capture transient startup behavior. Explained that latency values are in seconds (requiring ×10⁶ conversion to µs and ×10⁹ to ns). Explained the Reads_Per_Bank array as bank-indexed read counts where position 0 = Bank 0.

**How we used it:**  
Directly informed the parser design decision to always read the last timestamped block. The unit conversion factors (×1e6 for µs, ×1e9 for ns) were implemented exactly as specified. The bank array parsing logic in `parser.py` was written based on this explanation.

**Manual validation:**  
Verified the unit conversion by checking that a CMN-600 latency of ~3.45E-6 seconds = 3.45 µs, which is a physically plausible mesh traversal time for a 64-node NoC.

---

## Phase 2 — Parser Development

### Session 3 — PlotML XML Format

**Goal:** Understand the `.plt` file format and write correct parsing logic for both named datasets (RXDAT/RXRSP with 64 component names) and unnamed datasets (latency files with a single system-level dataset).

**Prompt used:**
```
I have VisualSim simulation output files in PlotML XML format (.plt).
Some files have 64 named datasets — one per network node (RNF_1, RNI_2, etc.).
Other files have a single unnamed dataset for a system-level metric.

The XML structure uses <dataset name="RNF_1"> elements containing either
<m x="..." y="..."> or <p x="..." y="..."> point tags.

Write a Python function using xml.etree.ElementTree that:
1. Parses both named and unnamed dataset files
2. Returns a dict with title, xlabel, ylabel, and a list of datasets
3. Each dataset has a name (or "system" if unnamed) and a pandas DataFrame of (x, y) points
4. Handles duplicate x values and sorts by x
5. Gracefully handles XML parse errors without crashing
```

**What AI produced:**  
A complete `parse_plt()` function that handled both file types, deduplicated x values, sorted by x, and wrapped parse errors in a warning log instead of raising exceptions.

**How we used it:**  
Adopted the structure directly. Modified the unnamed dataset fallback name from `"dataset_0"` to `"system"` for clarity in downstream analysis. Added the `drop_duplicates("x")` call after noticing duplicate timestamps in some `.plt` files during testing.

**Human modification made:**  
Changed unnamed dataset naming convention. Added `reset_index(drop=True)` after sort to clean up DataFrame indices.

---

### Session 4 — Regex Pattern Design for ArchStats Metrics

**Goal:** Write robust regex patterns for the five subsystem types (CMN600, Cache_SLC, MC_DRAM, CXL, PCIe) in ArchitectureStats.txt without accidentally matching partial metric names or cross-contaminating subsystem blocks.

**Prompt used:**
```
Write Python regex patterns using re.compile with re.DOTALL to extract
structured data from a free-text simulation log. The patterns need to match
multi-line blocks for these metric groups:

1. CMN600 per-component latency — 6 metrics per component:
   CMN600_{COMP}_Max_End_to_End_Latency, Mean_End_to_End_Latency,
   Min_End_to_End_Latency, Max_Network_Latency, Mean_Network_Latency,
   Min_Network_Latency

2. Cache_SLC_{N} — 10 metrics including hit ratio, entries, overflow, latency

3. MC_DRAM_DRAM_{N} — total requests, completed, throughput, read requests,
   max queue usage, and a special Reads_Per_Bank = {comma-separated values}

4. CXL_CXL_{N} — drop count on Port 1, Rx/Tx MBps, max and mean latency

5. PCIe_Switch_{N} — Rx GBps, useful Rx GBps, flits received/sent,
   max and mean latency

Requirements:
- Use named group {N} as a backreference to ensure all metrics belong
  to the same component index
- Compile for performance since the file is large
- Return dicts keyed by integer component index
```

**What AI produced:**  
Complete regex patterns for all 5 subsystems with backreference groups. The DRAM bank pattern used a separate `re.search` call for the array format since it couldn't be reliably captured in the main multi-line pattern.

**How we used it:**  
Adopted all 5 patterns. Discovered during testing on real data that the CMN600 pattern occasionally missed components when metric order varied slightly between simulation runs. Rewrote the CMN600 pattern from a single multi-line `re.DOTALL` match to individual per-metric searches grouped by component name — more robust to ordering variation.

**Human modification made:**  
CMN600 pattern was redesigned. All other 4 patterns were used as-generated after testing on real files.

---

## Phase 3 — Analysis Engine

### Session 5 — Bottleneck Scoring Model Design

**Goal:** Design a principled composite scoring model for ranking all 64 nodes by bottleneck severity, rather than using a single metric (which would miss nodes that are problematic across multiple dimensions).

**Prompt used:**
```
I am analyzing a 64-node CMN-600 NoC simulation. Each node has these metrics:
- max_e2e_latency_us: worst-case end-to-end latency
- mean_e2e_latency_us: average end-to-end latency
- mean_network_latency_ns: network-only latency (excluding endpoint processing)
- rxrsp_peak_gbps: peak response channel throughput

I want to rank nodes by bottleneck severity using a composite score.
The metrics are on different scales so they need normalization.

Questions:
1. What normalization method is most appropriate for outlier-heavy data?
2. How should I weight these 4 metrics relative to each other for
   CMN fabric analysis specifically? Justify each weight.
3. How should I map composite score to severity levels (critical/high/medium)?
4. What is the weakness of this approach and how would I validate it?
```

**What AI produced:**  
Recommended min-max normalization (robust to scale differences, interpretable as 0-1). Proposed initial weights: max_e2e 40%, mean_e2e 30%, network_lat 20%, rxrsp 10%. Explained that max latency matters most in CHI because a single stalled transaction blocks all subsequent transactions on that channel. Identified the weakness: a single extreme outlier inflates max_e2e scores for all nodes due to normalization.

**How we used it:**  
Adopted the min-max normalization approach. Adjusted weights to 35%/30%/20%/15% after testing on real data — the RXRSP weight was increased from 10% to 15% because response channel saturation (high RXRSP) is a strong independent signal of congestion in CHI that was being under-weighted.

**Human decision:**  
Weight tuning (35/30/20/15 vs AI's suggested 40/30/20/10) was made manually after observing that RND_2's high RXRSP throughput was not being ranked highly enough at the original weights. The final weights correctly elevated it to rank 5.

---

### Session 6 — Statistical Bug Detection Thresholds

**Goal:** Determine the right statistical method and threshold values for flagging components as bugs rather than normal outliers.

**Prompt used:**
```
I need to detect architectural bugs in NoC simulation data by finding
components whose metrics deviate significantly from the system baseline.

I have metrics for 64 nodes. Some bugs create extreme outliers
(e.g., one cache receiving 5× more traffic than all others).
Other bugs affect all nodes uniformly (e.g., all DRAM controllers
show 100% Bank 0 concentration).

For each scenario, recommend:
1. Which statistical baseline to use (mean, median, percentile)?
2. What ratio threshold separates a "bug" from normal variation?
3. How to handle the uniform-bug case where the median itself is abnormal?

Context: this is production chip simulation data, not noisy sensor data.
Deviations are typically caused by explicit model misconfigurations,
not random noise.
```

**What AI produced:**  
Recommended median over mean as baseline (more robust to the outliers we're trying to detect — using mean would inflate the baseline and miss bugs). Suggested ratio > 3× for HIGH, > 5× for CRITICAL based on chip architecture literature where >3σ deviations from expected behavior typically indicate configurati on errors. For uniform bugs (all nodes equally wrong), recommended comparing against theoretical expected values from the spec rather than the empirical median.

**How we used it:**  
Adopted the median baseline and the 3×/5× thresholds exactly. The uniform DRAM bug (all 12 controllers showing 100% Bank 0) was caught using a different detection path: checking whether `active_banks == 1` rather than comparing against median, exactly as AI suggested.

---

### Session 7 — Root Cause Narrative Generation

**Goal:** Generate architect-quality root cause explanations for each of the 5 bugs, including system impact and specific fix recommendations.

**Prompt used:**
```
I found 5 bugs in CMN-600 simulation data. For each bug, write a root cause
analysis that a chip architect would find actionable. Include:
- What the data shows (specific numbers)
- Why this indicates a bug rather than normal behavior
- The likely root cause in the hardware/firmware configuration
- The system-level impact (what else does this bug affect?)
- Specific fix recommendation with technical detail

Bug 1: Cache_SLC_1 received 115,094 entries. All other SLC nodes received
~19,000–23,000 entries. Ratio: 5.35×. System has 16 SLC partitions.

Bug 2: All 12 MC_DRAM controllers show Reads_Per_Bank = {all_reads, 0, 0, 0...}
100% of reads are hitting Bank 0. System should have 16-bank DRAM with
address-based interleaving.

Bug 3: All 10 CXL links show 3,894–4,017 drops on Port 1, exactly 0 drops
on Port 2. Total ~39,427 drops. Asymmetric drop pattern across all links.

Bug 4: PCIe switches show raw Rx = 5.12 GBps but useful Rx = only 0.64 GBps.
Efficiency = 12.5%. PCIe Gen 5 theoretical efficiency should be ~98%.

Bug 5: MC_DRAM_DRAM_13 has no entry in ArchStats. All other 12 DRAM
controllers (0–12) are present.
```

**What AI produced:**  
Full root cause paragraphs for all 5 bugs. Highlighted that Bug 1 (SLC_1 hotspot) is likely caused by incorrect SAM (System Address Map) configuration — the address range assigned to SLC_1 is too broad or overlaps with high-traffic regions. Bug 3's perfectly symmetric drop count across all 10 CXL links is a strong indicator of a flow control parameter bug rather than a physical link issue (random failures wouldn't produce the same drop count on every link).

**How we used it:**  
All 5 root cause explanations were refined and included in the PDF report §3 and in `analyze.py`'s `_recommend_*` functions. The SAM configuration explanation for Bug 1 and the flow-control parameter explanation for Bug 3 were particularly strong — these required architectural knowledge that would have taken hours to research manually.

**Human validation:**  
Verified Bug 3's symmetric pattern independently by summing drop counts across all 10 CXL links — confirmed the asymmetry (Port 1 total: ~39,427, Port 2 total: 0) is real in the data and not a parsing artifact.

---

## Phase 4 — Dashboard & Visualization

### Session 8 — Dashboard Tab Structure Design

**Goal:** Design an 8-tab dashboard structure that an architect would actually use, rather than a developer-oriented data dump.

**Prompt used:**
```
I am building a Dash dashboard for chip architects to analyze CMN-600
NoC simulation data. The audience is system architects, not software developers.

The data I have:
- 64-node per-component latency (min/mean/max E2E, network latency)
- RXDAT/RXRSP throughput time-series for all 64 nodes
- RXSNP time-series
- Buffer occupancy (8×8 mesh heatmap)
- Cache SLC stats (16 partitions)
- DRAM stats (12 controllers, bank utilization)
- CXL stats (10 links, drop counts)
- PCIe stats (4 switches)
- 5 detected bugs with evidence
- 5 bottleneck findings with scores

Design an 8-tab dashboard structure. For each tab:
1. What is the primary question an architect asks when they open this tab?
2. What charts best answer that question?
3. What should be visible immediately without scrolling?
```

**What AI produced:**  
An 8-tab structure organized around architect mental models rather than data types. Key insight: architects ask "is my system healthy?" first (System Overview), then drill down by concern (Latency → Throughput → Bugs → Cache → Interconnects). The "Data Explorer" tab for raw table access should be last, not first, because architects want insight before raw numbers.

**How we used it:**  
The tab ordering (Overview → Latency → Throughput → Bugs & Bottlenecks → Cache & Memory → CXL & PCIe → Data Explorer → Upload) was adopted directly from this session. Each tab's "primary question" framing was used to decide which chart should appear at the top of each tab.

**Human decision:**  
The Upload tab (live file reload) was added entirely by the team as a usability feature — AI did not suggest it.

---

### Session 9 — Visualization Type Selection

**Goal:** Choose the right chart type for each metric to maximize architect insight, not just display data.

**Prompt used:**
```
For each metric below, recommend the best chart type for a chip architect
audience and explain why. Also identify what pattern to highlight in each chart.

1. E2E latency over simulation time (single system-level value, 500 time points)
2. Per-component max vs mean E2E latency (64 components)
3. RXDAT peak throughput ranking (64 components)
4. Cache SLC entry imbalance (16 partitions, one is 5× higher)
5. DRAM bank utilization (12 controllers × 16 banks matrix)
6. CXL drop counts (10 links, Port 1 vs Port 2)
7. CMN mesh buffer occupancy (8×8 grid of routers)
8. PCIe raw vs useful throughput (4 switches)

For each: chart type, why it's better than alternatives, what to color/highlight
```

**What AI produced:**  
Specific recommendations: time-series line chart for latency (with min/mean/max bands to show variance); horizontal bar chart for component ranking (easier to read long component names than vertical); grouped bar for DRAM banks (makes the single-bank concentration visually obvious); heatmap for the 8×8 mesh (spatial layout communicates router position meaningfully); stacked bar for PCIe raw vs useful (makes the 87.5% overhead immediately visible).

**How we used it:**  
All chart type recommendations were implemented in `app.py`. The stacked bar for PCIe was particularly effective — when displayed, the 87.5% overhead segment is visually dominant and architects immediately understand the severity of Bug 4 without reading any text.

---

## Phase 5 — Report Generation

### Session 10 — Executive Summary Writing

**Goal:** Write a one-page executive summary that gives a chip architect the full picture in under 2 minutes of reading.

**Prompt used:**
```
Write a professional executive summary for a chip simulation analysis report.
Audience: system architects at a semiconductor company reviewing CMN-600 NoC
simulation results.

Key findings to include:
- 64-node CMN-600 mesh simulated over 500 µs
- 5 bugs detected: 2 critical (SLC hotspot, DRAM bank parallelism), 2 high
  (CXL drops, PCIe efficiency), 1 medium (missing DRAM controller)
- Top bottleneck: RNF_27 at 39.71 µs max E2E (8.2× system median)
- RNI nodes showing sustained high mean latency (~7.7 µs) due to PCIe overhead
- System cannot achieve full performance until Bug 1 (SAM misconfiguration)
  and Bug 2 (DRAM interleaving) are resolved

Write in a factual, direct engineering tone. No marketing language.
Lead with the most critical issue. Include a one-sentence system health verdict.
```

**What AI produced:**  
A 200-word executive summary opening with the system health verdict ("The CMN-600 Cyprus system is not operating at design performance due to two critical configuration errors that must be resolved before performance validation is meaningful") followed by prioritized findings.

**How we used it:**  
Used the structure and opening verdict. Rewrote the body paragraphs to include specific data numbers (ratios, exact values) since the AI-generated version was slightly generic. The opening verdict sentence was kept verbatim — it precisely captures the severity.

---

### Session 11 — Recommendation Prioritization

**Goal:** Generate a prioritized list of fix recommendations that an architect could take to an engineering team meeting.

**Prompt used:**
```
Based on these 5 bugs found in a CMN-600 simulation, generate prioritized
fix recommendations. Each recommendation should include:
- Which team owns the fix (architecture, firmware, RTL, verification)
- Estimated implementation complexity (low/medium/high)
- Whether the fix requires re-simulation to validate
- Expected performance impact if fixed

Bugs:
1. Cache_SLC_1 SAM misconfiguration (5.35× traffic imbalance)
2. DRAM bank interleaving disabled (100% Bank 0 utilization)  
3. CXL flow control parameter causing systematic Port 1 drops
4. PCIe protocol overhead at 87.5% (useful bandwidth only 12.5%)
5. MC_DRAM_13 missing from simulation output

Prioritize by: system performance impact first, then fix complexity.
```

**What AI produced:**  
A 5-item prioritized list with team ownership assignments, complexity ratings, and expected performance improvement estimates. Correctly identified Bug 2 (DRAM interleaving) as the highest-impact fix because it affects all memory-bound workloads and is typically a single parameter change in the memory controller configuration.

**How we used it:**  
The priority ordering (Bug 2 → Bug 1 → Bug 3 → Bug 4 → Bug 5) and team ownership assignments were used directly in PDF §6. Complexity ratings were manually reviewed — Bug 3 (CXL flow control) was downgraded from "medium" to "low" complexity because CXL flow control parameters are typically firmware-configurable without requiring RTL changes.

---

## Summary: Automated vs Manual Decisions

### Fully automated by AI (accepted without modification)
| Decision | AI Session | Rationale for accepting |
|----------|-----------|------------------------|
| Use last timestamped block for ArchStats parsing | Session 2 | Architecturally sound, validated against data |
| Min-max normalization for bottleneck scoring | Session 5 | Standard approach, no reason to deviate |
| Median as bug detection baseline | Session 6 | Statistically correct for outlier data |
| Dashboard tab ordering | Session 8 | Architect-workflow reasoning was sound |

### Guided by AI, modified by team
| Decision | AI Suggestion | Team Modification | Reason |
|----------|--------------|-------------------|--------|
| Bottleneck weights | 40/30/20/10 | 35/30/20/15 | RXRSP under-weighted at 10% |
| CMN600 regex | Single DOTALL pattern | Per-metric individual searches | Real data had variable metric ordering |
| Bug 3 fix complexity | Medium | Low | CXL flow control is firmware-only |
| Executive summary body | Generic text | Specific numbers added | Judges expect precise evidence |
| unnamed dataset fallback name | `"dataset_0"` | `"system"` | More meaningful in analysis output |

### Made entirely without AI
| Decision | Rationale |
|----------|-----------|
| Dashboard Upload tab feature | Team idea — live reload for usability |
| Dark theme for dashboard and PDF | Consistent visual identity for submission |
| Composite score top-5 cutoff | Domain judgment — more than 5 bottlenecks dilutes focus |
| DRAM active_banks bug detection path | Uniform-bug case requires spec-based check, not median |
| Unit test design for parser edge cases | Verification judgment |
| Evidence string format in Finding dataclass | Readability decision for terminal output |

---

## Reflection: What AI Did Well and Where We Corrected It

**Where AI added the most value:**
The architectural knowledge sessions (Sessions 1 and 7) saved the most time. Understanding that DRAM bank concentration is architecturally impossible in a correctly configured system — not just statistically unusual — elevated our bug detection from pattern matching to genuine diagnosis. This required domain knowledge that would have taken significant manual research to acquire.

**Where AI required correction:**
The CMN600 regex pattern (Session 4) failed on real data because metric ordering in ArchitectureStats.txt is not guaranteed. The AI assumed fixed ordering in a multi-line DOTALL match — a reasonable assumption that was wrong in practice. Discovering and fixing this required running the parser against actual files and debugging the output.

**Key principle applied throughout:**
AI was never the final decision-maker. Every finding — statistical, architectural, or analytical — was checked against the raw numbers in the simulation files. The 5 bugs reported in this submission are real, verifiable anomalies in the provided data, not AI-generated speculation.

---

*Document prepared by Team El Shaddai | VisualSim Hackathon 2026*
# 8-bit Adder RTL Design & Self-Checking Verification Testbench

A professional hardware verification project demonstrating a **Self-Checking Testbench** with **Constrained Random Verification (CRV)** concepts implemented in **SystemVerilog 2012**. Designed and simulated locally on macOS using open-source EDA tools.

---

## 📌 Project Overview

This repository contains the RTL design of a combinational 8-bit adder and its corresponding advanced verification environment. Instead of manually inspecting waveform diagrams, this testbench utilizes an automated **Scoreboard mechanism** to dynamically validate the correctness of the hardware design against a behavioral reference model.

### Key Features

* **Modern SystemVerilog Syntax:** Utilizes fully integrated `logic` datatypes and modern constructs instead of legacy Verilog-2001 `wire/reg`.
* **Directed Testcases:** Targets specific critical design aspects including basic arithmetic operations and extreme boundary values (Overflow conditions).
* **Constrained Random Verification (CRV):** Simulates 20 automated, pseudo-randomly generated stimulus pairs using `$urandom_range` to ensure robust functional coverage.
* **Automated Self-Checking:** Implements a dynamic monitoring system that prints detailed `[PASS]` or `[FAIL]` indicators, eliminating the need for manual inspection.

---

## 📂 Directory Structure

```text
.
├── adder_8bit.sv       # Design Under Test (DUT) - RTL Core
├── tb_adder_8bit.sv    # Self-Checking Testbench Environment
├── .gitignore          # Excludes simulation binaries and heavy VCD files
└── README.md           # Documentation
```

---

## 🛠️ Prerequisites & Toolchains

The simulation environment relies strictly on open-source, lightweight, yet powerful EDA tools:

* **Compiler/Simulator:** Icarus Verilog (`iverilog` v12.0+)
* **Simulation Runtime:** Virtual Verification Processor (`vvp`)
* **Waveform Viewer:** GTKWave (via XQuartz on macOS environment)

---

## 🚀 How to Compile and Run

Follow these commands in your terminal to execute the simulation locally:

### 1. Compilation
Compile the SystemVerilog source files using the IEEE 1800-2012 standard flag (`-g2012`):

```bash
iverilog -g2012 -o adder_sim adder_8bit.sv tb_adder_8bit.sv
```

### 2. Execution
Run the generated simulation binary executable using `vvp`:

```bash
vvp adder_sim
```

### 3. Waveform Visualization
To inspect the physical signal transitions (0s and 1s) across the timeline, load the dumped Value Change Dump (`.vcd`) file into GTKWave:

```bash
gtkwave adder_waveform.vcd
```

---

## 📊 Expected Simulation Outputs

Upon successful execution, the automated testbench will generate the following assertions in your terminal console logs:

```text

[START]

[PASS] TC1: 15 + 25 = 40
[PASS] TC2: 255 + 1 = 256 (Giu duoc bit tran ok!)
Chay nguyen nhien 20 cap so tu dong
[PASS] Cap 0: 142 + 53 = 195
[PASS] Cap 1: 12 + 201 = 213
...
[PASS] Cap 19: 88 + 114 = 202

[SUCCESS]

```

---

## 🗺️ Future Roadmap

To further escalate this portfolio to production-grade verification standards, the following milestones are planned:

* **Phase 1: ALU Expansion:** Upgrade the current 8-bit Adder into a full-scale Arithmetic Logic Unit (ALU) capable of performing execution operations (ADD, SUB, AND, OR, XOR, MUL) mapped via custom operation selection codes (Opcodes).
* **Phase 2: Object-Oriented Testbench Architecture:** Restructure the flat testbench layout into modular verification components using SystemVerilog OOP constructs (Classes, Mailboxes, and Interfaces) to explicitly decouple stimulus generation from driver execution.
* **Phase 3: Functional Coverage Integration:** Implement dedicated covergroups and coverpoints to track structural and functional assertion coverage, aiming for a quantified 100% verification metric before virtual physical layout tape-out simulation.

---

> *Developed as a part of Hardware Verification Portfolio for Advanced IC Design Engineering track.*
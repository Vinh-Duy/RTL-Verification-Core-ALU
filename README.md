# 8-bit ALU RTL Design & Advanced OOP Verification Testbench

A professional hardware verification portfolio demonstrating the evolution from a basic combinational circuit to a full-scale **Arithmetic Logic Unit (ALU)**. The project showcases both **Flat Self-Checking** and **Advanced Object-Oriented Programming (OOP) Constrained Random Verification (CRV)** environments implemented in **SystemVerilog 2012**.

---

## Project Overview

This repository captures the progressive development of an ASIC verification environment. It starts from a foundational 8-bit adder and scales up to a multi-operation ALU. To prove verification competency, the project features two distinct testbench architectures:

1. **Flat Self-Checking Testbench:** A traditional sequential approach using loops and dynamic scoreboard checking.
2. **Standard OOP Architecture:** A production-grade environment utilizing SystemVerilog Classes, Mailboxes, Interfaces, and Virtual Interfaces to decouple stimulus generation, driving, and monitoring, completely eliminating race conditions.

### Key Features

* **Multi-operation ALU RTL:** Supports 8 opcodes including ADD, SUB, MUL, DIV (with zero-division protection), AND, OR, XOR, and SHL.
* **Evolutionary Project Structure:** Clean separation of Design (`rtl/`) and Verification (`tb/`) files.
* **Constrained Random Verification (CRV):** Intelligent randomization ensuring high edge-case coverage without illegal states (e.g., constraining denominator `b != 0` during division).
* **Clockless Race-Condition Handling:** Implemented strategic delays (`#4` and `#1`) within the OOP Scoreboard to perfectly sync with the Driver, preventing simulation hang and data overriding.

---

## Directory Structure

```text
.
├── rtl/                        # Design Under Test (RTL Core)
│   ├── adder_8bit.sv           # (Phase 0) Basic 8-bit Adder
│   └── alu_8bit.sv             # (Phase 1) 8-bit ALU (8 Operations)
│
├── tb/                         # Verification Environment
│   ├── tb_adder_8bit.sv        # (Phase 0) Basic Testbench
│   ├── tb_alu_flat.sv          # (Phase 1a) Flat Self-Checking Testbench
│   └── tb_alu_oop.sv           # (Phase 1b) OOP SV Architecture Testbench
│
├── .gitignore                  # Excludes simulation binaries and VCD files
└── README.md                   # Documentation
```

---

## Prerequisites & Toolchains

* **For Flat Testbench (Local Simulation):** Icarus Verilog (`iverilog` v12.0+) and GTKWave.
* **For OOP Testbench (Advanced SV Features):** Commercial simulators (e.g., Aldec Riviera-PRO, Siemens Questa, Synopsys VCS, ModelSim). Highly recommended to run via EDA Playground as open-source `iverilog` has limited OOP support.

---

## How to Compile and Run

### Local Simulation (macOS / Linux / Windows) - Flat Testbench
For the sequential Flat Testbench, you can use the open-source **Icarus Verilog** toolchain across any operating system. Run these commands in your terminal/command prompt:

```bash
# 1. Compile with SystemVerilog 2012 support
iverilog -g2012 -o alu_flat_sim rtl/alu_8bit.sv tb/tb_alu_flat.sv

# 2. Execute the simulation
vvp alu_flat_sim

# 3. Open waveform (Ensure GTKWave is installed)
gtkwave alu_flat_waveform.vcd
```

### Windows (Local) - OOP Testbench
Since open-source `iverilog` lacks full support for SystemVerilog OOP, Windows users with commercial simulators like **ModelSim** or **QuestaSim** (often provided via Intel Quartus or university licenses) can run the OOP Testbench using the following TCL commands in the simulator transcript or command prompt:

```tcl
# 1. Create a working library
vlib work

# 2. Compile Design and OOP Testbench
vlog -sv rtl/alu_8bit.sv tb/tb_alu_oop.sv

# 3. Run Simulation (Command Line Interface mode)
vsim -c tb_alu_oop -do "run -all; quit"
```

### Cloud Simulation (Cross-Platform) - OOP Testbench
If you do not have a commercial simulator installed locally, it is highly recommended to run the OOP Testbench via [EDA Playground](https://www.edaplayground.com/).

1. Upload both `rtl/alu_8bit.sv` and `tb/tb_alu_oop.sv`.
2. Select a commercial simulator (e.g., Aldec Riviera-PRO or Siemens Questa).
3. Check "Open EPWave after run" to visualize the `.vcd` waveform output.

---

## Expected Simulation Outputs

Upon successful execution, the automated scoreboard will generate terminal logs similar to this:

```text

[START]

[PASS] ADD | a= 33, b=  5 | Result=   38
[PASS] SUB | a= 10, b=  4 | Result=    6
[PASS] MUL | a= 31, b= 16 | Result=  496
[PASS] DIV | a= 18, b=  1 | Result=   18
[PASS] AND | a= 30, b= 11 | Result=   10
[PASS] OR  | a= 39, b= 13 | Result=   47
[PASS] XOR | a= 49, b= 16 | Result=   33
[PASS] SHL | a= 50, b=  8 | Result=   50
...

[SUCCESS]

```

---

## Roadmap & Milestones

* [x] **Phase 1: ALU Expansion:** Upgraded the 8-bit Adder into a full-scale ALU.
* [x] **Phase 2: Object-Oriented Architecture:** Restructured the testbench into modular SV OOP components (Generator, Driver, Scoreboard, Environment).
* [ ] **Phase 3: Functional Coverage:** Implement SystemVerilog covergroups and coverpoints to track functional coverage.
* [ ] **Phase 4: UVM Integration:** Migrate the current custom OOP architecture into the industry-standard Universal Verification Methodology (UVM) framework.

---

> *Developed as a part of a Hardware Verification Portfolio for the Advanced IC Design Engineering track.*
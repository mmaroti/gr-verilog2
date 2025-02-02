title: gr-verilog2
brief: Compiles verilog code to executable GNU Radio blocks on the fly.
tags:
  - verilog
  - verilator
author:
  - Miklos Maroti <mmaroti@gmail.com>
copyright_owner:
  - Miklos Maroti <mmaroti@gmail.com>
license: GPL3, OHLS
dependencies:
  - verilator (>= 4.0)
repo: https://github.com/mmaroti/gr-verilog2
gr_supported_version: v3.8, v3.9, v3.10
---
This module takes a verilog source file and parameter values for the top module and
configures and compiles the module into a loadable dynamic library using verilator.
All of this happens at construction time, so the verilog parameters can be set on
the fly from GRC, and the resulting block can be used as any other gnuradio block.
The verilog code must consume and produce all items using AXI Stream interfaces, and
it can use TDATA, TUSER and TLAST values which are transferred as int32 values.

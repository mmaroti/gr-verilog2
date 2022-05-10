title: The VERILOG2 OOT Module
brief: Compiles verilog blocks to executable libraries on the fly .
tags: # Tags are arbitrary, but look at CGRAN what other authors are using
  - sdr
  - verilog
author:
  - Miklos Maroti <mmaroti@gmail.com>
copyright_owner:
  - Miklos Maroti
license: GPL3, OHLS
gr_supported_version: 3.10
#repo: # Put the URL of the repository here, or leave blank for default
#website: <module_website> # If you have a separate project website, put it here
#icon: <icon_url> # Put a URL to a square image here that will be used as an icon on CGRAN
---
This module takes a verilog source file and parameter values for the top module and
configures and compiles the module into a loadable dynamic library using verilator.
The verilog block must consume and produc all items using AXI Stream interfaces, and
it can use TDATA, TUSER and TLAST values which are transferred as int32 vectors.

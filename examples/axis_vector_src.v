/**
 * Copyright (C) 2017-2021, Miklos Maroti
 *
 * This source describes Open Hardware and is licensed under the CERN-OHL-S v2.
 * You may redistribute and modify this source and make products using it under
 * the terms of the CERN-OHL-S v2 (https://ohwr.org/cern_ohl_s_v2.txt).
 *
 * This source is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
 * INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
 * PARTICULAR PURPOSE. Please see the CERN-OHL-S v2 for applicable conditions. 
 */

`default_nettype none

/**
 * Simple block that produces the same sequence of samples repeatedly.
 */
module axis_vector_src #(
	parameter DATA_WIDTH = 16,
	parameter PERIOD = 1024,
	parameter READMEMH = "testbench.mem"
) (
	input wire clock,

	(* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
	input wire reset,

	output reg [DATA_WIDTH-1:0] m_tdata,
	output reg m_tlast,
	output reg m_tvalid,
	input wire m_tready
);

initial
begin
	if (PERIOD <= 1)
		$error("PERIOD must be at least two");
end

localparam ADDR_WIDTH = $clog2(PERIOD); // $clog2(4) = 2, $clog2(5) = 3
localparam [ADDR_WIDTH-1:0] LAST = PERIOD[ADDR_WIDTH-1:0] - 1;

(* RAM_STYLE = "BLOCK" *)
reg [DATA_WIDTH-1:0] memory [2**ADDR_WIDTH-1:0];

initial $readmemh(READMEMH, memory);

reg [ADDR_WIDTH-1:0] addr;

always @(posedge clock)
begin
	if (reset)
		addr <= 0;
	else if (m_tready)
		addr <= (addr == LAST) ? 0 : addr + 1;
end

reg [DATA_WIDTH-1:0] m_tdata_pre;
reg m_tvalid_pre;

always @(posedge clock)
begin
	if (m_tready)
		m_tdata_pre <= memory[addr];
end

always @(posedge clock)
begin
	if (reset)
		m_tvalid_pre <= 1'b0;
	else if (m_tready)
		m_tvalid_pre <= 1'b1;
end

always @(posedge clock)
begin
	if (m_tready)
		m_tdata <= m_tdata_pre;
end

always @(posedge clock)
begin
	if (m_tready)
		m_tlast <= addr == 0;
end

always @(posedge clock)
begin
	if (reset)
		m_tvalid <= 1'b0;
	else if (m_tready)
		m_tvalid <= m_tvalid_pre;
end

endmodule

`default_nettype wire

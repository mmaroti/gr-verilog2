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
 * Moves data from s_tdata to m_tdata. Data is transferred on the ports when
 * both valid and ready are high on the rising edge of the clock. This block
 * can move data on every clock, and all its outputs are registered (including
 * s_tready). This means, that it will store the accepted input value in an
 * internal buffer when both s_tready and s_tvalid are true and m_tready is
 * false.
 */
module axis_copy_reg #(
	parameter DATA_WIDTH = 8
) (
	input wire clock,
	input wire resetn,

	input wire [DATA_WIDTH-1:0] s_tdata,
	input wire s_tvalid,
	output reg s_tready,

	output reg [DATA_WIDTH-1:0] m_tdata,
	output reg m_tvalid,
	input wire m_tready
);

/**
 * s_tready && !m_tvalid: buffer is empty, m_tdata is empty
 * s_tready && m_tvalid: buffer is empty, m_tdata is full
 * !s_tready && m_tvalid: buffer is full, m_tdata is full
 * !s_tready && !m_tvalid: cannot happen
 */

reg [DATA_WIDTH-1:0] buffer;

always @(posedge clock)
begin
	if (!m_tvalid || m_tready)
		m_tdata <= s_tready ? s_tdata : buffer;
end

always @(posedge clock)
begin
	if (s_tready)
		buffer <= s_tdata;
end

always @(posedge clock)
begin
	if (!resetn)
		m_tvalid <= 1'b0;
	else
		m_tvalid <= (m_tvalid && !m_tready) || !s_tready || s_tvalid;
end

always @(posedge clock)
begin
	if (!resetn)
		s_tready <= 1'b1;
	else
		s_tready <= !m_tvalid || m_tready || (s_tready && !s_tvalid);
end

endmodule

`default_nettype wire

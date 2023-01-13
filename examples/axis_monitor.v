/**
 * Copyright (C) 2023, Miklos Maroti
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
 * A simple block that passes through an AXIS data stream and counts the
 * number of samples and records the last sample thorugh a DREG interface.
 */
module axis_monitor #(
	parameter DATA_WIDTH = 16,
	parameter COUNTER_WIDTH = 32
) (
	(* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s:m" *)
	input wire clock,

	(* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
	input wire reset,

	// Input AXIS interface
	input wire [DATA_WIDTH-1:0] s_tdata,
	input wire s_tvalid,
	output wire s_tready,

	// Output AXIS interface
	output wire [DATA_WIDTH-1:0] m_tdata,
	output wire m_tvalid,
	input wire m_tready,

	// Counter DREG interface
	output reg [COUNTER_WIDTH-1:0] counter_dout,
	input wire counter_dset,

	// Sample DREG interface
	output reg [DATA_WIDTH-1:0] sample_dout,
	input wire [DATA_WIDTH-1:0] sample_din,
	input wire sample_dset
);

assign s_tready = m_tready;
assign m_tdata = s_tdata;
assign m_tvalid = s_tvalid;

always @(posedge clock)
begin
	if (reset || counter_dset)
		counter_dout <= 0;
	else if (s_tvalid && s_tready)
		counter_dout <= counter_dout + 1;
end

always @(posedge clock)
begin
	if (reset)
		sample_dout <= 0;
	else if (sample_dset)
		sample_dout <= sample_din;
	else if (s_tvalid && s_tready)
		sample_dout <= s_tdata;
end

endmodule

`default_nettype wire

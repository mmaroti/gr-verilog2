/**
 * Copyright (C) 2022, Miklos Maroti
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

module axis_swap_wire #(
	parameter DATA_WIDTH = 8
) (
	input wire [2*DATA_WIDTH-1:0] s_tdata,
	input wire s_tvalid,
	output wire s_tready,

	output wire [2*DATA_WIDTH-1:0] m_tdata,
	output wire m_tvalid,
	input wire m_tready
);

assign s_tready = m_tready;
assign m_tdata = {s_tdata[DATA_WIDTH-1:0], s_tdata[2*DATA_WIDTH-1:DATA_WIDTH]};
assign m_tvalid = s_tvalid;

endmodule

`default_nettype wire

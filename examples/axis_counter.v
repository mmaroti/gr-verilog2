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
 * Just a simple counter producing output through an axis interface. The
 * couter is incremented when m_tready is true.
 */
module axis_counter #(
	parameter DATA_WIDTH = 16
) (
	input wire clock,

	(* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
	input wire reset,

	output reg [DATA_WIDTH-1:0] m_tdata,
	output wire m_tvalid,
	input wire m_tready
);

assign m_tvalid = 1'b1;

always @(posedge clock)
begin
	if (reset)
		m_tdata <= 0;
	else if (m_tready)
		m_tdata <= m_tdata + 1;
end

endmodule

`default_nettype wire

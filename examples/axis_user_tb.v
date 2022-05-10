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

module axis_chain_tb #(
	parameter DATA_WIDTH = 8,
	parameter USER_WIDTH = 8
) (
	input wire clock,

	(* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
	input wire reset,

	input wire [DATA_WIDTH-1:0] s_tdata,
	input wire s_tvalid,
	output wire s_tready,

	output wire [DATA_WIDTH-1:0] m_tdata,
	output wire [USER_WIDTH-1:0] m_tuser,
	output wire m_tvalid,
	input wire m_tready
);

wire unused;

axis_counter #(
	.DATA_WIDTH(USER_WIDTH)
) axis_counter_inst (
	.clock(clock),
	.reset(reset),

	.m_tdata(m_tuser),
	.m_tvalid(unused),
	.m_tready(m_tvalid && m_tready)
);

axis_copy_reg #(
	.DATA_WIDTH(DATA_WIDTH)
) axis_copy_reg_inst (
	.clock(clock),
	.resetn(!reset),

	.s_tdata(s_tdata),
	.s_tvalid(s_tvalid),
	.s_tready(s_tready),

	.m_tdata(m_tdata),
	.m_tvalid(m_tvalid),
	.m_tready(m_tready)
);

endmodule

`default_nettype wire

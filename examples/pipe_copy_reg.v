/**
 * Copyright (C) 2021-2023, Miklos Maroti
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
 * Moves data from the s_pipe interface to the m_pipe interface.
 * This module has a fixed pipeline delay of STAGES.
 */
module pipe_copy_reg #(
	parameter DATA_WIDTH = 32,
	parameter STAGES = 2
) (
`ifdef FORMAL
	output integer pending,
`endif

	input wire clock,

	(* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
	input wire reset,

	input wire [DATA_WIDTH-1:0] s_pipe_tdata,
	input wire s_pipe_tvalid,

	output wire [DATA_WIDTH-1:0] m_pipe_tdata,
	output wire m_pipe_tvalid
);

initial
begin
if (STAGES < 0)
	$error("Invalid STAGES value");
end

generate
if (STAGES <= 0)
begin : gen_stages_0
	assign m_pipe_tvalid = s_pipe_tvalid;
	assign m_pipe_tdata = s_pipe_tdata;

	wire unused = &{1'b0, clock, reset};

`ifdef FORMAL
	assign pending = 0;
`endif
end
else if (STAGES == 1)
begin : gen_stages_1
	reg valid_reg;
	reg [DATA_WIDTH-1:0] data_reg;

	assign m_pipe_tvalid = valid_reg;
	assign m_pipe_tdata = data_reg;

	always @(posedge clock)
	begin
		if (reset)
			valid_reg <= 1'b0;
		else
			valid_reg <= s_pipe_tvalid;
	end

	always @(posedge clock)
	begin
		data_reg <= s_pipe_tdata;
	end

`ifdef FORMAL
	assign pending = valid_reg;
`endif
end
else
begin : gen_stages_x
	reg [STAGES-1:0] valid_regs;
	reg [DATA_WIDTH-1:0] data_regs [0:STAGES-1];

	always @(posedge clock)
	begin
		if (reset)
			valid_regs <= 0;
		else
			valid_regs <= (valid_regs << 1) | {{STAGES-1{1'b0}},s_pipe_tvalid};
	end

	integer i;
	always @(posedge clock)
	begin
		for (i = 0; i < STAGES - 1; i = i + 1)
		begin
			data_regs[i + 1] <= data_regs[i];
		end
		data_regs[0] <= s_pipe_tdata;
	end

	assign m_pipe_tvalid = valid_regs[STAGES-1];
	assign m_pipe_tdata = data_regs[STAGES-1];

`ifdef FORMAL
	always @(*)
	begin
		pending = 0;
		for (i = 0; i < STAGES; i = i + 1)
			pending = pending + {31'b0,valid_regs[i]};
	end
`endif
end
endgenerate

endmodule

`default_nettype wire

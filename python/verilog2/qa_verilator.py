#!/usr/bin/env python3
# Copyright (C) 2022, Miklos Maroti
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy
import os
import random

from gnuradio import gr_unittest, verilog2


class qa_verilator(gr_unittest.TestCase):

    AXIS_COPY_REG = [
        os.path.join(os.path.dirname(__file__), '..',
                     '..', 'examples', 'axis_copy_reg.v'),
    ]

    def test1(self):
        mod = verilog2.Module(qa_verilator.AXIS_COPY_REG)
        print(mod.get_ports({}))
        assert(mod.get_input_vlens({}) == [1])

        assert(mod.get_input_vlens({'DATA_WIDTH': 8}) == [1])
        assert(mod.get_output_vlens({'DATA_WIDTH': 8}) == [1])

        assert(mod.get_input_vlens({'DATA_WIDTH': 32}) == [1])
        assert(mod.get_output_vlens({'DATA_WIDTH': 32}) == [1])

        assert(mod.get_input_vlens({'DATA_WIDTH': 33}) == [2])
        assert(mod.get_output_vlens({'DATA_WIDTH': 33}) == [2])

        assert(mod.get_input_vlens({'DATA_WIDTH': 64}) == [2])
        assert(mod.get_output_vlens({'DATA_WIDTH': 64}) == [2])

        assert(mod.get_input_vlens({'DATA_WIDTH': 65}) == [3])
        assert(mod.get_output_vlens({'DATA_WIDTH': 65}) == [3])

    def test2(self):
        mod = verilog2.Module(qa_verilator.AXIS_COPY_REG)
        ins = verilog2.Instance(mod, {'DATA_WIDTH': 8})

        len = random.randint(0, 50)
        input_item0 = numpy.random.randint(
            0, 1000, size=(len, 1), dtype=numpy.int32)
        output_item0 = numpy.empty((len + 10, 1), dtype=numpy.int32)

        consumed, produced = ins.work([input_item0], [output_item0])
        print("consumed", consumed)
        print("produced", produced)
        assert consumed == [len]
        assert produced == [len]

        print("input", input_item0.flatten())
        print("input mod 256", input_item0.flatten() % 256)
        print("output", output_item0[:len].flatten())
        assert numpy.alltrue(output_item0[:len] == input_item0 % 256)


if __name__ == '__main__':
    gr_unittest.run(qa_verilator)

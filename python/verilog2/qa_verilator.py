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

    SOURCES = [
        os.path.join(os.path.dirname(__file__), '..',
                     '..', 'examples', 'axis_copy_reg.v'),
    ]

    def test1(self):
        mod = verilog2.Module(qa_verilator.SOURCES)
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
        mod = verilog2.Module(qa_verilator.SOURCES)
        ins = verilog2.Instance(mod, {'DATA_WIDTH': 8})

        length = random.randint(0, 50)
        input_item0 = numpy.random.randint(
            0, 1000, size=(length, 1), dtype=numpy.int32)
        output_item0 = numpy.empty((length + 10, 1), dtype=numpy.int32)

        consumed, produced = ins.work([input_item0], [output_item0])
        print("consumed", consumed)
        print("produced", produced)
        assert consumed == [length]
        assert produced == [length]

        print("input", input_item0.flatten())
        print("input mod 256", input_item0.flatten() % 256)
        print("output", output_item0[:length].flatten())
        assert numpy.alltrue(output_item0[:length] == input_item0 % 256)

    def test3(self):
        mod = verilog2.Module(qa_verilator.SOURCES)
        ins = verilog2.Instance(mod, {'DATA_WIDTH': 33})

        length = 10
        input_item0 = numpy.random.randint(
            0, 1000, size=(length, 2), dtype=numpy.int32)
        output_item0 = numpy.empty((length + 10, 2), dtype=numpy.int32)

        consumed, produced = ins.work([input_item0], [output_item0])
        print("consumed", consumed)
        print("produced", produced)
        assert consumed == [length]
        assert produced == [length]

        print("input", input_item0)
        print("output", output_item0[:length])
        assert numpy.alltrue(output_item0[:length, 0] == input_item0[:, 0])
        assert numpy.alltrue(output_item0[:length, 1] == input_item0[:, 1] % 2)

    def test4(self):
        mod = verilog2.Module(qa_verilator.SOURCES)
        ins = verilog2.Instance(mod, {'DATA_WIDTH': 65})

        length = 10
        input_item0 = numpy.random.randint(
            0, 1000, size=(length, 3), dtype=numpy.int32)
        output_item0 = numpy.empty((length + 10, 3), dtype=numpy.int32)

        consumed, produced = ins.work([input_item0], [output_item0])
        print("consumed", consumed)
        print("produced", produced)
        assert consumed == [length]
        assert produced == [length]

        print("input", input_item0)
        print("output", output_item0[:length])
        assert numpy.alltrue(output_item0[:length, 0] == input_item0[:, 0])
        assert numpy.alltrue(output_item0[:length, 1] == input_item0[:, 1])
        assert numpy.alltrue(output_item0[:length, 2] == input_item0[:, 2] % 2)


if __name__ == '__main__':
    gr_unittest.run(qa_verilator)

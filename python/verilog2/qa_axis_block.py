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

from gnuradio import gr, gr_unittest, blocks, verilog2


class qa_axis_block(gr_unittest.TestCase):

    SOURCES = [
        os.path.join(os.path.dirname(__file__), '..',
                     '..', 'examples', 'axis_swap_wire.v'),
    ]

    def test1(self):
        length = random.randint(0, 50)
        data1 = numpy.random.randint(0, 1000, size=(length, 2))

        source = blocks.vector_source_i(data1.flatten(), vlen=2, repeat=False)
        block = verilog2.axis_block(qa_axis_block.SOURCES, {'DATA_WIDTH': 32})
        sink = blocks.vector_sink_i(vlen=2)

        top = gr.top_block()
        top.connect(source, block, sink)
        top.run()

        data2 = numpy.reshape(sink.data(), (-1, 2))
        assert data1.shape == data2.shape
        assert numpy.alltrue(data1[:, 0] == data2[:, 1])
        assert numpy.alltrue(data1[:, 1] == data2[:, 0])


if __name__ == '__main__':
    gr_unittest.run(qa_axis_block)

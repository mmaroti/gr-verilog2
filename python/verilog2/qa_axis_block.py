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
import time

from gnuradio import gr, gr_unittest, blocks, verilog2


class qa_axis_block(gr_unittest.TestCase):

    def test1(self):
        length = random.randint(0, 50)
        data1 = numpy.random.randint(0, 1000, size=(length, 2))

        source = blocks.vector_source_i(data1.flatten(), vlen=2, repeat=False)
        block = verilog2.axis_block([
            os.path.join(os.path.dirname(__file__), '..',
                         '..', 'examples', 'axis_swap_wire.v'),
        ], {'DATA_WIDTH': 32})
        sink = blocks.vector_sink_i(vlen=2)

        top = gr.top_block()
        top.connect(source, block, sink)
        top.run()

        data2 = numpy.reshape(sink.data(), (-1, 2))
        assert data1.shape == data2.shape
        assert numpy.alltrue(data1[:, 0] == data2[:, 1])
        assert numpy.alltrue(data1[:, 1] == data2[:, 0])

    def test2(self):
        block = verilog2.axis_block([
            os.path.join(os.path.dirname(__file__), '..',
                         '..', 'examples', 'axis_counter.v'),
        ], {'DATA_WIDTH': 8})
        sink = blocks.vector_sink_i(vlen=1, reserve_items=10)

        top = gr.top_block()
        top.connect(block, sink)
        top.start()
        time.sleep(0.01)
        top.stop()
        top.wait()

        data = numpy.array(sink.data()).flatten()
        print("produced", len(data))
        assert numpy.alltrue(data == numpy.arange(
            0, len(data), dtype=numpy.int32) % 256)

    def test3(self):
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'examples')
        block = verilog2.axis_block([
            os.path.join(path, 'axis_user_tb.v'),
            os.path.join(path, 'axis_counter.v'),
            os.path.join(path, 'axis_copy_reg.v'),
        ], {'DATA_WIDTH': 16, 'USER_WIDTH': 8})

        data1 = numpy.random.randint(0, 1000, size=(10, 1))
        source = blocks.vector_source_i(data1.flatten(), vlen=1, repeat=False)
        sink = blocks.vector_sink_i(vlen=2, reserve_items=10)

        top = gr.top_block()
        top.connect(source, block, sink)
        top.run()

        data2 = numpy.array(sink.data()).reshape((-1, 2))
        print(data1)
        print(data2)

        assert numpy.alltrue(data2[:, 0] == data1[:, 0])
        assert numpy.alltrue(data2[:, 1] == numpy.arange(
            0, len(data1), dtype=numpy.int32))


if __name__ == '__main__':
    gr_unittest.run(qa_axis_block)

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
from gnuradio import gr, blocks


class AxisSig():
    def __init__(self, tdata: int, tuser: int = 0, tlast: int = 0):
        assert tdata >= 0 and tuser >= 0 and tlast in [0, 1]

        self.tdata = int(tdata)
        self.tuser = int(tuser)
        self.tlast = int(tlast)

        self.vlen = (self.tdata + 31) // 32 + \
            (self.tuser + 31) // 32 + (self.tlast + 31) // 32

    def sig(self):
        return (numpy.int32, (self.vlen, ))


class AxisBlock(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name='Axis Block',
            in_sig=[
                AxisSig(32, 0, 0).sig(),
                AxisSig(11, 0, 1).sig(),
            ],
            out_sig=[
                AxisSig(1, 1, 1).sig()
            ]
        )

    def general_work(self, input_items, output_items):
        print(input_items, output_items)

        output_items[0][0, :] = [4, 5, 6]

        self.consume(0, 1)
        self.consume(1, 1)
        self.produce(0, 1)
        return gr.WORK_CALLED_PRODUCE


def test():
    source1 = blocks.vector_source_i([1, 2, 3], vlen=1, repeat=False)
    source2 = blocks.vector_source_i([4, 5, 6, 7], vlen=2, repeat=True)
    axis = AxisBlock()
    sink = blocks.vector_sink_i(vlen=3)

    top = gr.top_block()
    top.connect(source1, (axis, 0))
    top.connect(source2, (axis, 1))
    top.connect((axis, 0), sink)
    top.run()

    print(sink.data())


if __name__ == '__main__':
    test()

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

from typing import Any, Dict, List

import numpy
import os
from gnuradio import gr, blocks

import verilator

LIBRARY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'library'))


class AxisBlock(gr.basic_block):
    def __init__(self,
                 sources: List[str],
                 params: Dict[str, Any]):

        mod = verilator.Module(sources)
        self.ins = verilator.Instance(mod, params)

        gr.basic_block.__init__(
            self,
            name=mod.component,
            in_sig=[(numpy.int32, (n,)) for n in self.ins.input_vlens],
            out_sig=[(numpy.int32, (n,)) for n in self.ins.output_vlens],
        )

    def forecast(self, noutput_items, ninputs):
        # print("forecast", noutput_items, ninputs)
        return [1 for _ in range(ninputs)]

    def general_work(self, input_items, output_items):
        consumed, produced = self.ins.work(input_items, output_items)

        for idx, num in enumerate(consumed):
            self.consume(idx, num)
        for idx, num in enumerate(produced):
            self.produce(idx, num)

        return gr.WORK_CALLED_PRODUCE


def test():
    source = blocks.vector_source_i([1, 2, 3], vlen=1, repeat=False)
    axis_block = AxisBlock([
        os.path.join(LIBRARY, 'axis_copy_cdc', 'axis_copy_cdc.v'),
    ], {
        'DATA_WIDTH': 32,
    })
    sink = blocks.vector_sink_i(vlen=1)

    top = gr.top_block()
    top.connect(source, axis_block, sink)
    top.run()

    print(sink.data())


if __name__ == '__main__':
    test()

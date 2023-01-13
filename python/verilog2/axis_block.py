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
from gnuradio import gr

from . import verilator


class axis_block(gr.basic_block):
    def __init__(self,
                 sources: List[str],
                 params: Dict[str, Any]):

        module = verilator.Module(sources)
        self.instance = verilator.Instance(module, params)

        gr.basic_block.__init__(
            self,
            name=module.component,
            in_sig=[(numpy.int32, (n,)) for n in self.instance.input_vlens],
            out_sig=[(numpy.int32, (n,)) for n in self.instance.output_vlens],
        )

    def forecast(self, noutput_items, ninputs):
        # print("forecast", noutput_items, ninputs)
        return [1 for _ in range(ninputs)]

    def general_work(self, input_items, output_items):
        consumed, produced = self.instance.work(input_items, output_items)

        for idx, num in enumerate(consumed):
            self.consume(idx, num)
        for idx, num in enumerate(produced):
            self.produce(idx, num)

        return gr.WORK_CALLED_PRODUCE

    def read_register(self, name: str) -> int:
        return self.instance.read_register(name)

    def write_register(self, name: str, value: int = 0):
        self.instance.write_register(name, value)

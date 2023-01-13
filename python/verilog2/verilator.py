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

from typing import Any, Callable, Dict, List, Optional, Tuple

import ctypes
import hashlib
import json
import numpy
import os
import re
import subprocess
import threading


class Module:
    """
    A class that manages the parsing and compilation of a verilog module.
    """

    def __init__(self, sources: List[str],
                 component: Optional[str] = None,
                 build_dir: Optional[str] = None):
        assert len(sources) >= 1
        sources = [os.path.abspath(s) for s in sources]
        for s in sources:
            assert os.path.exists(s)
        self.sources = sources

        if component is None:
            component = os.path.splitext(os.path.basename(sources[0]))[0]
        self.component = component

        if build_dir is None:
            build_dir = os.path.join(os.path.dirname(sources[0]), 'build')
        self.build_dir = build_dir
        if not os.path.exists(build_dir):
            os.mkdir(build_dir)

        self.ports_cache = dict()
        self.lib_cache = dict()

    def _get_max_mtime(self):
        """
        Returns the maximum update time of all sources.
        """
        m = os.path.getmtime(__file__)
        for s in self.sources:
            m = max(m, os.path.getmtime(s))
        return m

    _BUILD_LOCK = threading.Lock()
    _BUILD_COND = dict()

    @staticmethod
    def _build_job(key: str, job: Callable) -> Any:
        """
        This method calls the given job with the arguments, but makes sure
        that for any key only one job is running at any given time.
        """

        with Module._BUILD_LOCK:
            while True:
                if key in Module._BUILD_COND:
                    Module._BUILD_COND[key].wait()
                else:
                    cond = threading.Condition(Module._BUILD_LOCK)
                    Module._BUILD_COND[key] = cond
                    break

        ret = job()

        with Module._BUILD_LOCK:
            del Module._BUILD_COND[key]
            cond.notify_all()

        return ret

    def _get_obj_dir(self, params: Dict[str, Any]) -> str:
        hash = hashlib.md5(str(params).encode('utf-8')).hexdigest()
        return os.path.join(self.build_dir, self.component + '-' + hash)

    def _verilator_job(self, params: Dict[str, Any]):
        obj_dir = self._get_obj_dir(params)

        if not os.path.exists(obj_dir):
            os.mkdir(obj_dir)

        header = os.path.join(obj_dir, self.component + '.h')
        if os.path.exists(header):
            if self._get_max_mtime() <= os.path.getmtime(header):
                return
            for f in os.listdir(obj_dir):
                os.remove(os.path.join(obj_dir, f))

        command = [
            'verilator',
            '-cc',
            '--exe',
            # '--threads', '1',
            '-CFLAGS', '-fPIC',
            '-LDFLAGS', '-shared',
            '-Wno-lint',
            '--prefix', self.component,
            '--Mdir', obj_dir,
            '-o', 'lib{}.so'.format(self.component),
        ]

        def quote(val):
            return '"' + val + '"' if isinstance(val, str) else str(val)
        command.extend(['-G{}={}'.format(key, quote(val))
                        for key, val in params.items()])

        command.extend(self.sources)
        command.append('wrapper.cpp')

        print(" ".join(command))
        result = subprocess.run(command, cwd=self.build_dir)
        result.check_returncode()
        assert(os.path.exists(header))

    _RE_PORT = re.compile(
        r'^\s*VL_(IN|OUT)(|8|16|32|64|W)\((\w+),(\d+),(\d+)(,\d+)?\)')

    def _parse_ports_job(self, obj_dir: str) -> Dict[str, Any]:
        header_path = os.path.join(obj_dir, self.component + '.h')

        mtime = os.path.getmtime(header_path)
        if header_path in self.ports_cache:
            ports, mtime2 = self.ports_cache[header_path]
            if mtime == mtime2:
                return ports

        clocks = []
        resets = []
        resetns = []
        buses = {}
        dregs = {}

        def axis(dir, name, width):
            for sig in ['tvalid', 'tready', 'tdata', 'tuser', 'tlast']:
                if not name.endswith('_' + sig):
                    continue
                bus = name[:-(1 + len(sig))]

                if sig in ['tvalid', 'tready', 'tlast']:
                    assert width == 1

                if sig == 'tready':
                    dir = 'OUT' if dir == 'IN' else 'IN'

                axis = buses.setdefault(bus, {'dir': dir})
                assert axis['dir'] == dir
                assert sig not in axis
                axis[sig] = width

                return True
            return False

        def dreg(dir, name, width):
            for sig in ['dout', 'din', 'dset']:
                if not name.endswith('_' + sig):
                    continue
                bus = name[:-(1 + len(sig))]

                if sig == 'dout':
                    assert dir == 'OUT'
                else:
                    assert dir == 'IN'

                dreg = dregs.setdefault(bus, {})
                assert sig not in dreg
                dreg[sig] = True

                if sig == 'dset':
                    assert width == 1
                else:
                    assert 'width' not in dreg or dreg['width'] == width
                    assert width <= 64
                    dreg['width'] = width

                return True
            return False

        with open(header_path, 'r') as file:
            for line in file.readlines():
                match = Module._RE_PORT.match(line)
                if not match:
                    continue

                dir = match.group(1)
                name = match.group(3)
                width = int(match.group(4)) + 1
                assert match.group(5) == '0'

                if name.endswith('clock') or name.endswith('clk'):
                    assert dir == 'IN' and width == 1
                    clocks.append(name)
                elif name.endswith('reset') or name.endswith('rst'):
                    assert dir == 'IN' and width == 1
                    resets.append(name)
                elif name.endswith('resetn') or name.endswith('rstn'):
                    assert dir == 'IN' and width == 1
                    resetns.append(name)
                elif axis(dir, name, width):
                    pass
                elif dreg(dir, name, width):
                    pass
                else:
                    raise ValueError('invalid signal: ' + name)

        clocks = sorted(clocks)
        resets = sorted(resets)
        resetns = sorted(resetns)

        for bus in buses.values():
            assert 'tvalid' in bus and 'tready' in bus

        for bus in dregs.values():
            assert 'din' not in bus or 'dset' in bus

        inputs = [{
            'name': key,
            'tdata': val.get('tdata', 0),
            'tuser': val.get('tuser', 0),
            'tlast': val.get('tlast', 0),
        } for key, val in buses.items() if val['dir'] == 'IN']
        inputs = sorted(inputs, key=lambda d: d['name'])

        outputs = [{
            'name': key,
            'tdata': val.get('tdata', 0),
            'tuser': val.get('tuser', 0),
            'tlast': val.get('tlast', 0),
        } for key, val in buses.items() if val['dir'] != 'IN']
        sorted(outputs, key=lambda d: d['name'])

        registers = [{
            'name': key,
            'width': val.get('width', 0),
            'dout': val.get('dout', False),
            'din': val.get('din', False),
            'dset': val.get('dset', False),
        } for key, val in dregs.items()]
        registers = sorted(registers, key=lambda d: d['name'])

        input_vlens = [Module._get_vlen(a) for a in inputs]
        output_vlens = [Module._get_vlen(a) for a in outputs]
        reg_widths = [a['width'] for a in registers]

        ports = {
            'clocks': clocks,
            'resets': resets,
            'resetns': resetns,
            'inputs': inputs,
            'outputs': outputs,
            'input_vlens': input_vlens,
            'output_vlens': output_vlens,
            'registers': registers,
            'reg_widths': reg_widths,
        }
        self.ports_cache[header_path] = (ports, mtime)

        return ports

    def get_ports(self, params: Dict[str, Any]):
        obj_dir = self._get_obj_dir(params)

        def job():
            self._verilator_job(params)
            return self._parse_ports_job(obj_dir)

        return Module._build_job(obj_dir, job)

    @staticmethod
    def _get_vlen(bus: Dict[str, int]) -> int:
        return (bus['tdata'] + 31) // 32 \
            + (bus['tuser'] + 31) // 32 \
            + (bus['tlast'] + 31) // 32

    def get_input_vlens(self, params: Dict[str, Any]) -> List[int]:
        return self.get_ports(params)['input_vlens']

    def get_output_vlens(self, params: Dict[str, Any]) -> List[int]:
        return self.get_ports(params)['output_vlens']

    def get_reg_widths(self, params: Dict[str, Any]) -> List[int]:
        return self.get_ports(params)['reg_widths']

    _WRAPPER_TEMPLATE = """// Generated, do not modify!

#include <iostream>
#include "{component}.h"

const wchar_t *CONFIG = L"{config}";

extern "C" const wchar_t *config()
{{
    return CONFIG;
}}

struct Block
{{
    const wchar_t *config = CONFIG;
    {component} impl;
}};

extern "C" Block *create_block()
{{
    std::cout << "create_block: {component}\\n";
    return new Block();
}}

extern "C" void destroy_block(Block *block)
{{
    std::cout << "destroy_block: {component}\\n";
    assert(block != nullptr && block->config == CONFIG);
    block->config = nullptr;
    delete block;
}}

void set_clocks(Block *block, int value)
{{
{set_clocks}}}

void set_resets(Block *block, int value)
{{
{set_resets}}}

extern "C" void reset_block(Block *block)
{{
    assert(block != nullptr && block->config == CONFIG);

    set_resets(block, 1);
{axis_disable}
    for (int i = 0; i < 4; i++)
    {{
        set_clocks(block, i & 1);
        block->impl.eval();
    }}

    set_resets(block, 0);
}}

QData get_qdata(const int32_t *input)
{{
    uint32_t data0 = input[0];
    uint32_t data1 = input[1];
    return ((uint64_t)data1 << 32) | data0;
}}

void set_qdata(int32_t *output, QData data)
{{
    output[0] = (uint64_t)data;
    output[1] = (uint64_t)data >> 32;
}}

extern "C" void work_block(Block *block,
                           int64_t *input_sizes,
                           int64_t *output_sizes,
                           int32_t **input_items,
                           int32_t **output_items)
{{
    assert(block != nullptr && block->config == CONFIG);

{read_sizes}
    int idle = 0;
    while (idle < 100)
    {{
        idle += 1;

{axis_stage1}
        set_clocks(block, 0);
        block->impl.eval();

{axis_stage2}
        set_clocks(block, 1);
        block->impl.eval();

{axis_stage3}    }}

{write_sizes}}}

extern "C" uint64_t read_register(Block *block, uint32_t reg)
{{
    assert(block != nullptr && block->config == CONFIG);
    uint64_t value = 0;

{read_regs}
    return value;
}}
"""

    def _compile_job(self, params: Dict[str, Any]):
        """
        This method generates the wrapper.cpp file and compiles the verilated
        sources into a dynamically linked library.
        """

        obj_dir = self._get_obj_dir(params)

        lib_path = os.path.join(obj_dir, 'lib{}.so'.format(self.component))
        if os.path.exists(lib_path):
            if self._get_max_mtime() <= os.path.getmtime(lib_path):
                return
            os.remove(lib_path)

        ports = self._parse_ports_job(obj_dir)

        set_clocks = ""
        for name in ports['clocks']:
            set_clocks += "    block->impl.{} = value;\n".format(name)

        set_resets = ""
        for name in ports['resets']:
            set_resets += "    block->impl.{} = value;\n".format(name)
        for name in ports['resetns']:
            set_resets += "    block->impl.{} = value == 0 ? 1 : 0;\n".format(
                name)

        axis_disable = ""
        for axis in ports['inputs']:
            axis_disable += "    block->impl.{}_tvalid = 0;\n".format(
                axis['name'])
        for axis in ports['outputs']:
            axis_disable += "    block->impl.{}_tready = 0;\n".format(
                axis['name'])

        read_sizes = ""
        for idx, axis in enumerate(ports['inputs']):
            read_sizes += (
                "    int64_t {name}_size = input_sizes[{idx}];\n"
                "    const int32_t *{name}_data = input_items[{idx}];\n"
                "    bool {name}_step;\n"
            ).format(name=axis['name'], idx=idx)
        for idx, axis in enumerate(ports['outputs']):
            read_sizes += (
                "    int64_t {name}_size = output_sizes[{idx}];\n"
                "    int32_t *{name}_data = output_items[{idx}];\n"
            ).format(name=axis['name'], idx=idx)

        axis_stage1 = ""

        for idx, axis in enumerate(ports['inputs']):
            name = axis['name']
            axis_stage1 += (
                "        if (block->impl.{name}_tvalid == 0 && {name}_size > 0)\n"
                "        {{\n"
            ).format(name=name)

            offset = 0
            for port in ['tdata', 'tuser', 'tlast']:
                width = axis[port]
                if width <= 0:
                    pass
                elif width <= 32:
                    axis_stage1 += (
                        "            block->impl.{name}_{port} = {name}_data[{offset}];\n"
                    ).format(name=name, port=port, offset=offset)
                    offset += 1
                elif width <= 64:
                    axis_stage1 += (
                        "            block->impl.{name}_{port} = get_qdata({name}_data + {offset});\n"
                    ).format(name=name, port=port, offset=offset)
                    offset += 2
                else:
                    for i in range((width + 31) // 32):
                        axis_stage1 += (
                            "            block->impl.{name}_{port}[{index}] = {name}_data[{offset}];\n"
                        ).format(name=name, port=port, index=i, offset=offset)
                        offset += 1

            assert(ports['input_vlens'][idx] == offset)
            axis_stage1 += (
                "            block->impl.{name}_tvalid = 1;\n"
                "            {name}_data += {offset};\n"
                "            {name}_size -= 1;\n"
                "            idle = 0;\n"
                "        }}\n"
            ).format(name=name, offset=offset)

        for axis in ports['outputs']:
            axis_stage1 += (
                "        block->impl.{name}_tready = {name}_size > 0 ? 1 : 0;\n"
            ).format(name=axis['name'])

        axis_stage2 = ""

        for axis in ports['inputs']:
            name = axis['name']
            axis_stage2 += (
                "        {name}_step = (block->impl.{name}_tvalid != 0 && block->impl.{name}_tready != 0);\n"
            ).format(name=axis['name'])

        for idx, axis in enumerate(ports['outputs']):
            name = axis['name']

            axis_stage2 += (
                "        if (block->impl.{name}_tvalid != 0 && block->impl.{name}_tready != 0)\n"
                "        {{\n"
            ).format(name=name)

            offset = 0
            for port in ['tdata', 'tuser', 'tlast']:
                width = axis[port]
                if width <= 0:
                    pass
                elif width <= 32:
                    axis_stage2 += (
                        "            {name}_data[{offset}] = block->impl.{name}_{port} & 0x{mask:x}u;\n"
                    ).format(name=name, port=port, offset=offset, mask=(1 << width)-1)
                    offset += 1
                elif width <= 64:
                    axis_stage2 += (
                        "            set_qdata({name}_data + {offset}, block->impl.{name}_{port} & 0x{mask:x}ul);\n"
                    ).format(name=name, port=port, offset=offset, mask=(1 << width)-1)
                    offset += 2
                else:
                    count = (width + 31) // 32
                    for i in range(count - 1):
                        axis_stage2 += (
                            "            {name}_data[{offset}] = block->impl.{name}_{port}[{index}];\n"
                        ).format(name=name, port=port, index=i, offset=offset)
                        offset += 1
                    axis_stage2 += (
                        "            {name}_data[{offset}] = block->impl.{name}_{port}[{index}] & 0x{mask:x}u;\n"
                    ).format(name=name, port=port, index=count - 1, offset=offset,
                             mask=(1 << (width + 32 - 32*count)) - 1)
                    offset += 1

            assert(ports['output_vlens'][idx] == offset)
            axis_stage2 += (
                "            {name}_data += {offset};\n"
                "            {name}_size -= 1;\n"
                "            idle = 0;\n"
                "        }}\n"
            ).format(name=name, offset=offset)

        axis_stage3 = ""
        for axis in ports['inputs']:
            axis_stage3 += (
                "        if ({name}_step)\n"
                "            block->impl.{name}_tvalid = 0;\n"
            ).format(name=axis['name'])

        write_sizes = ""
        for idx, axis in enumerate(ports['inputs']):
            write_sizes += (
                "    input_sizes[{idx}] -= {name}_size;\n"
            ).format(name=axis['name'], idx=idx)
        for idx, axis in enumerate(ports['outputs']):
            write_sizes += (
                "    output_sizes[{idx}] -= {name}_size;\n"
            ).format(name=axis['name'], idx=idx)

        read_regs = ""
        for idx, dreg in enumerate(ports['registers']):
            read_regs += (
                "    if (reg == {idx})\n"
                "        value = block->impl.{name}_dout;\n"
            ).format(idx=idx, name=dreg['name'])

        config = {
            'component': self.component,
            'params': params,
        }
        config.update(ports)
        config = json.dumps(config, ensure_ascii=True)
        config = config.replace('"', '\\"')

        content = Module._WRAPPER_TEMPLATE.format(
            component=self.component,
            config=config,
            set_clocks=set_clocks,
            set_resets=set_resets,
            axis_disable=axis_disable,
            read_sizes=read_sizes,
            axis_stage1=axis_stage1,
            axis_stage2=axis_stage2,
            axis_stage3=axis_stage3,
            write_sizes=write_sizes,
            read_regs=read_regs,
        )

        filename = os.path.join(obj_dir, 'wrapper.cpp')
        with open(filename, 'w') as file:
            file.write(content)

        command = [
            'make',
            '-j4',
            '-f', self.component + '.mk'
        ]

        print(" ".join(command))
        result = subprocess.run(
            command, cwd=os.path.join(obj_dir))
        result.check_returncode()
        assert(os.path.exists(lib_path))

    CTYPES_ITEMS = numpy.ctypeslib.ndpointer(
        ctypes.c_int32, flags="C_CONTIGUOUS")

    def _load_library_job(self, obj_dir: str) -> ctypes.CDLL:
        lib_path = os.path.join(obj_dir, 'lib{}.so'.format(self.component))

        mtime = os.path.getmtime(lib_path)
        if lib_path in self.lib_cache:
            lib, mtime2 = self.lib_cache[lib_path]
            if mtime == mtime2:
                return lib

        lib = ctypes.cdll.LoadLibrary(lib_path)
        lib.config.restype = ctypes.c_wchar_p
        config = json.loads(lib.config())
        num_inputs = len(config['input_vlens'])
        num_outputs = len(config['output_vlens'])

        lib.create_block.restype = ctypes.c_void_p
        lib.destroy_block.argtypes = [ctypes.c_void_p]
        lib.reset_block.argtypes = [ctypes.c_void_p]
        lib.work_block.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int64 * num_inputs,
            ctypes.c_int64 * num_outputs,
            Module.CTYPES_ITEMS * num_inputs,
            Module.CTYPES_ITEMS * num_outputs,
        ]
        lib.read_register.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.read_register.restype = ctypes.c_uint64

        self.lib_cache[lib_path] = (lib, mtime)
        return lib

    def get_library(self, params: Dict[str, Any]):
        obj_dir = self._get_obj_dir(params)

        def job():
            self._verilator_job(params)
            self._compile_job(params)
            return self._load_library_job(obj_dir)

        return Module._build_job(obj_dir, job)


class Instance:
    """
    A class that manages the creation and execution of a verilog instance.
    """

    def __init__(self, module: Module, params: Dict[str, Any]):
        self.block = None  # for clean __del__

        self.lib = module.get_library(params)
        self.config = json.loads(self.lib.config())
        self.input_vlens = self.config['input_vlens']
        self.output_vlens = self.config['output_vlens']

        self._reg_indices = {r['name']: i for
                             i, r in enumerate(self.config['registers'])}

        self._input_sizes = (ctypes.c_int64 * len(self.input_vlens))()
        self._output_sizes = (ctypes.c_int64 * len(self.output_vlens))()
        self._input_items = (Module.CTYPES_ITEMS * len(self.input_vlens))()
        self._output_items = (Module.CTYPES_ITEMS * len(self.output_vlens))()

        self.block = self.lib.create_block()
        self.reset()

    def close(self):
        if self.block is not None:
            self.lib.destroy_block(self.block)
            self.block = None

    def __del__(self):
        self.close()

    @ property
    def input_buses(self) -> List[str]:
        return [b['name'] for b in self.config['inputs']]

    @ property
    def output_buses(self) -> List[str]:
        return [b['name'] for b in self.config['outputs']]

    @ property
    def register_names(self) -> List[str]:
        return [b['name'] for b in self.config['registers']]

    def reset(self):
        """
        Resets the underlying verilog block.
        """

        self.lib.reset_block(self.block)

    def work(self,
             input_items: List[numpy.ndarray],
             output_items: List[numpy.ndarray]) -> Tuple[List[int], List[int]]:
        """
        Calls the underlying verilog block with the given input and output
        buffers and returns the number of consumed and produced items.
        """

        assert len(input_items) == len(self.input_vlens)
        for i, a in enumerate(input_items):
            assert a.ndim == 2 and a.shape[1] == self.input_vlens[i]
            self._input_sizes[i] = a.shape[0]
            self._input_items[i] = a.ctypes.data

        assert len(output_items) == len(self.output_vlens)
        for i, a in enumerate(output_items):
            assert a.ndim == 2 and a.shape[1] == self.output_vlens[i]
            self._output_sizes[i] = a.shape[0]
            self._output_items[i] = a.ctypes.data

        if False:
            print("input_sizes", list(self._input_sizes))
            print("output_sizes", list(self._output_sizes))
            print("input_items", input_items)
            print("output_items", output_items)

        self.lib.work_block(self.block,
                            self._input_sizes,
                            self._output_sizes,
                            self._input_items,
                            self._output_items)

        consumed = list(self._input_sizes)
        produced = list(self._output_sizes)

        if False:
            print("consumed", consumed)
            print("produced", produced)
            print("input_items", input_items)
            print("output_items", output_items)

        for i in range(len(self._input_items)):
            self._input_items[i] = None

        for i in range(len(self._output_items)):
            self._output_items[i] = None

        return consumed, produced

    def read_reg(self, reg: str) -> int:
        """
        Reads the current value of the given register.
        """
        idx = self._reg_indices[reg]
        return self.lib.read_register(self.block, idx)

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

from typing import Any, Dict, Optional

import ctypes
import hashlib
import json
import os
import re
import subprocess


class Verilator:
    def __init__(self,
                 verilog: str,
                 params: Dict[str, Any],
                 build_path: Optional[str] = None):
        self.verilog = os.path.abspath(verilog)
        if not os.path.exists(verilog):
            raise ValueError('Verilog file not found')

        self.component = os.path.splitext(os.path.basename(self.verilog))[0]
        self.params = params

        if build_path is None:
            build_path = os.path.join(os.path.dirname(self.verilog), 'build')
        self.build_path = build_path
        if not os.path.exists(self.build_path):
            os.mkdir(self.build_path)

        self.hash = hashlib.md5(str(params).encode('utf-8')).hexdigest()

        self.obj_dir = 'verilator-' + self.hash
        obj_path = os.path.join(self.build_path, self.obj_dir)
        if not os.path.exists(obj_path):
            os.mkdir(obj_path)

        self.lib_name = 'lib' + self.component + '-' + self.hash + '.so'

        lib_path = os.path.join(self.build_path, self.obj_dir, self.lib_name)
        if os.path.exists(lib_path):
            mtime = max([os.path.getmtime(f) for f in [
                __file__,
                verilog,
            ]])
            if os.path.getmtime(lib_path) < mtime:
                os.remove(lib_path)

        if not os.path.exists(lib_path):
            self._generate_verilator()
            self._generate_wrapper()
            self._make()

        self.lib = ctypes.cdll.LoadLibrary(lib_path)
        self.lib.create_block.restype = ctypes.c_void_p
        self.lib.destroy_block.argtypes = [ctypes.c_void_p]
        self.lib.reset_block.argtypes = [ctypes.c_void_p]
        self.lib.block_config.argtypes = [ctypes.c_void_p]
        self.lib.block_config.restype = ctypes.c_wchar_p
        self.lib.library_config.restype = ctypes.c_wchar_p

    def _generate_verilator(self):
        obj_path = os.path.join(self.build_path, self.obj_dir)
        if os.path.exists(obj_path):
            for file in os.listdir(obj_path):
                os.remove(os.path.join(obj_path, file))

        command = [
            'verilator',
            '-cc',
            '--exe',
            '--threads', '1',
            '-CFLAGS', '-fPIC',
            '-LDFLAGS', '-shared',
            '--prefix', self.component,
            '--Mdir', self.obj_dir,
            '-o', self.lib_name,
            self.verilog,
            'wrapper.cpp',
        ]
        command.extend(['-G{}={}'.format(key, str(val))
                        for key, val in self.params.items()])

        print(" ".join(command))
        result = subprocess.run(command, cwd=self.build_path)
        result.check_returncode()

    _RE_PORT = re.compile(r'^\s*VL_(IN|OUT)(|8|16|32|64)\((\w+),(\d+),(\d+)\)')

    def _parse_ports(self) -> Dict[str, Any]:
        clocks = []
        resets = []
        buses = {}

        def axis(dir, name, width):
            for sig in ['tvalid', 'tready', 'tdata', 'tuser', 'tlast']:
                if not name.endswith('_' + sig):
                    continue
                bus = name[:-(1 + len(sig))]

                if sig in ['tvalid', 'tready', 'tlast']:
                    assert width == 1

                if sig == 'tready':
                    dir = 'IN' if dir != 'IN' else 'OUT'

                axis = buses.setdefault(bus, {'dir': dir})
                assert axis['dir'] == dir
                assert sig not in axis
                axis[sig] = width

                return True
            return False

        filename = os.path.join(
            self.build_path, self.obj_dir, self.component + '.h')
        with open(filename, 'r') as file:
            for line in file.readlines():
                match = Verilator._RE_PORT.match(line)
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
                elif axis(dir, name, width):
                    pass
                else:
                    raise ValueError('invalid signal: ' + name)

        for axis in buses.values():
            assert 'tvalid' in axis and 'tready' in axis

        inputs = [{
            'name': key,
            'tdata': val.get('tdata', 0),
            'tuser': val.get('tuser', 0),
            'tlast': val.get('tlast', 0),
        } for key, val in buses.items() if val['dir'] == 'IN']

        outputs = [{
            'name': key,
            'tdata': val.get('tdata', 0),
            'tuser': val.get('tuser', 0),
            'tlast': val.get('tlast', 0),
        } for key, val in buses.items() if val['dir'] != 'IN']

        return {
            'clocks': sorted(clocks),
            'resets': sorted(resets),
            'inputs': sorted(inputs, key=lambda d: d['name']),
            'outputs': sorted(outputs, key=lambda d: d['name']),
        }

    _WRAPPER = """// Generated, do not modify!

#include <iostream>
#include "{component}.h"

const wchar_t *CONFIG = L"{config}";

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
    assert(block != nullptr && std::wcscmp(block->config, CONFIG) == 0);
    block->config = L"";
    delete block;
}}

extern "C" const wchar_t *library_config()
{{
    return CONFIG;
}}

extern "C" const wchar_t *block_config(Block *block)
{{
    return block->config;
}}

void set_clocks(Block *block, int value)
{{
{set_clocks}}}

void set_resets(Block *block, int value)
{{
{set_resets}}}

extern "C" void reset_block(Block *block)
{{
    set_resets(block, 1);
{inhibits}
    for (int i = 1; i <= 4; i++)
    {{
        set_clocks(block, i & 1);
        block->impl.eval();
    }}

    set_resets(block, 0);
}}
"""

    def _generate_wrapper(self):
        ports = self._parse_ports()

        set_clocks = ""
        for name in ports['clocks']:
            set_clocks += "    block->impl.{} = value;\n".format(name)

        set_resets = ""
        for name in ports['resets']:
            set_resets += "    block->impl.{} = value;\n".format(name)

        inhibits = ""
        for axis in ports['inputs']:
            inhibits += "    block->impl.{}_tvalid = 0;\n".format(axis['name'])
        for axis in ports['outputs']:
            inhibits += "    block->impl.{}_tready = 0;\n".format(axis['name'])

        config = {
            'component': self.component,
            'params': self.params,
            'hash': self.hash,
        }
        config.update(ports)
        config = json.dumps(config, ensure_ascii=True)
        config = config.replace('"', '\\"')

        content = Verilator._WRAPPER.format(
            component=self.component,
            config=config,
            set_clocks=set_clocks,
            set_resets=set_resets,
            inhibits=inhibits,
        )

        wrapper_path = os.path.join(
            self.build_path, self.obj_dir, 'wrapper.cpp')

        with open(wrapper_path, 'w') as file:
            file.write(content)

    def _make(self):
        command = [
            'make',
            '-j4',
            '-f', self.component + '.mk'
        ]

        print(" ".join(command))
        result = subprocess.run(
            command, cwd=os.path.join(self.build_path, self.obj_dir))
        result.check_returncode()


LIBRARY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'library'))


def test():
    ver = Verilator(
        os.path.join(LIBRARY, 'axis_copy_cdc', 'axis_copy_cdc.v'),
        {'DATA_WIDTH': 32})

    print(ver.lib.library_config())
    block = ver.lib.create_block()
    ver.lib.reset_block(block)
    print(ver.lib.block_config(block))
    ver.lib.destroy_block(block)


if __name__ == '__main__':
    test()

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

from typing import Any, Dict, List, Optional

import collections
import ctypes
import hashlib
import os
import re
import subprocess

Port = collections.namedtuple('Port', [
    'dir', 'name', 'width', 'bus', 'role'])


class Verilog:
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

    def generate_verilator(self):
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

    RE_PORT = re.compile(r'^\s*VL_(IN|OUT)(8|16|32|64)\((\w+),(\d+),(\d+)\)')

    def parse_ports(self) -> List[Port]:
        def resolve_port(dir: str, name: str, width: int) -> Port:
            if dir == 'IN' and name.lower() in ['clock', 'clk']:
                bus = ''
                role = 'clock'
            elif dir == 'IN' and name.lower() in ['reset', 'rst']:
                bus = ''
                role = 'reset'
            elif name.lower().endswith('_tvalid'):
                bus = name[:-7]
                role = 'tvalid'
            elif name.lower().endswith('_tready'):
                bus = name[:-7]
                role = 'tready'
            elif name.lower().endswith('_tdata'):
                bus = name[:-6]
                role = 'tdata'
            elif name.lower().endswith('_tuser'):
                bus = name[:-6]
                role = 'tuser'
            elif name.lower().endswith('_tlast'):
                bus = name[:-6]
                role = 'tlast'
            else:
                raise ValueError("Unknown port name: " + name)

            return Port(dir, name, width, bus, role)

        ports = []
        filename = os.path.join(
            self.build_path, self.obj_dir, self.component + '.h')
        with open(filename, 'r') as file:
            for line in file.readlines():
                match = Verilog.RE_PORT.match(line)
                if match:
                    dir = match.group(1)
                    name = match.group(3)
                    width = int(match.group(4)) + 1
                    assert match.group(5) == '0'
                    ports.append(resolve_port(dir, name, width))

        return ports

    WRAPPER = """// Generated, do not modify!

#include <iostream>
#include "{component}.h"

struct Block
{{
    const char *name = "{name}";
    {component} impl;
}};

extern "C" Block *create_block()
{{
    std::cout << "Creating {name}\\n";
    return new Block();
}}

extern "C" void destroy_block(Block *block)
{{
    std::cout << "Destroying {name}\\n";

    assert(block != nullptr && std::strcmp(block->name, "{name}") == 0);
    block->name = "";
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
    set_resets(block, 1);
    for (int i = 1; i <= 4; i++)
    {{
        set_clocks(block, i & 1);
        block->impl.eval();
    }}
    set_resets(block, 0);
}}
"""

    def generate_wrapper(self):
        ports = self.parse_ports()

        set_clocks = ""
        set_resets = ""

        for port in ports:
            if port.role == 'clock':
                set_clocks += "    block->impl.{} = value;\n".format(port.name)
            elif port.role == 'reset':
                set_resets += "    block->impl.{} = value;\n".format(port.name)

        name = self.component + ' ' + str(self.params)

        content = Verilog.WRAPPER.format(
            component=self.component,
            name=name,
            set_clocks=set_clocks,
            set_resets=set_resets,
        )

        wrapper_path = os.path.join(
            self.build_path, self.obj_dir, 'wrapper.cpp')

        with open(wrapper_path, 'w') as file:
            file.write(content)

    def make(self):
        command = [
            'make',
            '-j4',
            '-f', self.component + '.mk'
        ]

        print(" ".join(command))
        result = subprocess.run(
            command, cwd=os.path.join(self.build_path, self.obj_dir))
        result.check_returncode()

    def load_library(self, rebuild: bool = False):
        lib_path = os.path.join(self.build_path, self.obj_dir, self.lib_name)
        if rebuild or not os.path.exists(lib_path):
            self.generate_verilator()
            self.parse_ports()
            self.generate_wrapper()
            self.make()

        lib = ctypes.cdll.LoadLibrary(lib_path)
        lib.create_block.restype = ctypes.c_void_p
        lib.destroy_block.argtypes = [ctypes.c_void_p]
        lib.reset_block.argtypes = [ctypes.c_void_p]

        block = lib.create_block()
        lib.reset_block(block)
        lib.destroy_block(block)

        return lib


LIBRARY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'library'))


def test():
    ver = Verilog(
        os.path.join(LIBRARY, 'axis_counter', 'axis_counter.v'),
        {'DATA_WIDTH': 64})
    ver.load_library()


if __name__ == '__main__':
    test()

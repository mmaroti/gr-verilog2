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

import collections
import ctypes
import hashlib
import os
import re
import subprocess

Port = collections.namedtuple('Port', [
    'dir', 'name', 'width', 'bus', 'role'])

LIBRARY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'library'))


class Verilog:
    def __init__(self, component: str, params: Dict[str, Any]):
        self.component = component
        filename = os.path.abspath(
            os.path.join(LIBRARY, component, component + '.v'))
        if not os.path.exists(filename):
            raise ValueError("Component does not exists")

        self.build = os.path.join(LIBRARY, component, 'build')
        if not os.path.exists(self.build):
            os.mkdir(self.build)

        self.params = params

        # hash of verilog source and params
        with open(filename, 'rb') as file:
            data = file.read()
        data += str(params).encode('utf-8')
        self.hash = hashlib.md5(data).hexdigest()

        self.obj_dir = 'verilator-' + self.hash
        dirname = os.path.join(self.build, self.obj_dir)
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        self.lib_name = 'lib' + self.component + '-' + self.hash + '.so'

    def clean_obj_dir(self):
        dirname = os.path.join(self.build, self.obj_dir)
        if os.path.exists(dirname):
            for file in os.listdir(dirname):
                os.remove(os.path.join(dirname, file))

    def generate_verilator(self):
        self.clean_obj_dir()

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
            os.path.join('..', self.component + '.v'),
            'wrapper.cpp',
        ]
        command.extend(['-G{}={}'.format(key, str(val))
                        for key, val in self.params.items()])

        print(" ".join(command))
        result = subprocess.run(command, cwd=self.build)
        result.check_returncode()

    RE_PORT = re.compile(r'^\s*VL_(IN|OUT)(8|16|32|64)\((\w+),(\d+),(\d+)\)')

    @staticmethod
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

    def get_ports(self) -> List[Port]:
        ports = []
        filename = os.path.join(
            self.build, self.obj_dir, self.component + '.h')
        with open(filename, 'r') as file:
            for line in file.readlines():
                match = Verilog.RE_PORT.match(line)
                if match:
                    dir = match.group(1)
                    name = match.group(3)
                    width = int(match.group(4)) + 1
                    assert match.group(5) == '0'
                    ports.append(Verilog.resolve_port(dir, name, width))

        self.ports = ports
        print(ports)
        return ports

    def generate_wrapper(self):
        content = """// Generated, do not modify!

#include "{component}.h"

extern "C"
int test_verilog(int value)
{{
        {component} top;

        top.reset = 1;
        for (int i = 0; i < 2; i++) {{
            top.clock = 1;
            top.eval();
            top.clock = 0;
            top.eval();
        }}

        for (int i = 0; i < 100; i++)
        {{
                top.eval();
        }}

        top.final();
        return value + 1;
}}
"""

        content = content.format(
            component=self.component
        )

        filename = os.path.join(self.build, self.obj_dir, 'wrapper.cpp')
        with open(filename, 'w') as file:
            file.write(content)

    def make(self):
        command = [
            'make',
            '-j4',
            '-f', self.component + '.mk'
        ]

        print(" ".join(command))
        result = subprocess.run(
            command, cwd=os.path.join(self.build, self.obj_dir))
        result.check_returncode()

    def load_library(self):
        filename = os.path.join(self.build, self.obj_dir, self.lib_name)
        lib = ctypes.cdll.LoadLibrary(filename)
        print(lib.test_verilog(1))
        return lib

    def build_and_load(self, force: bool = False):
        filename = os.path.join(self.build, self.obj_dir, self.lib_name)
        if force or not os.path.exists(filename):
            self.clean_obj_dir()
            self.generate_verilator()
            self.get_ports()
            self.generate_wrapper()
            self.make()
        return self.load_library()


def test():
    ver = Verilog('axis_copy_reg', {'DATA_WIDTH': 64})
    ver.build_and_load()


if __name__ == '__main__':
    test()

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

from typing import Any, Callable, Dict, List, Optional

import ctypes
import hashlib
import json
import os
import re
import subprocess
import threading


class Module:
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
            cond.notifyAll()

        return ret

    def _get_obj_dir(self, params: Dict[str, Any]) -> str:
        hash = hashlib.md5(str(params).encode('utf-8')).hexdigest()
        return os.path.join(self.build_dir, 'verilator-' + hash)

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
            '--threads', '1',
            '-CFLAGS', '-fPIC',
            '-LDFLAGS', '-shared',
            '--prefix', self.component,
            '--Mdir', obj_dir,
            '-o', 'lib{}.so'.format(self.component),
        ]
        command.extend(['-G{}={}'.format(key, str(val))
                        for key, val in params.items()])
        command.extend(self.sources)
        command.append('wrapper.cpp')

        print(" ".join(command))
        result = subprocess.run(command, cwd=self.build_dir)
        result.check_returncode()
        assert(os.path.exists(header))

    _RE_PORT = re.compile(r'^\s*VL_(IN|OUT)(|8|16|32|64)\((\w+),(\d+),(\d+)\)')

    def _parse_ports_job(self, obj_dir: str) -> Dict[str, Any]:
        header_path = os.path.join(obj_dir, self.component + '.h')

        mtime = os.path.getmtime(header_path)
        if header_path in self.ports_cache:
            ports, mtime2 = self.ports_cache[header_path]
            if mtime == mtime2:
                return ports

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
                    dir = 'OUT' if dir == 'IN' else 'IN'

                axis = buses.setdefault(bus, {'dir': dir})
                assert axis['dir'] == dir
                assert sig not in axis
                axis[sig] = width

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
                elif axis(dir, name, width):
                    pass
                else:
                    raise ValueError('invalid signal: ' + name)

        for bus in buses.values():
            assert 'tvalid' in bus and 'tready' in bus

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

        ports = {
            'clocks': sorted(clocks),
            'resets': sorted(resets),
            'inputs': sorted(inputs, key=lambda d: d['name']),
            'outputs': sorted(outputs, key=lambda d: d['name']),
        }
        self.ports_cache[header_path] = (ports, mtime)

        return ports

    def get_ports(self, params: Dict[str, Any]):
        obj_dir = self._get_obj_dir(params)

        def job():
            self._verilator_job(params)
            return self._parse_ports_job(obj_dir)

        return Module._build_job(obj_dir, job)

    _WRAPPER = """// Generated, do not modify!

# include <iostream>
# include "{component}.h"

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
    assert(block != nullptr && std::wcscmp(block->config, CONFIG) == 0);
    block->config = L"";
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
    assert(block != nullptr);
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

    def _compile_job(self, params: Dict[str, Any]):
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

        inhibits = ""
        for axis in ports['inputs']:
            inhibits += "    block->impl.{}_tvalid = 0;\n".format(axis['name'])
        for axis in ports['outputs']:
            inhibits += "    block->impl.{}_tready = 0;\n".format(axis['name'])

        config = {
            'component': self.component,
            'params': params,
        }
        config.update(ports)
        config = json.dumps(config, ensure_ascii=True)
        config = config.replace('"', '\\"')

        content = Module._WRAPPER.format(
            component=self.component,
            config=config,
            set_clocks=set_clocks,
            set_resets=set_resets,
            inhibits=inhibits,
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

    def _load_library_job(self, obj_dir: str) -> ctypes.CDLL:
        lib_path = os.path.join(obj_dir, 'lib{}.so'.format(self.component))

        mtime = os.path.getmtime(lib_path)
        if lib_path in self.lib_cache:
            lib, mtime2 = self.lib_cache[lib_path]
            if mtime == mtime2:
                return lib

        lib = ctypes.cdll.LoadLibrary(lib_path)
        lib.config.restype = ctypes.c_wchar_p
        lib.create_block.restype = ctypes.c_void_p
        lib.destroy_block.argtypes = [ctypes.c_void_p]
        lib.reset_block.argtypes = [ctypes.c_void_p]
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
    def __init__(self, module: Module, params: Dict[str, Any]):
        self.lib = module.get_library(params)
        self.block = self.lib.create_block()

    def close(self):
        if self.block is not None:
            self.lib.destroy_block(self.block)
            self.block = None

    def __del__(self):
        self.close()

    def get_config(self) -> Dict[str, Any]:
        return json.loads(self.lib.config())

    def reset(self):
        self.lib.reset_block(self.block)


LIBRARY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'library'))


def test():
    mod = Module([
        os.path.join(LIBRARY, 'axis_copy_cdc', 'axis_copy_cdc.v'),
    ])

    ins1 = Instance(mod, {})
    ins2 = Instance(mod, {'DATA_WIDTH': 32})

    print(ins1.get_config())
    print(ins2.get_config())


if __name__ == '__main__':
    test()

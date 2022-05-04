// rm -rf obj_dir/
// verilator -cc --exe --prefix Top --threads 1 -CFLAGS -fPIC -o test.so axis_copy_reg.v test.cpp
// make -j4 -C obj_dir -f Top.mk USER_LDFLAGS=-shared

#include <iostream>
#include "Top.h"

int test()
{
        Top top;

        top.reset = 0;

        for (int i = 0; i < 100; i++)
        {
                top.eval();
        }

        top.final();
        return 0;
}

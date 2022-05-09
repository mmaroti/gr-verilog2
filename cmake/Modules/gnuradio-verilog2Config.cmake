find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_VERILOG2 gnuradio-verilog2)

FIND_PATH(
    GR_VERILOG2_INCLUDE_DIRS
    NAMES gnuradio/verilog2/api.h
    HINTS $ENV{VERILOG2_DIR}/include
        ${PC_VERILOG2_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_VERILOG2_LIBRARIES
    NAMES gnuradio-verilog2
    HINTS $ENV{VERILOG2_DIR}/lib
        ${PC_VERILOG2_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-verilog2Target.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_VERILOG2 DEFAULT_MSG GR_VERILOG2_LIBRARIES GR_VERILOG2_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_VERILOG2_LIBRARIES GR_VERILOG2_INCLUDE_DIRS)

cmake_minimum_required(VERSION 3.24)
project(web_port_bzip2 C)
if(NOT EXISTS "${BZIP2_SOURCE}/bzlib.c")
    message(FATAL_ERROR "BZIP2_SOURCE must name the pinned bzip2 checkout")
endif()
add_library(bz2 STATIC
    ${BZIP2_SOURCE}/blocksort.c ${BZIP2_SOURCE}/huffman.c
    ${BZIP2_SOURCE}/crctable.c ${BZIP2_SOURCE}/randtable.c
    ${BZIP2_SOURCE}/compress.c ${BZIP2_SOURCE}/decompress.c
    ${BZIP2_SOURCE}/bzlib.c)
target_include_directories(bz2 PRIVATE "${BZIP2_SOURCE}")
install(TARGETS bz2 ARCHIVE DESTINATION lib)
install(FILES "${BZIP2_SOURCE}/bzlib.h" DESTINATION include)

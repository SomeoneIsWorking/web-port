cmake_minimum_required(VERSION 3.24)
project(web_port_runtime_tests LANGUAGES CXX)
include(../cmake/WebRuntime.cmake)
add_executable(test_web_storage test_web_storage.cpp)
target_link_libraries(test_web_storage PRIVATE web_port::runtime)
target_compile_options(test_web_storage PRIVATE -UNDEBUG)
target_link_options(test_web_storage PRIVATE -sPROXY_TO_PTHREAD=1 -sPTHREAD_POOL_SIZE=3
                                                 -sEXIT_RUNTIME=1 -sASSERTIONS=1)
set_target_properties(test_web_storage PROPERTIES SUFFIX ".html")

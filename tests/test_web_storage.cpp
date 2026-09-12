#include "web_port/storage.h"

#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstring>

#include <emscripten/threading.h>
#include <emscripten/wasmfs.h>

int main() {
  assert(!emscripten_is_main_browser_thread());
  assert(!web_port_mount_storage(nullptr));
  assert(errno == EINVAL);
  assert(!web_port_mount_storage("/"));
  assert(!web_port_mount_storage("relative"));
  assert(!web_port_mount_storage("/nested/mount"));
  assert(web_port_mount_storage("/opfs"));
  const char *path = "/opfs/web-port-storage-test";
  FILE *file = std::fopen(path, "wb");
  assert(file);
  char message[] = "OPFS worker read/write";
  assert(std::fwrite(message, 1, sizeof(message), file) == sizeof(message));
  assert(std::fclose(file) == 0);
  assert(web_port_unmount_storage("/opfs"));
  assert(!web_port_unmount_storage("/opfs"));
  assert(errno == ENOENT);
  assert(!web_port_unmount_storage("/nested/mount"));
  assert(errno == EINVAL);
  assert(web_port_mount_storage("/opfs"));
  file = std::fopen(path, "rb");
  assert(file);
  char result[sizeof(message)]{};
  assert(std::fread(result, 1, sizeof(result), file) == sizeof(result));
  assert(std::fclose(file) == 0);
  assert(std::memcmp(message, result, sizeof(message)) == 0);
  assert(std::remove(path) == 0);
  assert(web_port_unmount_storage("/opfs"));
  std::puts("web-port storage: worker mount/write/unmount/remount/read/remove "
            "passed; 6 invalid "
            "mounts refused");
  wasmfs_flush();
  return 0;
}

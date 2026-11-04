/* Keeps a farm worker's threads on the worker's own cores (WP-38).
 *
 * SwiftShader (Chromium's software WebGL) pins its worker threads ("Thread<00>"...) to CPU 0 upwards whatever the
 * process may run on, so every pinned farm worker drew its 3D on core 0. Loaded with LD_PRELOAD into a worker and its
 * children, this narrows each affinity request to the cores the thread is already allowed: a request outside them is
 * ignored (the thread stays where the worker put it). Built by farm.render: cc -shared -fPIC -O2 -o keep_affinity.so
 * keep_affinity.c -ldl
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <sched.h>

static int narrow(pid_t tid, size_t size, const cpu_set_t *want, cpu_set_t *out) {
  cpu_set_t have;
  CPU_ZERO(&have);
  if (sched_getaffinity(tid, sizeof(have), &have) != 0) return 0;
  CPU_ZERO(out);
  size_t n = size < sizeof(cpu_set_t) ? size : sizeof(cpu_set_t);
  for (size_t c = 0; c < n * 8; c++)
    if (CPU_ISSET_S(c, size, want) && CPU_ISSET(c, &have)) CPU_SET(c, out);
  return CPU_COUNT(out);
}

int sched_setaffinity(pid_t pid, size_t size, const cpu_set_t *mask) {
  static int (*real)(pid_t, size_t, const cpu_set_t *);
  if (!real) real = dlsym(RTLD_NEXT, "sched_setaffinity");
  cpu_set_t m;
  if (!narrow(pid, size, mask, &m)) return 0;
  return real(pid, sizeof(m), &m);
}

int pthread_setaffinity_np(pthread_t th, size_t size, const cpu_set_t *mask) {
  static int (*real)(pthread_t, size_t, const cpu_set_t *);
  static int (*get)(pthread_t, size_t, cpu_set_t *);
  if (!real) real = dlsym(RTLD_NEXT, "pthread_setaffinity_np");
  if (!get) get = dlsym(RTLD_NEXT, "pthread_getaffinity_np");
  cpu_set_t have, m;
  CPU_ZERO(&have); CPU_ZERO(&m);
  if (get(th, sizeof(have), &have) != 0) return real(th, size, mask);
  size_t n = size < sizeof(cpu_set_t) ? size : sizeof(cpu_set_t);
  for (size_t c = 0; c < n * 8; c++)
    if (CPU_ISSET_S(c, size, mask) && CPU_ISSET(c, &have)) CPU_SET(c, &m);
  if (!CPU_COUNT(&m)) return 0;
  return real(th, sizeof(m), &m);
}

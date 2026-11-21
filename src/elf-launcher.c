/* SPDX-License-Identifier: GPL-3.0-only */
#define _XOPEN_SOURCE 700

#include <errno.h>
#include <ftw.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern const unsigned char kitilix_payload_start[], kitilix_payload_end[];

static const int forwarded_signals[] = {SIGINT, SIGTERM, SIGHUP};
static volatile sig_atomic_t child_pid;
static volatile sig_atomic_t stop_signal;

static void forward_signal(int signal_number) {
    int saved_errno = errno;
    stop_signal = signal_number;
    if (child_pid > 0) kill(child_pid, signal_number);
    errno = saved_errno;
}

static pid_t spawn(void) {
    sigset_t managed, saved;
    sigemptyset(&managed);
    for (size_t i = 0; i < sizeof(forwarded_signals) / sizeof(*forwarded_signals); i++)
        sigaddset(&managed, forwarded_signals[i]);
    sigprocmask(SIG_BLOCK, &managed, &saved);
    pid_t pid = fork();
    if (pid == 0) {
        for (size_t i = 0; i < sizeof(forwarded_signals) / sizeof(*forwarded_signals); i++)
            signal(forwarded_signals[i], SIG_DFL);
        signal(SIGPIPE, SIG_DFL);
    } else if (pid > 0) {
        child_pid = pid;
        if (stop_signal) kill(pid, stop_signal);
    }
    sigprocmask(SIG_SETMASK, &saved, NULL);
    return pid;
}

static int wait_for_child(pid_t pid) {
    int status;
    pid_t result;
    do {
        result = waitpid(pid, &status, 0);
    } while (result < 0 && errno == EINTR);
    child_pid = 0;
    if (result < 0) return 1;
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1;
}

static int unpack(const char *directory) {
    int stream[2];
    if (pipe(stream) < 0) return 1;
    pid_t pid = spawn();
    if (pid == 0) {
        close(stream[1]);
        if (stream[0] != STDIN_FILENO) {
            if (dup2(stream[0], STDIN_FILENO) < 0) _exit(1);
            close(stream[0]);
        }
        unsetenv("TAR_OPTIONS");
        unsetenv("GZIP");
        execl("/usr/bin/tar", "tar", "-xzf", "-", "--no-same-owner", "--no-overwrite-dir",
              "-C", directory, (char *)NULL);
        perror("Kitilix: /usr/bin/tar");
        _exit(127);
    }
    close(stream[0]);
    if (pid < 0) {
        close(stream[1]);
        return 1;
    }

    const unsigned char *data = kitilix_payload_start;
    size_t remaining = (uintptr_t)kitilix_payload_end - (uintptr_t)data;
    while (remaining) {
        ssize_t written = write(stream[1], data, remaining);
        if (written < 0 && errno == EINTR && !stop_signal) continue;
        if (written <= 0) break;
        data += written;
        remaining -= (size_t)written;
    }
    close(stream[1]);
    int status = wait_for_child(pid);
    return status == 0 && remaining ? 1 : status;
}

static int remove_item(const char *path, const struct stat *st, int type, struct FTW *info) {
    (void)st;
    (void)type;
    (void)info;
    return remove(path);
}

int main(int argc, char **argv) {
    if (argc == 2 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "-h"))) {
        puts("Uso: kitilix [--fresh] [--] [CARTELLA]");
        return 0;
    }

    const char *tmp = getenv("TMPDIR");
    if (!tmp || tmp[0] != '/') tmp = "/tmp";
    char directory[PATH_MAX];
    char launcher[sizeof(directory) + sizeof("/run.sh")];
    int length = snprintf(directory, sizeof(directory), "%s/kitilix-XXXXXX", tmp);
    if (length < 0 || (size_t)length >= sizeof(directory) - sizeof("/run.sh")) {
        fputs("Kitilix: percorso temporaneo troppo lungo.\n", stderr);
        return 1;
    }
    if (!mkdtemp(directory)) {
        perror("Kitilix: directory temporanea");
        return 1;
    }

    struct sigaction action = {.sa_handler = forward_signal};
    sigemptyset(&action.sa_mask);
    for (size_t i = 0; i < sizeof(forwarded_signals) / sizeof(*forwarded_signals); i++)
        sigaction(forwarded_signals[i], &action, NULL);
    signal(SIGPIPE, SIG_IGN);

    int status = unpack(directory);
    if (status == 0 && !stop_signal) {
        snprintf(launcher, sizeof(launcher), "%s/run.sh", directory);
        pid_t pid = spawn();
        if (pid == 0) {
            setenv("KITILIX_PROGRAM", "kitilix", 1);
            argv[0] = launcher;
            execv(launcher, argv);
            perror("Kitilix: avvio");
            _exit(127);
        }
        status = pid < 0 ? 1 : wait_for_child(pid);
    } else if (!stop_signal) {
        fputs("Kitilix: estrazione del runtime non riuscita.\n", stderr);
    }

    if (nftw(directory, remove_item, 32, FTW_DEPTH | FTW_PHYS) != 0)
        perror("Kitilix: pulizia della directory temporanea");
    return stop_signal ? 128 + stop_signal : status;
}

// main.cpp - command-line driver
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>

#include "emulator.h"
#include "parser.h"
#include "util.h"

using namespace std;

static void usage(const char *prog) {
    printf("Usage: %s [options] <input.asm>\n"
           "\n"
           "Options:\n"
           "  -p, --parse-only   Tasks 1-3 only: print each instruction's operands, then the\n"
           "                     initial registers and stack (nothing is executed)\n"
           "  -q, --quiet        Don't print each instruction as it executes\n"
           "  -t, --trace        Print the registers after every instruction\n"
           "      --base ADDR    Stack base address (default 0x0)\n"
           "      --sp-base      Start SP at the stack base instead of the top (base + 256).\n"
           "                     The default (top) is what compiled code expects, since it does\n"
           "                     \"sub sp, sp, #N\" first and the stack grows downward\n"
           "      --max-steps N  Stop after N instructions (default 1000000)\n"
           "  -h, --help         Show this help\n",
           prog);
}

static int emulate(int argc, char **argv, bool &interactive) {
    EmulatorOptions opts;
    bool parseOnly = false;
    bool spTop = true;
    uint64_t base = 0x0;
    string path;

    for (int i = 1; i < argc; i++) {
        string a = argv[i];
        if (a == "-h" || a == "--help") {
            usage(argv[0]);
            return 0;
        } else if (a == "-p" || a == "--parse-only") {
            parseOnly = true;
        } else if (a == "-q" || a == "--quiet") {
            opts.quiet = true;
        } else if (a == "-t" || a == "--trace") {
            opts.trace = true;
        } else if (a == "--sp-base") {
            spTop = false;
        } else if (a == "--sp-top") {
            spTop = true;  // kept for compatibility: this is now the default
        } else if (a == "--base" || a == "--max-steps") {
            uint64_t v = 0;
            if (i + 1 >= argc || !parseImmediate(argv[i + 1], v)) {
                fprintf(stderr, "Error: %s needs a numeric argument\n", a.c_str());
                return 1;
            }
            i++;
            (a == "--base" ? base : opts.maxSteps) = v;
        } else if (!a.empty() && a[0] == '-') {
            fprintf(stderr, "Error: unknown option '%s'\n", a.c_str());
            usage(argv[0]);
            return 1;
        } else if (path.empty()) {
            path = a;
        } else {
            fprintf(stderr, "Error: more than one input file given\n");
            return 1;
        }
    }

    // No file on the command line (for example the program was double-clicked or started from an
    // IDE with no arguments): ask for one instead of printing usage and closing immediately.
    if (path.empty()) {
        interactive = true;
        printf("ARM64 emulator - no input file was given.\n"
               "Enter the path to a .txt/.asm file (or drag the file onto this window): ");
        fflush(stdout);
        string typed;
        getline(cin, typed);
        typed = trim(typed);
        if (typed.size() >= 2 && ((typed.front() == '"' && typed.back() == '"') ||
                                  (typed.front() == '\'' && typed.back() == '\'')))
            typed = typed.substr(1, typed.size() - 2);  // drag-and-drop adds quotes
        if (typed.empty()) {
            usage(argv[0]);
            return 1;
        }
        path = typed;
    }

    Program program;
    vector<string> errors;
    if (!loadProgram(path, program, errors)) {
        for (const string &e : errors) fprintf(stderr, "Error: %s\n", e.c_str());
        return 2;
    }

    Emulator emu(std::move(program), base, spTop);
    bool ok = true;

    if (parseOnly) {
        for (const Instruction &ins : emu.program().instructions) printInstruction(ins);
    } else {
        ok = emu.run(opts);
        if (!ok) fprintf(stderr, "%s\n", emu.error().c_str());
    }

    emu.registers().print();
    emu.stack().print();
    return ok ? 0 : 3;
}

int main(int argc, char **argv) {
    bool interactive = false;
    int rc = emulate(argc, argv, interactive);

    // When we had to ask for the file, keep the window open so the output can be read.
    if (interactive) {
        printf("\nPress Enter to exit...");
        fflush(stdout);
        string ignored;
        getline(cin, ignored);
    }
    return rc;
}

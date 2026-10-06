#!/usr/bin/env python3
"""Runs the emulator on every objdump test and compares the final machine state with values
worked out by hand from each program's C source and stack-frame offsets.

Usage (from the project folder, after `make`):   python3 tests/run_tests.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMU = ROOT / "emulator"
TOP = 0x100  # SP starts at the top of the 256-byte stack (base 0x0)


def mem_with(*writes, size=256):
    """writes = (address, bytes) pairs -> expected 256-byte stack image."""
    m = bytearray(size)
    for addr, data in writes:
        m[addr:addr + len(data)] = data
    return bytes(m)


def u64(v):
    return v.to_bytes(8, "little")


def run(asm):
    p = subprocess.run([str(EMU), "-q", str(asm)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"emulator exited {p.returncode}: {p.stderr.strip()}")
    regs, mem = {}, bytearray(256)
    for line in p.stdout.splitlines():
        for name, val in re.findall(r"\b(X\d+|SP|PC):\s+0x([0-9a-f]{16})", line):
            regs[name] = int(val, 16)
        m = re.match(r"Processor State ([NZ]) bit: (\d)", line)
        if m:
            regs[m.group(1)] = int(m.group(2))
        m = re.match(r"([0-9a-f]{8}) ((?:[0-9a-f]{2} ){16})\|", line)
        if m:
            off = int(m.group(1), 16)
            mem[off:off + 16] = bytes.fromhex(m.group(2))
    return regs, bytes(mem)


# ---- expected final states (see each main.c; frame offsets come from the disassembly) -------------
# test1: sub sp,#0x10 -> sp=0xf0. [sp+8]=123, then copied to [sp].
# test3: sp=0xd0. a=2 @sp+40, b=3 @sp+32, a_sq=4 @sp+24, b_sq=9 @sp+16, c_sq=13 @sp+8. x0=13, x1=4.
# test4: sp=0xf0. factorial @sp+8 ends at 1, result @sp ends at 2*1=2. last cmp is 1-1 -> Z=1.
# test2: sp=0xd0. dst=sp+0..15, src=sp+0x10..0x1f (both 0..15), i=16 @sp+40, i2=16 @sp+32.
# test5: sp=0xc0. dst=sp+8.., src=sp+0x18.., dst[i]=i^0x66, key @sp+47, i2=16 @sp+48, i=16 @sp+56.
seq = bytes(range(16))
xored = bytes(i ^ 0x66 for i in range(16))

TESTS = {
    "test1": dict(
        mem=mem_with((0xF8, u64(123)), (0xF0, u64(123))),
        regs=dict(X0=0, SP=TOP, PC=0x1C, N=0, Z=0)),
    "test3": dict(
        mem=mem_with((0xF8, u64(2)), (0xF0, u64(3)), (0xE8, u64(4)), (0xE0, u64(9)), (0xD8, u64(13))),
        regs=dict(X0=13, X1=4, SP=TOP, PC=0x44, N=0, Z=0)),
    "test4": dict(
        mem=mem_with((0xF8, u64(1)), (0xF0, u64(2))),
        regs=dict(X0=1, X1=2, SP=TOP, PC=0x4C, N=0, Z=1)),
    "test2": dict(
        mem=mem_with((0xD0, seq), (0xE0, seq), (0xF8, u64(16)), (0xF0, u64(16))),
        regs=dict(X0=0, X1=0xD0, X2=15, SP=TOP, PC=0x78, N=0, Z=0)),
    "test5": dict(
        mem=mem_with((0xC8, xored), (0xD8, seq), (0xEF, b"\x66"), (0xF0, u64(16)), (0xF8, u64(16))),
        regs=dict(X0=0, X1=0xC8, X2=0x69, SP=TOP, PC=0x8C, N=0, Z=0)),
}

failures = 0
for name, exp in TESTS.items():
    asm = ROOT / "tests" / "objdump" / name / f"{name}.txt"
    try:
        regs, mem = run(asm)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {name}: {e}")
        failures += 1
        continue

    problems = []
    for reg, want in exp["regs"].items():
        if regs.get(reg) != want:
            problems.append(f"{reg} = {regs.get(reg):#x}, expected {want:#x}")
    # every register not listed must still be 0
    for reg, got in regs.items():
        if reg not in exp["regs"] and reg not in ("N", "Z") and got != 0:
            problems.append(f"{reg} = {got:#x}, expected 0")
    if mem != exp["mem"]:
        diff = [i for i in range(256) if mem[i] != exp["mem"][i]]
        problems.append("stack differs at " + ", ".join(f"{i:#04x}(got {mem[i]:02x} want {exp['mem'][i]:02x})" for i in diff[:6]))

    if problems:
        failures += 1
        print(f"FAIL {name}")
        for p in problems:
            print("   -", p)
    else:
        print(f"PASS {name}")

sys.exit(1 if failures else 0)

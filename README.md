# ArchieOS 0.3 (YES I CANT THINK OF A BETTER NAME)

A Python-based os simulator with:
- a custom 16-bit CPU
- 8 registers (R0-R7)
- 64 KB virtual RAM
-  byte-level machine code executed from virtual RAM
- a two-pass assembler with labels
- a virtual filesystem
- an interactive terminal

Run:
```bash
python main.py
```

Try:
```text
about
ram
programs
assemble hello.asm
listing count.asm
run hello.asm
run math.asm
run count.asm
mem 0x1000 32
cpu
```

Assembler instructions: `NOP`, `SET`, `ADD`, `SUB`, `INC`, `CMP`, `JMP`, `JZ`, `PRINTREG`, `PRINT`, `HALT`.

DISCLAIMER This is still a simulator NOT AN ACTUAL OS. The CPU, RAM, machine code and filesystem all exist inside my amazing Python.

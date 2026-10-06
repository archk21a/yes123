# ArchieOS 0.3

A Python-based operating-system simulator with:
- a custom 16-bit CPU
- 8 registers (R0-R7)
- 64 KB virtual RAM
- real byte-level machine code executed from virtual RAM
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

This is still a simulator, not a bare-metal operating system. The CPU, RAM, machine code and filesystem all exist inside Python.

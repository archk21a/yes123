import tkinter as tk
import time
import re

RAM_SIZE = 65536
MASK16 = 0xFFFF

REGS = {f"R{i}": i for i in range(8)}
OP = {
    "NOP": 0x00,
    "SET": 0x10,      # SET reg, imm16
    "ADD": 0x20,      # ADD rd, rs
    "SUB": 0x21,
    "INC": 0x22,
    "CMP": 0x30,      # CMP r1, r2
    "JMP": 0x40,      # JMP addr16
    "JZ": 0x41,
    "PRINTREG": 0x50,
    "PRINT": 0x51,    # PRINT string embedded in code: len8 + bytes
    "HALT": 0xFF,
}

ASM_PROGRAMS = {
    "/home/archie/hello.asm": '''; Hello world\nPRINT "Hello from machine code!"\nHALT\n''',
    "/home/archie/math.asm": '''; 10 + 25 using registers\nSET R0, 10\nSET R1, 25\nADD R0, R1\nPRINTREG R0\nHALT\n''',
    "/home/archie/count.asm": '''; Count from 1 to 5\nSET R0, 1\nSET R1, 5\nloop:\nPRINTREG R0\nCMP R0, R1\nJZ done\nINC R0\nJMP loop\ndone:\nHALT\n''',
}

class AssemblerError(Exception):
    pass


def strip_comment(line):
    in_quote = False
    out = []
    for ch in line:
        if ch == '"':
            in_quote = not in_quote
        if ch == ';' and not in_quote:
            break
        out.append(ch)
    return ''.join(out).strip()


def parse_args(text):
    parts = []
    cur = ''
    in_quote = False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
            cur += ch
        elif ch == ',' and not in_quote:
            if cur.strip():
                parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def number(s, labels):
    s = s.strip()
    if s in labels:
        return labels[s]
    try:
        return int(s, 0)
    except ValueError:
        raise AssemblerError(f"invalid number/label: {s}")


def reg(s):
    s = s.strip().upper()
    if s not in REGS:
        raise AssemblerError(f"invalid register: {s}")
    return REGS[s]


def assemble(source, base=0x1000):
    lines = []
    labels = {}
    pc = base

    # Pass 1: calculate machine-code addresses.
    for raw in source.splitlines():
        line = strip_comment(raw)
        if not line:
            continue
        while ':' in line:
            left, right = line.split(':', 1)
            label = left.strip()
            if not re.fullmatch(r'[A-Za-z_]\w*', label):
                raise AssemblerError(f"invalid label: {label}")
            if label in labels:
                raise AssemblerError(f"duplicate label: {label}")
            labels[label] = pc
            line = right.strip()
            if not line:
                break
        if not line:
            continue
        lines.append(line)
        parts = line.split(None, 1)
        op = parts[0].upper()
        args = parse_args(parts[1] if len(parts) > 1 else '')
        if op in ('NOP', 'HALT'):
            pc += 1
        elif op == 'SET':
            if len(args) != 2: raise AssemblerError('SET needs register, value')
            pc += 4
        elif op in ('ADD', 'SUB', 'CMP'):
            if len(args) != 2: raise AssemblerError(f'{op} needs two registers')
            pc += 3
        elif op == 'INC':
            if len(args) != 1: raise AssemblerError('INC needs one register')
            pc += 2
        elif op in ('JMP', 'JZ'):
            if len(args) != 1: raise AssemblerError(f'{op} needs an address/label')
            pc += 3
        elif op == 'PRINTREG':
            if len(args) != 1: raise AssemblerError('PRINTREG needs one register')
            pc += 2
        elif op == 'PRINT':
            if len(args) != 1 or not (args[0].startswith('"') and args[0].endswith('"')):
                raise AssemblerError('PRINT needs a quoted string')
            text = bytes(args[0][1:-1], 'utf-8')
            if len(text) > 255: raise AssemblerError('PRINT string too long')
            pc += 2 + len(text)
        else:
            raise AssemblerError(f'unknown instruction: {op}')

    code = bytearray()
    listing = []
    pc = base
    for line in lines:
        parts = line.split(None, 1)
        op = parts[0].upper()
        args = parse_args(parts[1] if len(parts) > 1 else '')
        start = pc
        if op == 'NOP':
            code += bytes([OP[op]])
        elif op == 'HALT':
            code += bytes([OP[op]])
        elif op == 'SET':
            code += bytes([OP[op], reg(args[0])]) + number(args[1], labels).to_bytes(2, 'little', signed=False)
        elif op in ('ADD', 'SUB', 'CMP'):
            code += bytes([OP[op], reg(args[0]), reg(args[1])])
        elif op == 'INC':
            code += bytes([OP[op], reg(args[0])])
        elif op in ('JMP', 'JZ'):
            addr = number(args[0], labels)
            if not 0 <= addr < RAM_SIZE: raise AssemblerError('jump address outside RAM')
            code += bytes([OP[op]]) + addr.to_bytes(2, 'little')
        elif op == 'PRINTREG':
            code += bytes([OP[op], reg(args[0])])
        elif op == 'PRINT':
            text = bytes(args[0][1:-1], 'utf-8')
            code += bytes([OP[op], len(text)]) + text
        listing.append(f"{start:04X}: {line}")
        pc = base + len(code)
    return bytes(code), labels, '\n'.join(listing)


class CPU:
    def __init__(self, output):
        self.output = output
        self.reset()

    def reset(self):
        self.ram = bytearray(RAM_SIZE)
        self.registers = [0] * 8
        self.pc = 0
        self.zero = False
        self.running = False
        self.steps = 0
        self.program_size = 0

    def out(self, s):
        self.output(s)

    def u16(self, addr):
        return self.ram[addr] | (self.ram[(addr + 1) & MASK16] << 8)

    def load_machine_code(self, code, address=0x1000):
        if address + len(code) > RAM_SIZE:
            raise ValueError('program does not fit in RAM')
        self.ram[address:address + len(code)] = code
        self.pc = address
        self.program_size = len(code)
        self.steps = 0
        self.running = True

    def step(self):
        if not self.running:
            return False
        op = self.ram[self.pc]
        self.steps += 1

        if op == 0x00: self.pc = (self.pc + 1) & MASK16
        elif op == 0x10:
            r = self.ram[self.pc + 1]; v = self.u16(self.pc + 2)
            self.registers[r] = v & MASK16; self.pc += 4
        elif op in (0x20, 0x21):
            rd, rs = self.ram[self.pc + 1], self.ram[self.pc + 2]
            if op == 0x20: self.registers[rd] = (self.registers[rd] + self.registers[rs]) & MASK16
            else: self.registers[rd] = (self.registers[rd] - self.registers[rs]) & MASK16
            self.zero = self.registers[rd] == 0; self.pc += 3
        elif op == 0x22:
            r = self.ram[self.pc + 1]; self.registers[r] = (self.registers[r] + 1) & MASK16
            self.zero = self.registers[r] == 0; self.pc += 2
        elif op == 0x30:
            a, b = self.ram[self.pc + 1], self.ram[self.pc + 2]
            self.zero = self.registers[a] == self.registers[b]; self.pc += 3
        elif op in (0x40, 0x41):
            addr = self.u16(self.pc + 1)
            if op == 0x40 or self.zero: self.pc = addr
            else: self.pc += 3
        elif op == 0x50:
            r = self.ram[self.pc + 1]; self.out(f"R{r} = {self.registers[r]}\n"); self.pc += 2
        elif op == 0x51:
            n = self.ram[self.pc + 1]; start = self.pc + 2
            self.out(self.ram[start:start+n].decode('utf-8', errors='replace') + '\n')
            self.pc += 2 + n
        elif op == 0xFF:
            self.running = False; self.pc += 1; self.out('CPU: HALT\n')
        else:
            self.out(f'CPU: invalid opcode 0x{op:02X} at 0x{self.pc:04X}\n')
            self.running = False
        return True

    def run(self, limit=10000):
        count = 0
        while self.running and count < limit:
            self.step(); count += 1
        if self.running:
            self.running = False
            self.out(f'CPU: execution limit reached ({limit} instructions)\n')


class ArchieOS:
    def __init__(self):
        self.cwd = '/home/archie'
        self.files = {
            '/readme.txt': 'ArchieOS 0.3 - virtual RAM, machine code and assembler.',
            **ASM_PROGRAMS,
        }
        self.dirs = {'/', '/home', '/home/archie'}
        self.root = tk.Tk(); self.root.title('ArchieOS 0.3 - Virtual Computer'); self.root.geometry('1100x720'); self.root.configure(bg='#0b0f14')
        tk.Label(self.root, text='ARCHIEOS 0.3', fg='#7dd3fc', bg='#0b0f14', font=('Consolas', 24, 'bold')).pack(anchor='w', padx=20, pady=(15,0))
        tk.Label(self.root, text='Python kernel | 16-bit CPU | 64 KB virtual RAM | assembler + machine code', fg='#94a3b8', bg='#0b0f14', font=('Consolas', 10)).pack(anchor='w', padx=22)
        self.term = tk.Text(self.root, bg='#05070a', fg='#d1fae5', insertbackground='white', font=('Consolas', 12), relief='flat', padx=12, pady=12)
        self.term.pack(fill='both', expand=True, padx=20, pady=15)
        self.term.bind('<Return>', self.enter); self.term.bind('<BackSpace>', self.backspace); self.term.bind('<Up>', self.up)
        self.history=[]; self.history_pos=0; self.cpu=CPU(self.write)
        self.write('ARCHIEOS BOOT\n----------------\nBootloader OK\nMemory manager OK\nProcess manager OK\nVirtual CPU OK\nAssembler OK\n64 KB RAM online\n\nType \'help\' for commands.\n\n'); self.prompt()

    def write(self,s): self.term.insert('end',s); self.term.see('end')
    def start(self): return self.term.index('end-1c linestart')
    def prompt(self): self.write(f'archie@archieos:{self.cwd}$ ')
    def enter(self,event=None):
        line=self.term.get(self.start(),'end-1c'); cmd=line.split('$ ',1)[-1].strip(); self.write('\n')
        if cmd: self.history.append(cmd); self.history_pos=len(self.history); self.execute(cmd)
        self.prompt(); return 'break'
    def backspace(self,event=None):
        if self.term.compare('insert','>',self.start()): self.term.delete('insert-1c')
        return 'break'
    def up(self,event=None):
        if self.history:
            self.history_pos=max(0,self.history_pos-1); self.term.delete(self.start(),'end-1c'); self.term.insert('end',self.history[self.history_pos])
        return 'break'
    def norm(self,p):
        if not p.startswith('/'): p=self.cwd.rstrip('/')+'/'+p
        parts=[]
        for x in p.split('/'):
            if x in ('','.'): continue
            if x=='..':
                if parts: parts.pop()
            else: parts.append(x)
        return '/'+ '/'.join(parts)
    def ls(self,path):
        path=path.rstrip('/') or '/'; prefix=path+'/' if path!='/' else '/'; result=set()
        for d in self.dirs:
            if d!=path and d.startswith(prefix):
                x=d[len(prefix):]
                if '/' not in x and x: result.add(x+'/')
        for f in self.files:
            if f.startswith(prefix):
                x=f[len(prefix):]
                if '/' not in x and x: result.add(x)
        return sorted(result)
    def execute(self,command):
        p=command.split(); cmd=p[0].lower() if p else ''; args=p[1:]
        if cmd=='help':
            self.write('SYSTEM\n  about       system information\n  cpu         CPU registers/state\n  ram         RAM information\n  mem <a> [n] dump RAM bytes\n  reboot      reboot\n\nASSEMBLER\n  programs    list .asm programs\n  assemble <f> assemble source\n  run <f>     assemble, load into RAM and execute\n  step        execute one machine-code instruction\n  listing <f> show assembler listing\n\nFILES\n  ls [path]   list files\n  cd <dir>    change directory\n  pwd         current directory\n  cat <file>  read file\n  mkdir <dir> create directory\n  write <f> <text>  write file\n\nOTHER\n  clear       clear terminal\n  time        system time\n')
        elif cmd=='about': self.write('ArchieOS 0.3\nKernel: Python\nCPU: custom 16-bit virtual CPU\nRegisters: R0-R7\nRAM: 65536 bytes (64 KB)\nMachine code: yes\nAssembler: yes\nFilesystem: virtual\n')
        elif cmd=='cpu': self.write(f'PC=0x{self.cpu.pc:04X} ({self.cpu.pc}) ZERO={self.cpu.zero} RUNNING={self.cpu.running} STEPS={self.cpu.steps}\n'+' '.join(f'R{i}=0x{v:04X}({v})' for i,v in enumerate(self.cpu.registers))+'\n')
        elif cmd=='ram': self.write('RAM: 65536 bytes (64 KB)\nProgram load address: 0x1000\nAddress range: 0x0000-0xFFFF\n')
        elif cmd=='mem':
            try: addr=int(args[0],0) if args else 0x1000; n=int(args[1],0) if len(args)>1 else 32
            except ValueError: self.write('usage: mem <address> [count]\n'); return
            n=max(1,min(n,128)); addr=max(0,min(addr,RAM_SIZE-1)); data=self.cpu.ram[addr:min(RAM_SIZE,addr+n)]
            for off in range(0,len(data),16): self.write(f'{addr+off:04X}: '+' '.join(f'{b:02X}' for b in data[off:off+16])+'\n')
        elif cmd=='programs': self.write('hello.asm\nmath.asm\ncount.asm\n')
        elif cmd in ('assemble','listing','run'):
            if not args: self.write(f'usage: {cmd} <file>\n'); return
            path=self.norm(args[0]); source=self.files.get(path)
            if source is None: self.write('file not found\n'); return
            try: code, labels, listing=assemble(source)
            except AssemblerError as e: self.write(f'assembler error: {e}\n'); return
            if cmd=='assemble':
                self.write(f'assembled {len(code)} bytes\n'); self.write('machine code: '+' '.join(f'{b:02X}' for b in code)+'\n')
                if labels: self.write('labels: '+', '.join(f'{k}=0x{v:04X}' for k,v in labels.items())+'\n')
            elif cmd=='listing': self.write(listing+'\n')
            else:
                self.cpu.registers=[0]*8; self.cpu.zero=False
                self.cpu.load_machine_code(code,0x1000); self.write(f'loaded {len(code)} bytes at 0x1000\n'); self.cpu.run()
        elif cmd=='step':
            if not self.cpu.running: self.write('CPU is not running; use run <file> first\n')
            else: self.cpu.step()
        elif cmd=='ls': self.write('  '.join(self.ls(self.norm(args[0]) if args else self.cwd))+'\n')
        elif cmd=='pwd': self.write(self.cwd+'\n')
        elif cmd=='cd':
            path=self.norm(args[0]) if args else '/home/archie'; self.cwd=path if path in self.dirs else self.cwd
            if path not in self.dirs: self.write('cd: directory not found\n')
        elif cmd=='cat':
            if not args: self.write('cat: missing file\n')
            else: self.write(self.files.get(self.norm(args[0]),'cat: file not found')+'\n')
        elif cmd=='mkdir':
            if not args: self.write('mkdir: missing directory\n')
            else:
                path=self.norm(args[0]); parent=path.rsplit('/',1)[0] or '/'
                if parent not in self.dirs: self.write('mkdir: parent does not exist\n')
                else: self.dirs.add(path); self.write('directory created\n')
        elif cmd=='write':
            if len(args)<2: self.write('usage: write <file> <text>\n')
            else:
                path=self.norm(args[0]); parent=path.rsplit('/',1)[0] or '/'
                if parent not in self.dirs: self.write('write: parent does not exist\n')
                else: self.files[path]=' '.join(args[1:]); self.write('file written\n')
        elif cmd=='clear': self.term.delete('1.0','end')
        elif cmd=='time': self.write(time.strftime('%Y-%m-%d %H:%M:%S')+'\n')
        elif cmd=='reboot':
            self.term.delete('1.0','end'); self.cpu.reset(); self.write('Rebooting...\n'); self.root.after(300,self.boot)
        else: self.write(f'{cmd}: command not found\n')
    def boot(self): self.write('ARCHIEOS KERNEL 0.3\nCPU online\n64 KB RAM online\nAssembler online\nFilesystem mounted\n\n'); self.prompt()
    def run(self): self.root.mainloop()

if __name__=='__main__': ArchieOS().run()

import re
from webapp.models import *


class GoldenRunParser:
    re_inst = re.compile(
        r'^(?:0x)?(?P<address>[0-9a-fA-F]{8}):\s+(?P<instruction>\S+)\s+'
        r'(?P<mnemonic>\S+)\s*(?P<ops>[\w,()-]+)?\s*\s+(?:#.*)?')
    re_regs = re.compile(r'^(?:-?[0-9]+\()?(?P<reg>[^-\d][^,\s()]+)\)?$')
    re_gpr_filter = re.compile(
        r'^LD/ST for GPR (?P<gpr>\d+) \(Access (?P<access>\d+)\): \[(?P<base>[0-9a-fA-F]{8})\s\+\s(?P<offset>-?\d+)]$')

    re_gpr_summary = re.compile(r'^GPR\[(?P<idx>\d+)]:(?P<read>\d+),(?P<write>\d+),(?P<total>\d+)$')
    re_csr_summary = re.compile(r'^CSR\[(?P<idx>\d+)]:(?P<read>\d+),(?P<write>\d+),(?P<total>\d+)$')
    re_insn_exe = re.compile(r'^EXE\[(?P<pc>[0-9a-fA-F]+)]:(?P<total>\d+)$')

    # TO DO: Would be better to merge the three regexes below into one and handle all mem accesses in the same way...
    re_mem8_rwx = re.compile(r'^MEM_8\[(?P<loc>[0-9a-fA-F]+)]:(?P<read>\d+),(?P<write>\d+),(?P<total>\d+)$')
    re_mem16_rwx = re.compile(r'^MEM_16\[(?P<loc>[0-9a-fA-F]+)]:(?P<read>\d+),(?P<write>\d+),(?P<total>\d+)$')
    re_mem32_rwx = re.compile(r'^MEM_32\[(?P<loc>[0-9a-fA-F]+)]:(?P<read>\d+),(?P<write>\d+),(?P<total>\d+)$')

    def __init__(self, arch, disassembly_file):
        self.insn_list = Instruction.objects.filter(subset__arch=arch)
        self.gprs = Gpr.objects.filter(subset__arch=arch)
        self.fprs = Fpr.objects.filter(subset__arch=arch)
        self.csrs = Csr.objects.filter(subset__arch=arch)
        self.pc_values = set()
        self.arch = arch

        self.disas_file = disassembly_file
        with open(disassembly_file, 'r') as f:
            self.goldenrun_lines = f.readlines()

        self.pc2insn = dict()
        # 1) ROM Reset Vector
        #    (qemu/hw/riscv/boot.c:260:270)
        # self.pc2insn[0x00001000] = self.get_instruction("0x00001000:  00000297          auipc           t0,0")
        self.pc2insn[0x00001004] = self.get_instruction("0x00001004:  02828613          addi            a2,t0,40")
        self.pc2insn[0x00001008] = self.get_instruction(
            "0x00001008:  f1402573          csrrs           a0,mhartid,zero")
        # self.pc2insn[0x0000100c] = self.get_instruction("0x0000100c:  0202a583          lw              a1,32(t0)")
        # self.pc2insn[0x00001010] = self.get_instruction("0x00001010:  0182a283          lw              t0,24(t0)")
        # self.pc2insn[0x00001014] = self.get_instruction("0x00001014:  00028067          jr              t0")
        # 2) Parse the objdump of the executable sections:
        for line in self.goldenrun_lines:
            m = GoldenRunParser.re_inst.match(line)
            if m is not None:
                pc = int(m.group('address').strip(), 16)
                insn = self.get_instruction(line)
                if pc is not None and insn is not None:
                    self.pc2insn[pc] = insn

        self.min = None
        self.max = None
        for line in self.goldenrun_lines:
            m8 = GoldenRunParser.re_mem8_rwx.match(line)
            m16 = GoldenRunParser.re_mem16_rwx.match(line)
            m32 = GoldenRunParser.re_mem32_rwx.match(line)

            if m8 is not None:
                loc = int(m8.group("loc"), 16)
                loc2 = loc
            elif m16 is not None:
                loc = int(m16.group("loc"), 16)
                loc2 = loc + 1
            elif m32 is not None:
                loc = int(m32.group("loc"), 16)
                loc2 = loc + 3
            else:
                continue

            if self.min is None or loc < self.min:
                self.min = loc
            if self.max is None or loc2 >= self.max:
                self.max = loc2

    @staticmethod
    def get_registers(line):
        regs = set()
        m = GoldenRunParser.re_inst.match(line)
        re_regs = GoldenRunParser.re_regs
        if m is not None:
            ops = m.group('ops')
            if ops is not None:
                for o in list(filter(None, re.split(r'[,()]', ops))):
                    if re_regs.match(o):
                        regs.add(re_regs.match(o).group('reg'))
        return regs

    def get_instruction(self, line):
        m = GoldenRunParser.re_inst.match(line)
        if m is not None:
            # This line corresponds to an instuction in the binary:
            instruction = int(''.join(reversed(m.group('instruction').strip().split(' '))), 16)

            # Store PC value
            self.pc_values.add(int(m.group('address'), 16))

            # Try to match opcode
            for i in self.insn_list:
                if (instruction & i.mask) == i.opcode:
                    self.pc2insn[int(m.group('address'), 16)] = i
                    return i

            # Regex matched but not corresponding instruction was found!
            print("   [WARNING] cannot match opcode '" + m.group("instruction") + " (" + m.group(
                'mnemonic') + ")' @ " + format(int(m.group('address'), 16), '#08x'))

        return None

    @staticmethod
    def get_address(line):
        m = GoldenRunParser.re_inst.match(line)
        if m is not None:
            address = int(m.group('address').strip(), 16)
            return address
        return None

    def get_covered_registers(self):
        all_register_names = set()
        for line in self.goldenrun_lines:
            all_register_names = all_register_names.union(self.get_registers(line))

        gprs = self.gprs.filter(abiname__in=list(all_register_names))
        fprs = self.fprs.filter(abiname__in=list(all_register_names))
        csrs = self.csrs.filter(name__in=list(all_register_names))
        unknown = all_register_names-set(
            self.gprs.values_list("abiname", flat=True)) - set(
            self.fprs.values_list("abiname", flat=True)) - set(
            self.csrs.values_list("name", flat=True)
        )
        return gprs, fprs, csrs, unknown

    def get_instruction_faults(self):
        result = []
        for line in self.goldenrun_lines:
            i = self.get_instruction(line)
            if i is not None:
                a = self.get_address(line)
                result.append((a, i))
                self.pc2insn[a] = i
        return result

    def get_all_gpr_accesses(self):
        gpr_access = dict()
        for line in self.goldenrun_lines:
            m = GoldenRunParser.re_gpr_summary.match(line)
            if m is not None:
                idx = int(m.group("idx"))
                if idx not in gpr_access:
                    gpr_access[idx] = (int(m.group("read")), int(m.group("write")), int(m.group("total")))
                else:
                    raise Exception("GPR Reads", "already parsed read count for GPR {}!".format(idx))
        return gpr_access

    def get_all_csr_accesses(self):
        csr_access = dict()
        for line in self.goldenrun_lines:
            m = GoldenRunParser.re_csr_summary.match(line)
            if m is not None:
                idx = int(m.group("idx"))
                csr_access[idx] = (int(m.group("read")), int(m.group("write")), int(m.group("total")))
        return csr_access

    def get_all_mem_accesses(self):
        mem8 = dict()
        mem16 = dict()
        mem32 = dict()
        for line in self.goldenrun_lines:
            m8 = GoldenRunParser.re_mem8_rwx.match(line)
            m16 = GoldenRunParser.re_mem16_rwx.match(line)
            m32 = GoldenRunParser.re_mem32_rwx.match(line)
            if m8 is not None:
                loc = int(m8.group("loc"), 16)
                mem8[loc] = (int(m8.group("read")), int(m8.group("write")), int(m8.group("total")))
            elif m16 is not None:
                loc = int(m16.group("loc"), 16)
                mem16[loc] = (int(m16.group("read")), int(m16.group("write")), int(m16.group("total")))
            elif m32 is not None:
                loc = int(m32.group("loc"), 16)
                mem32[loc] = (int(m32.group("read")), int(m32.group("write")), int(m32.group("total")))
        return mem8, mem16, mem32

    def get_instruction_executions(self):
        insn2count = {}
        for line in self.goldenrun_lines:
            m = GoldenRunParser.re_insn_exe.match(line)
            if m is not None:
                pc = int(m.group('pc').strip(), 16)
                count = int(m.group("total"))
                if pc not in self.pc2insn:
                    print("   [WARNING] instruction @ '{}' not found in file '{}'!".format(hex(pc), self.disas_file))
                    continue
                i = self.pc2insn[pc]
                if i not in insn2count:
                    insn2count[i] = 0
                insn2count[i] = insn2count[i] + count
        return insn2count

    def get_instruction_instances(self):
        insn2inst = {}
        for i in self.pc2insn.values():
            if i not in insn2inst:
                insn2inst[i] = 0
            insn2inst[i] = insn2inst[i] + 1
        return insn2inst

import itertools
import yaml
from django.db import models
from ..managers.hardware import ArchitectureManager, DeviceManager, DeviceCsrManager, MemoryRegionManager, \
    RegisterManager


def exp_bit_faults(bits, limit=1):
    exp = []
    for b in range(limit):
        for c in itertools.combinations(range(bits), b + 1):
            i = 0
            for n in c:
                i += 1 << n
            exp.append(i)
    exp.sort()
    return exp


class NamedItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        abstract = True


class Register(NamedItem):
    abiname = models.CharField(max_length=80, blank=True)
    number = models.PositiveIntegerField()

    qemu_reference = models.CharField(max_length=255)
    rtl_reference = models.CharField(max_length=255)

    objects = RegisterManager()

    class Meta(NamedItem.Meta):
        abstract = True
        ordering = ['subset', 'number']
        unique_together = ('subset', 'number')


class Gpr(Register):
    subset = models.ForeignKey("Subset", related_name='gprs', on_delete=models.CASCADE)

    @property
    def bits(self):
        return 32


class Fpr(Register):
    subset = models.ForeignKey("Subset", related_name='fprs', on_delete=models.CASCADE)

    @property
    def bits(self):
        return 64


class Csr(Register):
    ACCESS_CHOICES = (
        ("RO", "read-only"),
        ("RW", "read-write"),
    )
    subset = models.ForeignKey("Subset", related_name='csrs', on_delete=models.CASCADE)
    bits = models.PositiveSmallIntegerField(default=32)
    access = models.CharField(max_length=10, choices=ACCESS_CHOICES)
    mask = models.PositiveBigIntegerField(default=0xFFFFFFFF)


class DeviceCsr(Register):
    device = models.ForeignKey("Device", related_name='csrs', on_delete=models.CASCADE)
    bits = models.PositiveSmallIntegerField(default=32)

    objects = DeviceCsrManager()

    class Meta(Register.Meta):
        ordering = ['device', 'number']
        unique_together = ('device', 'number')
        indexes = [
            models.Index(fields=['device', 'number'])
        ]


class Operand(NamedItem):
    OPERAND_TYPE_CHOICES = (
        ('gpr', 'General-Purpose Register'),
        ('fpr', 'Floating-Point Register'),
        ('csr', 'Control and Status Register'),
        ('imm', 'Immediate'),
        ('uimm', 'Immediate (Unsigned)'),
        ('shamt', 'Shift Amount'),
        ('other', 'Other'),
    )
    shortname = models.CharField(max_length=10)
    mask = models.PositiveBigIntegerField()
    optype = models.CharField(max_length=10, choices=OPERAND_TYPE_CHOICES, default="other")

    class Meta(NamedItem.Meta):
        unique_together = ("name",)


class Instruction(NamedItem):
    INSTRUCTION_FORMAT_CHOICES = (
        ('R', 'R-type'),
        ('R4', 'R4-type'),
        ('I', 'I-type'),
        ('S', 'S-type'),
        ('B', 'B-type'),
        ('U', 'U-type'),
        ('J', 'J-type'),
        ('CR', 'CR-type'),
        ('CI', 'CI-type'),
        ('CSS', 'CSS-type'),
        ('CIW', 'CIW-type'),
        ('CL', 'CL-type'),
        ('CS', 'CS-type'),
        ('CA', 'CA-type'),
        ('CB', 'CB-type'),
        ('CJ', 'CJ-type'),
        ('__UNDEFINED__', '__UNDEFINED__')
    )

    subset = models.ForeignKey("Subset", related_name='instructions', on_delete=models.CASCADE)
    opcode = models.PositiveBigIntegerField()
    mask = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=100)
    bits = models.IntegerField(default=32)
    fmt = models.CharField(max_length=50, choices=INSTRUCTION_FORMAT_CHOICES, default="__UNDEFINED___")
    operands = models.ManyToManyField("Operand", blank=True)

    class Meta(NamedItem.Meta):
        unique_together = ("subset", "opcode")
        index_together = [
            ["subset"],
            ["subset", "bits"],
        ]


class InstructionFault(models.Model):
    OPCODE_FAULT_CHOICES = (
        ('none', 'No change'),
        ('newop', 'Opcode change'),
        ('cfchange', 'Control flow change'),
        ('illegal', 'Illegal Opcode')
    )

    source = models.ForeignKey(Instruction, related_name="+", on_delete=models.CASCADE)
    error_mask = models.PositiveBigIntegerField()
    distance = models.PositiveSmallIntegerField()
    target = models.ForeignKey(Instruction, related_name="+", null=True, blank=True, on_delete=models.CASCADE)

    effect_opcode = models.CharField(max_length=20,
                                     choices=OPCODE_FAULT_CHOICES,
                                     default='none')

    effect_gpr = models.BooleanField(default=False)
    effect_fpr = models.BooleanField(default=False)
    effect_csr = models.BooleanField(default=False)
    effect_imm = models.BooleanField(default=False)

    class Meta:
        unique_together = ("source", "error_mask")
        index_together = [
            ["source"],
            ["source", "error_mask"],
            ["source", "error_mask", "distance"],
            ["source", "effect_opcode"],
            ["source", "effect_gpr"],
            ["source", "effect_fpr"],
            ["source", "effect_csr"],
            ["source", "effect_imm"],
            ["source", "distance"],
            ["source", "distance", "effect_opcode"],
            ["source", "distance", "target"],
        ]


class Device(NamedItem):
    arch = models.ForeignKey("Architecture", related_name='devices', on_delete=models.CASCADE)

    objects = DeviceManager()

    class Meta(NamedItem.Meta):
        unique_together = ("arch", "name")
        base_manager_name = 'objects'


class MemoryRegion(NamedItem):
    MEMORYREGION_TYPE_CHOICES = (
        ('RAM', 'Random Access Memory'),
        ('ROM', 'Read Only Memory'),
        ('__undef__', 'Undefined'),
    )

    addr_from = models.PositiveBigIntegerField()
    addr_to = models.PositiveBigIntegerField()
    memtype = models.CharField(max_length=20, choices=MEMORYREGION_TYPE_CHOICES, default="__undef__")

    arch = models.ForeignKey("Architecture", related_name='memory_regions', on_delete=models.CASCADE)
    device = models.ForeignKey(Device, related_name='memory_regions', on_delete=models.CASCADE, blank=True, null=True)

    objects = MemoryRegionManager()

    class Meta(NamedItem.Meta):
        unique_together = ("arch", "addr_from")
        indexes = [
            models.Index(fields=['arch', 'addr_from', 'addr_to'])
        ]


class Architecture(NamedItem):
    gcc_march = models.CharField(max_length=40)
    gcc_mabi = models.CharField(max_length=40)

    qemu_machine = models.CharField(max_length=40, default="spike")
    qemu_cpu = models.CharField(max_length=256)
    qemu_testsetup = models.CharField(max_length=255, default="")
    qemu_terminator = models.CharField(max_length=24)

    extra_faults_from_cla = models.FilePathField(null=True, blank=True)

    max_faults_gpr = models.PositiveSmallIntegerField(default=1)
    max_faults_csr = models.PositiveSmallIntegerField(default=1)
    max_faults_mmcsr = models.PositiveSmallIntegerField(default=1)
    max_faults_coremem = models.PositiveSmallIntegerField(default=1)
    max_faults_imem = models.PositiveSmallIntegerField(default=1)
    max_faults_ifr = models.PositiveSmallIntegerField(default=1)

    objects = ArchitectureManager()

    def gpr_faults(self, limit=None):
        if limit is None:
            limit = self.max_faults_gpr

        # Do we have information from Cell-Layout-Analysis (CLA)?
        if self.extra_faults_from_cla is not None:
            _extra = yaml.load(open(self.extra_faults_from_cla, 'r'), Loader=yaml.Loader)
            return {int(k, 10): [x for x in v if bin(x).count('1') <= limit] for k, v in _extra['gprs'].items()}

        # Fallback to naive calculation
        return {k: exp_bit_faults(32, limit=limit) for k in range(1, 32)}

    def csr_faults(self, limit=None):
        if limit is None:
            limit = self.max_faults_csr

        # Do we have information from Cell-Layout-Analysis (CLA)?
        if self.extra_faults_from_cla is not None:
            _extra = yaml.load(open(self.extra_faults_from_cla, 'r'), Loader=yaml.Loader)
            return {int(k, 16): [x for x in v if bin(x).count('1') <= limit] for k, v in _extra['csrs'].items()}

        # Fallback to naive calculation
        r = {}
        exp = exp_bit_faults(32, limit=limit)
        for c in Csr.objects.filter(subset__arch=self, mask__gt=0):
            exp_new = set()
            for e in exp:
                if (e & c.mask) != 0:
                    exp_new.add(e & c.mask)
            r[c.number] = exp_new
        return r

    def mmcsr_faults(self, limit=None):
        if limit is None:
            limit = self.max_faults_mmcsr

        e16 = exp_bit_faults(16, limit)
        e32 = exp_bit_faults(32, limit)

        r = {}
        for mmcsr in DeviceCsr.objects.filter(device__arch=self):
            exp = e16 if mmcsr.bits == 16 else e32
            r[mmcsr.pk] = exp

        return r

        # 2: MemoryRegion mr (ONLY IF mr.device IS NOT NONE!)
        #  ----> MOVE TO data_faults (to be created...!)

    def instruction_faults(self, limit=None):
        if limit is None:
            limit = self.max_faults_imem

        e16 = exp_bit_faults(16, limit)
        e32 = exp_bit_faults(32, limit)

        # This is independent of CLA (or we do not know how to make use of it for I-Faults)
        r = {}
        for i in Instruction.objects.filter(subset__arch=self):
            exp = e16 if i.bits == 16 else e32

            # NOTE: For E300 all bits for all instructions are used. Skip below for performance reasons...
            exp_new = set()
            msk = i.mask
            for o in i.operands.all():
                msk |= o.mask
            for e in exp:
                if (e & msk) != 0:
                    exp_new.add(e & msk)

            # # # NOTE: For E300, add all experiments instead
            # exp_new = set(exp)

            r[i.pk] = exp_new
        return r

    def memory_faults(self, device_memory=False, limit=None):
        # TO DO: sollte eigentlich in das if-else-stmt unten!
        if limit is None:
            limit = self.max_faults_coremem

        e8 = exp_bit_faults(8, limit)

        r = {}

        q_set = MemoryRegion.objects.filter(arch=self)
        if device_memory:
            q_set = q_set.exclude(device=None)
        else:
            q_set = q_set.filter(device=None)

        for mr in q_set:

            # Check maximum region size
            mr_size = (mr.addr_to - mr.addr_from + 1)
            if mr_size > (32 * 1024 * 1024):
                # IGNORE MEMORIES LARGER THAN 32MB
                # (will tage ages and consume way too much memory otherwise.)
                print("WARNING: MemoryRegion {} is too large (only up to 32MB is supported).".format(mr.name))
                print("         Skip and continue.")
                continue

            for x in range(mr.addr_from, mr.addr_to + 1):
                r[mr.pk, x] = e8

        return r

    def all_faults(self, limit=None):
        items = []
        for k, v in self.gpr_faults(limit).items():
            items.extend(["g,{},0x{:08x}".format(k, f) for f in v])
        for k, v in self.csr_faults(limit).items():
            items.extend(["c,{},0x{:08x}".format(k, f) for f in v])
        for k, v in self.mmcsr_faults(limit).items():
            items.extend(["mcsr,{},0x{:08x}".format(k, f) for f in v])
        for k, v in self.instruction_faults(limit).items():
            items.extend(["i,{},0x{:08x}".format(k, f) for f in v])
        for k, v in self.memory_faults(limit).items():
            items.extend(["mcore,0x{:08x},0x{:08x}".format(k[0], k[1], f) for f in v])
        for k, v in self.memory_faults(device_memory=True, limit=limit).items():
            items.extend(["mdevice,0x{:08x},0x{:08x}".format(k[0], k[1], f) for f in v])
        return items

    def uncovered_faults(self, limit=None):
        from .mutation import MutantList
        f_return = set(self.all_faults(limit))
        for ml in MutantList.objects.filter(software__arch_id=self.pk):
            f_return -= ml.fault_coverage

        gpr_numbers = set()
        csr_numbers = set()
        insn_ids = set()
        mcsr_ids = set()

        for f in f_return:
            tpe, pk, flt = f.split(',')
            if tpe == "g":
                gpr_numbers.add(pk)
            elif tpe == "c":
                csr_numbers.add(pk)
            elif tpe == "i":
                insn_ids.add(pk)
            elif tpe == "mcsr":
                mcsr_ids.add(pk)
            elif tpe == "mcore" or tpe == "mdevice":
                # print("WARNING: Architecture.uncovered_faults(...)\n"
                #       "mcore and mdevice not yet supported, skipping!")
                pass
            else:
                raise Exception("Should not get here!")

        gprs = Gpr.objects.filter(subset__arch_id=self.pk, number__in=gpr_numbers)
        csrs = Csr.objects.filter(subset__arch_id=self.pk, number__in=csr_numbers)
        insns = Instruction.objects.filter(pk__in=insn_ids)

        return f_return, gprs, csrs, insns

    class Meta(NamedItem.Meta):
        unique_together = ("name",)


class Subset(models.Model):
    ISA_SUBSET_CHOICES = (
        ('I', 'Integer'),
        ('E', 'Reduced Integer'),
        ('M', 'Integer Multiplication and Division'),
        ('A', 'Atomics'),
        ('F', 'Single-Precision Floating-Point'),
        ('D', 'Double-Precision Floating-Point'),
        ('C', '16-bit Compressed Instructions'),
        ('N', 'User-Level Interrupts'),
        ('Zicsr', 'Control and Status Register Access'),
        ('Zifencei', 'Instruction-Fetch Fence'),
        ('M-mode', 'Privilege-Level Machine'),
        ('S-mode', 'Privilege-Level Supervisor'),
        ('PMP', 'Physical Memory Protection Unit'),
    )

    arch = models.ForeignKey(Architecture, on_delete=models.CASCADE, related_name="subsets")
    name = models.CharField(max_length=50, choices=ISA_SUBSET_CHOICES)

    class Meta:
        unique_together = ("arch", "name",)


class ExecCoverage(models.Model):
    software = models.ForeignKey("Software", related_name="%(class)s", on_delete=models.CASCADE)
    x = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['x'])
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(x__gt=0), name="%(app_label)s_%(class)s_x_gt_0")
        ]


class InstructionCoverage(ExecCoverage):
    instruction = models.ForeignKey(Instruction, related_name="exec_coverage", on_delete=models.CASCADE)
    instances = models.PositiveIntegerField(default=0)

    class Meta:
        index_together = [
            ["software"],
            ["software", "x"],
            ["software", "instances"],
        ]


class ReadWriteCoverage(ExecCoverage):
    r = models.PositiveIntegerField(default=0)
    w = models.PositiveIntegerField(default=0)

    class Meta(ExecCoverage.Meta):
        abstract = True


class GprCoverage(ReadWriteCoverage):
    register = models.ForeignKey(Gpr, related_name="exec_coverage", on_delete=models.CASCADE)


class FprCoverage(ReadWriteCoverage):
    register = models.ForeignKey(Fpr, related_name="exec_coverage", on_delete=models.CASCADE)
    # Disable quantitative analysis for FPRs as this is not available in QEMU...
    x = None
    r = None
    w = None

    class Meta:
        pass


class CsrCoverage(ReadWriteCoverage):
    register = models.ForeignKey(Csr, related_name="exec_coverage", on_delete=models.CASCADE)


class DeviceCsrCoverage(ReadWriteCoverage):
    register = models.ForeignKey(DeviceCsr, related_name="exec_coverage", on_delete=models.CASCADE)


class MemoryRegionCoverage(ReadWriteCoverage):
    memory_region = models.ForeignKey(MemoryRegion, related_name="exec_coverage", on_delete=models.CASCADE)

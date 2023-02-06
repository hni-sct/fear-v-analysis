import os
import re
import tempfile
from subprocess import run, DEVNULL
from django.core.files import File
from django.db import models
from . import InstructionFault
from ..managers.mutants import MutantListManager, MutantManager


class Mutant(models.Model):

    class Kind(models.IntegerChoices):
        GPR_PERMANENT_FLIP = 1
        GPR_PERMANENT_SA_0 = 10
        GPR_PERMANENT_SA_1 = 11
        GPR_TRANSIENT_FLIP = 2

        CSR_PERMANENT_FLIP = 3
        CSR_PERMANENT_SA_0 = 30
        CSR_PERMANENT_SA_1 = 31
        CSR_TRANSIENT_FLIP = 4

        IMEM_PERMANENT_FLIP = 5
        IMEM_PERMANENT_SA_0 = 50
        IMEM_PERMANENT_SA_1 = 51

        IFR_PERMANENT_FLIP = 7
        IFR_PERMANENT_SA_0 = 70
        IFR_PERMANENT_SA_1 = 71

        COREMEM_PERMANENT_FLIP = 8
        COREMEM_PERMANENT_SA_0 = 80
        COREMEM_PERMANENT_SA_1 = 81

    parent = models.ForeignKey("MutantList", related_name="mutants", on_delete=models.CASCADE)
    # kind = models.CharField(max_length=25, choices=MUTANT_KIND_CHOICES)
    kind = models.IntegerField(choices=Kind.choices)
    bitflip = models.PositiveBigIntegerField()
    nr_or_address = models.PositiveBigIntegerField()
    access_idx = models.PositiveBigIntegerField(default=0)
    ifault = models.ForeignKey(InstructionFault, null=True, blank=True, on_delete=models.CASCADE)

    detected_error = models.CharField(max_length=100, default="?")
    runtime = models.BigIntegerField(default=0)

    objects = MutantManager()

    # Zu Indizes:
    # - ["parent_id", "runtime"],# TBD: Wichtig? Auf jeden Fall fuer FSIM Resultate Export
    # - ["parent_id", "detected_error"],# TBD: Wichtig? Auf jeden Fall fuer FSIM Resultate Export

    class Meta:
        index_together = [
            ["kind"],
            ["kind", "bitflip", "detected_error"],
            ["kind", "ifault", "bitflip", "detected_error"],
            ["parent", "kind"],
            ["parent", "detected_error", "nr_or_address"],
            ["parent", "kind", "bitflip", "detected_error"],
            ["parent", "kind", "ifault", "bitflip", "detected_error"],
        ]


class MutantList(models.Model):
    software = models.OneToOneField("Software", related_name="mutantlist", on_delete=models.CASCADE, primary_key=True)
    skipped = models.PositiveIntegerField(default=0)
    with_gpr = models.BooleanField(default=True)
    with_csr = models.BooleanField(default=True)
    # with_devices = models.BooleanField(default=True)
    with_imem = models.BooleanField(default=True)
    with_coremem = models.BooleanField(default=False)
    with_ifr = models.BooleanField(default=True)
    with_flip_faults = models.BooleanField(default=True)
    with_stuckat_faults = models.BooleanField(default=True)
    with_transient_faults = models.BooleanField(default=False)
    mutantlist = models.FileField(upload_to="mutants", null=True, blank=True)
    testresults = models.FileField(upload_to="results", null=True, blank=True)

    objects = MutantListManager()

    def __str__(self):
        return "MutantList[pk:{}, mutants.count:{}]".format(self.pk, self.mutants.count())

    def run_tests(self, verbose=True):
        skipped = self.skipped

        with tempfile.NamedTemporaryFile(mode="w", delete=True, suffix=".mutants", buffering=20 * (1024 ** 2)) as temp:
            # print("CREATED MUTANT LIST '{}'".format(temp.name))
            # print("ELF FILE '{}'".format(self.software.elf.path))
            # print("TEST-REPORT FILE '{}'".format(temp.name.replace(".mutants", ".testreport")))
            mutant_file = temp.name

            # 1) Create the mutant list and store it as temporary file...
            temp.write("#id,kind,address/regnum,nracc,biterror\n")

            for p in self.mutants.values_list('id', 'kind', 'nr_or_address', 'access_idx', 'bitflip').iterator():
                temp.write("{},{},{},{},0x{:08X}\n".format(p[0], p[1], p[2], p[3], p[4]))

            temp.write("# Done: created {} mutants (skipped: {}).\n".format(self.mutants.count(), skipped))
            temp.flush()
            self.mutantlist.save("{}_{}.mutants".format(self.pk, self.software.name), File(open(mutant_file, "r")))
            self.save()

            # 2) Run QEMU simulation...
            # print("BEGINNING QEMU SIMULATION...")
            results_file = mutant_file.replace(".mutants", ".testreport")
            cmd = ["qemu-system-riscv32",
                   "-M", self.software.arch.qemu_machine,
                   "-cpu", self.software.arch.qemu_cpu,
                   "-kernel", self.software.elf.path,
                   "-bios", "none", "-nographic", "-display", "none",
                   "-serial", "none",
                   "-device", "terminator,address=0x{:08X}".format(int(self.software.arch.qemu_terminator)),
                   "-test-setup", self.software.arch.qemu_testsetup,
                   # "-mutant-list", self.mutantlist.path,
                   "-mutant-list", mutant_file,
                   "-test-report", results_file,
                   ]
            # print("      CMD: {}".format(" ".join(cmd)))
            # os.system("{} 1> /dev/null".format(" ".join(cmd)))
            if verbose:
                run(cmd, check=True, stdout=DEVNULL, stdin=DEVNULL, encoding="UTF-8")
            else:
                run(cmd, check=True, stdout=DEVNULL, stdin=DEVNULL, stderr=DEVNULL, encoding="UTF-8")
            # run(cmd, check=True, encoding="UTF-8")

            self.testresults.save("{}_{}.testreport".format(self.pk, self.software.name), File(open(results_file, 'r')))
            self.save()
            os.remove(results_file)

            # print("\nDONE SIMULATING!")

            return

        # NOTE: Statements below are unreachable -> commented out...
        # print("\n              ERROR while running MutantList.run_tests()")
        # sys.exit(1)

    def read_results(self):
        self.read_time()

        regex = re.compile(r"\s*(?P<id>\d+),\s*(?P<result>[\w\-_: ]+),\s*(?P<duration>\d+) us")
        with open(self.testresults.path, 'r') as f:
            m_update = list()
            # for l in f.readlines():
            for line in f:
                m = regex.match(line)
                if m is not None:
                    i = int(m.group('id').strip(), 10)
                    res = m.group('result').strip()
                    dur = int(m.group('duration').strip(), 10)
                    m_update.append(Mutant(id=i, detected_error=res, runtime=dur))

                if len(m_update) > 10000:
                    Mutant.objects.bulk_update(m_update, ['detected_error', 'runtime'], batch_size=2000)
                    m_update = list()

            Mutant.objects.bulk_update(m_update, ['detected_error', 'runtime'], batch_size=2000)

    def read_time(self):
        regex = re.compile(r"#\s+Golden run took\s+(?P<time>\d+) us to complete...")
        with open(self.testresults.path, 'r') as f:
            for line in f:
                m = regex.match(line)
                if m is not None:
                    time = int(m.group('time').strip(), 10)
                    self.software.time = time
                    self.software.save()
                    return

    @property
    def fault_coverage(self):
        items = []

        # One line per GPR
        all_gpr_mutants = self.mutants.killed().filter(kind__in=[
                Mutant.Kind.GPR_PERMANENT_FLIP,
                Mutant.Kind.GPR_PERMANENT_SA_0,
                Mutant.Kind.GPR_PERMANENT_SA_1,
                Mutant.Kind.GPR_TRANSIENT_FLIP
            ])
        for (pk, bit) in all_gpr_mutants.values_list("nr_or_address", "bitflip").distinct():
            items.append("g,{},0x{:08x}".format(pk, bit))

        # One line per CSR
        all_csr_mutants = self.mutants.killed().filter(kind__in=[
                Mutant.Kind.CSR_PERMANENT_FLIP,
                Mutant.Kind.CSR_PERMANENT_SA_0,
                Mutant.Kind.CSR_PERMANENT_SA_1,
                Mutant.Kind.CSR_TRANSIENT_FLIP,
            ])
        for (pk, bit) in all_csr_mutants.values_list("nr_or_address", "bitflip").distinct():
            items.append("c,{},0x{:08x}".format(pk, bit))

        #######################################################################
        # ERR: | This does not work yet since it needs to                     #
        # -----| output "mcore,<MCORE_ID>,<ADDR>,<BITERROR>" there is no      #
        #      | fast method to decide whether this COREMEM mutant refers to  #
        #      | a MMCSR, a CoreMemRegion or DeviceMemRegion.                 #
        #      |------------------------------------------------------------- #
        #      | TO-DO: Implement different Mutant types for all use cases.   #
        #      |------------------------------------------------------------- #
        #      | (Searching for <ADDR> in all MemoryRegion is possible but    #
        #      |  probably extremely slow...)                                 #
        #######################################################################

        #######################################################################
        # TO DO: One line per CoreMemoryRegion                                #
        #######################################################################
        # all_mem_mutants = self.mutants.killed().filter(kind__in=[
        #         Mutant.Kind.COREMEM_PERMANENT_FLIP,
        #         Mutant.Kind.COREMEM_PERMANENT_SA_0,
        #         Mutant.Kind.COREMEM_PERMANENT_SA_1,
        #         #Mutant.Kind.COREMEM_TRANSIENT_FLIP,
        #     ])
        #
        # ------------------------------------------------------------------- #
        #                                                                     #
        # for (addr, bit) in all_mcore_mutants.values_list("nr_or_address", "bitflip").distinct():
        #     items.append("mcore,0x{:08x},0x{:08x}".format(mcore_id, addr, bit))
        #                                                                     #
        #######################################################################

        #######################################################################
        # TO DO: One line per DeviceMemoryRegion                              #
        #######################################################################

        #######################################################################
        # TO DO: One line per MMCSR                                           #
        #######################################################################

        # IMEM
        all_imem_mutants = self.mutants.killed().filter(kind__in=[
                Mutant.Kind.IMEM_PERMANENT_FLIP,
                Mutant.Kind.IMEM_PERMANENT_SA_0,
                Mutant.Kind.IMEM_PERMANENT_SA_1,
                # Mutant.Kind.IMEM_TRANSIENT_FLIP,
            ])
        for (pk, bit) in all_imem_mutants.values_list("ifault__source_id", "bitflip").distinct():
            items.append("i,{},0x{:08x}".format(pk, bit))

        return frozenset(items)

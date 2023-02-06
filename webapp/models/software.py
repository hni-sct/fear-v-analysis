import itertools
import os
import sys
from heapq import *
from subprocess import run, DEVNULL
from django.core.files import File
from django.db import models
from django.db.models import Sum


class SoftwareList(models.Model):
    name = models.CharField(max_length=40, default='', unique=True)
    software = models.ManyToManyField("Software", blank=True)

    def get_cov_instructions(self, subset=None):
        from . import Instruction
        c = Instruction.objects.filter(exec_coverage__software__in=self.software.all())
        if isinstance(subset, str):
            c = c.filter(subset__name=subset)
        return set(c.values_list("name", flat=True))

    def get_all_instructions(self, subset=None):
        from . import Instruction
        c = Instruction.objects.filter(subset__arch=self.software.first().arch)
        if isinstance(subset, str):
            c = c.filter(subset__name=subset)
        return set(c.values_list("name", flat=True))

    def get_summary_instructions(self, subset=None):
        i_all = self.get_all_instructions(subset)
        i_cov = self.get_cov_instructions(subset)
        i_mis = i_all - i_cov
        if len(i_all) == 0:
            ratio = "N/A"
        elif len(i_all) == len(i_cov):
            ratio = "100"
        else:
            ratio = "{0:0.1f}".format(100.0 * len(i_cov) / len(i_all)).replace(".0", "")
        return {
            'all': sorted(i_all),
            'cov': sorted(i_cov),
            'mis': sorted(i_mis),
            'ratio': ratio,
        }

    def aggregate_all(self):
        from . import GprCoverage, CsrCoverage, DeviceCsrCoverage, MemoryRegionCoverage, InstructionCoverage
        r = {"gpr": GprCoverage.objects.filter(software__softwarelist=self).aggregate(r=Sum('r'), w=Sum('w'),
                                                                                      x=Sum('x')),
             "csr": CsrCoverage.objects.filter(software__softwarelist=self).aggregate(r=Sum('r'), w=Sum('w'),
                                                                                      x=Sum('x')),
             "dcsr": DeviceCsrCoverage.objects.filter(software__softwarelist=self).aggregate(r=Sum('r'), w=Sum('w'),
                                                                                             x=Sum('x')),
             "mr": MemoryRegionCoverage.objects.filter(software__softwarelist=self).aggregate(r=Sum('r'), w=Sum('w'),
                                                                                              x=Sum('x')),
             "insn": InstructionCoverage.objects.filter(software__softwarelist=self).aggregate(x=Sum('x'),
                                                                                               instances=Sum(
                                                                                                   'instances'))}
        return r


class SoftwareQuerySet(models.QuerySet):
    def set_cover(self):

        subsets = {}

        for sw in self.select_related('mutantlist').iterator():
            c = sw.mutantlist.fault_coverage
            if c not in subsets:
                subsets[c] = sw

        """Find a family of subsets that covers the universal set"""
        elements = set(e for s in subsets for e in s)
        covered = set()
        cover = []

        # Greedily add the subsets with the most uncovered points
        while covered != elements:
            subset = max(subsets, key=lambda s: len(s - covered))
            cover.append(subset)
            covered |= subset

        return [subsets[c] for c in cover]

    MAXPRIORITY = sys.maxsize

    class PriorityQueue:
        def __init__(self):
            self._pq = []
            self._entry_map = {}
            self._counter = itertools.count()

        def addtask(self, task, priority=0):
            # Add a new task or update the priority of an existing task.
            if task in self._entry_map:
                self.removetask(task)
            count = next(self._counter)
            entry = [priority, count, task]
            self._entry_map[task] = entry
            heappush(self._pq, entry)

        def removetask(self, task):
            # Mark an existing task as REMOVED.
            entry = self._entry_map.pop(task)
            entry[-1] = 'removed'

        def poptask(self):
            # Remove and return the lowest priority task.
            while self._pq:
                priority, count, task = heappop(self._pq)
                if task != 'removed':
                    del self._entry_map[task]
                    return task

        def __len__(self):
            return len(self._entry_map)

    def weighted_set_cover(self, tpe):

        subsets = {}
        for sw in self.select_related('mutantlist').prefetch_related('instructioncoverage').iterator():
            c = sw.mutantlist.fault_coverage
            if c not in subsets:
                subsets[c] = sw
            else:
                if tpe == 'time':
                    if sw.time < subsets[c].time:
                        subsets[c] = sw
                elif tpe == 'iinst':
                    if sw.instructioncoverage.aggregate(i_inst=Sum('instances'))["i_inst"] < \
                            subsets[c].instructioncoverage.aggregate(i_inst=Sum('instances'))["i_inst"]:
                        subsets[c] = sw
                elif tpe == 'iexec':
                    if sw.instructioncoverage.aggregate(i_exec=Sum('x'))["i_exec"] < \
                            subsets[c].instructioncoverage.aggregate(i_exec=Sum('x'))["i_exec"]:
                        subsets[c] = sw
                # elif tpe == 'progs':
                #     if sw.pk < subsets[c].pk:
                #         subsets[c] = sw
                else:
                    raise Exception("Unknown tpe!")

        l_subsets = list(subsets.keys())
        if tpe == 'time':
            l_weigths = [subsets[k].time for k in l_subsets]
        elif tpe == 'iinst':
            l_weigths = [subsets[k].instructioncoverage.aggregate(i_inst=Sum('instances'))["i_inst"] for k in l_subsets]
        elif tpe == 'iexec':
            l_weigths = [subsets[k].instructioncoverage.aggregate(i_exec=Sum('x'))["i_exec"] for k in l_subsets]
        # elif tpe == 'progs':
        #     l_weigths = [1 for k in l_subsets]
        else:
            raise Exception("Unknown tpe!")

        # from weightedsetcover(l_subsets, l_weigths)
        udict = {}
        selected = list()
        scopy = []  # During the process, l_subsets will be modified. Make a copy for l_subsets.
        for index, item in enumerate(l_subsets):
            scopy.append(set(item))
            for j in item:
                if j not in udict:
                    udict[j] = set()
                udict[j].add(index)

        pq = SoftwareQuerySet.PriorityQueue()
        cost = 0
        coverednum = 0
        for index, item in enumerate(scopy):  # add all sets to the priorityqueue
            if len(item) == 0:
                pq.addtask(index, SoftwareQuerySet.MAXPRIORITY)
            else:
                # pq.addtask(index, float(l_weigths[index]) / len(item))
                pq.addtask(index, l_weigths[index] / len(item))
        while coverednum < len(udict):
            a = pq.poptask()  # get the most cost-effective set
            selected.append(subsets[l_subsets[a]])  # a: set id
            cost += l_weigths[a]
            coverednum += len(scopy[a])
            # Update the sets that contains the new covered elements
            for m in scopy[a]:  # m: element
                for n in udict[m]:  # n: set id
                    if n != a:
                        scopy[n].discard(m)
                        if len(scopy[n]) == 0:
                            pq.addtask(n, SoftwareQuerySet.MAXPRIORITY)
                        else:
                            # pq.addtask(n, float(l_weigths[n]) / len(scopy[n]))
                            pq.addtask(n, l_weigths[n] / len(scopy[n]))
            scopy[a].clear()
            pq.addtask(a, SoftwareQuerySet.MAXPRIORITY)

        return selected, cost


class Software(models.Model):
    OPTIMIZATION_CHOICES = (
        ('-O0', '-O0'),
        ('-O1', '-O1'),
        ('-O2', '-O2'),
        ('-O3', '-O3'),
        ('-Os', '-Os'),
    )

    arch = models.ForeignKey("Architecture", related_name="testsoftware", on_delete=models.CASCADE)
    name = models.CharField(max_length=40, default='', unique=True)
    generator = models.CharField(max_length=50, default='csmith')
    optimization = models.CharField(max_length=50, choices=OPTIMIZATION_CHOICES, default='-O0')
    time = models.PositiveIntegerField(default=0)

    src = models.FileField(upload_to="src", null=True, blank=True)
    elf = models.FileField(upload_to="bin", null=True, blank=True)
    lst = models.FileField(upload_to="analysis", null=True, blank=True)

    objects = SoftwareQuerySet.as_manager()

    def delete(self, using=None, keep_parents=False):
        if self.src and self.src.storage.exists(self.src.name):
            self.src.storage.delete(self.src.name)
        if self.elf and self.elf.storage.exists(self.elf.name):
            self.elf.storage.delete(self.elf.name)
        if self.lst and self.lst.storage.exists(self.lst.name):
            self.lst.storage.delete(self.lst.name)
        super().delete()

    def gen_lst(self, retries_left=5):
        try:
            cmd = ["qemu-system-riscv32",
                   "-M", self.arch.qemu_machine,
                   "-cpu", self.arch.qemu_cpu,
                   "-kernel", self.elf.path,
                   "-bios", "none", "-device", "terminator,address={}".format(self.arch.qemu_terminator), "-nographic",
                   "-d", "in_asm,goldenrun", "-D", "/tmp/{}.lst".format(self.name)]

            if retries_left == 0:
                print("ERROR running '{}' (gave up after 5 attempts)".format(" ".join(cmd)))
                # TO DO: This does not kill the subprocess pool. But we should really stop here!
                sys.exit(1)

            run(cmd, check=True, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL, timeout=120, encoding="UTF-8")

            self.lst.save("{}.lst".format(self.name), File(open("/tmp/{}.lst".format(self.name), "rb")))
            os.remove("/tmp/{}.lst".format(self.name))

        except Exception as e:
            print("WARNING: Got an Exception while during Software.gen_lst(...).")
            print("         Exception text was: {}.".format(e))
            print("         Retrying...")
            self.gen_lst(retries_left - 1)

    def get_gpr_rwx(self):
        return self.gprcoverage.aggregate(total=Sum('x'), reads=Sum('r'), writes=Sum('w'))

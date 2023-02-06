from .models.hardware import Csr, GprCoverage, FprCoverage, CsrCoverage, DeviceCsr, DeviceCsrCoverage, MemoryRegion, \
    MemoryRegionCoverage, InstructionCoverage
from tools.GoldenRunParser import GoldenRunParser


def match_memory_accesses(sw, mem_x, x_size, cached_mrcov, cached_dcsrcov):
    for loc, exe in mem_x.items():
        loc2 = loc + x_size - 1
        if MemoryRegion.objects.filter(arch=sw.arch, addr_from__lte=loc, addr_to__gte=loc2).exists():
            mr = MemoryRegion.objects.get(arch=sw.arch, addr_from__lte=loc, addr_to__gte=loc2)
            # retrieve MemoryRegionCoverage object from cache
            mrcov = cached_mrcov[mr]
            mrcov.x = mrcov.x + exe[2]
            mrcov.r = mrcov.r + exe[0]
            mrcov.w = mrcov.w + exe[1]
        elif DeviceCsr.objects.filter(device__arch=sw.arch, number=loc).exists():
            csr = DeviceCsr.objects.get(device__arch=sw.arch, number=loc)
            # retrieve DeviceCsrCoverage object from cache
            csrcov = cached_dcsrcov[csr]
            csrcov.x = csrcov.x + exe[2]
            csrcov.r = csrcov.r + exe[0]
            csrcov.w = csrcov.w + exe[1]
        else:
            print("   *** TO DO *** : Implement memory matching! (Loc: {}, #Reads: {}, #Writes: {}".format(hex(loc),
                                                                                                           exe[0],
                                                                                                           exe[1]))


def analyze_hwcoverage(sw):
    # HW Coverage Analysis...
    dp = GoldenRunParser(sw.arch, sw.lst.path)

    # Store results right here in this model...
    for r, exe in dp.get_all_gpr_accesses().items():
        if exe[2] > 0:
            regcov = GprCoverage(software=sw, register_id=r, x=exe[2], r=exe[0], w=exe[1])
            regcov.save()

    for r in dp.get_covered_registers()[1]:
        regcov = FprCoverage(software=sw, register=r)
        regcov.save()

    for idx, exe in dp.get_all_csr_accesses().items():
        if not Csr.objects.filter(subset__arch=sw.arch, number=idx).exists():
            # Csr.objects.create(arch=sw.arch, number=idx)
            print("  *** WARNING *** : undefined CSR with id={}.".format(idx))
            continue
        r = Csr.objects.get(subset__arch=sw.arch, number=idx)
        regcov = CsrCoverage(software=sw, register=r, x=exe[2], r=exe[0], w=exe[1])
        regcov.save()

    # initialize MemoryRegionCoverage objects and store in cache
    cached_mrcov = dict()
    for mr in MemoryRegion.objects.filter(arch=sw.arch):
        cached_mrcov[mr] = MemoryRegionCoverage(software=sw, memory_region=mr)

    # initialize DeviceCsrCoverage objects and store in cache
    cached_dcsrcov = dict()
    for csr in DeviceCsr.objects.filter(device__arch=sw.arch):
        cached_dcsrcov[csr] = DeviceCsrCoverage(software=sw, register=csr)

    # match/accumulate memory location accesses
    mem8, mem16, mem32 = dp.get_all_mem_accesses()
    match_memory_accesses(sw, mem8,  1, cached_mrcov, cached_dcsrcov)
    match_memory_accesses(sw, mem16, 2, cached_mrcov, cached_dcsrcov)
    match_memory_accesses(sw, mem32, 4, cached_mrcov, cached_dcsrcov)

    # bulk create all cached Coverage objects
    MemoryRegionCoverage.objects.bulk_create([m for m in cached_mrcov.values() if m.x > 0])
    DeviceCsrCoverage.objects.bulk_create([m for m in cached_dcsrcov.values() if m.x > 0])

    insn2inst = dp.get_instruction_instances()
    for insn, count in dp.get_instruction_executions().items():
        insncov = InstructionCoverage(software=sw, instruction=insn, x=count, instances=insn2inst[insn])
        insncov.save()

    # # Add Zero-Execution-Coverage for all remaining instructions
    # for i in Instruction.objects.filter(subset__arch=sw.arch):
    #     if not InstructionCoverage.objects.filter(software=sw, instruction=i).exists():
    #         insncov = InstructionCoverage(software=sw, instruction=i, x=0)
    #         insncov.save()

    # # Copy PC Values List:
    # pcvals = [ TagValue(data=d) for d in dp.pc_values ]
    # TagValue.objects.bulk_create(pcvals, batch_size=1000, ignore_conflicts=True)
    # sw.covered_pc_values.add(*pcvals)

from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from ..models import SoftwareList, Software, MemoryRegionCoverage, GprCoverage, FprCoverage, CsrCoverage, \
    DeviceCsrCoverage, MemoryRegion, Gpr, Fpr, Csr, DeviceCsr, MutantList


def software(request, software_id):
    sw = get_object_or_404(Software, pk=software_id)

    return render(request,
                  "software/detail.html",
                  {
                      'arch': sw.arch,
                      'sw': sw,
                      'gprs': sw.gprcoverage.all(),
                      'fprs': sw.fprcoverage.all(),
                      'csrs': sw.csrcoverage.all(),
                      'insns': sw.instructioncoverage.order_by('instruction__subset', 'instruction__name'),
                      'dev_csrs': sw.devicecsrcoverage.order_by('register__number'),
                      'mem_regions': sw.memoryregioncoverage.exclude(memory_region__memtype="CSR").order_by(
                              'memory_region__addr_from'),

                      # 'exec_gprs': sw.gprcoverage.aggregate(total=Sum('x'), reads=Sum('r'), writes=Sum('w')),
                      'exec_csrs': sw.csrcoverage.aggregate(total=Sum('x'), reads=Sum('r'), writes=Sum('w')),
                      'exec_insns': sw.instructioncoverage.aggregate(total=Sum('x'), instances=Sum('instances')),
                      'exec_dcsrs': sw.devicecsrcoverage.aggregate(total=Sum('x'), reads=Sum('r'), writes=Sum('w')),
                      'exec_mr': sw.memoryregioncoverage.aggregate(total=Sum('x'), reads=Sum('r'), writes=Sum('w')),
                  })


def softwarelist(request, softwarelist_id):
    slist = get_object_or_404(SoftwareList, pk=softwarelist_id)
    arch = slist.software.first().arch

    covered_gprs = set(GprCoverage.objects.filter(
        software__softwarelist=slist).values_list("register__name", flat=True))
    covered_fprs = set(FprCoverage.objects.filter(
        software__softwarelist=slist).values_list("register__name", flat=True))
    covered_csrs = set(CsrCoverage.objects.filter(
        software__softwarelist=slist).values_list("register__name", flat=True))
    covered_dcsrs = set(DeviceCsrCoverage.objects.filter(
        software__softwarelist=slist).values_list("register__name", flat=True))
    covered_mr = set(MemoryRegionCoverage.objects.filter(
        software__softwarelist=slist).values_list("memory_region__name", flat=True))

    summary_insn_all = slist.get_summary_instructions()
    summary_insn_i = slist.get_summary_instructions(subset="I")
    summary_insn_icsr = slist.get_summary_instructions(subset="Zicsr")
    summary_insn_ifencei = slist.get_summary_instructions(subset="Zifencei")
    summary_insn_m = slist.get_summary_instructions(subset="M")
    summary_insn_a = slist.get_summary_instructions(subset="A")
    summary_insn_f = slist.get_summary_instructions(subset="F")
    summary_insn_d = slist.get_summary_instructions(subset="D")
    summary_insn_c = slist.get_summary_instructions(subset="C")
    summary_insn_machine = slist.get_summary_instructions(subset="M-mode")

    all_gprs = set(Gpr.objects.filter(subset__arch=arch).values_list("name", flat=True))
    all_fprs = set(Fpr.objects.filter(subset__arch=arch).values_list("name", flat=True))
    all_csrs = set(Csr.objects.filter(subset__arch=arch).values_list("name", flat=True))
    all_dcsrs = set(DeviceCsr.objects.filter(device__arch=arch).values_list("name", flat=True))
    all_mr = set(MemoryRegion.objects.filter(arch=arch).values_list("name", flat=True))

    r_gprs = "{0:0.2f}".format(100.0 * len(covered_gprs)/max(1, len(all_gprs)))
    r_fprs = "{0:0.2f}".format(100.0 * len(covered_fprs)/max(1, len(all_fprs)))
    r_csrs = "{0:0.2f}".format(100.0 * len(covered_csrs)/max(1, len(all_csrs)))
    r_dcsrs = "{0:0.2f}".format(100.0 * len(covered_dcsrs)/max(1, len(all_dcsrs)))
    r_mr = "{0:0.2f}".format(100.0 * len(covered_mr)/max(1, len(all_mr)))

    return render(request,
                  "software/list.html",
                  {
                      'arch': arch,
                      'slist': slist,

                      'covered_gprs': sorted(covered_gprs),
                      'covered_fprs': sorted(covered_fprs),
                      'covered_csrs': sorted(covered_csrs),
                      'covered_dcsrs': sorted(covered_dcsrs),
                      'covered_mr': sorted(covered_mr),

                      'missing_gprs': sorted(all_gprs-covered_gprs),
                      'missing_fprs': sorted(all_fprs-covered_fprs),
                      'missing_csrs': sorted(all_csrs-covered_csrs),
                      'missing_dcsrs': sorted(all_dcsrs-covered_dcsrs),
                      'missing_mr': sorted(all_mr-covered_mr),

                      'covered_instructions': summary_insn_all['cov'],
                      'covered_instructions_rv32i': summary_insn_i['cov'],
                      'covered_instructions_rv32icsr': summary_insn_icsr['cov'],
                      'covered_instructions_rv32ifencei': summary_insn_ifencei['cov'],
                      'covered_instructions_rv32m': summary_insn_m['cov'],
                      'covered_instructions_rv32a': summary_insn_a['cov'],
                      'covered_instructions_rv32f': summary_insn_f['cov'],
                      'covered_instructions_rv32d': summary_insn_d['cov'],
                      'covered_instructions_rv32c': summary_insn_c['cov'],
                      'covered_instructions_machine': summary_insn_machine['cov'],

                      'missing_instructions': summary_insn_all['mis'],
                      'missing_instructions_rv32i': summary_insn_i['mis'],
                      'missing_instructions_rv32icsr': summary_insn_icsr['mis'],
                      'missing_instructions_rv32ifencei': summary_insn_ifencei['mis'],
                      'missing_instructions_rv32m': summary_insn_m['mis'],
                      'missing_instructions_rv32a': summary_insn_a['mis'],
                      'missing_instructions_rv32f': summary_insn_f['mis'],
                      'missing_instructions_rv32d': summary_insn_d['mis'],
                      'missing_instructions_rv32c': summary_insn_c['mis'],
                      'missing_instructions_machine': summary_insn_machine['mis'],

                      'r_gprs': r_gprs,
                      'r_fprs': r_fprs,
                      'r_csrs': r_csrs,
                      'r_dcsrs': r_dcsrs,
                      'r_mr': r_mr,

                      'r_instructions': summary_insn_all['ratio'],
                      'r_instructions_rv32i': summary_insn_i['ratio'],
                      'r_instructions_rv32icsr': summary_insn_icsr['ratio'],
                      'r_instructions_rv32ifencei': summary_insn_ifencei['ratio'],
                      'r_instructions_rv32m': summary_insn_m['ratio'],
                      'r_instructions_rv32a': summary_insn_a['ratio'],
                      'r_instructions_rv32f': summary_insn_f['ratio'],
                      'r_instructions_rv32d': summary_insn_d['ratio'],
                      'r_instructions_rv32c': summary_insn_c['ratio'],
                      'r_instructions_machine': summary_insn_machine['ratio'],
                  })


def mutantlist(request, mutantlist_id):
    ml = get_object_or_404(MutantList, pk=mutantlist_id)
    mutants = list(ml.mutants.order_by("id", "kind", "nr_or_address"))

    return render(request,
                  "mutants/list.html",
                  {
                      'arch': ml.software.arch,
                      'ml': ml,
                      'mutants': mutants,
                  })

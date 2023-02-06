from django.shortcuts import render, get_object_or_404
from ..models import *


def architecture_faults(request, arch_id):
    
    a = Architecture.objects.get(pk=arch_id)
    # Things to consider:
    # - Average nr of faults per
    #   - 16 Bit Instruction (1, 2, 3, [1-3])
    #   - 32 Bit Instruction (1, 2, 3, [1-3])
    # - Average chance to cause
    #   - Illegal
    #   - Wrong Opcode
    #   - Wrong Opcode with unwanted control flow change
    #   - Parameter fault:
    #     - Gpr/Fpr/Csr
    #     - Immediate
    
    # Instruction count:
    icount_16 = Instruction.objects.filter(subset__arch=a, bits=16).count()
    icount_32 = Instruction.objects.filter(subset__arch=a, bits=32).count()
    icount = [icount_16, icount_32, (icount_16+icount_32)]
    
    # Nr of all possible faults:
    faults_16_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=16).count()
    faults_32_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=32).count()
    faults = [faults_16_all, faults_32_all, (faults_16_all+faults_32_all)]
    
    # No effect (don't care) faults:
    dc_faults_16_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=16, effect_opcode='none',
                                                       effect_gpr=False, effect_fpr=False, effect_csr=False,
                                                       effect_imm=False).count()
    dc_faults_32_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=32, effect_opcode='none',
                                                       effect_gpr=False, effect_fpr=False, effect_csr=False,
                                                       effect_imm=False).count()
    dc_faults = [dc_faults_16_all, dc_faults_32_all]
    
    # Illegal opcode faults:
    illegal_faults_16_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=16,
                                                            effect_opcode='illegal').count()
    illegal_faults_32_all = InstructionFault.objects.filter(source__subset__arch=a, source__bits=32,
                                                            effect_opcode='illegal').count()
    illegal_faults = [illegal_faults_16_all, illegal_faults_32_all]
    
    #  All other faults:
    relevant_faults = [
        faults[0] - (dc_faults[0] + illegal_faults[0]),
        faults[1] - (dc_faults[1] + illegal_faults[1]),
        (faults[0] - (dc_faults[0] + illegal_faults[0])) + (faults[1] - (dc_faults[1] + illegal_faults[1]))
    ]
    
    percent = [0, 0, 0]
    if faults[0] != 0:
        percent[0] = round((relevant_faults[0] / float(faults[0])) * 100.0, 2)
    if faults[1] != 0:
        percent[1] = round((relevant_faults[1] / float(faults[1])) * 100.0, 2)
    if (faults[0] + faults[1]) > 0:
        percent[2] = round((relevant_faults[2] / float(faults[2])) * 100.0, 2)
    
    return render(request, 
                  'architecture/faults.html',
                  {
                      'arch': a,
                      'nav_id': 1,
                      'icount': icount,
                      'faults': faults,
                      'dc_faults': dc_faults,
                      'illegal_faults': illegal_faults,
                      'relevant_faults': relevant_faults,
                      'other': Instruction.objects.filter(subset__arch=a).order_by('name'),
                      'percent': percent,
                  })


def detail(request, instruction_id):
    instruction = get_object_or_404(Instruction, pk=instruction_id)
    a = instruction.subset.arch
    other = Instruction.objects.filter(subset__arch_id=a.id).order_by('name')
    return render(request,
                  'instruction/detail.html',
                  {
                      'arch': a,
                      'nav_id': instruction.id,
                      'instruction': instruction,
                      'other': other,
                  })


def interactive(request, instruction_id):
    instruction = get_object_or_404(Instruction, pk=instruction_id)
    a = instruction.subset.arch
    other = Instruction.objects.filter(subset__arch_id=a.id).order_by('name')
    return render(request,
                  'instruction/bitflip.html',
                  {
                      'arch': a,
                      'nav_id': instruction.id,
                      'instruction': instruction,
                      'other': other,
                  })


COLORS = {
    'grey_light': '#F2F2F2',  
    'grey_medium': '#B2B2B2',
    'grey_dark': '#222222',
    'white': '#FFFFFF',
    'black': '#000000',
    
    'immediate': '#D5D5FF',
    'immediate_sel': '#8888FF',
    'register': '#D5FFD5',
    'register_sel': '#88FF88',
    'opcode': '#DDDDDD',
    'opcode_sel': '#A5A5A5',
    'dontcare': '#505050',
    'dontcare_sel': '#171717',
}


def css(request, file):
    return render(request,
                  'css/' + file,
                  {
                     'color': COLORS, 
                  },
                  content_type='text/css')


def architecture_mapping(request, arch_id):
    arch = get_object_or_404(Architecture, pk=arch_id)

    return render(request,
                  "architecture/mapping.html",
                  {
                      'arch': arch,
                      'gprs': Gpr.objects.filter(subset__arch=arch),
                      'fprs': Fpr.objects.filter(subset__arch=arch),
                      'csrs': Csr.objects.filter(subset__arch=arch),
                      'dev_csrs': DeviceCsr.objects.filter(device__arch=arch).order_by('number'),
                      'mem_regions':
                          MemoryRegion.objects.filter(arch=arch).exclude(memtype="CSR").order_by('addr_from'),
                  })


def architecture(request, arch_id):
    arch = get_object_or_404(Architecture, pk=arch_id)
    slists = SoftwareList.objects.filter(software__arch_id=arch_id).distinct()

    return render(request,
                  "architecture/index.html",
                  {
                      'arch': arch,
                      'slists': slists,
                  })

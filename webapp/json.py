from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Architecture, Instruction, InstructionFault
from math import comb

THEME_COLORS = {
    'RED_0_BG': 'rgba(255, 200, 200, 0.6)',
    'RED_1_BG': 'rgba(255, 128, 128, 0.6)',
    'RED_2_BG': 'rgba(255, 50, 50, 0.6)',
    'RED_3_BG': 'rgba(255, 0, 0, 0.6)',
    'RED_0_HOV': 'rgba(255, 200, 200, 0.8)',
    'RED_1_HOV': 'rgba(255, 128, 128, 0.8)',
    'RED_2_HOV': 'rgba(255, 50, 50, 0.8)',
    'RED_3_HOV': 'rgba(255, 0, 0, 0.8)',
    'RED_0_BRD': 'rgba(255, 200, 200, 1.0)',
    'RED_1_BRD': 'rgba(255, 128, 128, 1.0)',
    'RED_2_BRD': 'rgba(255, 50, 50, 1.0)',
    'RED_3_BRD': 'rgba(255, 0, 0, 1.0)',

    'MAG_0_BG': 'rgba(255, 204, 230, 0.6)',
    'MAG_1_BG': 'rgba(255, 128, 191, 0.6)',
    'MAG_2_BG': 'rgba(255, 51, 153, 0.6)',
    'MAG_3_BG': 'rgba(255, 0, 115, 0.6)',
    'MAG_0_HOV': 'rgba(255, 204, 230, 0.8)',
    'MAG_1_HOV': 'rgba(255, 128, 191, 0.8)',
    'MAG_2_HOV': 'rgba(255, 51, 153, 0.8)',
    'MAG_3_HOV': 'rgba(255, 0, 115, 0.8)',
    'MAG_0_BRD': 'rgba(255, 204, 230, 1.0)',
    'MAG_1_BRD': 'rgba(255, 128, 191, 1.0)',
    'MAG_2_BRD': 'rgba(255, 51, 153, 1.0)',
    'MAG_3_BRD': 'rgba(255, 0, 115, 1.0)',

    'BLU_0_BG': 'rgba(200, 200, 255, 0.6)',
    'BLU_1_BG': 'rgba(128, 128, 255, 0.6)',
    'BLU_2_BG': 'rgba(50, 50, 255, 0.6)',
    'BLU_3_BG': 'rgba(0, 0, 255, 0.6)',
    'BLU_0_HOV': 'rgba(200, 200, 255, 0.8)',
    'BLU_1_HOV': 'rgba(128, 128, 255, 0.8)',
    'BLU_2_HOV': 'rgba(50, 50, 255, 0.8)',
    'BLU_3_HOV': 'rgba(0, 0, 255, 0.8)',
    'BLU_0_BRD': 'rgba(200, 200, 255, 1.0)',
    'BLU_1_BRD': 'rgba(128, 128, 255, 1.0)',
    'BLU_2_BRD': 'rgba(50, 50, 255, 1.0)',
    'BLU_3_BRD': 'rgba(0, 0, 255, 1.0)',
}


def encoding(request, instruction_id, fault_mask=0):
    i = get_object_or_404(Instruction, pk=instruction_id)
    m = int(fault_mask)
    if int(fault_mask) != 0:
        f = get_object_or_404(InstructionFault, source=i, error_mask=m)
    bit_text = []
    for b in range(i.bits):
        bit = dict()
        if m != 0:
            i = f.target
        if i is None:
            bit["txt"] = "ILL"
            bit["class"] = "dontcare"
        elif i.mask & 1 << b:
            bit["class"] = "opcode"
            if i.opcode & 1 << b:
                bit["txt"] = "1"
            else:
                bit["txt"] = "0"
        else:
            bit["class"] = "dontcare"
            bit["txt"] = "X"
            for o in i.operands.all():
                if o.mask & 1 << b:
                    # This is operand
                    if o.optype == 'gpr' or o.optype == 'fpr' or o.optype == 'csr':
                        bit["class"] = "register"
                    else:
                        bit["class"] = "immediate"
                    bit["txt"] = o.shortname
        if m != 0 and m & 1 << b:
            bit["class"] += "_sel"
        bit_text.append(bit)
        
    result = dict()
    result['data'] = list(reversed(bit_text))
    return JsonResponse(result)


def testrelevance(request, arch_id, bits):
    a = get_object_or_404(Architecture, pk=arch_id)
    
    if int(bits) == 0:
        allfaults_count = InstructionFault.objects.filter(source__subset__arch=a).count()
        dc_count = InstructionFault.objects.filter(source__subset__arch=a,
                                                   effect_opcode='none',
                                                   effect_gpr=False,
                                                   effect_fpr=False,
                                                   effect_csr=False,
                                                   effect_imm=False).count()
        illegal_count = InstructionFault.objects.filter(source__subset__arch=a,
                                                        effect_opcode='illegal').count()
    else:
        allfaults_count = InstructionFault.objects.filter(source__subset__arch=a, 
                                                          source__bits=bits).count()
        dc_count = InstructionFault.objects.filter(source__subset__arch=a,
                                                   source__bits=bits,
                                                   effect_opcode='none',
                                                   effect_gpr=False,
                                                   effect_fpr=False,
                                                   effect_csr=False,
                                                   effect_imm=False).count()
        illegal_count = InstructionFault.objects.filter(source__subset__arch=a,
                                                        source__bits=bits,
                                                        effect_opcode='illegal').count()
                                                    
    relevant_count = allfaults_count - (dc_count + illegal_count)
    
    result = dict()
    result['labels'] = ["No effect", "Illegal opcode", "Remaining tests"]
    result['datasets'] = []
    result['datasets'].append(dict())
    result['datasets'][0]['data'] = [dc_count, illegal_count, relevant_count]
    result['datasets'][0]['borderWidth'] = 2
    result['datasets'][0]['backgroundColor'] = ["#404040", "#808080", "#ffdf80"]
    return JsonResponse(result)


def faultdistribution(request, arch_id):
    a = get_object_or_404(Architecture, pk=arch_id)
    
    dist = [
        InstructionFault.objects.filter(source__subset__arch=a, distance=1).exclude(effect_opcode='none').count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=1).filter(Q(effect_gpr=True) |
                                                                                   Q(effect_fpr=True) |
                                                                                   Q(effect_csr=True)).count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=1, effect_imm=True).count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=2).exclude(effect_opcode='none').count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=2).filter(Q(effect_gpr=True) |
                                                                                   Q(effect_fpr=True) |
                                                                                   Q(effect_csr=True)).count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=2, effect_imm=True).count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=3).exclude(effect_opcode='none').count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=3).filter(Q(effect_gpr=True) |
                                                                                   Q(effect_fpr=True) |
                                                                                   Q(effect_csr=True)).count(),
        InstructionFault.objects.filter(source__subset__arch=a, distance=3, effect_imm=True).count(),
    ]
    
    result = dict()
    result['labels'] = ["Opcode", "Data", "Address"]
    result['datasets'] = [dict(), dict(), dict(), dict()]
    
    result['datasets'][0]['label'] = "1 bitflip"
    result['datasets'][0]['borderWidth'] = 2
    result['datasets'][0]['borderColor'] = [THEME_COLORS['RED_0_BRD'], THEME_COLORS['MAG_0_BRD'],
                                            THEME_COLORS['BLU_0_BRD']]
    result['datasets'][0]['backgroundColor'] = [THEME_COLORS['RED_0_BG'], THEME_COLORS['MAG_0_BG'],
                                                THEME_COLORS['BLU_0_BG']]
    result['datasets'][0]['hoverBackgroundColor'] = [THEME_COLORS['RED_0_HOV'], THEME_COLORS['MAG_0_HOV'],
                                                     THEME_COLORS['BLU_0_HOV']]
    result['datasets'][0]['data'] = [dist[0], dist[1], dist[2]]
    
    result['datasets'][1]['label'] = "2 bitflips"
    result['datasets'][1]['borderWidth'] = 2
    result['datasets'][1]['borderColor'] = [THEME_COLORS['RED_1_BRD'], THEME_COLORS['MAG_1_BRD'],
                                            THEME_COLORS['BLU_1_BRD']]
    result['datasets'][1]['backgroundColor'] = [THEME_COLORS['RED_1_BG'], THEME_COLORS['MAG_1_BG'],
                                                THEME_COLORS['BLU_1_BG']]
    result['datasets'][1]['hoverBackgroundColor'] = [THEME_COLORS['RED_1_HOV'], THEME_COLORS['MAG_1_HOV'],
                                                     THEME_COLORS['BLU_1_HOV']]
    result['datasets'][1]['data'] = [dist[3], dist[4], dist[5]]
    
    result['datasets'][2]['label'] = "3 bitflips"
    result['datasets'][2]['borderWidth'] = 2
    result['datasets'][2]['borderColor'] = [THEME_COLORS['RED_2_BRD'], THEME_COLORS['MAG_2_BRD'],
                                            THEME_COLORS['BLU_2_BRD']]
    result['datasets'][2]['backgroundColor'] = [THEME_COLORS['RED_2_BG'], THEME_COLORS['MAG_2_BG'],
                                                THEME_COLORS['BLU_2_BG']]
    result['datasets'][2]['hoverBackgroundColor'] = [THEME_COLORS['RED_2_HOV'], THEME_COLORS['MAG_2_HOV'],
                                                     THEME_COLORS['BLU_2_HOV']]
    result['datasets'][2]['data'] = [dist[6], dist[7], dist[8]]
    
    result['datasets'][3]['label'] = "All errors (1-3 bit)"
    result['datasets'][3]['borderWidth'] = 2
    result['datasets'][3]['borderColor'] = [THEME_COLORS['RED_3_BRD'], THEME_COLORS['MAG_3_BRD'],
                                            THEME_COLORS['BLU_3_BRD']]
    result['datasets'][3]['backgroundColor'] = [THEME_COLORS['RED_3_BG'], THEME_COLORS['MAG_3_BG'],
                                                THEME_COLORS['BLU_3_BG']]
    result['datasets'][3]['hoverBackgroundColor'] = [THEME_COLORS['RED_3_HOV'], THEME_COLORS['MAG_3_HOV'],
                                                     THEME_COLORS['BLU_3_HOV']]
    result['datasets'][3]['data'] = [(dist[0]+dist[3]+dist[6]),
                                     (dist[1]+dist[4]+dist[7]),
                                     (dist[2]+dist[5]+dist[8])]
    
    return JsonResponse(result)


def chartdata(request, instruction_id, distance):
    i = get_object_or_404(Instruction, pk=instruction_id)

    # Number of faults with no effect (only dontcare is hit)
    dc_weight = i.mask
    for o in i.operands.all():
        dc_weight |= o.mask
    dc_weight = i.bits - bin(dc_weight).count('1')
    count_dontcare = comb(dc_weight, distance)

    # Number of faults that result in illegal opcode
    count_illegal = InstructionFault.objects.filter(source=i, distance=distance, target=None).count()
    
    # 3 Types of relevant tests
    # a) Opcode modified
    count_fault_wrongop = InstructionFault.objects.filter(source=i, 
                                                          distance=distance,
                                                          effect_gpr=False,
                                                          effect_fpr=False,
                                                          effect_csr=False,
                                                          effect_imm=False).filter(Q(effect_opcode="newop") |
                                                                                   Q(effect_opcode="cfchange")).count()
    # b) Parameter(s) modified
    count_fault_params = InstructionFault.objects.filter(source=i,
                                                         distance=distance,
                                                         effect_opcode="none").filter(Q(effect_gpr=True) |
                                                                                      Q(effect_fpr=True) |
                                                                                      Q(effect_csr=True) |
                                                                                      Q(effect_imm=True)).count()
    # c) Both
    count_fault_both = InstructionFault.objects.filter(source=i,
                                                       distance=distance).filter(Q(effect_opcode="newop") |
                                                                                 Q(effect_opcode="cfchange")).filter(
        Q(effect_gpr=True) | Q(effect_fpr=True) | Q(effect_csr=True) | Q(effect_imm=True)).count()
    
    result = dict()
    result['piedata'] = [count_dontcare, count_illegal, count_fault_wrongop, count_fault_params, count_fault_both]
    result['total'] = comb(i.bits, distance)
    
    return JsonResponse(result)

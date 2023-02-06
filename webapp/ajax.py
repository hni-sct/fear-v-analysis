from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import InstructionFault


def fault_effect(request, instruction_id, fault_mask):
    parameters = []
    if int(fault_mask) == 0:
        opcode = "Opcode is not affected."
        newinsn = ""
    else:
        f = get_object_or_404(InstructionFault, source__id=instruction_id, error_mask=fault_mask)
        opcode = "CPU will try to execute an undefined (illegal) instruction!"
        newinsn = ""
        if f.target is not None:
            # Opcode
            if f.target != f.source:
                opcode = "CPU will execute the wrong instruction: "
                newinsn = "<a href=\"" + reverse('interactive', args=(
                    f.target.id,)) + "\">" + f.target.name + "</a>"
            else:
                opcode = "Opcode is not affected."
                newinsn = ""
            # Parameters:
            for p in f.target.operands.all():
                if p.mask & int(fault_mask):
                    op = dict()
                    op['name'] = p.shortname
                    op['optype'] = p.optype
                    parameters.append(op)

    return render(request,
                  'ajax/faulteffect.html',
                  {
                      'opcode': opcode,
                      'newinsn': newinsn,
                      'parameters': parameters,
                  })

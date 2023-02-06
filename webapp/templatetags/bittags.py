from django import template
from ..models import InstructionFault
from math import comb
register = template.Library()


@register.filter
def sub(n, r):
    return n-r


@register.filter
def binom(n, r):
    return comb(n, r)


@register.filter    
def illegal_count_one(instruction):
    return InstructionFault.objects.filter(source=instruction, effect_opcode='illegal', distance=1).count()


@register.filter    
def illegal_count_two(instruction):
    return InstructionFault.objects.filter(source=instruction, effect_opcode='illegal', distance=2).count()


@register.filter    
def illegal_count_three(instruction):
    return InstructionFault.objects.filter(source=instruction, effect_opcode='illegal', distance=3).count()


@register.filter
def modulo(num, val):
    return num % val


@register.filter
def hex(num, bits):
    digits = int(bits) >> 2
    fmt = "0x%0" + str(digits) + "X"
    return fmt % num

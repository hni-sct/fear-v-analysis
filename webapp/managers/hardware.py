from lxml import etree
import os
from django.apps import apps
from django.db import models
from pathlib import Path
from app_main.settings import ISA_DIR


class DeviceManager(models.Manager):

    def create(self, xml=None, **obj_data):
        if xml is not None:
            obj_data['name'] = xml.get('Name')

        return super().create(**obj_data)


class DeviceCsrManager(models.Manager):

    def create(self, xml=None, **obj_data):
        if xml is not None:
            obj_data['name'] = xml.get('Name')
            obj_data['number'] = int(xml.get('Address'), 0)
            obj_data['bits'] = int(xml.get('Bits'), 10)
            obj_data['qemu_reference'] = xml.get('Qemu', '')
            obj_data['rtl_reference'] = xml.get('RTL', '')

        return super().create(**obj_data)


class MemoryRegionManager(models.Manager):

    def create(self, xml=None, **obj_data):
        if xml is not None:
            obj_data['name'] = xml.get('Name')
            obj_data['addr_from'] = int(xml.get('From'), 0)
            obj_data['addr_to'] = int(xml.get('To'), 0)
            obj_data['memtype'] = xml.get('Type', '__undef__')

        if 'arch' not in obj_data and 'device' in obj_data:
            obj_data['arch'] = obj_data['device'].arch

        return super().create(**obj_data)


class RegisterManager(models.Manager):

    def create(self, xml=None, **obj_data):
        if xml is not None:
            obj_data['name'] = xml.get('Name')
            obj_data['abiname'] = xml.get('AbiName', '')
            obj_data['description'] = xml.get('Description', '')
            obj_data['number'] = int(xml.get('Number'), 0)
            obj_data['qemu_reference'] = xml.get('Qemu', '')
            obj_data['rtl_reference'] = xml.get('RTL', '')

        return super().create(**obj_data)


def parse_file(a, p):
    if Path(p).is_file():
        doc = etree.fromstring(open(p).read())
        isa_subset_name = doc.attrib['Name']
        subs, created = a.subsets.get_or_create(name=isa_subset_name)
        for r in doc.xpath('/IsaSubset/Gpr'):
            subs.gprs.create(xml=r)

        for r in doc.xpath('/IsaSubset/Fpr'):
            subs.fprs.create(xml=r)

        for r in doc.xpath('/IsaSubset/Csr'):
            subs.csrs.create(xml=r, access=r.get('Access', 'RO'))

        for o in doc.xpath('/IsaSubset/Operand'):
            apps.get_app_config('webapp').get_model('Operand').objects.get_or_create(
                name=o.get('Name'),
                shortname=o.get('ShortName', o.get('Name')),
                mask=int(o.get('Mask'), 0),
                optype=o.get('Type', 'other'),
            )

        for i in doc.xpath('/IsaSubset/Instruction'):
            # 1) Parse Instruction
            i_name = i.get('Name')
            i_desc = i.get('Description', '')
            i_mask = int(i.get('Mask'), 0)
            i_opcode = int(i.get('Opcode'), 0)
            i_fmt = i.get('Format', '')
            i_kind = i.get('Kind', '')
            i_bits = 32
            if isa_subset_name == "C":
                i_bits = 16

            skip = False
            i_req_subset = i.get('RequiresSubset', '')
            if i_req_subset != "":
                subsets = set(a.subsets.values_list("name", flat=True).order_by().distinct())
                if i_req_subset not in subsets:
                    # print("   INFO:  exclude '{}' (requires subset '{}')".format(i_name, i_req_subset))
                    skip = True
            if skip:
                continue

            # 2) Add Instruction
            insn, created = subs.instructions.get_or_create(subset=subs, opcode=i_opcode, mask=i_mask,
                                                            kind=i_kind)
            insn.name = i_name
            insn.description = '' if i_desc is None else str(i_desc)
            insn.bits = i_bits
            insn.fmt = i_fmt
            insn.save()

            # 3) Operand references...
            i_operands = i.get('Operands', '')
            if i_operands != "":
                for r in i_operands.split(','):
                    opref = apps.get_app_config('webapp').get_model('Operand').objects.get(name=r)
                    insn.operands.add(opref)

        for d in doc.xpath('/IsaSubset/Device'):
            dev = a.devices.create(xml=d)

            for m in d.xpath('MemoryRegion'):
                dev.memory_regions.create(xml=m)

            for m in d.xpath('Csr'):
                dev.csrs.create(xml=m)

        for m in doc.xpath('/IsaSubset/MemoryRegion'):
            a.memory_regions.create(xml=m)

        for m in doc.xpath('/IsaSubset/Gpr2Rtl'):
            from webapp.models import Gpr
            gpr = Gpr.objects.get(subset__arch=a, number=int(m.get("Number"), 0))
            gpr.rtl_reference = m.get("RTL", "")
            gpr.save()

        for m in doc.xpath('/IsaSubset/Fpr2Rtl'):
            from webapp.models import Fpr
            fpr = Fpr.objects.get(subset__arch=a, number=int(m.get('Number'), 0))
            fpr.rtl_reference = m.get("RTL", "")
            fpr.save()

        for m in doc.xpath('/IsaSubset/Csr2Rtl'):
            from webapp.models import Csr
            csr = Csr.objects.get(subset__arch=a, number=int(m.get('Number'), 0))
            csr.rtl_reference = m.get("RTL", "")
            csr.mask = int(m.get("Mask", "0xFFFFFFFF"), 16)
            csr.save()
    else:
        print("CANNOT FIND FILE {}".format(p))
        exit(1)


class ArchitectureManager(models.Manager):

    def create(self, name, march, mabi, qemu_machine, qemu_cpu, qemu_testsetup, qemu_terminator,
               subsets, privileged, system,
               max_faults_gpr, max_faults_csr, max_faults_imem, max_faults_coremem, max_faults_ifr,
               extra_faults_from_cla):
        # TO DO: Checks

        # Create, Save, Return
        a = self.model(name=name, gcc_march=march, gcc_mabi=mabi,
                       qemu_machine=qemu_machine, qemu_cpu=qemu_cpu, qemu_testsetup=qemu_testsetup,
                       qemu_terminator=qemu_terminator, max_faults_gpr=max_faults_gpr,
                       max_faults_csr=max_faults_csr, max_faults_imem=max_faults_imem,
                       max_faults_coremem=max_faults_coremem, max_faults_ifr=max_faults_ifr,
                       extra_faults_from_cla=extra_faults_from_cla)
        a.save()

        # 1) Add unprivileged ISA subsets
        for s in subsets:
            parse_file(a, "{}/subsets/{}.xml".format(ISA_DIR, s))

        # 2) Add privilege-levels
        parse_file(a, "{}/privileged/M-mode.xml".format(ISA_DIR))
        for p in privileged:
            parse_file(a, "{}/privileged/{}.xml".format(ISA_DIR, p))

        # 3) Add peripherals and memories
        parse_file(a, "{}/{}.xml".format(ISA_DIR, system))

        return a

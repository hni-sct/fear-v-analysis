from django.db import models
from tools.GoldenRunParser import GoldenRunParser
from webapp.models.hardware import InstructionFault, exp_bit_faults


def do_bulk_insert(items):
    from webapp.models.mutation import Mutant
    if len(items) > 0:
        Mutant.objects.bulk_create(items, batch_size=2000, ignore_conflicts=True)
    items.clear()


class MutantListManager(models.Manager):
    def create(self, **kwargs):
        from webapp.models.mutation import Mutant
        instance = super().create(**kwargs)

        # Generate Mutants:
        dp = GoldenRunParser(instance.software.arch, instance.software.lst.path)
        pk = instance.pk

        items = []
        skipped = 0

        # 1) GPR
        if instance.with_gpr:
            all_gpr = {
                cov[0]: (cov[1], cov[2], cov[3]) for cov in instance.software.gprcoverage.all()
                .order_by('register__number').values_list('register__number', 'r', 'w', 'x')
            }
            experiments_gpr = instance.software.arch.gpr_faults()

            # 1a) PERMANENT GPR faults
            for pGpr in sorted(all_gpr):
                if all_gpr[pGpr][2] > 0:
                    # Create faults for experiment set...
                    for e in experiments_gpr[pGpr]:
                        if instance.with_flip_faults:
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.GPR_PERMANENT_FLIP, nr_or_address=pGpr,
                                                bitflip=e))
                        if instance.with_stuckat_faults:
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.GPR_PERMANENT_SA_0, nr_or_address=pGpr,
                                                bitflip=e))
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.GPR_PERMANENT_SA_1, nr_or_address=pGpr,
                                                bitflip=e))
                do_bulk_insert(items)

            # 1a) TRANSIENT GPR faults
            if instance.with_transient_faults:
                for idx in sorted(all_gpr):
                    if all_gpr[idx][2] > 0:
                        # Create faults for experiment set...
                        for c in range(1, all_gpr[idx][2] + 1):
                            for e in experiments_gpr[idx]:
                                # if (idx, c) in dp.filter_gprs:
                                #     base = dp.filter_gprs[(idx, c)][0]
                                #     offset = dp.filter_gprs[(idx, c)][1]
                                #     faulty_address = (base ^ c) + offset
                                #     if faulty_address < dp.min or faulty_address > dp.max:
                                #         skipped += 1
                                #         continue
                                items.append(Mutant(parent_id=pk, kind=Mutant.Kind.GPR_TRANSIENT_FLIP, access_idx=c,
                                                    nr_or_address=idx, bitflip=e))
                        do_bulk_insert(items)

        # 2) CSR
        if instance.with_csr:
            all_csr = {
                cov[0]: (cov[1], cov[2], cov[3]) for cov in instance.software.csrcoverage.all()
                .order_by('register__number').values_list('register__number', 'r', 'w', 'x')
            }
            experiments_csr = instance.software.arch.csr_faults()

            # 2a) PERMANENT CSR faults
            for csrno in sorted(all_csr):
                if csrno not in experiments_csr:
                    print("WARNING: Unkown CSR access (Number: {})".format(csrno))
                    continue
                if all_csr[csrno][2] > 0:
                    # Create faults for experiment set...
                    for e in experiments_csr[csrno]:
                        if instance.with_flip_faults:
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.CSR_PERMANENT_FLIP, nr_or_address=csrno,
                                                bitflip=e))
                        if instance.with_stuckat_faults:
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.CSR_PERMANENT_SA_0, nr_or_address=csrno,
                                                bitflip=e))
                            items.append(Mutant(parent_id=pk, kind=Mutant.Kind.CSR_PERMANENT_SA_1, nr_or_address=csrno,
                                                bitflip=e))
                do_bulk_insert(items)

            # 2b) TRANSIENT CSR faults
            if instance.with_transient_faults:
                for csr in sorted(all_csr):
                    if csr not in experiments_csr:
                        print("WARNING: Unknown CSR access (Number: {})!".format(csr))
                        continue
                    if all_csr[csr][2] > 0:
                        # Create faults for experiment set...
                        for c in range(1, all_csr[csr][2] + 1):
                            for e in experiments_csr[csr]:
                                items.append(Mutant(parent_id=pk, kind=Mutant.Kind.CSR_TRANSIENT_FLIP, access_idx=c,
                                                    nr_or_address=csr, bitflip=e))
                        do_bulk_insert(items)

        if instance.with_imem:
            experiments_imem = instance.software.arch.instruction_faults()
            # Prefetch mapping: (instr_id, experiment) -> ifault_id
            ifaults = dict()
            for i, e, f in InstructionFault.objects.values_list('source_id', 'error_mask', 'id').iterator():
                ifaults[i, e] = f
            for (a, i) in dp.get_instruction_faults():
                for e in experiments_imem[i.pk]:
                    # ifault_pk = InstructionFault.objects.get(source_id=i.pk, error_mask=e).pk
                    ifault_pk = ifaults[i.pk, e]
                    if instance.with_flip_faults:
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.IMEM_PERMANENT_FLIP, nr_or_address=a, bitflip=e,
                                   ifault_id=ifault_pk))
                    if instance.with_stuckat_faults:
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.IMEM_PERMANENT_SA_0, nr_or_address=a, bitflip=e,
                                   ifault_id=ifault_pk))
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.IMEM_PERMANENT_SA_1, nr_or_address=a, bitflip=e,
                                   ifault_id=ifault_pk))
                do_bulk_insert(items)

        if instance.with_ifr:
            for e in exp_bit_faults(32, instance.software.arch.max_faults_ifr):
                if instance.with_flip_faults:
                    items.append(Mutant(parent_id=pk, kind=Mutant.Kind.IFR_PERMANENT_FLIP, nr_or_address=0, bitflip=e))
                if instance.with_stuckat_faults:
                    items.append(Mutant(parent_id=pk, kind=Mutant.Kind.IFR_PERMANENT_SA_0, nr_or_address=0, bitflip=e))
                    items.append(Mutant(parent_id=pk, kind=Mutant.Kind.IFR_PERMANENT_SA_1, nr_or_address=0, bitflip=e))
            do_bulk_insert(items)

        if instance.with_coremem:
            # Get all memory locations involved in loads/stores
            coremem = set()
            m8, m16, m32 = dp.get_all_mem_accesses()
            for loc, a in m32.items():
                coremem |= set(range(loc, loc + 4))
            for loc, a in m16.items():
                coremem |= set(range(loc, loc + 2))
            for loc, a in m8.items():
                coremem.add(loc)
            for loc in coremem:
                for e in exp_bit_faults(8, instance.software.arch.max_faults_coremem):
                    if instance.with_flip_faults:
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.COREMEM_PERMANENT_FLIP, nr_or_address=loc, bitflip=e))
                    if instance.with_stuckat_faults:
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.COREMEM_PERMANENT_SA_0, nr_or_address=loc, bitflip=e))
                        items.append(
                            Mutant(parent_id=pk, kind=Mutant.Kind.COREMEM_PERMANENT_SA_1, nr_or_address=loc, bitflip=e))
            do_bulk_insert(items)

        instance.skipped = skipped

        instance.save()
        return instance


class MutantQuerySet(models.QuerySet):
    def notkilled(self):
        return self.filter(detected_error="not killed")

    def timeout(self):
        return self.filter(detected_error="timeout")

    def killed(self):
        return self.exclude(models.Q(detected_error="not killed") | models.Q(detected_error="timeout"))


class MutantManager(models.Manager):
    def get_queryset(self):
        return MutantQuerySet(self.model, using=self._db)

    def notkilled(self):
        return self.get_queryset().notkilled()

    def timeout(self):
        return self.get_queryset().timeout()

    def killed(self):
        return self.get_queryset().killed()

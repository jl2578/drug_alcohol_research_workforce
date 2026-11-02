"""Behavioral, matrix, domain and fixture checks. No external packages."""
import copy, json, unittest, tempfile, shutil
from pathlib import Path
from unittest.mock import patch
import scorer
import instrument

class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets=scorer.load_assets()
        cls.domains={s:scorer.domain(s) for s in scorer.SPECS}

    def test_original_declaration_is_two_specs(self):
        self.assertEqual(instrument.specification_ids(self.assets[2]),['conservative','inclusive'])
        self.assertEqual(len(scorer.SPECS),3)

    def test_full_domain_benchmarks(self):
        expected=json.loads((scorer.ROOT/'expected_domain_fingerprints.json').read_text())
        for spec,rows in self.domains.items():
            self.assertEqual(len(rows),20604)
            self.assertEqual(len({r['pair_id'] for r in rows}),20604)
            self.assertEqual(scorer.fingerprint(rows),expected['score_fingerprints'][spec])

    def test_all_60_matrix_cells(self):
        table=self.assets[3]
        self.assertEqual(len(table),60)
        for axis in ('research','clinical'):
            prefix='R' if axis=='research' else 'C'
            for context in ('0','1','2','3','U'):
                self.assertEqual(instrument.score(table,axis,'U',prefix+context)[0],'U')
                self.assertEqual(instrument.score(table,axis,'0',prefix+context)[0],'0')
            for base in ('0','1','2','3','4'):
                self.assertEqual(instrument.score(table,axis,base,prefix+'1')[0],base)
                self.assertEqual(instrument.score(table,axis,base,prefix+'U')[0],base)
        with self.assertRaises(instrument.RuleTableError):instrument.score(table,'research','5','R1')

    def test_threshold_and_unknown(self):
        self.assertFalse(instrument.is_likely('2'))
        self.assertTrue(instrument.is_likely('3'))
        self.assertEqual(instrument.joint_class('2','2'),'neither')
        self.assertEqual(instrument.joint_class('3','2'),'research_likely_only')
        self.assertEqual(instrument.joint_class('2','3'),'clinical_likely_only')
        self.assertEqual(instrument.joint_class('3','3'),'both')
        for other in scorer.SCORES:self.assertEqual(instrument.joint_class('U',other),'unclassifiable')

    def test_all_25_clinical_gate_combinations(self):
        for directness in instrument.DIRECTNESS_VALUES:
            for context in ('C0','C1','C2','C3','CU'):
                eff,applied=instrument.apply_corroboration_gate(context,directness)
                expected=context in ('C2','C3') and directness in instrument.NON_CORROBORATING_DIRECTNESS
                self.assertEqual(eff,'C1' if expected else context)
                self.assertEqual(applied,'yes' if expected else 'no')
        with self.assertRaises(instrument.ClinicalRecordError):instrument.apply_corroboration_gate('C3','invented')

    def test_hand_specified_pairs(self):
        occupation={'soc_code_canonical':'synthetic','official_soc_title':'Synthetic role','research_base_recorded':'2','research_base_effective':'2','clinical_base_recorded':'2','directness_recorded':'direct_care','component_path':''}
        industry={'naics_code_canonical':'synthetic','official_naics_title':'Synthetic establishment','research_context_recorded':'R3','research_context_effective':'R3','clinical_context_recorded':'C3','component_path':''}
        direct=instrument.resolve_pair(self.assets[3],occupation,industry,'inclusive','test')
        self.assertEqual((direct['research_final_score'],direct['clinical_final_score'],direct['joint_class']),('3','3','both'))
        occupation.update(clinical_base_recorded='1',directness_recorded=instrument.NO_CARE)
        no_care=instrument.resolve_pair(self.assets[3],occupation,industry,'inclusive','test')
        self.assertEqual((no_care['research_final_score'],no_care['clinical_final_score'],no_care['joint_class']),('3','1','research_likely_only'))
        occupation.update(research_base_effective='U',clinical_base_recorded='2',directness_recorded='direct_care')
        unknown=instrument.resolve_pair(self.assets[3],occupation,industry,'inclusive','test')
        self.assertEqual((unknown['research_final_score'],unknown['clinical_final_score'],unknown['joint_class']),('U','3','unclassifiable'))

    def test_missing_duplicate_and_incomplete_assets_fail(self):
        original=scorer.ROOT
        with tempfile.TemporaryDirectory(dir=original.parent,prefix='scorer-test-') as temp:
            root=Path(temp).resolve()
            self.assertTrue(root.is_relative_to(original.parent.resolve()))
            shutil.copytree(original/'data',root/'data')
            matrix=root/'data/combination_rules.csv'
            saved=matrix.read_bytes();lines=matrix.read_text(encoding='utf-8').splitlines(keepends=True)
            with patch.object(scorer,'ROOT',root):
                matrix.write_text(''.join(lines+lines[1:2]),encoding='utf-8')
                with self.assertRaises(instrument.RuleTableError):scorer.load_assets()
                matrix.write_text(''.join(lines[:-1]),encoding='utf-8')
                with self.assertRaises(ValueError):scorer.load_assets()
                matrix.write_bytes(saved)
                occupations=root/'data/occupation_decisions.csv';parts=occupations.read_text(encoding='utf-8').splitlines(keepends=True)
                occupations.write_text(''.join(parts+parts[1:2]),encoding='utf-8')
                with self.assertRaises(ValueError):scorer.load_assets()
                occupations.unlink()
                with self.assertRaises(FileNotFoundError):scorer.load_assets()

    def test_no_care_constraints_fail_instead_of_clipping(self):
        row={'soc_code_canonical':'synthetic','directness_final':instrument.NO_CARE,'clinical_final':'2'}
        with self.assertRaises(instrument.ClinicalRecordError):instrument.assert_no_care_base_ceiling([row])
        row={'soc_code_canonical':'synthetic','naics_code_canonical':'synthetic','clinical_directness':instrument.NO_CARE,'clinical_final_score':'2'}
        with self.assertRaises(instrument.ClinicalRecordError):instrument.assert_no_care_final_ceiling([row])
        for rows in self.domains.values():self.assertTrue(instrument.assert_no_care_final_ceiling(rows))

    def test_intermediate_changes_only_hospital_research(self):
        a={r['pair_id']:r for r in self.domains['inclusive']}
        changed=0
        for spec in scorer.SPECS[1:]:
            for r in self.domains[spec]:
                self.assertEqual(r['clinical_final_score'],a[r['pair_id']]['clinical_final_score'])
                if spec=='no_hospital_override' and r['research_final_score']!=a[r['pair_id']]['research_final_score']:
                    changed+=1;self.assertIn(r['naics_code_canonical'],('622110','622210','622310'))
        self.assertGreater(changed,0)

    def test_operations_order_and_no_double_resolution(self):
        originals=copy.deepcopy(self.assets[:3])
        rows={r['pair_id']:r for r in self.domains['inclusive']}
        math=rows['25-1022.00|611310'];nursing=rows['25-1072.00|611310']
        self.assertEqual(math['research_base_effective'],'3')
        self.assertEqual(nursing['research_base_effective'],'3')
        self.assertTrue(math['research_component_path'].startswith('mathematics_faculty_erratum'))
        self.assertTrue(nursing['research_component_path'].startswith('nursing_faculty_research_base'))
        self.assertEqual(scorer.load_assets()[:3],originals)
        # Each build restarts from recorded inputs; a second call has identical values.
        self.assertEqual(scorer.fingerprint(scorer.domain('inclusive')),scorer.fingerprint(self.domains['inclusive']))

    def test_synthetic_input_missing_unmapped_and_crosswalk(self):
        fixture=scorer.read(scorer.ROOT/'fixtures/synthetic_pairs.csv')
        for spec in scorer.SPECS:
            result=scorer.score_rows(fixture,spec)
            self.assertEqual([r['application_status'] for r in result],['scored_pair','scored_pair','missing_pair_applicability_unresolved','missing_pair_applicability_unresolved','unmapped_pair'])
            self.assertEqual(result[1]['mapping_status'],'unique_frozen_crosswalk_source_to_unit')
            for r in result[2:]:
                self.assertEqual([r[f] for f in ('research_final_score','clinical_final_score','joint_class')],['','',''])
        with self.assertRaises(ValueError):scorer.score_rows([{'soc_code':'','naics_code':'','research_final':'3'}],'inclusive')
        with self.assertRaises(ValueError):scorer.domain('unrecognized')

if __name__=='__main__':unittest.main(verbosity=2)

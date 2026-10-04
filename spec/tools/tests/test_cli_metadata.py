"""CLI descriptor checks. These tests do not run a DiskEd argv parser."""
import copy
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
from test_corrective import TemporaryCorrectiveFixture

class CliMetadataTests(TemporaryCorrectiveFixture):
    def catalog(self):return sc.read_json(self.root/'catalog/commands.json')
    def save(self,value):sc.write_json(self.root/'catalog/commands.json',value)
    def bind(self,command,option='--sample',arity=1,repeatable=False,shape=None):
        reference='urn:disked:schema:fixture-'+command['id']+':1'
        self.bundle.schemas[reference]={'type':'object','properties':{'sample':shape or {'type':'string'}}}
        command.update(syntax_status='defined',parameter_schema=reference,argument_bindings=[{
            'parameter':'sample','option':option,'option_aliases':[],'value_arity':arity,
            'repeatable':repeatable,'completion':'none'}])

    def test_natural_forms_keep_exact_command_scope(self):
        commands=self.bundle.command_registry()
        aliases={a:c['id'] for c in commands for a in c['aliases']}
        self.assertEqual({'target.list'},{aliases[a] for a in ['list','ls','list targets']})
        self.assertEqual('target.inspect',aliases['show']);self.assertEqual('command.list',aliases['commands'])
        self.assertNotIn('disks',aliases);self.assertNotIn('tgt ls',aliases)
        reference=self.bundle.generated_files()['generated/command-reference.txt']
        self.assertIn('`list targets`',reference);self.assertIn('`--json`, `-j`',reference)

    def test_option_metadata_requires_explicit_arity_and_repeatability(self):
        catalog=self.catalog();command=catalog['commands'][0];self.bind(command)
        self.save(catalog);self.bundle.command_registry()
        original=copy.deepcopy(command['argument_bindings'][0])
        for key in ['value_arity','repeatable','option_aliases']:
            command['argument_bindings'][0]=dict(original);del command['argument_bindings'][0][key]
            self.save(catalog)
            with self.subTest(key=key),self.assertRaises(sc.SpecError):self.bundle.command_registry()

    def test_global_aliases_are_unique_and_cannot_be_shadowed(self):
        path=self.root/'catalog/cli-syntax.json';syntax=sc.read_json(path);original=copy.deepcopy(syntax)
        next(o for o in syntax['global_options'] if o['id']=='gui')['spellings'].append('-j')
        sc.write_json(path,syntax)
        with self.assertRaisesRegex(sc.SpecError,'Duplicate global option'):self.bundle.cli_syntax()
        sc.write_json(path,original)
        for word in ['--format','--json','--help','--force']:
            catalog=self.catalog();self.bind(catalog['commands'][0],word);self.save(catalog)
            with self.subTest(word=word),self.assertRaisesRegex(sc.SpecError,'reserved global option'):
                self.bundle.command_registry()

    def test_short_option_shadow_is_rejected(self):
        catalog=self.catalog();self.bind(catalog['commands'][0])
        catalog['commands'][0]['argument_bindings'][0]['option_aliases']=['-j']
        self.save(catalog)
        with self.assertRaisesRegex(sc.SpecError,'reserved global option'):self.bundle.command_registry()

    def test_command_option_arity_cannot_change_with_command(self):
        catalog=self.catalog();self.bind(catalog['commands'][0]);self.bind(catalog['commands'][1],arity=0,shape={'type':'boolean'})
        self.save(catalog)
        with self.assertRaisesRegex(sc.SpecError,'Inconsistent option arity'):self.bundle.command_registry()

    def test_zero_arity_and_repeatability_require_matching_parameter_shapes(self):
        for kwargs,error in [({'arity':0},'boolean parameter'),({'repeatable':True},'array parameter')]:
            catalog=self.catalog();self.bind(catalog['commands'][0],**kwargs);self.save(catalog)
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(sc.SpecError,error):self.bundle.command_registry()
        catalog=self.catalog();self.bind(catalog['commands'][0],repeatable=True,shape={'type':'array','items':{'type':'string','enum':['a','b']}})
        catalog['commands'][0]['argument_bindings'][0]['completion']='schema-enum';self.save(catalog)
        self.bundle.command_registry()

    def test_new_prefix_cannot_steal_an_existing_commands_operands(self):
        catalog=self.catalog();next(c for c in catalog['commands'] if c['id']=='image.inspect')['aliases'].append('show image')
        self.save(catalog)
        with self.assertRaisesRegex(sc.SpecError,'reinterpret operands'):self.bundle.command_registry()

    def test_retired_and_meta_entry_spellings_cannot_be_reassigned(self):
        original=self.catalog()
        for alias,error in [('tgt ls','Retired command'),('help','Reserved command entry')]:
            catalog=copy.deepcopy(original);catalog['commands'][0]['aliases'].append(alias);self.save(catalog)
            with self.subTest(alias=alias),self.assertRaisesRegex(sc.SpecError,error):self.bundle.command_registry()

    def test_syntax_expectations_have_references_and_cannot_claim_execution(self):
        result=self.bundle.command_syntax_cases();self.assertEqual('not_run',result['native_execution'])
        path=self.root/'fixtures/command-syntax.json';value=sc.read_json(path);original=copy.deepcopy(value)
        value['groups'][0]['expected']['command_id']='nonexistent.command';sc.write_json(path,value)
        with self.assertRaisesRegex(sc.SpecError,'Unknown expected command'):self.bundle.command_syntax_cases()
        original['native_execution']='passed';sc.write_json(path,original)
        with self.assertRaises(sc.SpecError):self.bundle.command_syntax_cases()

    def test_context_binds_both_global_metadata_and_expected_parser_cases(self):
        self.pack_context()
        manifest=sc.read_json(self.pack/'manifest.json');paths={row['path'] for row in manifest['files']}
        for name in ['spec/catalog/cli-syntax.json','spec/fixtures/command-syntax.json']:
            self.assertIn(name,paths)
            source=self.bundle.input_path(name);data=source.read_bytes();source.write_bytes(data+b'\n')
            with self.subTest(name=name),self.assertRaisesRegex(sc.SpecError,'Context source changed'):
                self.bundle.verify_context(self.pack)
            source.write_bytes(data)
        self.assertEqual('PASS',self.bundle.verify_context(self.pack)['status'])

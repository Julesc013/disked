import copy
import unittest
from windows_ui_observations import COLUMNS, ROOT_PARENT, complete_observations, project_ui

def fixture():
    def prop(value):return dict(hresult=0,value=value)
    nodes=[]
    def node(parent,name,cls=''):
        index=len(nodes);nodes.append(dict(index=index,parent=parent,depth=0 if parent==ROOT_PARENT else nodes[parent]['depth']+1,
            name=prop(name),**{'class':prop(cls)}));return index
    root=node(ROOT_PARENT,'Disk Management','MMCMainFrame');table=node(root,'','SysListView32');header=node(table,'','SysHeader32')
    for label in COLUMNS:node(header,label)
    row=node(table,'(Disk 2 partition 1)')
    for value in ['(Disk 2 partition 1)','Simple','Basic','RAW','Healthy (Primary Partition)','1 MB','1 MB','100 %']:node(row,value)
    binding=dict(display_locator='Disk 2',actor_sid='owned',desktop='private',observer_pid=10,mmc_pid=11,nonce='nonce')
    value=dict(identity=dict(sid='owned',administrator=True,restricted=False,appcontainer=False,session=3,station='WinSta0',desktop='private',pid=10),uia_hresult=0,
        capture=dict(mmc_pid=11,nonce='nonce',target_label='Disk 2',target_label_seen=True,truncated=False,stable_snapshots=2,
            frames=[dict(hwnd=12,**{'class':'MMCMainFrame'},hresult=0)],nodes=nodes,
            attempts=[dict(stable_snapshots=1,target_seen=True,nodes=len(nodes)),dict(stable_snapshots=2,target_seen=True,nodes=len(nodes))]))
    return value,binding

class UiObservationTests(unittest.TestCase):
    def test_display_capacity_is_not_converted_to_bytes_or_health(self):
        value,binding=fixture();result=project_ui(value,binding)
        self.assertEqual(result['rows'][0]['Capacity'],'1 MB');self.assertIsNone(result['byte_extents'])
        self.assertIsNone(result['filesystem_integrity']);self.assertIsNone(result['gpt_winner'])

    def test_wrong_process_nonce_or_actor_refused(self):
        value,binding=fixture()
        for section,key,replacement in [('capture','mmc_pid',99),('capture','nonce','other'),('identity','sid','foreign'),('identity','pid',99)]:
            with self.subTest(key=key):
                bad=copy.deepcopy(value);bad[section][key]=replacement
                with self.assertRaises(ValueError):project_ui(bad,binding)

    def test_target_flag_alone_cannot_supply_missing_ui_data(self):
        value,binding=fixture();binding['display_locator']='Disk 9';value['capture']['target_label']='Disk 9'
        with self.assertRaisesRegex(ValueError,'target_data_missing'):project_ui(value,binding)

    def test_broken_tree_and_truncated_capture_refused(self):
        value,binding=fixture();bad=copy.deepcopy(value);bad['capture']['nodes'][-1]['parent']=999
        with self.assertRaisesRegex(ValueError,'ui_parent'):project_ui(bad,binding)
        value['capture']['truncated']=True
        with self.assertRaisesRegex(ValueError,'ui_readiness'):project_ui(value,binding)

    def test_missing_cell_is_not_an_empty_display_value(self):
        value,binding=fixture();value['capture']['nodes'][-1]['name']['hresult']=0x80004005
        with self.assertRaisesRegex(ValueError,'ui_cells'):project_ui(value,binding)

    def test_reference_can_display_a_different_partition_count(self):
        value,binding=fixture();result=project_ui(value,binding)
        self.assertEqual(len(result['rows']),1)  # Collection completeness is not fixture agreement.

    def test_boolean_is_not_a_numeric_success_hresult(self):
        value,binding=fixture();value['uia_hresult']=False
        with self.assertRaisesRegex(ValueError,'ui_role'):project_ui(value,binding)

    def test_complete_set_refuses_missing_duplicate_and_wrong_kind(self):
        expected=[dict(name='a',participant='disk-management',kind='ui-layout')]
        self.assertTrue(complete_observations(expected,expected))
        for actual in [[],expected+expected,[dict(expected[0],kind='partition-presentation')]]:
            with self.subTest(actual=actual):
                with self.assertRaises(ValueError):complete_observations(expected,actual)

    def test_empty_manifest_is_not_a_complete_campaign(self):
        with self.assertRaisesRegex(ValueError,'empty_expected_set'):complete_observations([],[])

if __name__=='__main__':unittest.main()

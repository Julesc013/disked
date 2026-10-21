"""Pure validation/projection of the pinned English Disk Management UI surface.

Display strings remain display strings. This never derives byte extents, free
bytes, filesystem health or a GPT winner from rounded or descriptive UI text.
"""
import re

ROOT_PARENT=18446744073709551615
COLUMNS=('Volume','Layout','Type','File System','Status','Capacity','Free Space','% Free')

def require(value,reason):
    if not value:raise ValueError(reason)

def text(node,field='name'):
    value=node.get(field)
    if not isinstance(value,dict) or type(value.get('hresult')) is not int or value['hresult']!=0:return None
    data=value.get('value');require(type(data) is str and len(data.encode('utf-8'))<=16384,'ui_text')
    return data

def project_ui(raw,binding):
    identity=raw['identity'];view=raw['capture'];label=binding['display_locator']
    require(re.fullmatch(r'Disk [0-9]+',label),'ui_locator')
    require(type(raw['uia_hresult']) is int and raw['uia_hresult']==0 and identity['sid']==binding['actor_sid'] and identity['administrator'] is True and
            identity['restricted'] is False and identity['appcontainer'] is False,'ui_role')
    require(identity['session']==3 and identity['station']=='WinSta0' and identity['desktop']==binding['desktop'] and
            identity['pid']==binding['observer_pid'],'ui_observer_identity')
    require(view['mmc_pid']==binding['mmc_pid'] and view['nonce']==binding['nonce'] and view['target_label']==label,'ui_binding')
    require(view['target_label_seen'] is True and view['truncated'] is False and type(view['stable_snapshots']) is int and view['stable_snapshots']>=2,'ui_readiness')
    frames=view['frames'];require(0<len(frames)<16 and all(type(f['hwnd']) is int and 0<f['hwnd']<=ROOT_PARENT for f in frames) and len({f['hwnd'] for f in frames})==len(frames),'ui_frames')
    require(sum(f.get('class')=='MMCMainFrame' and type(f.get('hresult')) is int and f['hresult']==0 for f in frames)==1,'ui_mmc_frame')
    nodes=view['nodes'];require(0<len(nodes)<=2048,'ui_node_bound');children={}
    for index,node in enumerate(nodes):
        require(type(node['index']) is int and node['index']==index and type(node['depth']) is int and 0<=node['depth']<=20,'ui_node_index')
        parent=node['parent']
        require(type(parent) is int and (parent==ROOT_PARENT and node['depth']==0 or
                0<=parent<index and node['depth']==nodes[parent]['depth']+1),'ui_parent')
        children.setdefault(parent,[]).append(index)
    roots=[n['index'] for n in nodes if n['parent']==ROOT_PARENT and text(n,'class')=='MMCMainFrame']
    require(len(roots)==1 and text(nodes[roots[0]])=='Disk Management','ui_mmc_root')
    def in_main(index):
        while nodes[index]['parent']!=ROOT_PARENT:index=nodes[index]['parent']
        return index==roots[0]
    number=int(label[5:]);rows=[];nameplate=None;regions=[]
    for index,node in enumerate(nodes):
        if not in_main(index):continue
        name=text(node)
        if name==label:nameplate=text(node,'legacy_value')
        if name and re.fullmatch(re.escape(label)+r', Region +[0-9]+',name):
            regions.append(dict(name=name,value=text(node,'legacy_value')))
        match=re.fullmatch(r'\(Disk ([0-9]+) partition ([0-9]+)\)',name or '')
        if not match or int(match[1])!=number or not children.get(index):continue
        parent=node['parent'];require(text(nodes[parent],'class')=='SysListView32','ui_volume_container')
        headers=[child for child in children.get(parent,[]) if text(nodes[child],'class')=='SysHeader32']
        require(len(headers)==1,'ui_header')
        labels=[(text(nodes[child]) or '').strip() for child in children.get(headers[0],[])]
        require(tuple(labels)==COLUMNS,'ui_columns')
        values=[text(nodes[child]) for child in children[index]]
        require(len(values)==len(COLUMNS) and all(value is not None for value in values) and values[0]==name,'ui_cells')
        row=dict(zip(COLUMNS,values));row['partition_number']=int(match[2]);row['uia_offscreen']=node.get('offscreen');rows.append(row)
    require(len({r['partition_number'] for r in rows})==len(rows),'ui_duplicate_partition')
    require(rows or nameplate,'ui_target_data_missing')
    attempts=view['attempts'];require(2<=len(attempts)<=40,'ui_attempts')
    require(attempts[-1]['stable_snapshots']==view['stable_snapshots'] and attempts[-1]['target_seen'] is True and
            attempts[-1]['nodes']==len(nodes),'ui_attempt_binding')
    return dict(surface='Disk Management UI Automation volume list/graphical accessibility',display_locator=label,
        rows=rows,graphical_nameplate=nameplate,graphical_regions=regions,
        byte_extents=None,filesystem_integrity=None,gpt_winner=None,pixels_captured=False,
        interpretation='Rounded capacities,free-space and Healthy labels are presentation observations,not byte geometry or storage verification.')

def complete_observations(expected,actual):
    def key(row):return (row['name'],row['participant'],row['kind'])
    wanted=[key(v) for v in expected];observed=[key(v) for v in actual]
    require(wanted,'empty_expected_set')
    require(len(set(wanted))==len(wanted),'duplicate_expected_observation')
    require(len(set(observed))==len(observed),'duplicate_observation')
    require(set(observed)==set(wanted),'missing_or_unexpected_observation')
    return True

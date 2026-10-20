"""Private bounded control framing and independent full-RGB comparison."""
import json
import re
import struct

METHOD='owned-ui-thread-cooperative-client-control/1'
TREE_METHOD='owned-ui-thread-cooperative-client-tree/1'
TREE_NEGATIVES=('foreign_child_thread','child_count_limit','child_geometry_during_capture','child_visibility_during_capture')
NEGATIVES=('wrong_process','wrong_thread','wrong_nonce','wrong_desktop','wrong_image',
           'wrong_job','wrong_geometry','wrong_window','foreign_thread',
           'epoch_during_capture','geometry_during_capture')


def require(value,reason):
    if not value:raise ValueError(reason)


def parse_frame(body,*,process_id,nonce,actor_sid,tree=False):
    require(type(body) is bytes and 4<=len(body)<=262144,'frame_bound')
    size=struct.unpack_from('<I',body)[0]
    require(0<size<=16384 and len(body)==4+size+184320,'frame_length')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'duplicate_field');result[key]=value
        return result
    def invalid(value):raise ValueError('nonfinite_json')
    header=json.loads(body[4:4+size],object_pairs_hook=unique,parse_constant=invalid)
    keys={'schema','method','pid','thread','window','nonce','identity','negative_controls','phases',
          'mutating_open_refusals','job_access_refusals','display_dc_read','desktop_switched'}
    if tree:keys|={'tree_controls','descendants'}
    require(type(tree) is bool and isinstance(header,dict) and set(header)==keys,'header_shape')
    require(header['schema']==('org.disked.cooperative-tree-control/1' if tree else 'org.disked.cooperative-capture-control/1') and
            header['method']==(TREE_METHOD if tree else METHOD),'method')
    if tree:
        require(header['descendants']=='2' and isinstance(header['tree_controls'],list) and len(header['tree_controls'])==4,'tree_set')
        for i,(row,name) in enumerate(zip(header['tree_controls'],TREE_NEGATIVES)):
            require(row==dict(name=name,refused=True,render_called=i>=2) and
                    type(row.get('refused')) is bool and type(row.get('render_called')) is bool,'tree_result')
    require(type(process_id) is int and process_id>0 and type(nonce) is int and nonce>0 and
            header['pid']==str(process_id) and header['nonce']==str(nonce),'process_nonce')
    require(all(isinstance(header[k],str) and re.fullmatch(r'[1-9][0-9]{0,19}',header[k]) for k in ('thread','window')),'window_thread')
    require(header['identity']==dict(sid=actor_sid,integrity_sid='S-1-16-8192',restricted=True,elevated=False,appcontainer=False) and
            type(header['identity'].get('restricted')) is bool and all(type(header['identity'].get(k)) is bool for k in ('elevated','appcontainer')),'token_identity')
    require(header['display_dc_read'] is False and header['desktop_switched'] is False,'surface_scope')
    negatives=header['negative_controls']
    require(isinstance(negatives,list) and len(negatives)==11,'negative_set')
    for i,(row,name) in enumerate(zip(negatives,NEGATIVES)):
        require(row==dict(name=name,refused=True,render_called=i>=9) and
                type(row.get('refused')) is bool and type(row.get('render_called')) is bool,'negative_result')
    phases=header['phases'];require(isinstance(phases,list) and len(phases)==2,'phase_set')
    for i,row in enumerate(phases):
        require(isinstance(row,dict) and set(row)=={'phase','width','height','bytes','gdi_before','gdi_after'} and
            (row['phase'],row['width'],row['height'],row['bytes'])==(str(i),'240','96','92160') and
            isinstance(row['gdi_before'],str) and re.fullmatch(r'0|[1-9][0-9]{0,9}',row['gdi_before']) and
            row['gdi_before']==row['gdi_after'],'phase_binding')
    mutation=header['mutating_open_refusals']
    require(isinstance(mutation,list) and len(mutation)==2,'image_open_refusal')
    for row,access in zip(mutation,(0x40000000,0x10000)):
        require(isinstance(row,dict) and set(row)=={'access','error'} and
                row['access']==str(access) and row['error'] in ('5','32'),'image_open_refusal')
    require(header['job_access_refusals']==[dict(access=str(v),error='5') for v in (1,2,8)],'job_access_refusal')
    return header,[body[4+size:4+size+92160],body[4+size+92160:]]


def verify_pixels(payloads,expected):
    require(isinstance(payloads,list) and len(payloads)==2 and isinstance(expected,list) and len(expected)==2,'pixel_set')
    require(all(type(v) is bytes and len(v)==69120 for v in expected) and expected[0]!=expected[1],'independent_expectations')
    result=[]
    for body,wanted in zip(payloads,expected):
        require(type(body) is bytes and len(body)==92160,'pixel_length')
        rgb=bytearray(69120);rgb[0::3]=body[2::4];rgb[1::3]=body[1::4];rgb[2::3]=body[0::4]
        require(bytes(rgb)==wanted,'pixel_origin');result.append(bytes(rgb))
    return result

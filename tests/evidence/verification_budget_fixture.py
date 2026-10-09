"""Valid synthetic private review whose parameters fit but envelope does not.

No paths are read or effects granted. Expanded ancestry and original raw JSON
whitespace preserve the independently validated private definition semantics.
"""
import copy,hashlib

FLAGS=('case_read','image_read','map_read','store_write','host_effects','private_metadata')

def envelope_boundary(definition,encode):
    d=copy.deepcopy(definition);original=d['request_raw']
    def digest(value):return 'sha256:'+hashlib.sha256(encode(value)).hexdigest()
    def update(padding):
        d['request_raw']=original+' '*padding
        assert len(d['request_raw'].encode())<=32768
        d['case_source']['files'][0]['metadata']['bytes']=str(len(d['request_raw'].encode()))
        d['case_source']['files'][0]['digest']='sha256:'+hashlib.sha256(d['request_raw'].encode()).hexdigest()
        for role in ('image','map'):d['verification']['resources'][role]['epoch']=digest(d['image_binding'][role])
        d['verification_digest']=digest(d['verification'])
        return dict(phase='execute',definition=d,definition_digest=digest(d),**{'allow_'+f:True for f in FLAGS})
    for count in range(1,121):
        for selected in (d['store'],d['case_source'],d['image_binding']['image'],d['image_binding']['map']):selected['ancestors']=[copy.deepcopy(selected['ancestors'][-1]) for _ in range(count)]
        q=update(0)
        if len(encode(q))>=40000:break
    padding=0
    for _ in range(6):
        q=update(padding);difference=65500-len(encode(q))
        if difference==0:return q
        padding+=difference
        assert padding>=0
    raise AssertionError('Cannot construct exact public envelope boundary')

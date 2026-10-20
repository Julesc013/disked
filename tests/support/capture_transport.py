"""Private fixed-size owned-capture packets; not a public DiskEd protocol."""
import hashlib
import struct

TAG=0x44454331
REQUEST_BYTES=640
HEADER_BYTES=4096


def require(value,reason):
    if not value:raise ValueError(reason)


def encode_request(*,nonce,sequence,width,height,window,process,thread,job_handle,section_handle,volume,file_id,case_id,window_rect,desktop):
    values=(nonce,sequence,width,height,window,process,thread,job_handle,section_handle,volume)
    require(all(type(v) is int and v>=0 for v in values),'integer_domain')
    require(0<nonce<2**64 and nonce&0xffffffff and nonce>>32 and 1<=sequence<=8 and 0<window<2**64 and
            0<process<2**32 and 0<thread<2**32 and 0<job_handle<2**64 and 0<section_handle<2**64 and volume<2**64,'identity_domain')
    require(0<width<=4096 and 0<height<=2160 and width*height*4<=16777216,'geometry_bound')
    require(type(file_id) is bytes and len(file_id)==16 and type(case_id) is bytes and len(case_id)==16 and any(case_id),'object_ids')
    require(isinstance(window_rect,(tuple,list)) and len(window_rect)==4 and all(type(v) is int and -2**31<=v<2**31 for v in window_rect) and
            window_rect[2]>window_rect[0] and window_rect[3]>window_rect[1],'window_rect')
    require(isinstance(desktop,str) and '\0' not in desktop,'desktop')
    text=desktop.encode('utf-16le');require(0<len(text)<=510,'desktop_bound')
    body=bytearray(640);body[:8]=b'DECAPR1\0'
    struct.pack_into('<QIIIIQIIQQQ',body,8,nonce,sequence,width,height,len(text)//2,window,process,thread,job_handle,section_handle,volume)
    body[72:88]=file_id;body[88:104]=case_id;struct.pack_into('<iiii',body,104,*window_rect);body[120:120+len(text)]=text
    return bytes(body)


def decode_reply(body,request):
    require(type(request) is bytes and len(request)==640 and request[:8]==b'DECAPR1\0','request')
    width,height=struct.unpack_from('<II',request,20);size=4096+width*height*4
    require(type(body) is bytes and 4096<len(body)<=16781312 and len(body)==size,'reply_bound')
    require(body[:8]==b'DECAPS1\0' and struct.unpack_from('<I',body,120)[0]==size and not any(body[124:4096]),'reply_publication')
    for output,input_,length in ((8,8,20),(32,32,16),(48,64,8),(56,72,32),(104,104,16)):
        require(body[output:output+length]==request[input_:input_+length],'reply_identity')
    pixel_bytes,=struct.unpack_from('<I',body,28);count,before,after,format_=struct.unpack_from('<IIII',body,88)
    require(pixel_bytes==width*height*4 and count<=64 and before==after and format_==1,'reply_pixels')
    pixels=body[4096:]
    metadata=dict(method='owned-ui-thread-cooperative-client-tree-transport/1',nonce=str(struct.unpack_from('<Q',body,8)[0]),
        sequence=struct.unpack_from('<I',body,16)[0],width=width,height=height,window=str(struct.unpack_from('<Q',body,32)[0]),
        process=struct.unpack_from('<I',body,40)[0],thread=struct.unpack_from('<I',body,44)[0],volume=str(struct.unpack_from('<Q',body,48)[0]),
        file_id=body[56:72].hex(),case_id=body[72:88].hex(),descendants=count,gdi_before=before,gdi_after=after,
        window_rect=list(struct.unpack_from('<iiii',body,104)),bytes=len(pixels),sha256=hashlib.sha256(pixels).hexdigest())
    return metadata,pixels

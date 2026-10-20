"""Independent frozen packet offsets and contradictory publication controls."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec=importlib.util.spec_from_file_location('capture_packets',Path(__file__).resolve().parents[1]/'support/capture_transport.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class CaptureTransportTests(unittest.TestCase):
    def setUp(self):
        self.args=dict(nonce=0x0102030405060708,sequence=1,width=2,height=1,window=0x1122334455667788,process=12,thread=34,
            job_handle=56,section_handle=78,volume=90,file_id=bytes(range(16)),case_id=bytes(range(16,32)),window_rect=(-1,-2,3,4),desktop='Station\\Desktop')
    def reply(self):
        # Written directly from the declared layout, not by a producer encoder.
        body=bytearray(4104);body[:8]=b'DECAPS1\0';struct.pack_into('<QIIIIQIIQ',body,8,0x0102030405060708,1,2,1,8,0x1122334455667788,12,34,90)
        body[56:72]=bytes(range(16));body[72:88]=bytes(range(16,32));struct.pack_into('<IIIIiiiiI',body,88,2,4,4,1,-1,-2,3,4,4104)
        body[4096:]=b'abcdefgh';return bytes(body)
    def test_declared_offsets_and_exact_reply(self):
        request=S.encode_request(**self.args);self.assertEqual(len(request),640);self.assertEqual(request[:16],b'DECAPR1\0\x08\x07\x06\x05\x04\x03\x02\x01')
        self.assertEqual(struct.unpack_from('<QQQ',request,48),(56,78,90));self.assertEqual(request[72:104],bytes(range(32)))
        self.assertEqual(struct.unpack_from('<iiii',request,104),(-1,-2,3,4));self.assertEqual(request[120:150],'Station\\Desktop'.encode('utf-16le'));self.assertFalse(any(request[150:]))
        header,pixels=S.decode_reply(self.reply(),request);self.assertEqual(pixels,b'abcdefgh');self.assertEqual(header['case_id'],bytes(range(16,32)).hex())
    def test_bad_domain_never_encodes(self):
        for key,value in [('nonce',1),('sequence',9),('process',True),('window',2**64),('width',4097),('height',2161),('case_id',bytes(16)),('file_id',b''),('desktop','a\0b'),('desktop','x'*256),('window_rect',(0,0,0,0))]:
            with self.subTest(key=key),self.assertRaises((ValueError,UnicodeError)):S.encode_request(**dict(self.args,**{key:value}))
    def test_wrong_partial_replayed_or_unbound_frame_refuses(self):
        request=S.encode_request(**self.args);valid=self.reply()
        for offset in (0,8,16,20,24,28,32,40,44,48,56,72,88,96,100,104,120,128):
            wrong=bytearray(valid)
            if offset==88:struct.pack_into('<I',wrong,offset,65)
            else:wrong[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):S.decode_reply(bytes(wrong),request)
        for body in (b'',valid[:-1],valid+b'x'):
            with self.assertRaises(ValueError):S.decode_reply(body,request)
        with self.assertRaises(ValueError):S.decode_reply(valid,S.encode_request(**dict(self.args,sequence=2)))


if __name__=='__main__':unittest.main()

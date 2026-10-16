"""Independent JSON implementation, malformed Unicode and resource-bound tests."""
import argparse
import json
import random
import subprocess
import unittest


class JsonCodec(unittest.TestCase):
    def invoke(self, value):
        result = subprocess.run([EXE], input=value, capture_output=True, timeout=5)
        self.assertEqual(b'', result.stderr)
        return result.returncode, json.loads(result.stdout)

    def valid(self, value):
        wire = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        status, actual = self.invoke(wire)
        self.assertEqual(0, status, actual)
        self.assertEqual(value, actual)

    def invalid(self, wire, code=None):
        status, actual = self.invoke(wire)
        self.assertEqual(2, status, actual)
        if code:
            self.assertEqual(code, actual['code'])

    def test_primitives_unicode_and_exact_integer_lexemes(self):
        for value in [None, True, False, 0, -1, 1.5, 2**64-1, '磁盘🙂', '\0\t\r\n\\"', [], {}, {'a':[1,False,None]}]:
            with self.subTest(value=value):
                self.valid(value)
        self.assertEqual((0, '🙂'), self.invoke(b'"\\uD83D\\uDE42"'))

    def test_invalid_json_and_duplicate_decoded_keys(self):
        for wire in [b'',b' ',b'NaN',b'Infinity',b'-Infinity',b'01',b'+1',b'1.',b'.1',b'1e',b'[1,]',b'{"a":1,}',b'{a:1}',b'true false',b'{}\0',b'\xef\xbb\xbf{}',b'"\x01"',b'"\\x41"']:
            with self.subTest(wire=wire):
                self.invalid(wire)
        for wire in [b'{"a":1,"a":2}',b'{"a":1,"\\u0061":2}',b'{"x":{"b":0,"b":1}}']:
            self.invalid(wire, 'duplicate_key')
        self.invalid(b'1e9999', 'nonfinite_number')

    def test_utf8_and_surrogate_rejection(self):
        for raw in [b'\x80',b'\xc0\x80',b'\xc1\xbf',b'\xe0\x80\x80',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xf5\x80\x80\x80',b'\xe2\x82']:
            self.invalid(b'"'+raw+b'"', 'invalid_utf8')
        for wire in [b'"\\uD800"',b'"\\uDC00"',b'"\\uD800\\u0041"',b'"\\uD800x"']:
            self.invalid(wire, 'invalid_unicode')

    def test_exact_resource_boundaries(self):
        self.assertEqual((0, {}), self.invoke(b'{}'+b' '*(65536-2)))
        self.invalid(b'{}'+b' '*(65536-1), 'frame_limit_exceeded')
        self.valid('a'*32768)
        self.invalid(b'"'+b'a'*32769+b'"', 'string_limit_exceeded')
        self.assertEqual(0, self.invoke(b'['*32+b'0'+b']'*32)[0])
        self.invalid(b'['*33+b'0'+b']'*33, 'depth_limit_exceeded')
        self.valid([0]*8191)
        self.invalid(b'['+b'0,'*8191+b'0]', 'value_limit_exceeded')

    def test_deterministic_differential_corpus(self):
        rng=random.Random(12006)
        def value(depth):
            if depth==0:
                return rng.choice([None,True,False,rng.randrange(-2**53,2**53),'a\n雪🙂'])
            return rng.choice([lambda:[value(depth-1) for _ in range(rng.randrange(4))],
                lambda:{str(i):value(depth-1) for i in range(rng.randrange(4))},lambda:value(0)])()
        for i in range(100):
            with self.subTest(case=i):
                self.valid(value(4))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--exe',required=True)
    EXE=parser.parse_args().exe
    unittest.main(argv=[__file__],verbosity=2)

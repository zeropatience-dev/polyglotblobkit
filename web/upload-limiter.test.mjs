import test from 'node:test';
import assert from 'node:assert/strict';
import {validateFiles} from './upload-limiter.mjs';
const file = (size, name='合同_😀.pdf') => ({size,name});
test('5 MB boundary including exact size and one byte above', () => {
  const files = [file(0),file(4_999_999),file(5_000_000),file(5_000_001)];
  const r = validateFiles(files,5);
  assert.deepEqual(r.accepted,files.slice(0,3));
  assert.equal(r.rejected[0].file,files[3]);
  assert.equal(r.rejected[0].code,'UPLOAD_TOO_LARGE');
});
test('default matches backend', () => assert.equal(validateFiles([]).maxBytes,50_000_000));
test('per-file not aggregate', () => assert.equal(validateFiles([file(5_000_000),file(5_000_000)],5).accepted.length,2));
test('reject invalid limits', () => {for (const n of [0,-1,1.5,'5',NaN,Infinity,Number.MAX_SAFE_INTEGER]) assert.throws(()=>validateFiles([],n),RangeError);});
test('reject invalid sizes', () => {for (const n of [-1,1.5,NaN,Infinity,'5']) assert.throws(()=>validateFiles([file(n)],5),TypeError);});
test('real File object and exact Unicode name preserved', () => {const f = new File(['abc'],'e\u0301_合同.pdf'); assert.equal(validateFiles([f],5).accepted[0],f);});

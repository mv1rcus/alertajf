import {test} from 'node:test';
import assert from 'node:assert/strict';
import {cleanup, validPath} from './cleanup.mjs';
function mock(rows, {eligible=true, removeError=false, lookupError=false}={}) {
  const calls=[];
  return {calls, rpc:async (fn,args)=> {
    calls.push([fn,args]);
    if(fn==='ajf_media_cleanup_candidates') return {data:rows,error:lookupError};
    if(fn==='ajf_media_cleanup_eligible') return {data:eligible};
    return {};
  },storage:{from:bucket=>({remove:async paths=>{calls.push(['remove',bucket,paths]);return {error:removeError};}})}};
}
test('accept only bounded r/ object paths, reject traversal/other buckets',()=>{
  assert.ok(validPath('r/abcd-123.mp4'));
  for(const x of ['other/x.mp4','r/../x','r/a/b','r/x?z','',null,'r/'+'a'.repeat(201)]) assert.equal(validPath(x),false);
});
test('remove only eligible paths, acknowledge after storage success',async()=>{
  const c=mock([{path:'r/test.png'}]);assert.deepEqual(await cleanup(c),{removed:1,failed:0});
  assert.deepEqual(c.calls.map(x=>x[0]),['ajf_media_cleanup_candidates','ajf_media_cleanup_eligible','remove','ajf_media_cleanup_ack']);
  assert.equal(c.calls[2][1],'relatos-midia');
});
test('active/reference-protected item is not deleted',async()=>{
  const c=mock([{path:'r/test.png'}],{eligible:false});await cleanup(c);assert.ok(!c.calls.some(x=>x[0]==='remove'));
});
test('storage failure remains queued, no ack',async()=>{
  const c=mock([{path:'r/test.png'}],{removeError:true});assert.deepEqual(await cleanup(c),{removed:0,failed:1});assert.ok(!c.calls.some(x=>x[0]==='ajf_media_cleanup_ack'));
});
test('invalid path never reaches storage',async()=>{
 const c=mock([{path:'r/../../unrelated'}]);await cleanup(c);assert.ok(!c.calls.some(x=>x[0]==='remove'));
});
test('lookup fails closed',async()=>{const c=mock([],{lookupError:true});await assert.rejects(()=>cleanup(c));assert.equal(c.calls.length,1)});

"""Scoped read-only dependency checks via existing clients in the same project."""
import json
import time

def collect(docker, ids, user_id, post_id, marker, early_stop=False, after_probe=None):
    user_id=str(user_id);post_id=str(post_id)
    if not user_id.isdigit() or not post_id.isdigit():
        raise ValueError('Expected numeric synthetic record IDs')
    commands={
        'timeline_redis':['exec',ids['home-timeline-redis'],'timeout','2s','redis-cli',
            '-h','user-timeline-redis','--raw','ZREVRANGE',user_id,'0','99'],
        'timeline_mongo':['exec',ids['user-mongodb'],'timeout','2s','mongo',
            '--quiet','--host','user-timeline-mongodb','--eval',
            "var d=db.getSiblingDB('user-timeline').getCollection('user-timeline').findOne({user_id:NumberLong("+json.dumps(user_id)+")});"
            "print(JSON.stringify({ids:d ? d.posts.map(function(p){return p.post_id.toString();}) : []}));"],
    }
    lua=("local th=require 'Thrift'; for k,v in pairs(th) do _G[k]=v end; "
         "local ty=require 'social_network_ttypes'; for k,v in pairs(ty) do _G[k]=v end; require 'social_network_PostStorageService'; "
         "local f=require 'RpcClientFactory'; local l=require 'liblualongnumber'; local j=require 'cjson'; "
         "local c=f:createClient(PostStorageServiceClient,'post-storage-service',9090,1000,false); "
         "local rows=c:ReadPosts(1,{l.new("+json.dumps(post_id)+")},{}); local result={}; "
         "for _,p in ipairs(rows) do result[#result+1]={post_id=tostring(p.post_id),text=p.text,creator=tostring(p.creator.user_id)} end; "
         "print(j.encode(result))")
    commands['post_storage']=['exec',ids['nginx-thrift'],'timeout','3s','/usr/local/openresty/bin/resty',
        '--errlog-level','error','--ns','127.0.0.11',
        '-e',lua]
    output={}
    stopped=False
    for name,args in commands.items():
        if stopped:
            output[name]={'verified':None,'returncode':None,'elapsed_ms':0,'executed':False}
            continue
        start=time.perf_counter()
        result=docker(args,check=False,timeout=10)
        valid=False
        if result.returncode==0:
            try:
                if name=='timeline_redis':
                    valid=post_id in result.stdout.splitlines()
                elif name=='timeline_mongo':
                    # NumberLong.toString may retain its wrapper; do not parse as float.
                    vals=json.loads(result.stdout)['ids']
                    valid=any(v==post_id or v=='NumberLong("'+post_id+'")' or v=='NumberLong('+post_id+')' for v in vals)
                else:
                    rows=json.loads(result.stdout)
                    valid=any(p['post_id']==post_id and p['text']==marker and p['creator']==user_id for p in rows)
            except (ValueError,KeyError,TypeError):
                valid=False
        output[name]={'verified':valid,'returncode':result.returncode,
                      'elapsed_ms':1000*(time.perf_counter()-start),'executed':True,
                      'started_monotonic':start,'completed_monotonic':time.perf_counter()}
        if after_probe is not None:after_probe(name,dict(output[name]))
        stopped=early_stop and not valid
    return output

def policies(functional_classification, direct):
    def decision(valid):
        return {'decision':'approve' if valid else 'abstain'}
    return {
        'alternate_route':decision(functional_classification=='verified_readback'),
        'alternate_plus_redis':decision(functional_classification=='verified_readback' and direct['timeline_redis']['verified']),
        'direct_dependencies':decision(all(direct[k]['verified'] for k in ('timeline_redis','timeline_mongo','post_storage')))}

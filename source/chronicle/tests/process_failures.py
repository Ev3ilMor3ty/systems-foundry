#!/usr/bin/env python3
"""Linux process/filesystem fault checks for the actual Chronicle executable."""
import argparse,json,os,pathlib,resource,signal,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run(binary):
    checks=[]
    with tempfile.TemporaryDirectory(prefix='chronicle faults ') as temp:
        path=pathlib.Path(temp)/'events.jsonl'
        process=subprocess.Popen([binary,'serve',path],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def exchange(request):
            process.stdin.write(json.dumps(request)+'\n');process.stdin.flush();return json.loads(process.stdout.readline())
        try:
            for i in range(50):
                response=exchange({'op':'append','id':f'ack-{i}','event':{'n':i,'message':'durable'}});assert response['ok'];head=response['record']['hash']
            locked=subprocess.run([binary,'verify',path],capture_output=True);assert locked.returncode!=0;checks.append('cross-process writer lock')
            assert not exchange({'op':'append','id':'ack-0','event':{'n':'different'}})['ok']
            assert exchange({'op':'status'})['records']==50;checks.append('conflicting key rejected without losing server state')
            process.kill();process.wait(timeout=3)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)
            process.stdin.close();process.stdout.close();process.stderr.close()
        verified=subprocess.run([binary,'verify',path,head],capture_output=True,text=True,check=True);assert json.loads(verified.stdout)['records']==50;checks.append('acknowledged records survive writer SIGKILL with exact head')
        before=path.read_bytes()
        # Force a real short write followed by EFBIG. Ignoring SIGXFSZ lets the
        # program report uncertain durability instead of dying on the signal.
        def file_limit():
            signal.signal(signal.SIGXFSZ,signal.SIG_IGN);resource.setrlimit(resource.RLIMIT_FSIZE,(len(before)+37,len(before)+37))
        failed=subprocess.run([binary,'append',path,'short-write',json.dumps({'blob':'x'*10000})],capture_output=True,text=True,preexec_fn=file_limit)
        assert failed.returncode!=0 and 'uncertain' in failed.stderr
        damaged=path.read_bytes();assert damaged.startswith(before) and len(damaged)>len(before)
        assert subprocess.run([binary,'verify',path],capture_output=True).returncode!=0
        retry=subprocess.run([binary,'append',path,'retry','{}'],capture_output=True);assert retry.returncode!=0 and path.read_bytes()==damaged
        checks.append('real partial write detected; corrupt tail never silently truncated')
        clean=pathlib.Path(temp)/'clean.jsonl'
        incomplete=subprocess.run([binary,'serve',clean],input='{"op":"append","id":"torn-input","event":{}}',capture_output=True,text=True)
        assert incomplete.returncode!=0 and clean.read_bytes()==b'';checks.append('incomplete protocol line cannot append')
        huge=pathlib.Path(temp)/'oversized.jsonl'
        with huge.open('wb') as f:f.truncate(64*1024*1024+1)
        assert subprocess.run([binary,'serve',huge],capture_output=True,timeout=2).returncode!=0;checks.append('oversized file rejected before replay')
    print(json.dumps({'ok':True,'checks':checks}))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=pathlib.Path,default=ROOT/'target/release/foundry-chronicle');args=parser.parse_args();run(args.binary)

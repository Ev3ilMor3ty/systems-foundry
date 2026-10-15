#!/usr/bin/env python3
"""Seeded size/density benchmarks; every result is independently certified."""
import argparse,hashlib,json,pathlib,platform,random,statistics,subprocess,time
from check_certificate import verify
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=pathlib.Path,default=ROOT/'build/foundry-dispatch');parser.add_argument('--output',type=pathlib.Path,default=ROOT.parent/'docs/evidence/dispatch-benchmark.json');a=parser.parse_args()
    rng=random.Random(0xF01D2026);results=[]
    for n in [32,64,128,256]:
        for density in [.08,.5,1.0]:
            for trial in range(3):
                problem={'workers':n,'tasks':n,'edges':[{'worker':w,'task':t,'cost':rng.randrange(1_000_000)} for w in range(n) for t in range(n) if rng.random()<density]}
                payload=json.dumps(problem,separators=(',',':'));start=time.perf_counter()
                p=subprocess.run([a.binary],input=payload,text=True,capture_output=True,check=True,timeout=20);wall=(time.perf_counter()-start)*1000;response=json.loads(p.stdout);verify(problem,response)
                optimal=response['optimal'];greedy=response['greedy']
                record={'n':n,'density':density,'trial':trial,'edges':len(problem['edges']),'input_sha256':hashlib.sha256(payload.encode()).hexdigest(),'wall_ms':round(wall,3),'solve_us':response['solve_us'],'optimal_count':optimal['cardinality'],'greedy_count':greedy['cardinality'],'optimal_cost':optimal['cost'],'greedy_cost':greedy['cost'],'certificate_checked':True};results.append(record)
                print(json.dumps(record),flush=True)
    report={'ok':True,'seed':'0xF01D2026','binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'platform':platform.platform(),'logical_cpus_visible':__import__('os').cpu_count(),'cpu_quota_cores':2,'scope':'shared development host; includes a low-duty QEMU soak; illustrative timings, not controlled native performance claims','cases':results}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()

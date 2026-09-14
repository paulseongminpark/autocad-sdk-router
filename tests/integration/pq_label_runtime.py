"""Explicit AutoCAD 2027 runtime smoke; run directly, never during ordinary pytest.

Creates a synthetic fixture through the existing router on a staged blank seed.
Uses existing IR/SQL discovery and then all PQ operations. Saves full receipts
under runs/pq-label-runtime-<uuid>. Requires installed project requirements.
"""
def main():
    import sys,os,json,subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'tools'))
    os.environ['PATH']=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH']
    from cadctl import Cad
    cad=Cad()
    out=root/'runs'/('pq-label-runtime-'+__import__('uuid').uuid4().hex)
    out.mkdir(parents=True,exist_ok=False)
    scr=out/'seed.scr'
    scr.write_text('''(entmake '((0 . "LAYER") (100 . "AcDbSymbolTableRecord") (100 . "AcDbLayerTableRecord") (2 . "A-WALL") (70 . 0)))
    (entmake '((0 . "LINE") (8 . "A-WALL") (10 0.0 0.0 0.0) (11 10.0 0.0 0.0)))
    (entmake '((0 . "BLOCK") (2 . "PQ_INNER") (70 . 0) (10 0.0 0.0 0.0)))
    (entmake '((0 . "LINE") (10 0.0 0.0 0.0) (11 1.0 0.0 0.0)))
    (entmake '((0 . "ENDBLK")))
    (entmake '((0 . "BLOCK") (2 . "PQ_OUTER") (70 . 0) (10 0.0 0.0 0.0)))
    (entmake '((0 . "INSERT") (2 . "PQ_INNER") (10 0.0 0.0 0.0)))
    (entmake '((0 . "ENDBLK")))
    (entmake '((0 . "INSERT") (2 . "PQ_OUTER") (10 20.0 0.0 0.0)))
    (entmake '((0 . "INSERT") (2 . "PQ_OUTER") (10 30.0 0.0 0.0)))
    (regapp "COMPANY_PQ")
    (regapp "Rhino")
    (entmake '((0 . "LINE") (10 40.0 0.0 0.0) (11 41.0 0.0 0.0) (-3 ("COMPANY_PQ" (1000 . "SCHEMA") (1000 . "1.1") (1000 . "CLASS_ID") (1000 . "LEGACY") (1000 . "CLASS_KIND") (1000 . "STUFF")) ("Rhino" (1002 . "{") (1000 . "CUSTOM") (1000 . "preserve-me") (1002 . "}")))))
    _QSAVE
    _QUIT

    ''')
    cmd=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'tools/autocad-router.ps1'),'-Action','run','-Intent','dwg','-InputPath',str(root/'tests/fixtures/blank_seed.dwg'),'-Script',str(scr),'-PythonExe',sys.executable]
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert p.returncode==0,p.stderr
    seed=json.loads(p.stdout)['execution']['engine_output']['staged_input']
    inspect=cad.inspect(seed,str(out/'inspect'),include_rich=True)
    (out/'inspect.json').write_text(json.dumps(inspect,indent=2))
    print('inspect',inspect.get('status'),flush=True)
    ir=out/'inspect/dwg_graph_ir.json'
    query=cad.query(str(ir),"SELECT handle FROM entities WHERE layer = 'A-WALL'")
    print('query',query,flush=True)
    assert query['status']=='ok' and query['rows']
    handles=[row[0] for row in query['rows']]
    blocks=[row[0] for row in cad.query(str(ir), "SELECT handle FROM entities WHERE dxf_name = 'INSERT'")['rows']]
    assert len(blocks)==2
    current=seed
    results=[]
    def run(op,args=None,ok=True):
        nonlocal current
        r=cad.run_operation('pq_label.'+op,args=args,dwg_path=current,out_dir=str(out/f'{len(results):02d}-{op}'))
        results.append(r)
        (out/'results.json').write_text(json.dumps(results,indent=2))
        print(op,r['status'],r.get('result'),r.get('reason'),flush=True)
        assert (r['status']=='ok') == ok
        assert r['original_unchanged']
        if ok and r['write_mode']=='write_copy': current=r['staged_result']
        return r.get('result',{}).get('data')
    run('class.set',{'handles':handles,'class_id':'WALL','class_kind':'STUFF'})
    assert run('inspect',{'handles':handles})[0]['class_id']=='WALL'
    run('instance.new',{'handles':handles},ok=False)
    run('class.set',{'handles':handles,'class_id':'OTHER','class_kind':'THING'},ok=False)
    run('class.set_kind',{'class_id':'WALL','class_kind':'THING'})
    run('instance.new',{'handles':handles})
    assert run('validate')['Errors']==0
    run('instance.set',{'handles':handles,'instance_id':'test-instance'})
    run('inventory')
    run('sync')
    run('migrate')
    run('instance.clear',{'handles':handles})
    run('class.clear',{'handles':handles})
    assert run('inspect',{'handles':handles})[0]['class_id'] is None
    run('class.set',{'handles':blocks[:1],'class_id':'DOOR','class_kind':'THING'},ok=False)
    run('class.set',{'handles':blocks[:1],'class_id':'DOOR','class_kind':'THING','allow_shared_definitions':True})
    assert all(row['effective_class']=='DOOR' for row in run('inspect',{'handles':blocks}))
    run('class.clear',{'handles':blocks[:1],'allow_shared_definitions':True})
    assert all(row['effective_class'] is None for row in run('inspect',{'handles':blocks}))
    assert run('validate')['Errors']==0
    final_dir=out/'final-inspect'
    assert cad.inspect(current,str(final_dir),include_rich=True)['status']=='ok'
    final_ir=json.loads((final_dir/'dwg_graph_ir.json').read_text(encoding='utf-8'))
    groups=[g for e in final_ir['entities'] for g in e.get('xdata',[])]
    assert not any(g['app']=='COMPANY_PQ' for g in groups)
    assert any(g['app']=='Rhino' and any(row.get('value')=='preserve-me' for row in g['rows']) for g in groups)
    print('PQ E2E PASS',flush=True)


if __name__ == "__main__":
    main()

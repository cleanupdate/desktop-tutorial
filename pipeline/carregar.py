import sys, pandas as pd, os
os.makedirs('work',exist_ok=True); os.makedirs('out',exist_ok=True)
hist, fut = sys.argv[1], (sys.argv[2] if len(sys.argv)>2 else None)
d=pd.read_excel(hist,header=1)
d.columns=['data','cliente','end','tipoend','tipo','freq','status','ini','fim','dur','equipe','qtd','nomes','valor','extra','det','pstatus','pvalor','pdata','pdet']
d['data']=pd.to_datetime(d.data,errors='coerce'); d.to_pickle('work/d.pkl')
if fut:
    f=pd.read_excel(fut,header=1)
    f.columns=['cliente','ref','tipoend','tipo','freq','data','status','ini','fim','dur','equipe','qtd','nomes','valor','x','extra','det']
    f['data']=pd.to_datetime(f.data,errors='coerce'); f.to_pickle('work/fut.pkl')
elif os.path.exists('work/fut.pkl'): os.remove('work/fut.pkl')
print('histórico',d.data.min().date(),'a',d.data.max().date(),len(d),'linhas')

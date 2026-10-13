import pandas as pd
from people import x, act, ATIVAS, B, END
MES=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
SN={'Paula Gregório':'Paula G.','Paula Lopes':'Paula L.','Paula Gabrielly Gregorio':'Paula Gabrielly'}
nm=lambda p:SN.get(p,p.split()[0])
x=x[x.data.dt.year==END.year].copy(); x['mes']=x.data.dt.month
meses=range(x.mes.min(),END.month+1)
rows=[]
for eq,g in x.groupby('equipe'):
    if g.data.max()<END-pd.Timedelta(days=42): continue
    r={'equipe':f'Eq {eq}'}
    for m in meses:
        gm=g[g.mes==m]
        if len(gm)==0: r[MES[m-1]]=''; continue
        vc=gm.p.value_counts(); r[MES[m-1]]=' + '.join(sorted({nm(k) for k,v in vc.items() if v>=vc.max()*0.3}))
    rows.append(r)
h=pd.DataFrame(rows); h['n']=h.equipe.str.extract(r'(\d+)').astype(int); h.sort_values('n').drop(columns='n').to_csv('out/equipes_hist.csv',index=False)
s=act[(~act.index.isin(ATIVAS))&(act['count']>=10)].sort_values('max',ascending=False).reset_index()
pd.DataFrame(dict(pessoa=s.p,entrou=s['min'].dt.strftime('%d/%m'),saiu=s['max'].dt.strftime('%d/%m'),limpezas=s['count'])).to_csv('out/saidas.csv',index=False)
b=B.copy()
b['quem_fez']=b.pessoas.map(lambda l:', '.join(p.split()[0] for p in l))
b['nao_mandar']=b.bloqueadas.map(lambda l:', '.join(p.split()[0] for p in l if p in ATIVAS))
b['situacao']=b.apply(lambda r:'Não mandar' if r.nao_mandar else ('Já voltou a limpar depois' if any(p in ATIVAS for p in r.pessoas) else 'Pessoas já saíram'),axis=1)
b=b.sort_values('data_relimpeza',ascending=False)
b['id']=b.data_relimpeza.dt.strftime('%y%m%d')+'-'+b.cliente+b.manual.map(lambda m:'-fb' if m else '')
pd.DataFrame(dict(id=b.id,data=b.data_relimpeza.dt.strftime('%d/%m'),cliente=b.cliente,quem_fez=b.quem_fez,situacao=b.situacao,nao_mandar=b.nao_mandar,origem=b.manual.map(lambda m:m or 'Relimpeza'))).drop_duplicates('id').to_csv('out/reclamacoes.csv',index=False)
print('extras ok')

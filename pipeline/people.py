import pandas as pd, re
d=pd.read_pickle('work/d.pkl'); d=d[d.data.notna()].copy(); d['equipe']=d.equipe.astype(str)
END=d.data.max()
def ppl(s): return [p.strip() for p in str(s).split(',') if p.strip() and str(s)!='nan']
c=d[d.status=='Concluído'].sort_values('data')
x=c.assign(p=c.nomes.map(ppl)).explode('p').dropna(subset=['p'])
act=x.groupby('p').data.agg(['min','max','count'])
ATIVAS=set(act[act['max']>=END-pd.Timedelta(days=42)].index)
recent=x[x.data>=END-pd.Timedelta(days=30)]
P2T=recent.groupby('p').equipe.agg(lambda s:s.mode()[0]).to_dict()
# bloqueios
REG=~c.tipo.astype(str).str.contains('Relimpeza|Check')
blk=[]
for i,row in c.iterrows():
    t=str(row.tipo); pd_=str(row.pdet)
    if t=='Relimpeza':
        prev=c[(c.cliente==row.cliente)&(c.data<row.data)&REG]
        if len(prev):
            pv=prev.iloc[-1]; blk.append(dict(cliente=row.cliente,pessoas=ppl(pv.nomes),data_ruim=pv.data,data_relimpeza=row.data))
    elif re.search('refaz|teve que voltar',pd_,re.I):
        blk.append(dict(cliente=row.cliente,pessoas=ppl(row.nomes),data_ruim=row.data,data_relimpeza=row.data))
B=pd.DataFrame(blk); B=B[B.pessoas.map(len)>0]
# perdoado: pessoa voltou a limpar o cliente depois da relimpeza
def ainda(b):
    later=c[(c.cliente==b.cliente)&(c.data>b.data_relimpeza)&REG]
    voltou=set(p for n in later.nomes for p in ppl(n))
    return [p for p in b.pessoas if p not in voltou]
B['bloqueadas']=B.apply(ainda,axis=1); B['manual']=''
c_all=sorted(c.cliente.dropna().unique())
# reclamações informadas manualmente (bloqueios_manual.csv): pessoa ou 'Eq N'
try:
    M=pd.read_csv('bloqueios_manual.csv').fillna('')
except Exception: M=pd.DataFrame(columns=['cliente','quem_nao_mandar','motivo','data'])
_eqs=x[x.data>=END-pd.Timedelta(days=30)].groupby('equipe').p.agg(lambda s:set(s))
def _resolve(q):
    out=set()
    for it in [i.strip() for i in str(q).replace(';',',').split(',') if i.strip()]:
        m=re.match(r'(?i)eq(?:uipe)?\s*(\d+)',it)
        if m: out|=_eqs.get(m.group(1),set()); continue
        cand=[p for p in act.index if p.lower().startswith(it.lower())]
        out|=set(cand[:1]) if cand else {it}
    return out
for _,m in M.iterrows():
    cl=[c for c in c_all if str(c).lower().startswith(str(m.cliente).lower())] if m.cliente else []
    for cc in cl[:1]:
        B.loc[len(B)]=dict(cliente=cc,pessoas=sorted(_resolve(m.quem_nao_mandar)),data_ruim=pd.Timestamp(m.data) if m.data else END,data_relimpeza=pd.Timestamp(m.data) if m.data else END,bloqueadas=sorted(_resolve(m.quem_nao_mandar)),manual=m.motivo or 'Feedback do cliente')
BLOQ={}
for _,b in B.iterrows(): BLOQ.setdefault(b.cliente,set()).update(b.bloqueadas)
def equipe_proxima(cliente, fallback):
    g=c[(c.cliente==cliente)&REG]
    if not len(g): return fallback,'',set()
    last=ppl(g.iloc[-1].nomes); bl=BLOQ.get(cliente,set())
    ok=[p for p in last if p in ATIVAS and p not in bl and p in P2T]
    blteams={P2T[p] for p in bl if p in P2T}
    if ok:
        t=pd.Series([P2T[p] for p in ok]).mode()[0]
        quem=[p for p in ok if P2T[p]==t][0]
        return t,'Mesma equipe da última limpeza' if t==str(g.iloc[-1].equipe) else f"Segue {quem.split()[0]} (fez a última), hoje na Eq {t}",blteams
    why='Quem fez a última saiu' if any(p not in ATIVAS for p in last) else ('Última limpeza teve reclamação' if any(p in bl for p in last) else 'Sem dado da última')
    t=fallback if fallback not in blteams else None
    return t,why,blteams
if __name__=='__main__':
    print(len(B)); print(B.to_string()); print(len(ATIVAS), sorted(ATIVAS)); print(P2T)

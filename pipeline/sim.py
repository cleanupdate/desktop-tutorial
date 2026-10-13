import pandas as pd, numpy as np
import json, os
R=json.load(open('regras.json'))
r=pd.read_pickle('work/rfull.pkl')
_END=pd.read_pickle('work/d.pkl').data.max()
DN=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']
EXP={'Semanal':7,'Cada 2 Semanas':14,'Cada 3 Semanas':21,'Cada 4 Semanas':28,'Cada 5 Semanas':35,'Cada 6 Semanas':42,'Cada 8 Semanas':56}
_m=_END+pd.Timedelta(days=7-_END.dayofweek)
W=[_m,_m+pd.Timedelta(days=7)]
NTH={'Primeiro do Mês':1,'Terceiro do Mês':3,'Último do Mês':-1}
def nth(y,m,wd,n):
    days=[d for d in pd.date_range(f'{y}-{m:02d}-01',periods=31) if d.month==m and d.dayofweek==wd]
    return days[n-1] if n>0 else days[-1]
out=[]
for _,x in r.iterrows():
    days=x.dia_ideal.split('/')
    for dd in days:
        wd=DN.index(dd)
        if x.frequencia in NTH:
            for m in (10,11):
                dt=nth(2026,m,wd,NTH[x.frequencia])
                if W[0]<=dt<W[1]+pd.Timedelta(days=7): out.append((dt,x,'mensal'))
            continue
        e=EXP[x.frequencia]
        if x.multi: e=7
        t=x.ultima+pd.Timedelta(days=e)
        while t<W[0]-pd.Timedelta(days=3): t+=pd.Timedelta(days=e)  # atrasado -> próxima
        while t<W[1]+pd.Timedelta(days=7):
            wk=t-pd.Timedelta(days=t.dayofweek)
            if wk in W: out.append((wk+pd.Timedelta(days=wd),x,'encaixe' if x.enc else 'fixo'))
            t+=pd.Timedelta(days=e)
rows=[]
for dt,x,tp in out:
    rows.append(dict(data=dt,dia=DN[dt.dayofweek],cliente=x.cliente,frequencia=x.frequencia,horario=x.horario_ideal if not x.enc else '',
        hi=float(x.hi_med) if pd.notna(x.hi_med) else 10.0,horas=max(1.0,x.horas_mediana) if pd.notna(x.horas_mediana) else 2.0,equipe=x.equipe,tipo=tp))
a=pd.DataFrame(rows).drop_duplicates(['data','cliente'])
# horário já combinado na agenda real de outubro tem prioridade sobre a média do histórico
fu=pd.read_pickle('work/fut.pkl') if os.path.exists('work/fut.pkl') else pd.DataFrame(columns=['status','ini','cliente','dur']); fu=fu[(fu.status=='Agendado')&fu.ini.notna()].copy()
_h=pd.to_datetime(fu.ini.astype(str),format='%H:%M:%S',errors='coerce'); fu['h']=_h.dt.hour+_h.dt.minute/60
_k=lambda s:str(s).split('(')[0].strip().lower()
HREAL=fu.assign(k=fu.cliente.map(_k)).groupby('k').h.median().to_dict()
a['hi']=[HREAL.get(_k(c),h) for c,h in zip(a.cliente,a.hi)]
fu['d']=pd.to_numeric(fu.dur.astype(str).str.extract(r'([\d.]+)')[0],errors='coerce')
HDUR=fu[fu.d>0].assign(k=fu.cliente.map(_k)).groupby('k').d.median().to_dict()
# duração da agenda real não é usada: são janelas, não tempo de limpeza
from people import equipe_proxima, BLOQ, ATIVAS
CAP=8.0; TRAV=0.5; TOL=1.0
def h2s(h): hh=round(h*2)/2; return f"{int(hh)}:{'30' if hh%1 else '00'}"
def dur(h): hh=round(h*2)/2; return f"{int(hh)}h"+('30' if hh%1 else '')
# equipes atuais (out/2026) e regras de capacidade
_D={"seg-sex": "01234", "seg-dom": "0123456", "ter-qui": "123", "qua-sex": "234"}
SPEC={k:(f"Eq {k} ({v['nome']})",v['pessoas'],v['casas_normal'],v['casas_max'],_D[v['dias']],v['pagamento']) for k,v in R['equipes'].items()}
RESERVA={k for k,v in R['equipes'].items() if v.get('reserva')}
FIXA=R['cliente_fixo_na_equipe']
def fixa(c):
    for k,v in FIXA.items():
        if str(c).startswith(k): return v
    return None
SO9={k for k,v in R['equipes'].items() if v.get('so_9h')}
NUM2T={k:v[0] for k,v in SPEC.items()}
TEAMS=[v[0] for k,v in SPEC.items()]
T2N={v[0]:k for k,v in SPEC.items()}
pt,mot,bt=[],[],[]
for _,x in a.iterrows():
    fb=x.equipe.split()[1]
    tn,why,bl=equipe_proxima(x.cliente,fb)
    if fixa(x.cliente): tn,why=fixa(x.cliente),'Cliente fixo da equipe'
    if tn is None or tn not in NUM2T: tn=fb if fb not in bl else None
    if tn in RESERVA or tn is None or tn not in NUM2T:
        why=(why+' · ' if why and why!='Mesma equipe da última limpeza' else '')+('Última foi com reserva' if tn in RESERVA else 'Sem equipe definida')
        tn=None
    pt.append(NUM2T[tn] if tn else None); mot.append(why); bt.append({NUM2T[b] for b in bl if b in NUM2T})
a['equipe']=pt; a['motivo']=mot; a['bloq']=bt
a['evitar']=a.cliente.map(lambda c:', '.join(sorted(p.split()[0] for p in BLOQ.get(c,set()) if p in ATIVAS)))
a['pref']=(a.hi*2).round()/2
a['ini']=np.nan; a['conflito']=''; a['obs']=''
for dt,g in a.groupby('data'):
    wd=str(dt.dayofweek)
    free={t:8.0 for t in TEAMS}; load={t:0.0 for t in TEAMS}; casas={t:0 for t in TEAMS}
    disp=lambda t: wd in SPEC[T2N[t]][4]
    def pode(t,x,p,lim):
        n=SPEC[T2N[t]]; cap=n[2] if lim=='normal' else n[3]
        if T2N[t] in SO9 and (p is None or p>10): return False
        if fixa(x.cliente) and fixa(x.cliente)!=T2N[t]: return False
        return disp(t) and casas[t]<cap and load[t]+x.horas<=CAP and t not in x.bloq and (p is None or free[t]<=p+TOL)
    fixed=g[g.tipo!='encaixe'].assign(_f=lambda z:z.cliente.map(lambda c:0 if fixa(c) else 1)).sort_values(['_f','pref']); enc=g[g.tipo=='encaixe'].sort_values('horas',ascending=False)
    for i,x in fixed.iterrows():
        p=max(8.0,x.pref); pref=x.equipe if isinstance(x.equipe,str) else None; t=None; nota=''
        regular=[u for u in TEAMS if T2N[u] not in RESERVA]
        if pref and pode(pref,x,p,'normal'): t=pref
        elif fixa(x.cliente):
            t=pref; nota='Cliente fixo da Eq '+fixa(x.cliente)
        else:
            for lim in ('normal','max'):
                c=[u for u in regular if pode(u,x,p,lim)]
                if pref and lim=='max' and pode(pref,x,p,'max'): c=[pref]
                if c:
                    t=pref if pref in c else min(c,key=lambda u:(casas[u],load[u]))
                    if lim=='max': nota=f"{SPEC[T2N[t]][2]+1}ª casa da equipe no dia"
                    if pref and t!=pref: nota=(f"{pref.split(' (')[0]} ocupada/cheia: foi para outra equipe"+(' · '+nota if nota else ''))
                    elif not pref: nota=(x.motivo+' → '+t.split(' (')[0]) if x.motivo else ''
                    break
            if t is None:
                c=[u for u in TEAMS if T2N[u] in RESERVA and pode(u,x,p,'normal')]
                if c: t=c[0]; nota=f"Sem equipe livre: precisa de reserva ({t.split('(')[1][:-1]})"
                elif pref and disp(pref) and casas[pref]<SPEC[T2N[pref]][3] and pref not in x.bloq:
                    t=pref; nota='Equipe de costume, mais tarde que o horário'
                else:
                    c=[u for u in regular if disp(u) and u not in x.bloq and casas[u]<SPEC[T2N[u]][3] and not (T2N[u] in SO9)]
                    t=min(c,key=lambda u:max(free[u],p)); a.at[i,'conflito']=f"Sem equipe livre às {h2s(p)}: atrasa {dur(max(free[t],p)-p)}"
        st=np.ceil(max(free[t],p)*2)/2
        if T2N[t] in SO9: st=9.0
        if st-p>=0.5 and not a.at[i,'conflito']: nota=(nota+' · ' if nota else '')+f"Começa {dur(st-p)} depois do horário de costume"
        a.at[i,'ini']=st; a.at[i,'equipe']=t; a.at[i,'obs']=nota; free[t]=st+x.horas+TRAV; load[t]+=x.horas; casas[t]+=1
    for i,x in enc.iterrows():
        c=[u for u in TEAMS if T2N[u] not in RESERVA and pode(u,x,None,'normal') and free[u]+x.horas<=17.5]
        if c:
            t=x.equipe if isinstance(x.equipe,str) and x.equipe in c else min(c,key=lambda u:(casas[u]-SPEC[T2N[u]][2],free[u]))
            a.at[i,'obs']='Encaixe na sobra da equipe'
        else:
            t=min([u for u in TEAMS if disp(u) and T2N[u] not in RESERVA],key=lambda u:free[u]); a.at[i,'conflito']="Sem sobra no dia: remarcar encaixe"
        st=np.ceil(free[t]*2)/2; a.at[i,'ini']=st; a.at[i,'equipe']=t; free[t]=st+x.horas+TRAV; load[t]+=x.horas; casas[t]+=1
# encaixe sem sobra no dia: procura outro dia da mesma semana com sobra
for i,x in a[(a.tipo=='encaixe')&(a.conflito!='')].iterrows():
    ok=a[(a.conflito=='')|(a.index==i)]
    wk=x.data-pd.Timedelta(days=x.data.dayofweek); best=None
    for k in range(5):
        d=wk+pd.Timedelta(days=k)
        if d==x.data: continue
        for u in TEAMS:
            n=T2N[u]
            if n in RESERVA or str(k) not in SPEC[n][4] or u in x.bloq: continue
            g=a[(a.data==d)&(a.equipe==u)&(a.conflito=='')]
            if len(g)<SPEC[n][2] and g.horas.sum()+x.horas<=CAP:
                fim=(g.ini+g.horas).max()+TRAV if len(g) else 9.0
                cand=(len(g)-SPEC[n][2],fim,d,u)
                if best is None or cand<best: best=cand
    if best:
        _,fim,d,u=best; a.at[i,'data']=d; a.at[i,'dia']=DN[d.dayofweek]; a.at[i,'equipe']=u; a.at[i,'ini']=np.ceil(fim*2)/2
        a.at[i,'conflito']=''; a.at[i,'obs']=f"Encaixe movido para {DN[d.dayofweek]} (sem sobra no dia previsto)"
    else:
        a.at[i,'equipe']=None
a['valor']=a.cliente.map(dict(zip(r.cliente,r.valor))).fillna(0)
a['horario']=a.ini.map(h2s); a['fim']=(a.ini+a.horas).map(h2s)
a=a.sort_values(['data','ini','equipe'])
a['data_txt']=a.data.dt.strftime('%d/%m')
a['semana']=np.where(a.data<W[1],'Semana de '+W[0].strftime('%d/%m'),'Semana de '+W[1].strftime('%d/%m'))
a['id']=a.data.dt.strftime('%m%d')+'-'+a.cliente
a[['id','semana','data_txt','dia','horario','fim','cliente','equipe','frequencia','tipo','horas','valor','motivo','evitar','obs','conflito']].to_csv('out/agenda.csv',index=False)
a=a.sort_values(['data','ini','equipe'])
# resumo equipe x dia
def pag(t,g):
    k=T2N[t]; rule=SPEC[k][5]; rec=g.valor.sum(); wk=g.data.iloc[0].dayofweek>=5
    if rule=='70' or (rule=='debora' and wk): return round(rec*0.7)
    if rule=='debora': return 200 if (len(g)>=2 and rec>=360) else 160
    return None
td=[]
for (dt,t),g in a.groupby(['data','equipe']):
    p=pag(t,g); td.append(dict(id=dt.strftime('%m%d')+'-'+T2N[t],data_txt=dt.strftime('%d/%m'),equipe=t,pessoas=SPEC[T2N[t]][1],casas=len(g),normal=SPEC[T2N[t]][2],receita=round(g.valor.sum()),pagamento=p if p is not None else '',margem=round(g.valor.sum()-p) if p is not None else '',receita_por_pessoa=round(g.valor.sum()/SPEC[T2N[t]][1])))
pd.DataFrame(td).to_csv('out/equipe_dia_sim.csv',index=False)
print(pd.DataFrame(td).groupby('equipe')[['casas','receita','receita_por_pessoa']].mean().round(1))
print(a.obs.str.split(':').str[0].value_counts().head(10))
print(a.groupby(['semana','dia'],sort=False).agg(n=('cliente','size'),h=('horas','sum'),enc=('tipo',lambda s:(s=='encaixe').sum()),conf=('conflito',lambda s:(s!='').sum())))
print('trocas',(a.obs!='').sum()); print(a.motivo.value_counts()); print('bloq',sum(1 for b in a.bloq if b)); print(a.groupby('data_txt').equipe.nunique())
print(a[a.conflito!=''][['data_txt','horario','cliente','equipe','conflito']].to_string())
print(a.tipo.value_counts())

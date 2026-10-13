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
HZ0,HZ1=W[0],W[1]+pd.Timedelta(days=6)   # horizonte da simulação
def nth(y,m,wd,n):
    days=[d for d in pd.date_range(f'{y}-{m:02d}-01',periods=31) if d.month==m and d.dayofweek==wd]
    return days[n-1] if n>0 else days[-1]
# ---------- visitas de dia fixo (semanal, quinzenal, 3 semanas, mensal por data) ----------
out=[]
for _,x in r[~r.enc].iterrows():
    for dd in x.dia_ideal.split('/'):
        wd=DN.index(dd)
        if x.frequencia in NTH:
            for mo in pd.period_range(HZ0,HZ1,freq='M'):
                dt=nth(mo.year,mo.month,wd,NTH[x.frequencia])
                if HZ0<=dt<=HZ1: out.append((dt,x,'mensal'))
            continue
        e=7 if x.multi else EXP[x.frequencia]
        t=x.ultima+pd.Timedelta(days=e)
        while t<W[0]-pd.Timedelta(days=3): t+=pd.Timedelta(days=e)
        while t<=HZ1+pd.Timedelta(days=3):
            wk=t-pd.Timedelta(days=t.dayofweek)
            if wk in W: out.append((wk+pd.Timedelta(days=wd),x,'fixo'))
            t+=pd.Timedelta(days=e)
rows=[]
def _row(dt,x,tp,**kw):
    d=dict(data=dt,dia=DN[dt.dayofweek],cliente=x.cliente,frequencia=x.frequencia,
        hi=float(x.hi_med) if pd.notna(x.hi_med) else 10.0,horas=max(1.0,x.horas_mediana) if pd.notna(x.horas_mediana) else 2.0,equipe=x.equipe,tipo=tp)
    d.update(kw); return d
for dt,x,tp in out: rows.append(_row(dt,x,tp))
# ---------- encaixes: janela de 1 semana antes até 1 semana depois da data ideal ----------
fu=pd.read_pickle('work/fut.pkl') if os.path.exists('work/fut.pkl') else pd.DataFrame(columns=['status','ini','cliente','dur','data'])
_k=lambda s:str(s).split('(')[0].strip().lower()
fua=fu[fu.status=='Agendado'].copy(); fua['k']=fua.cliente.map(_k)
REALDATA=fua.groupby('k').data.apply(list).to_dict()
fila=[]
for _,x in r[r.enc].iterrows():
    e=EXP.get(x.frequencia,35); ideal=x.ultima+pd.Timedelta(days=e)
    ini=ideal-pd.Timedelta(days=7); prazo=ideal+pd.Timedelta(days=7)
    marc=[d for d in REALDATA.get(_k(x.cliente),[]) if d>_END]
    st=('Atrasado' if prazo<HZ0 else 'Vence nas próximas 2 semanas' if prazo<=HZ1 else 'Na janela' if ini<=HZ1 else 'Ainda cedo')
    fila.append(dict(cliente=x.cliente,frequencia=x.frequencia,ultima=x.ultima,ideal=ideal,prazo=prazo,status=st,
        marcado=min(marc) if marc else pd.NaT,dia_pref=x.dia_ideal,equipe=x.equipe,wshare=x.wshare,x=x))
F=pd.DataFrame(fila)
enc_rows=[]
for _,f in F.iterrows():
    if pd.notna(f.marcado) and f.marcado<HZ0: continue   # já marcado ainda nesta semana
    if pd.notna(f.marcado) and HZ0<=f.marcado<=HZ1:
        enc_rows.append(_row(f.marcado,f.x,'encaixe',prazo=f.prazo,ideal=f.ideal,ja_marcado=True,ultima_=f.ultima))
    elif f.status!='Ainda cedo' and not (pd.notna(f.marcado) and f.marcado>HZ1):
        enc_rows.append(_row(max(f.ideal,HZ0) if f.ideal<=HZ1 else HZ0,f.x,'encaixe',prazo=f.prazo,ideal=f.ideal,ja_marcado=False,x_wshare=f.wshare,ultima_=f.ultima))
a=pd.DataFrame(rows+enc_rows).drop_duplicates(['data','cliente'])
for c_ in ('prazo','ideal'):
    if c_ not in a: a[c_]=pd.NaT
a['ja_marcado']=a.get('ja_marcado',False); a['ja_marcado']=a.ja_marcado.fillna(False)
fu=fu[(fu.status=='Agendado')&fu.ini.notna()].copy()
_h=pd.to_datetime(fu.ini.astype(str),format='%H:%M:%S',errors='coerce'); fu['h']=_h.dt.hour+_h.dt.minute/60
HREAL=fu.assign(k=fu.cliente.map(_k)).groupby('k').h.median().to_dict()
a['hi']=[HREAL.get(_k(c),h) for c,h in zip(a.cliente,a.hi)]
from people import equipe_proxima, BLOQ, ATIVAS, RELIMP
CAP=8.0; TRAV=0.5; TOL=1.0
def h2s(h):
    if pd.isna(h): return ''
    hh=round(h*2)/2; return f"{int(hh)}:{'30' if hh%1 else '00'}"
def dur(h): hh=round(h*2)/2; return f"{int(hh)}h"+('30' if hh%1 else '')
# equipes atuais (out/2026) e regras de capacidade
_D={"seg-sex": "01234", "seg-dom": "0123456", "ter-qui": "123", "qua-sex": "234"}
R['equipes']={k:v for k,v in R['equipes'].items() if v.get('disponivel',True)}
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
a['atencao']=a.cliente.map(lambda c:f"Teve relimpeza em {RELIMP[c][0].strftime('%d/%m')} (feita por {RELIMP[c][1]}): caprichar" if c in RELIMP else '')
a['evitar']=a.cliente.map(lambda c:', '.join(sorted(p.split()[0] for p in BLOQ.get(c,set()) if p in ATIVAS)))
a['pref']=(a.hi*2).round()/2
a['ini']=np.nan; a['conflito']=''; a['obs']=''
PRI={'Semanal':1,'Cada 2 Semanas':2}
a['_pri']=[0 if fixa(c) else PRI.get(f,3) for c,f in zip(a.cliente,a.frequencia)]
ST={}   # estado por dia: ocupação de cada equipe
def est(d):
    if d not in ST: ST[d]={t:dict(busy=[],casas=0,load=0.0) for t in TEAMS}
    return ST[d]
def disp(t,d): return str(d.dayofweek) in SPEC[T2N[t]][4]
def livre(S,t,s,h): return all(s+h+TRAV<=b0 or s>=b1 for b0,b1 in S[t]['busy'])
def slot(S,t,p,h,ate):
    s=p
    while s<=ate+1e-9:
        if livre(S,t,s,h) and s+h<=19.5: return s
        s+=0.5
    return None
def pode(S,d,t,x,lim):
    n=SPEC[T2N[t]]; cap=n[2] if lim=='normal' else n[3]
    if fixa(x.cliente) and fixa(x.cliente)!=T2N[t]: return False
    return disp(t,d) and S[t]['casas']<cap and S[t]['load']+x.horas<=CAP and t not in x.bloq
def poe(S,i,t,s,x,nota):
    if T2N[t] in SO9: s=9.0
    S[t]['busy'].append((s,s+x.horas+TRAV)); S[t]['casas']+=1; S[t]['load']+=x.horas
    a.at[i,'ini']=s; a.at[i,'equipe']=t; a.at[i,'obs']=nota
regular=[u for u in TEAMS if T2N[u] not in RESERVA]
# 1) dia fixo: prioridade cliente fixo da equipe > semanal > quinzenal > demais; depois pelo horário
for i,x in a[a.tipo!='encaixe'].sort_values(['data','_pri','pref']).iterrows():
    d=x.data; S=est(d); p=max(8.0,x.pref); pref=x.equipe if isinstance(x.equipe,str) else None
    p9=lambda u: 9.0 if T2N[u] in SO9 else p
    def tenta(u,lim,tol):
        if not pode(S,d,u,x,lim): return None
        if T2N[u] in SO9: return 9.0 if (p<=10 and livre(S,u,9.0,x.horas)) else None
        return slot(S,u,p,x.horas,p+tol)
    if pref and (s:=tenta(pref,'normal',TOL)) is not None: poe(S,i,pref,s,x,''); continue
    if fixa(x.cliente) and pref:
        s=slot(S,pref,p,x.horas,17.5) if pode(S,d,pref,x,'max') else None
        if s is not None: poe(S,i,pref,s,x,'Cliente fixo da Eq '+fixa(x.cliente)); continue
    feito=False
    for lim in ('normal','max'):
        if pref and lim=='max' and (s:=tenta(pref,'max',TOL)) is not None:
            poe(S,i,pref,s,x,f"{SPEC[T2N[pref]][2]+1}ª casa da equipe no dia"); feito=True; break
        c=[(tenta(u,lim,TOL),u) for u in regular]; c=[(s,u) for s,u in c if s is not None]
        if c:
            s,u=min(c,key=lambda z:(z[0],S[z[1]]['casas']))
            nota=(f"{pref.split(' (')[0]} cheia ou ocupada: foi para outra equipe" if pref else (x.motivo+' → '+u.split(' (')[0] if x.motivo else ''))
            if lim=='max': nota+=f" · {SPEC[T2N[u]][2]+1}ª casa da equipe"
            poe(S,i,u,s,x,nota); feito=True; break
    if feito: continue
    if pref and pode(S,d,pref,x,'max') and (s:=slot(S,pref,p,x.horas,17.5)) is not None:
        poe(S,i,pref,s,x,'Equipe de costume, mais tarde que o horário'); continue
    c=[u for u in TEAMS if T2N[u] in RESERVA and pode(S,d,u,x,'normal') and slot(S,u,p,x.horas,p+TOL) is not None]
    if c: poe(S,i,c[0],slot(S,c[0],p,x.horas,p+TOL),x,f"Sem equipe livre: precisa de reserva ({c[0].split('(')[1][:-1]})"); continue
    a.at[i,'conflito']=f"Sem equipe livre no dia ({h2s(p)})"; a.at[i,'equipe']=None
# marca atraso em relação ao horário de costume
for i,x in a[(a.tipo!='encaixe')&a.ini.notna()].iterrows():
    if x.ini-max(8.0,x.pref)>=0.5 and not fixa(x.cliente) and SPEC[T2N[x.equipe]][0] and T2N[x.equipe] not in SO9:
        a.at[i,'obs']=(x.obs+' · ' if x.obs else '')+f"Começa {dur(x.ini-max(8.0,x.pref))} depois do horário de costume"
# 2) encaixes: só na sobra (casas abaixo do normal), do prazo mais curto para o mais longo
for i,x in a[a.tipo=='encaixe'].sort_values('prazo').iterrows():
    if x.ja_marcado: dias=[x.data]
    else:
        fim=min(x.prazo,HZ1) if x.prazo>=HZ0 else HZ1
        ini_=max(HZ0,x.ideal-pd.Timedelta(days=7)) if x.prazo>=HZ0 else HZ0
        dias=[d for d in pd.date_range(ini_,fim) if d.dayofweek<5]
        pref_d=set(k for k,v in x.x_wshare.items() if v>=0.15) if isinstance(getattr(x,'x_wshare',None),dict) else set()
        dias.sort(key=lambda d:(abs((d-x.ideal).days)//7, DN[d.dayofweek] not in pref_d, d))
    ok=False
    urg=x.prazo<=HZ1
    for lim in (('normal','max') if (urg or x.ja_marcado) else ('normal',)):
        for d in dias:
            S=est(d)
            cand=[]
            for u in regular:
                if T2N[u] in SO9 or not pode(S,d,u,x,lim): continue
                s_=slot(S,u,8.5,x.horas,17.5-x.horas)
                if s_ is not None: cand.append((u!=x.equipe,S[u]['casas']-SPEC[T2N[u]][2],s_,u))
            if cand:
                _,_,s_,u=min(cand); a.at[i,'data']=d; a.at[i,'dia']=DN[d.dayofweek]
                nota='Já marcado na agenda' if x.ja_marcado else f"Encaixe · prazo {x.prazo.strftime('%d/%m')}"
                if x.prazo<HZ0: nota+=f" · ATRASADO ({(d-x.ultima_).days//7} semanas sem limpeza)" if hasattr(x,'ultima_') else ' · ATRASADO'
                if lim=='max': nota+=' · casa extra da equipe para não passar do prazo'
                poe(S,i,u,s_,x,nota); ok=True; break
        if ok: break
    if not ok and urg:
        for d in dias:
            S=est(d); c=[u for u in TEAMS if T2N[u] in RESERVA and pode(S,d,u,x,'normal') and slot(S,u,8.5,x.horas,17.5-x.horas) is not None]
            if c:
                a.at[i,'data']=d; a.at[i,'dia']=DN[d.dayofweek]
                poe(S,i,c[0],slot(S,c[0],8.5,x.horas,17.5-x.horas),x,f"Encaixe · prazo {x.prazo.strftime('%d/%m')} · precisa de reserva ({c[0].split('(')[1][:-1]})"); ok=True; break
    if not ok:
        if x.prazo>HZ1:
            a.at[i,'obs']=f"Fica para depois de {HZ1.strftime('%d/%m')} (prazo {x.prazo.strftime('%d/%m')})"
        else:
            a.at[i,'conflito']=f"Encaixe sem sobra: passa do prazo de {x.prazo.strftime('%d/%m')}"
        a.at[i,'equipe']=None
# fila de encaixe (todos os clientes de 4+ semanas)
ag=a[a.tipo=='encaixe'].set_index('cliente')
def _sug(c,st,m):
    if c in ag.index:
        g=ag.loc[c]
        if isinstance(g.equipe,str): return g.data.strftime('%d/%m')+' '+DN[g.data.dayofweek]+' · '+g.equipe.split(' (')[0]
        return g.obs if g.obs else 'Sem sobra antes do prazo: decidir'
    if pd.notna(m) and m<HZ0: return 'Já marcado nesta semana'
    if pd.notna(m): return 'Já marcado'
    return 'Ainda cedo'
F['sugestao']=[_sug(c,st,m) for c,st,m in zip(F.cliente,F.status,F.marcado)]
F['status']=[('Já marcado' if pd.notna(m) else s_) for s_,m in zip(F.status,F.marcado)]
F['marcado_txt']=F.marcado.map(lambda d:d.strftime('%d/%m') if pd.notna(d) else '')
F=F.sort_values('prazo')
pd.DataFrame(dict(cliente=F.cliente,frequencia=F.frequencia,ultima=F.ultima.dt.strftime('%d/%m'),ideal=F.ideal.dt.strftime('%d/%m'),prazo=F.prazo.dt.strftime('%d/%m'),
    status=F.status,ja_marcado=F.marcado_txt,sugestao=F.sugestao,dia_pref=F.dia_pref,equipe=F.equipe)).to_csv('out/fila_encaixe.csv',index=False)
a=a[a.equipe.notna()|(a.conflito!='')]
a['valor']=a.cliente.map(dict(zip(r.cliente,r.valor))).fillna(0)
a['horario']=a.ini.map(h2s); a['fim']=(a.ini+a.horas).map(h2s)
a=a.sort_values(['data','ini','equipe'])
a['data_txt']=a.data.dt.strftime('%d/%m')
a['semana']=np.where(a.data<W[1],'Semana de '+W[0].strftime('%d/%m'),'Semana de '+W[1].strftime('%d/%m'))
a['id']=a.data.dt.strftime('%m%d')+'-'+a.cliente
a[['id','semana','data_txt','dia','horario','fim','cliente','equipe','frequencia','tipo','horas','valor','motivo','evitar','atencao','obs','conflito']].to_csv('out/agenda.csv',index=False)
a=a.sort_values(['data','ini','equipe'])
# resumo equipe x dia
def pag(t,g):
    k=T2N[t]; rule=SPEC[k][5]; rec=g.valor.sum(); wk=g.data.iloc[0].dayofweek>=5
    if rule=='70' or (rule=='debora' and wk): return round(rec*0.7)
    if rule=='debora': return 200 if (len(g)>=2 and rec>=360) else 160
    return None
td=[]
for (dt,t),g in a[a.equipe.notna()].groupby(['data','equipe']):
    p=pag(t,g); td.append(dict(id=dt.strftime('%m%d')+'-'+T2N[t],data_txt=dt.strftime('%d/%m'),equipe=t,pessoas=SPEC[T2N[t]][1],casas=len(g),normal=SPEC[T2N[t]][2],receita=round(g.valor.sum()),pagamento=p if p is not None else '',margem=round(g.valor.sum()-p) if p is not None else '',receita_por_pessoa=round(g.valor.sum()/SPEC[T2N[t]][1])))
pd.DataFrame(td).to_csv('out/equipe_dia_sim.csv',index=False)
print(pd.DataFrame(td).groupby('equipe')[['casas','receita','receita_por_pessoa']].mean().round(1))
print(a.obs.str.split(':').str[0].value_counts().head(10))
print(a.groupby(['semana','dia'],sort=False).agg(n=('cliente','size'),h=('horas','sum'),enc=('tipo',lambda s:(s=='encaixe').sum()),conf=('conflito',lambda s:(s!='').sum())))

print(a[a.conflito!=''][['data_txt','horario','cliente','equipe','conflito']].to_string())
print(a.tipo.value_counts())

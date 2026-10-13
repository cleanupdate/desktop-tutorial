import pandas as pd, numpy as np, re
import json
R=json.load(open('regras.json'))
d=pd.read_pickle('work/d.pkl'); d=d[d.data.notna()]
d['wd']=d.data.dt.dayofweek
_t=pd.to_datetime(d.ini,errors='coerce'); d['hi']=_t.dt.hour+_t.dt.minute/60
ENC=set(R['frequencias_encaixe'])
d['h']=pd.to_numeric(d.dur.astype(str).str.extract(r'([\d.]+)')[0],errors='coerce')
DN=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']
EXP={'Semanal':7,'Cada 2 Semanas':14,'Cada 3 Semanas':21,'Cada 4 Semanas':28,'Cada 5 Semanas':35,'Cada 6 Semanas':42,'Cada 8 Semanas':56}
WEQ={'Semanal':1,'Cada 2 Semanas':.5,'Cada 3 Semanas':1/3,'Cada 4 Semanas':.25,'Cada 5 Semanas':.2,'Cada 6 Semanas':1/6,'Cada 8 Semanas':1/8,'Primeiro do Mês':.23,'Terceiro do Mês':.23,'Último do Mês':.23,'Segundo do Mês':.23}
END=d.data.max(); ACTIVE=END-pd.Timedelta(days=60); REC=END-pd.Timedelta(weeks=15)
team=d[(d.equipe.astype(str)!='Sem Equipe')&(d.data>=ACTIVE)].assign(equipe=lambda x:x.equipe.astype(str)).groupby('equipe').nomes.agg(lambda s:s.dropna().mode()[0] if s.notna().any() else '')
def tn(e):
    v=team.get(e,''); 
    return f"Eq {e} ({' + '.join(x.strip().split()[0] for x in v.split(','))})" if v else str(e)
c=d[d.status=='Concluído'].copy(); c['equipe']=c.equipe.astype(str)
canc=d[d.status=='Cancelado'].groupby('cliente').size()
rows=[]; inativos=0
for cl,g in c.sort_values('data').groupby('cliente'):
    g=g.copy()
    fr=g.freq.iloc[-1]
    if fr=='Uma Vez' or pd.isna(fr) or len(g)<2 or any(str(cl).startswith(x) for x in R['clientes_ignorados']): continue
    if (g.tipo=='Airbnb').mean()>.5 or (g.tipoend=='Airbnb').mean()>.5: continue
    if g.data.max()<ACTIVE: inativos+=1; continue
    # mudança de endereço: usa só as visitas no endereço atual
    def _ak(e):
        e=str(e).split(' - ')[-1].lower(); m=re.search(r'(\d+)\s+([a-z]+)',e); return m.group(1)+m.group(2) if m else e
    g['ak']=g.end.map(_ak)
    novo_end=False
    if g.ak.nunique()>1 and g.ak.iloc[-1]!=g.ak.iloc[0]:
        ch=g.index[g.ak!=g.ak.iloc[-1]][-1]; pos=g.index.get_loc(ch)+1
        if pos<len(g): g=g.iloc[pos:].copy(); novo_end=True
    g['w']=0.5**((END-g.data).dt.days/90)
    ws=g.groupby('wd').w.sum(); share=ws/ws.sum()
    sug=int(ws.idxmax()); cons=share.max()
    vc=g.wd.value_counts()
    wds=g.wd.tolist()
    chg=sum(1 for a,b in zip(wds,wds[1:]) if a!=b)
    off=0
    for (_,a),(_,b) in zip(g.iloc[:-1].iterrows(),g.iloc[1:].iterrows()):
        e=EXP.get(b.freq); x=(b.data-a.data).days
        if e:
            k=max(1,round(x/e))
            if abs(x-k*e)>=2: off+=1
    rec=g[g.data>=REC]; vpw=len(rec)/15
    multi=vpw>=1.4 and fr=='Semanal'
    if multi:
        k=round(vpw); rws=rec.groupby('wd').w.sum().sort_values(ascending=False)
        sugs='/'.join(DN[i] for i in sorted(rws.index[:k])); weq=k
    else: sugs=DN[sug]; weq=WEQ.get(fr,0)
    # recent change: last 3 visits same day, different from overall raw mode
    last3=wds[-3:]; mudou_rec = len(set(last3))==1 and last3[0]!=vc.idxmax()
    eq=g.equipe.tolist(); tch=sum(1 for a,b in zip(eq,eq[1:]) if a!=b)
    teq=pd.Series(eq[-5:]).mode()[0]
    nc=int(canc.get(cl,0)); 
    if multi: off=0
    enc=fr in ENC
    if enc: off=0
    hor='';hvar=None
    if not enc:
        gd=g[g.wd.isin([DN.index(x) for x in sugs.split('/')])&g.hi.between(6,20)]
        if len(gd):
            med=gd.hi.median(); hh=round(med*2)/2; hor=f"{int(hh)}:{'30' if hh%1 else '00'}"; hvar=round(gd.hi.std(),1) if len(gd)>1 else 0.0
    rows.append(dict(valor=pd.to_numeric(g.valor,errors='coerce').dropna().iloc[-1] if pd.to_numeric(g.valor,errors='coerce').notna().any() else 0,cliente=cl,frequencia=fr,visitas=len(g),primeira=g.data.min(),ultima=g.data.max(),hi_med=g.hi[g.hi.between(6,20)].median(),
        historico=' · '.join(f"{DN[k]} {v}" for k,v in vc.sort_index().items()),
        dia_ideal=sugs,consistencia_pct=round(cons*100),mudancas_dia=chg,fora_ciclo=off,cancelamentos=nc,conflitos=off+nc,
        equipe=tn(teq),trocas_equipe=tch,horas_mediana=round(g.h.median(),1) if g.h.notna().any() else 2.0,
        weq=weq,multi=multi,novo_end=novo_end,enc=enc,horario_ideal=hor,variacao_horario_h=hvar,mudou_rec=mudou_rec,wshare={DN[k]:v for k,v in share.items()}))
r=pd.DataFrame(rows)
r['classe']=np.where(r.enc,'Encaixe',np.where(r.consistencia_pct>=80,'Fixo',np.where(r.consistencia_pct>=60,'Quase fixo','Instável')))
r['hw']=r.weq*r.horas_mediana
def load(col):
    L={k:0.0 for k in DN[:5]}
    for _,x in r[~r.enc].iterrows():
        ds=x[col].split('/')
        for dd in ds:
            if dd in L: L[dd]+=x.hw/len(ds)
    return L
r['orig']=r.dia_ideal
L=load('dia_ideal'); A=dict(L); tgt=sum(L.values())/5; print({k:round(v,1) for k,v in L.items()},round(tgt,1))
r['mover']=''
for i,x in r[(~r.multi)&(~r.enc)&(r.classe!='Fixo')].sort_values('consistencia_pct').iterrows():
    if x.dia_ideal not in L or L[x.dia_ideal]<tgt+1: continue
    alts=[(dd,s) for dd,s in x.wshare.items() if dd in L and dd!=x.dia_ideal and L[dd]<tgt-1 and s>=0.15]
    if not alts: continue
    dd=min(alts,key=lambda t:L[t[0]])[0]
    L[x.dia_ideal]-=x.hw; L[dd]+=x.hw; r.at[i,'mover']=x.dia_ideal; r.at[i,'dia_ideal']=dd
print({k:round(v,1) for k,v in L.items()})
E={k:0.0 for k in DN[:5]}
for i,x in r[r.enc].sort_values('hw',ascending=False).iterrows():
    ok=[dd for dd,sh in x.wshare.items() if dd in L and sh>=0.15] or list(L)
    dd=min(ok,key=lambda k:L[k]+E[k]); E[dd]+=x.hw; r.at[i,'dia_ideal']=dd
print('enc',{k:round(v,1) for k,v in E.items()})
def acao(x):
    if x.enc: return f"Encaixe: preferir {x.dia_ideal} (dia com folga)"

    if x.multi: return f"Várias vezes/semana: fixar {x.dia_ideal}"
    if x.mover: return f"Mover {x.mover} → {x.dia_ideal} (aliviar {x.mover})"
    if x.classe=='Instável': return f"Combinar dia fixo: {x.dia_ideal}"
    if x.classe=='Quase fixo': return f"Confirmar {x.dia_ideal}"
    return "Manter"
r['acao']=r.apply(acao,axis=1)
r.loc[r.mudou_rec&(r.acao=='Manter'),'acao']=r.loc[r.mudou_rec&(r.acao=='Manter')].apply(lambda x:f"Manter {x.dia_ideal} (mudou recentemente)",axis=1)
r.loc[r.novo_end,'acao']=r.loc[r.novo_end,'acao']+' · mudou de endereço (só o endereço novo conta)'
cols=['cliente','frequencia','visitas','historico','dia_ideal','horario_ideal','variacao_horario_h','consistencia_pct','classe','mudancas_dia','fora_ciclo','cancelamentos','conflitos','equipe','trocas_equipe','horas_mediana','acao']
r.sort_values(['conflitos','mudancas_dia'],ascending=False)[cols].to_csv('out/clientes.csv',index=False)
# real weekly avg per weekday over full weeks
wk=c.data.dt.to_period('W-SUN'); _m0=c.data.min()+pd.Timedelta(days=(7-c.data.min().dayofweek)%7); _m1=END-pd.Timedelta(days=(END.dayofweek+1)%7)
full=wk[(c.data>=_m0)&(c.data<=_m1)]
nw=full.nunique(); act=c.loc[full.index].groupby('wd').size()/nw
pd.DataFrame([dict(dia=k,limpezas_semana_real=round(act.get(i,0),1),horas_semana_sem_ajuste=round(A[k],1),horas_semana_proposta=round(L[k],1),horas_semana_encaixe=round(E[k],1)) for i,k in enumerate(DN[:5])]).to_csv('out/carga_dia.csv',index=False)
rr=[]
for _,x in r.iterrows():
    ds=x.dia_ideal.split('/')
    for dd in ds: rr.append((x.equipe,dd,x.weq/len(ds)))
t=pd.DataFrame(rr,columns=['equipe','dia','v']).groupby(['equipe','dia']).v.sum().unstack(fill_value=0).reindex(columns=DN,fill_value=0)
t=t.loc[:,(t.sum()>0)].round(1).reset_index(); t.to_csv('out/equipe_dia.csv',index=False)
# monthly
m=c.assign(mes=c.data.dt.strftime('%Y-%m')).groupby('mes').size().rename('limpezas').reset_index()
m=m.merge(d[d.status=='Cancelado'].assign(mes=lambda x:x.data.dt.strftime('%Y-%m')).groupby('mes').size().rename('cancelamentos').reset_index(),how='left').fillna(0)
m.cancelamentos=m.cancelamentos.astype(int); m.to_csv('out/mensal.csv',index=False)
print(len(r),'inativos',inativos); print(r.classe.value_counts()); print(r.acao.str.split().str[0].value_counts()); print((r.conflitos>0).sum(), r.conflitos.sum())
print(r[r.multi][['cliente','dia_ideal']]); print(r[r.mover!=''][['cliente','mover','dia_ideal']])
print(r.sort_values(['conflitos','mudancas_dia'],ascending=False).head(8)[['cliente','conflitos','mudancas_dia','dia_ideal']])
print(r.sort_values('mudancas_dia',ascending=False).head(6)[['cliente','mudancas_dia']]); print(r.mudou_rec.sum())
print(open('out/carga_dia.csv').read()); print(t.to_string())
r.to_pickle('work/rfull.pkl')

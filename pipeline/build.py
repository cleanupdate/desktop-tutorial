import csv,json,re
import pandas as pd
old=open('../index.html',encoding='utf-8').read()
_d=pd.read_pickle('work/d.pkl'); PER=_d.data.min().strftime('%d/%m')+' a '+_d.data.max().strftime('%d/%m/%Y')
def rows(p):
    with open(p,encoding='utf-8') as f:
        r=csv.DictReader(f); return {'status':'ok','data':list(r),'columns':r.fieldnames}
D={k:rows(f'out/{v}') for k,v in dict(clientes='clientes.csv',carga='carga_dia.csv',equipes='equipe_dia.csv',mensal='mensal.csv',agenda='agenda.csv',equipes_hist='equipes_hist.csv',saidas='saidas.csv',reclamacoes='reclamacoes.csv',equipe_dia_sim='equipe_dia_sim.csv',fila_encaixe='fila_encaixe.csv').items()}
page=open('pagina.html',encoding='utf-8').read().replace('--font-anthropic-sans','--font-sans').replace('--font-anthropic-serif','--font-serif')
style=re.search(r'<style>(.*?)</style>',page,re.S).group(1)
body=re.sub(r'<style>.*?</style>','',page,flags=re.S).replace(' dash-skeleton','')
body=body.replace('<h1 id="titulo">Dias fixos por cliente</h1>','<h1 id="titulo">Dias fixos por cliente</h1><p class="note" style="margin:4px 0 0">Histórico de limpezas de '+PER+'</p>')
h0=old.index('<style>')+7; s1=old.index('</style>')
tk=old[h0:s1]; mq=tk.index('@media (max-width:600px)'); tk=tk[:tk.index('}',tk.index('}',mq)+1)+1]
new=old[:h0]+tk+style+old[s1:]
new=re.sub(r'window.__DATA__=.*?;\nwindow.dash',lambda m:'window.__DATA__='+json.dumps(D,ensure_ascii=False)+';\nwindow.dash',new,flags=re.S)
b0=new.index('<div id="dash-root">')+len('<div id="dash-root">'); b1=new.rindex('</div></body>')
new=new[:b0]+body+new[b1:]
new=new.replace('Base: histórico de 02/01 a 13/10/2026','Base: histórico de '+PER)
open('../index.html','w',encoding='utf-8').write(new); print(len(new))

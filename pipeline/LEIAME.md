# Atualização semanal da agenda

Entrada (exportar do sistema toda semana):
1. **Histórico** de limpezas desde 01/01 (mesmo formato de `History_260101-261013.xlsx`).
2. **Future Jobs Report** do mês (opcional; usado para horários já combinados).

Rodar:
```
./rodar.sh historico.xlsx future_jobs.xlsx
```
Gera `../index.html` (o painel publicado) e os CSVs em `out/`.

## Arquivos de regras (editar aqui, não no código)
- `regras.json`: equipes (pessoas, casas normais e máximas, dias, pagamento, reserva, só 9h),
  clientes fixos de uma equipe, clientes ignorados, frequências de encaixe.
- `bloqueios_manual.csv`: feedback de cliente. Uma linha por reclamação:
  `cliente,quem_nao_mandar,motivo,data` — `quem_nao_mandar` pode ser nomes (`Sara, Raiana`) ou equipe (`Eq 4`).
  Bloqueio manual é permanente até a linha ser apagada.

Relimpezas do histórico viram bloqueio automaticamente (some quando a pessoa volta a limpar o cliente).

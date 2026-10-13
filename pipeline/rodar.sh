#!/bin/bash
# Uso: ./rodar.sh historico.xlsx [future_jobs_mes1.xlsx future_jobs_mes2.xlsx ...]
set -e
cd "$(dirname "$0")"
python3 carregar.py "$@"
python3 full.py > /dev/null
python3 sim.py > /dev/null
python3 extras.py
python3 build.py > /dev/null
echo "Pronto: ../index.html atualizado; dados em out/"

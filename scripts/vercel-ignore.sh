#!/bin/bash
# Decide se a Vercel deve pular o deploy deste commit (exit 0 = pula, exit 1 = builda).
# Motivo: o workflow da Defesa Civil commita public/defesa-civil.json a cada ~10 min
# e cada commit vira um deploy. No plano Hobby (100 deploys/dia) isso esgota a cota
# e trava deploys de código. Aqui, um commit que só muda esse JSON e só no campo
# "fonte_atualizada_em" (batimento do feed, sem mudança de alerta) não gera deploy.
# Qualquer outra mudança (código ou alerta novo/alterado/removido) builda normal.

# Se o diff tocou qualquer arquivo além do JSON de dados, builda.
if git diff --name-only HEAD^ HEAD | grep -qv '^public/defesa-civil\.json$'; then
  exit 1
fi

# Só o JSON mudou: builda se o diff tiver qualquer linha de conteúdo além do timestamp.
if git diff HEAD^ HEAD -- public/defesa-civil.json | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' | grep -qv '"fonte_atualizada_em"'; then
  exit 1
fi

# Mudança só de batimento (timestamp): pula o deploy.
exit 0


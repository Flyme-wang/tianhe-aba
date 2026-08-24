#!/bin/bash
# 新5模型批量三面截图: p_elastic/p_vis001/c_strhalf/c_gc2x (c_bk20 已完成)
cd /XYFS01/HOME/apm_zcshen/apm_zcshen_5/abaqus/abaqus2024-try/new-model-260822
for pair in "c2_p_elastic:p_elastic" "c2_p_vis001:p_vis001" "c2_c_strhalf:c_strhalf" "c2_c_gc2x:c_gc2x"; do
  odb="${pair%%:*}"; tag="${pair##*:}"
  echo "=== start ${tag} $(date +%T) ==="
  ODB=${odb}.odb TAG=${tag} OUTDIR=. OUTLOG=snap_${tag}_faces.log \
    $HOME/bin/abaqus2024 cae noGUI=snap_sdeg_face.py >> snap_batch_cae.log 2>&1
  echo "=== done ${tag} $(date +%T) ==="
done
echo "ALL NEW5 DONE $(date +%T)"

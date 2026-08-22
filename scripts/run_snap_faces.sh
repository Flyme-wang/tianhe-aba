#!/bin/bash
# 批量三面截图: v4/c1/c3/c4/c5r1/c6 (c2 已完成)
cd /XYFS01/HOME/apm_zcshen/apm_zcshen_5/abaqus/abaqus2024-try
for pair in "hweak_v4:v4" "sens_c1_q2x:c1" "sens_c3_m4weak:c3" "sens_c4_hstrength:c4" "sens_c5r1_bk2x_vis30:c5r1" "sens_c6_comb:c6"; do
  odb="${pair%%:*}"; tag="${pair##*:}"
  echo "=== start ${tag} $(date +%T) ==="
  ODB=CodexTarget49_CAE_NATIVE_allcohesive_gc50x_maxinc2p5_${odb}.odb TAG=${tag} OUTDIR=. OUTLOG=snap_${tag}_faces.log $HOME/bin/abaqus2024 cae noGUI=snap_sdeg_face.py >> snap_faces_batch_cae.log 2>&1
  echo "=== done ${tag} $(date +%T) ==="
done
echo "ALL FACES DONE $(date +%T)"

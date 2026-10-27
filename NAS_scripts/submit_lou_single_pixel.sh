#!/bin/bash
# Submit the PBS array job for single pixel analysis on Lou/Endeavour.
#
# Already on lfe/pfe (NAS shared filesystem):
#   bash NAS_scripts/submit_lou_single_pixel.sh --local
#
# From a local machine:
#   bash NAS_scripts/submit_lou_single_pixel.sh

set -e

PROJECT_DIR="/home4/tvnguy18/tide_models_analysis_global"
LOU_HOST="lfe"

if [[ "$1" == "--local" ]]; then
    echo "Skipping copy (shared filesystem)"
else
    echo "Copying project to ${LOU_HOST}:${PROJECT_DIR} ..."
    rsync -avz --exclude '.git' --exclude '__pycache__' \
        --exclude 'tide_analysis_results' --exclude 'single_pixel_results' \
        --exclude 'logs' \
        ./ "${LOU_HOST}:${PROJECT_DIR}/"
    echo "Copy done."
fi

# Create output directories and submit
if [[ "$1" == "--local" ]]; then
    mkdir -p "${PROJECT_DIR}/single_pixel_results"
    mkdir -p "${PROJECT_DIR}/logs"
    cd "${PROJECT_DIR}"
    echo "Submitting PBS array job (single pixel) ..."
    qsub NAS_scripts/run_lou_single_pixel.pbs
else
    ssh "${LOU_HOST}" bash -lc "'
        mkdir -p ${PROJECT_DIR}/single_pixel_results
        mkdir -p ${PROJECT_DIR}/logs
        cd ${PROJECT_DIR}
        qsub NAS_scripts/run_lou_single_pixel.pbs
    '"
fi

echo ""
echo "Job submitted.  Monitor with:  qstat -u \$USER"
echo "After all 32 jobs finish, run:"
echo "  cd ${PROJECT_DIR}/single_pixel_analysis && module load python3/3.11.5 && python3 aggregate.py"

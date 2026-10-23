#!/bin/bash
# Submit the PBS array job on Lou/Endeavour.
#
# Already on lfe/pfe (NAS shared filesystem):
#   bash NAS_scripts/submit_lou.sh --local
#
# From a local machine:
#   bash NAS_scripts/submit_lou.sh

set -e

PROJECT_DIR="/home4/tvnguy18/tide_models_analysis_global"
LOU_HOST="lfe"

if [[ "$1" == "--local" ]]; then
    echo "Skipping copy (shared filesystem)"
else
    echo "Copying project to ${LOU_HOST}:${PROJECT_DIR} ..."
    rsync -avz --exclude '.git' --exclude '__pycache__' \
        --exclude 'tide_analysis_results' --exclude 'logs' \
        ./ "${LOU_HOST}:${PROJECT_DIR}/"
    echo "Copy done."
fi

# Create output directories and submit
if [[ "$1" == "--local" ]]; then
    mkdir -p "${PROJECT_DIR}/tide_analysis_results"
    mkdir -p "${PROJECT_DIR}/logs"
    cd "${PROJECT_DIR}"
    echo "Submitting PBS array job ..."
    qsub NAS_scripts/run_lou.pbs
else
    ssh "${LOU_HOST}" bash -lc "'
        mkdir -p ${PROJECT_DIR}/tide_analysis_results
        mkdir -p ${PROJECT_DIR}/logs
        cd ${PROJECT_DIR}
        qsub NAS_scripts/run_lou.pbs
    '"
fi

echo ""
echo "Job submitted.  Monitor with:  qstat -u \$USER"
echo "After all 32 jobs finish, run:"
echo "  cd ${PROJECT_DIR} && module load python3/3.11.5 && python3 aggregate.py"

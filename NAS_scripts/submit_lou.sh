#!/bin/bash
# Copy project to Lou and submit the PBS array job.
#
# From a local machine:
#   bash submit_lou.sh
#
# Already on lfe/pfe (NAS shared filesystem):
#   bash submit_lou.sh --local

set -e

PROJECT_DIR="/home4/tvnguy18/tide_models_analysis_global"
LOU_HOST="lfe"   # Lou frontend

if [[ "$1" == "--local" ]]; then
    echo "Skipping copy (shared filesystem)"
else
    echo "Copying project to ${LOU_HOST}:${PROJECT_DIR} ..."
    rsync -avz --exclude '.git' --exclude '__pycache__' \
        --exclude 'tide_analysis_results' --exclude 'logs' \
        ./ "${LOU_HOST}:${PROJECT_DIR}/"
    echo "Copy done."
fi

# Create output directories (works locally or via ssh)
if [[ "$1" == "--local" ]]; then
    mkdir -p "${PROJECT_DIR}/tide_analysis_results"
    mkdir -p "${PROJECT_DIR}/logs"
    cd "${PROJECT_DIR}"
    echo "Submitting PBS array job ..."
    qsub run_lou.pbs
else
    ssh "${LOU_HOST}" bash -lc "'
        mkdir -p ${PROJECT_DIR}/tide_analysis_results
        mkdir -p ${PROJECT_DIR}/logs
        cd ${PROJECT_DIR}
        qsub run_lou.pbs
    '"
fi

echo ""
echo "Job submitted.  Monitor with:  qstat -u \$USER"
echo "After all 32 jobs finish, run:"
echo "  cd ${PROJECT_DIR} && module load python3/3.11.5 && python3 aggregate.py"

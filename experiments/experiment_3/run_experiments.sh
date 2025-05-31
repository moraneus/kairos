#!/bin/bash

# Navigate to the project root directory (two levels up from experiments/experiment_3)
PROJECT_ROOT_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
RESULT_FILE="${PROJECT_ROOT_PATH}/experiments/experiment_3/result-experiment-3"

# Store results in the experiment folder
echo "########## experiment 3 ##########" >> "${RESULT_FILE}"

# Define relative paths for spec and traces from the project root
SPEC_FILE="experiments/experiment_3/spec_experiment_3.pbtl"
TRACE_DIR="experiments/experiment_3/traces"

echo "########## TRACE=1K, STOP ON CONCLUSIVE=False ##########"
echo "########## TRACE=1K, STOP ON CONCLUSIVE=False ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-1K.csv" -v) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=1K, STOP ON CONCLUSIVE=True ##########"
echo "########## TRACE=1K, STOP ON CONCLUSIVE=True ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-1K.csv" -v --stop-on-verdict) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=10K, STOP ON CONCLUSIVE=False ##########"
echo "########## TRACE=10K, STOP ON CONCLUSIVE=False ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-10K.csv" -v) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=10K, STOP ON CONCLUSIVE=True ##########"
echo "########## TRACE=10K, STOP ON CONCLUSIVE=True ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-10K.csv" -v --stop-on-verdict) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=100K, STOP ON CONCLUSIVE=False ##########"
echo "########## TRACE=100K, STOP ON CONCLUSIVE=False ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-100K.csv" -v) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=100K, STOP ON CONCLUSIVE=True ##########"
echo "########## TRACE=100K, STOP ON CONCLUSIVE=True ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-100K.csv" -v --stop-on-verdict) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=500K, STOP ON CONCLUSIVE=False ##########"
echo "########## TRACE=500K, STOP ON CONCLUSIVE=False ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-500K.csv" -v) >> "${RESULT_FILE}" 2>&1

echo "########## TRACE=500K, STOP ON CONCLUSIVE=True ##########"
echo "########## TRACE=500K, STOP ON CONCLUSIVE=True ##########" >> "${RESULT_FILE}"
(cd "${PROJECT_ROOT_PATH}" && gtime python3.12 run_monitor.py -p "${SPEC_FILE}" -t "${TRACE_DIR}/trace-500K.csv" -v --stop-on-verdict) >> "${RESULT_FILE}" 2>&1
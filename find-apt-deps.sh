#/bin/bash

if [ -z "$1" ]; then
    echo "Error: Path to requirements.txt file is required."
    exit 1
fi

REQ_FILE="$1"
VENV_DIR=/tmp/venv

# python3 -m venv ${VENV_DIR}
# source ${VENV_DIR}/bin/activate
# pip install -r "$REQ_FILE"

for dir in $(ls ${VENV_DIR}/lib/python3.12/site-packages); do
    for lib in $(find ${VENV_DIR}/lib/python3.12/site-packages/${dir} -name "*.so*"); do
        ldd "$lib" 2>&1 | awk '{ print $1 }'
    done
done | sort | uniq #| xargs dpkg -S 2>/dev/null | awk -F: '{ print $1 }' | sort | uniq

# deactivate

#!/bin/bash
# Comunicazione rapida con MW28912 sulla porta 28500
# Uso: ./mw.sh [IP]
IP=${1:-0.0.0.0}
rlwrap nc -k -l -s $IP -p 28500 2>/dev/null || nc -k -l -s $IP -p 28500

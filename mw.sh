#!/bin/bash
# Comunicazione rapida con MW28912 sulla porta 28500
rlwrap nc -k -l -p 28500 2>/dev/null || nc -k -l -p 28500

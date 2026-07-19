#!/usr/bin/env bash
awk '/^cpu / {printf "%d\n", ($2+$4)*100/($2+$4+$5)}' /proc/stat

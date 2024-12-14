#!/bin/bash

COMMAND="make test-full TYPE=finetune"

tmux \
new-window \
${COMMAND} > .output \; \
split-window \
${COMMAND} \; \
split-window -h \
${COMMAND} \; \
split-window \
${COMMAND} \; \
select-layout even-horizontal\; \
select-pane -t 0 \; \
split-window  -v \
${COMMAND} \; \
select-pane -t 2 \; \
split-window  -v \
${COMMAND} \; \
select-pane -t 4 \; \
split-window  -v \
${COMMAND} \; \
select-pane -t 6 \; \
split-window  -v \
${COMMAND} \; \
set -w remain-on-exit on \; \
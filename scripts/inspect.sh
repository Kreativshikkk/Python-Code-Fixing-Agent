#!/bin/sh
# Copyright 2000-2021 JetBrains s.r.o. and contributors. Use of this source code is governed by the Apache 2.0 license that can be found in the LICENSE file.
# ------------------------------------------------------
# PyCharm offline inspection script.
# ------------------------------------------------------

export DEFAULT_PROJECT_PATH="$(pwd)"

CONFIG_PATH="config.yaml"
IDE_BIN_HOME=$(grep '^pycharm_bin_directory:' "$CONFIG_PATH" | sed 's/pycharm_bin_directory:[[:space:]]*//')
exec "$IDE_BIN_HOME/../MacOS/pycharm" inspect "$@"
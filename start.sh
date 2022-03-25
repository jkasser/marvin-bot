#!/bin/sh

git pull
export ENV=prod
pipenv run python3 main.py

#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py check --deploy --settings=livestock.settings_production
python manage.py collectstatic --no-input --settings=livestock.settings_production
python manage.py migrate --no-input --settings=livestock.settings_production
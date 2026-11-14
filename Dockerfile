# The official Odoo image plus what our addons need. pymysql comes from Debian, as Odoo's own packages do, so pip
# never touches the image's Python. Dependabot keeps the base tag up to date.
FROM odoo:19.0-20261112

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pymysql \
    && rm -rf /var/lib/apt/lists/*
USER odoo

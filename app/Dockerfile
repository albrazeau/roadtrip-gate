FROM tiangolo/uwsgi-nginx-flask:python3.8

COPY ./ /app

COPY ./prod_entrypoint.sh /prod_entrypoint.sh

RUN pip install -r /app/requirements.txt
RUN chmod +x /app/run_all.sh